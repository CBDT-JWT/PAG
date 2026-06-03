import html
import json
import os
import re
import traceback
import uuid
from urllib.parse import urlencode

from .http_client import http_get, http_json, http_json_stream
from .wechat_html import fallback_article, markdown_to_wechat_html


SYSTEM_PROMPT = """
你是资深中文科技公众号作者和论文解读编辑。

你必须只输出一个合法 JSON 对象。
不要输出 Markdown 代码块。
不要输出解释。
不要输出 DSML。

你可以在需要补充论文项目地址、作者信息、开源仓库、相关页面或背景资料时使用联网工具。
工具只用于检索和读取网页；完成工具调用后，最终回复仍必须只输出一个合法 JSON 对象。

JSON 字段必须为：
{
  "paper_title": "论文标题",
  "project_url": "项目地址，如果没有找到则为空字符串",
  "paper_url": "论文地址",
  "article_markdown": "公众号文章 Markdown 正文"
}

article_markdown 写作要求：
1. 使用自然流畅的中文公众号文章风格，不要堆砌分点。
2. 文章开头必须放 [[HEAD_IMAGE]]。
3. 论文信息部分只放一个占位符 [[PAPER_INFO]]，不要自己写论文标题、项目地址、论文地址列表。
4. 正文图片使用 [[IMAGE:具体图片描述]] 占位，例如 [[IMAGE:nuReasoning 数据构建流程图]]。
5. 如果 tail_url 非空，文章末尾放 [[TAIL_IMAGE]]。
6. 二级标题使用 Markdown 二级标题，例如：## 现有数据集的不足
7. 重点强调使用 **加粗文本**。
8. 不要输出 HTML。
9. 字数3k左右，**每个段落不能太长**，**严禁使用三级及以上标题！！！**
10. 格式上，应当是一段leadingin-论文信息-前序研究不足或现状-核心设计-具体实验-亮点重现-总结展望，leadingin部分不需要二级标题，其他需要。leadingin要有一点故事性。
"""

TOOLS = [
    {"type": "function", "function": {"name": "web_search", "description": "Search web pages for paper metadata, project pages, GitHub repositories, and related works.", "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}},
    {"type": "function", "function": {"name": "fetch_url", "description": "Fetch readable text from a public URL.", "parameters": {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]}}},
]

STREAM_PROGRESS_START = 60
STREAM_PROGRESS_SPAN = 40
STREAM_PROGRESS_EXPECTED_CHARS = 5000
STREAM_PROGRESS_MAX = 99


def emit_progress(progress, percent, message, detail=""):
    if progress:
        progress(percent, message, detail)


def parse_dsml_tool_calls(text):
    text = text or ""
    if "<｜｜DSML｜｜tool_calls>" not in text and "<｜｜DSML｜｜invoke" not in text:
        return []

    calls = []
    invoke_pattern = re.compile(
        r'<｜｜DSML｜｜invoke\s+name="([^"]+)">\s*(.*?)\s*</｜｜DSML｜｜invoke>',
        flags=re.S,
    )
    param_pattern = re.compile(
        r'<｜｜DSML｜｜parameter\s+name="([^"]+)"(?:\s+[^>]*)?>(.*?)</｜｜DSML｜｜parameter>',
        flags=re.S,
    )

    for invoke_match in invoke_pattern.finditer(text):
        func_name = html.unescape(invoke_match.group(1)).strip()
        body = invoke_match.group(2)
        args = {}
        for param_match in param_pattern.finditer(body):
            key = html.unescape(param_match.group(1)).strip()
            value = html.unescape(param_match.group(2).strip())
            args[key] = value

        calls.append({
            "id": "dsml_" + uuid.uuid4().hex[:12],
            "function": {
                "name": func_name,
                "arguments": json.dumps(args, ensure_ascii=False),
            },
        })
    return calls


def web_search(query):
    if not query:
        return "[]"
    body, _, _ = http_get("https://duckduckgo.com/html/?" + urlencode({"q": query}), timeout=20)
    text = body.decode("utf-8", errors="ignore")
    results = []
    for match in re.finditer(r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', text, flags=re.S):
        title = html.unescape(re.sub(r"<.*?>", "", match.group(2))).strip()
        url = html.unescape(match.group(1)).strip()
        if title and url:
            results.append({"title": title, "url": url})
        if len(results) >= 6:
            break
    return json.dumps(results, ensure_ascii=False)


def safe_web_search(query, progress=None):
    try:
        return web_search(query)
    except Exception as exc:
        emit_progress(progress, 45, "联网预搜索失败，继续使用论文文本生成", repr(exc))
        return "[]"


def fetch_url(url):
    body, _, _ = http_get(url, timeout=20)
    text = body.decode("utf-8", errors="ignore")
    text = re.sub(r"<script.*?</script>|<style.*?</style>", " ", text, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    return html.unescape(re.sub(r"\s+", " ", text)).strip()[:7000]


def run_tool(name, raw_args):
    try:
        args = json.loads(raw_args or "{}")
        if name == "web_search":
            return web_search(args.get("query", ""))
        if name == "fetch_url":
            return fetch_url(args.get("url", ""))
    except Exception as exc:
        return f"TOOL_ERROR: {exc}"
    return "UNKNOWN_TOOL"


def handle_tool_calls(messages, assistant_message, max_calls=6, progress=None):
    tool_results = []
    structured_calls = assistant_message.get("tool_calls") or []

    if structured_calls:
        messages.append(assistant_message)
        for index, call in enumerate(structured_calls[:max_calls], start=1):
            call_id = call.get("id") or "tool_" + uuid.uuid4().hex[:8]
            name = call["function"]["name"]
            arguments = call["function"].get("arguments", "{}")
            emit_progress(progress, min(59, 46 + index * 2), f"正在调用联网工具：{name}", arguments[:240])
            result = run_tool(name, arguments)
            emit_progress(progress, min(59, 47 + index * 2), f"联网工具返回：{name}", result[:240])
            messages.append({"role": "tool", "tool_call_id": call_id, "content": result})
            tool_results.append({"name": name, "arguments": arguments, "result": result})
        return tool_results

    content = assistant_message.get("content", "") or ""
    dsml_calls = parse_dsml_tool_calls(content)
    if dsml_calls:
        messages.append({"role": "assistant", "content": content})
        for index, call in enumerate(dsml_calls[:max_calls], start=1):
            name = call["function"]["name"]
            arguments = call["function"].get("arguments", "{}")
            emit_progress(progress, min(59, 46 + index * 2), f"正在调用联网工具：{name}", arguments[:240])
            result = run_tool(name, arguments)
            emit_progress(progress, min(59, 47 + index * 2), f"联网工具返回：{name}", result[:240])
            messages.append({
                "role": "user",
                "content": (
                    f"工具 {name} 的调用参数：\n{arguments}\n\n"
                    f"工具 {name} 的返回结果：\n{result}\n\n"
                    "请基于以上工具结果和已有论文文本继续完成任务。"
                ),
            })
            tool_results.append({"name": name, "arguments": arguments, "result": result})
    return tool_results


def chat(messages, tools=None, stream=False, on_delta=None):
    api_url = (os.environ.get("OPENAI_BASE_URL") or os.environ.get("API_URL") or "").rstrip("/")
    api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("API_KEY")
    if not api_url or not api_key:
        raise RuntimeError(".env 中缺少 API_URL/API_KEY")
    payload = {
        "model": os.environ.get("OPENAI_MODEL") or os.environ.get("MODEL") or "deepseek-v4-pro",
        "messages": messages,
        "temperature": 0.55,
        "max_tokens": 6000,
    }
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"
    if stream:
        payload["stream"] = True
        return http_json_stream(f"{api_url}/chat/completions", payload, on_delta=on_delta)
    return http_json(f"{api_url}/chat/completions", payload)


def stream_progress_percent(total_chars):
    estimated = STREAM_PROGRESS_START + int(
        (min(total_chars, STREAM_PROGRESS_EXPECTED_CHARS) / STREAM_PROGRESS_EXPECTED_CHARS)
        * STREAM_PROGRESS_SPAN
    )
    return min(STREAM_PROGRESS_MAX, estimated)


def parse_json_text(text):
    text = (text or "").strip()
    if not text:
        raise ValueError("模型返回内容为空，无法解析 JSON")
    if "<｜｜DSML｜｜tool_calls>" in text or "<｜｜DSML｜｜invoke" in text:
        raise ValueError("模型返回了 DSML 工具调用文本，而不是 JSON")

    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, flags=re.S)
    if fenced:
        text = fenced.group(1).strip()

    start, end = text.find("{"), text.rfind("}")
    if start >= 0 and end > start:
        text = text[start : end + 1]
    else:
        raise ValueError(f"模型返回内容中没有 JSON 对象。开头内容：{text[:300]}")

    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"JSON 解析失败：{exc}. 内容开头：{text[:500]}")


def get_first_present(d, keys, default=""):
    for key in keys:
        value = d.get(key)
        if value:
            return value
    return default


def get_article_markdown(parsed):
    candidates = [
        "article_markdown",
        "article_markmarkdown",
        "article_md",
        "markdown",
        "article",
        "content",
        "body",
        "正文",
    ]
    value = get_first_present(parsed, candidates, "")
    if value:
        return value

    for key, val in parsed.items():
        k = str(key).lower()
        if val and (
            "markdown" in k
            or "mark" in k
            or "md" == k
            or ("article" in k and "html" not in k)
        ):
            return val
    return ""


def generate_article(paper_text, paper_url, focus_authors, head_url, tail_url, progress=None):
    data = {
        "paper_title": "",
        "project_url": "",
        "paper_url": paper_url or "",
        "article_markdown": "",
        "article_html": "",
    }

    emit_progress(progress, 44, "正在检索论文相关项目和补充信息")
    seed_search = safe_web_search(f"{paper_url} project github paper", progress=progress) if paper_url else ""

    if not paper_text:
        paper_text = "本地未安装 pdftotext，需结合论文 URL 和联网检索理解论文。"

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"""论文地址：{paper_url}
头图 URL：{head_url}
尾图 URL：{tail_url}
重点关注作者：{focus_authors or '无'}
预搜索结果：{seed_search}

论文文本：
{paper_text}
""",
        },
    ]

    try:
        emit_progress(progress, 46, "正在请求大模型生成初稿，可按需使用联网工具")
        first = chat(messages, TOOLS)["choices"][0]["message"]
        print("[generate_article] first message =", json.dumps(first, ensure_ascii=False, indent=2)[:3000], flush=True)

        emit_progress(progress, 48, "正在检查模型是否需要补充联网检索")
        tool_results = handle_tool_calls(messages, first, max_calls=6, progress=progress)
        streamed_chars = 0

        def on_final_delta(delta, total_chars):
            nonlocal streamed_chars
            if total_chars - streamed_chars >= 240:
                streamed_chars = total_chars
                percent = stream_progress_percent(total_chars)
                emit_progress(progress, percent, "正在通过 SSE 流式生成富文本", f"已接收 {total_chars} / 5000 字")

        if tool_results:
            print(f"[generate_article] handled {len(tool_results)} tool calls", flush=True)
            emit_progress(progress, 58, f"已完成 {len(tool_results)} 个联网工具调用，正在整理最终稿")
            messages.append({
                "role": "user",
                "content": (
                    "工具调用已经完成。现在请不要再调用工具，不要输出 DSML，不要输出 Markdown 代码块。"
                    "请只输出一个合法 JSON 对象，字段必须包含 paper_title, project_url, paper_url, article_markdown。"
                ),
            })
        else:
            messages.append({
                "role": "user",
                "content": (
                    "现在请不要调用工具，不要输出 DSML，不要输出 Markdown 代码块。"
                    "请只输出一个合法 JSON 对象，字段必须包含 paper_title, project_url, paper_url, article_markdown。"
                ),
            })

        emit_progress(progress, STREAM_PROGRESS_START, "正在通过 SSE 请求最终富文本", "预计 5000 字")
        final = chat(messages, tools=None, stream=True, on_delta=on_final_delta)["choices"][0]["message"]
        final_content = final.get("content", "") or ""
        emit_progress(progress, stream_progress_percent(len(final_content)), "SSE 富文本接收完成", f"共 {len(final_content)} 字")
        print("[generate_article] final message =", json.dumps(final, ensure_ascii=False, indent=2)[:3000], flush=True)
        print("[generate_article] final content =", repr(final_content)[:3000], flush=True)

        if parse_dsml_tool_calls(final_content):
            print("[generate_article] final is still DSML, retrying once...", flush=True)
            messages.append({"role": "assistant", "content": final_content})
            messages.append({
                "role": "user",
                "content": (
                    "上一次输出仍然是工具调用格式，这是错误的。"
                    "现在禁止调用工具，禁止输出 DSML，禁止输出任何解释。"
                    "请只输出一个合法 JSON 对象，字段必须包含 paper_title, project_url, paper_url, article_markdown。"
                ),
            })
            emit_progress(progress, STREAM_PROGRESS_START, "模型输出格式需要修正，正在重试一次")
            streamed_chars = 0
            final = chat(messages, tools=None, stream=True, on_delta=on_final_delta)["choices"][0]["message"]
            final_content = final.get("content", "") or ""
            emit_progress(progress, stream_progress_percent(len(final_content)), "SSE 富文本重试接收完成", f"共 {len(final_content)} 字")
            print("[generate_article] retry final content =", repr(final_content)[:3000], flush=True)

        emit_progress(progress, 99, "正在解析模型返回内容")
        parsed = parse_json_text(final_content)
        article_markdown = get_article_markdown(parsed)
        data.update({
            "paper_title": parsed.get("paper_title") or parsed.get("title") or parsed.get("论文标题") or "",
            "project_url": parsed.get("project_url") or parsed.get("project") or parsed.get("project_link") or parsed.get("项目地址") or "",
            "paper_url": parsed.get("paper_url") or parsed.get("url") or parsed.get("论文地址") or paper_url or "",
            "article_markdown": article_markdown,
        })
        metadata = {
            "paper_title": data.get("paper_title") or "未能自动识别标题",
            "project_url": data.get("project_url") or "",
            "paper_url": data.get("paper_url") or paper_url or "",
        }
        print("[generate_article] parsed keys:", list(parsed.keys()), flush=True)
        print("[generate_article] article_markdown length:", len(data["article_markdown"]), flush=True)

        if data["article_markdown"]:
            try:
                emit_progress(progress, 99, "正在转换为微信富文本 HTML")
                data["article_html"] = markdown_to_wechat_html(
                    data["article_markdown"],
                    metadata=metadata,
                    head_url=head_url,
                    tail_url=tail_url,
                )
            except Exception as exc:
                print("[generate_article] markdown_to_wechat_html ERROR:", repr(exc), flush=True)
                traceback.print_exc()
                raise

        if not data["article_html"]:
            emit_progress(progress, 99, "未拿到完整正文，正在生成降级稿")
            data["article_html"] = fallback_article(data, paper_text, head_url, tail_url)
        return data
    except Exception as exc:
        print("[generate_article] ERROR:", repr(exc), flush=True)
        data["_error"] = repr(exc)
        emit_progress(progress, 99, "AI 生成失败，正在生成降级稿", repr(exc))
        data["article_html"] = fallback_article(data, paper_text, head_url, tail_url)
        return data
