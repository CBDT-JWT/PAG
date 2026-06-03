import base64
import html
import json
import os
import re
import shutil
import socket
import subprocess
import time
import traceback
import uuid
from http.client import IncompleteRead
from pathlib import Path
from urllib.parse import quote, urlencode, urljoin, urlparse
from urllib.request import Request, urlopen
from flask import render_template
from flask import Flask, Response, jsonify, render_template_string, request, send_from_directory


BASE_DIR = Path(__file__).resolve().parent
PUBLIC_DIR = BASE_DIR / "public"
RUNS_DIR = PUBLIC_DIR / "runs"
ASSETS_DIR = BASE_DIR / "assets"
STATIC_DIR = BASE_DIR / "static"
PORT = int(os.environ.get("PORT", "5001"))
MAX_PAPER_CHARS = 24000

app = Flask(__name__, static_folder=str(STATIC_DIR), static_url_path="/static")
def parse_dsml_tool_calls(text):
    """
    Parse DeepSeek/DSML-style textual tool calls.

    Input example:
    <｜｜DSML｜｜tool_calls>
    <｜｜DSML｜｜invoke name="web_search">
    <｜｜DSML｜｜parameter name="query" string="true">xxx</｜｜DSML｜｜parameter>
    </｜｜DSML｜｜invoke>
    </｜｜DSML｜｜tool_calls>

    Return:
    [
        {
            "id": "dsml_xxx",
            "function": {
                "name": "web_search",
                "arguments": "{\"query\":\"xxx\"}"
            }
        }
    ]
    """
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
            value = param_match.group(2).strip()
            value = html.unescape(value)
            args[key] = value

        calls.append({
            "id": "dsml_" + uuid.uuid4().hex[:12],
            "function": {
                "name": func_name,
                "arguments": json.dumps(args, ensure_ascii=False),
            },
        })

    return calls

def handle_tool_calls(messages, assistant_message, max_calls=6):
    """
    Handle either OpenAI-style structured tool_calls
    or DSML-style textual tool calls inside assistant content.
    """
    tool_results = []

    structured_calls = assistant_message.get("tool_calls") or []

    # Case 1: OpenAI-compatible structured tool calls
    if structured_calls:
        # 关键：必须先把带 tool_calls 的 assistant 消息放回 messages
        messages.append(assistant_message)

        for call in structured_calls[:max_calls]:
            call_id = call.get("id") or "tool_" + uuid.uuid4().hex[:8]
            name = call["function"]["name"]
            arguments = call["function"].get("arguments", "{}")

            result = run_tool(name, arguments)

            messages.append({
                "role": "tool",
                "tool_call_id": call_id,
                "content": result,
            })

            tool_results.append({
                "name": name,
                "arguments": arguments,
                "result": result,
            })

        return tool_results

    # Case 2: DSML textual tool calls
    content = assistant_message.get("content", "") or ""
    dsml_calls = parse_dsml_tool_calls(content)

    if dsml_calls:
        messages.append({
            "role": "assistant",
            "content": content,
        })

        for call in dsml_calls[:max_calls]:
            name = call["function"]["name"]
            arguments = call["function"].get("arguments", "{}")
            result = run_tool(name, arguments)

            # DSML 不是标准 tool_call，保险起见用 user 消息塞回
            messages.append({
                "role": "user",
                "content": (
                    f"工具 {name} 的调用参数：\n"
                    f"{arguments}\n\n"
                    f"工具 {name} 的返回结果：\n"
                    f"{result}\n\n"
                    "请基于以上工具结果和已有论文文本继续完成任务。"
                ),
            })

            tool_results.append({
                "name": name,
                "arguments": arguments,
                "result": result,
            })

    return tool_results
def load_env():
    path = BASE_DIR / ".env"
    if not path.exists():
        return
    try:
        content = subprocess.check_output(["/bin/cat", str(path)], text=True, timeout=2)
    except Exception:
        return
    for raw in content.splitlines():
        line = raw.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_env()


def http_get(url, timeout=40, headers=None):
    req_headers = {"User-Agent": "Mozilla/5.0 paper-wechat-writer/1.0", "Accept": "application/pdf,text/html;q=0.8,*/*;q=0.6"}
    if headers:
        req_headers.update(headers)
    req = Request(url, headers=req_headers)
    with urlopen(req, timeout=timeout) as resp:
        try:
            body = resp.read()
        except IncompleteRead as exc:
            body = exc.partial
        return body, {k.lower(): v for k, v in resp.headers.items()}, resp.geturl()


def http_json(url, payload, timeout=300):
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = Request(
        url,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {os.environ.get('OPENAI_API_KEY') or os.environ.get('API_KEY', '')}",
        },
    )
    with urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def local_lan_ip():
    try:
        output = subprocess.check_output(["ifconfig"], text=True, timeout=3)
        for ip in re.findall(r"\binet\s+(\d+\.\d+\.\d+\.\d+)\b", output):
            parts = [int(x) for x in ip.split(".")]
            if ip.startswith("192.168.") or ip.startswith("10.") or (parts[0] == 172 and 16 <= parts[1] <= 31):
                return ip
    except Exception:
        pass
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]


def public_base():
    configured = os.environ.get("PUBLIC_BASE_URL", "").strip().rstrip("/")
    if configured:
        return configured
    host = request.headers.get("host") or request.headers.get("Host") or f"127.0.0.1:{PORT}"
    name = host.split(":", 1)[0]
    if name not in {"127.0.0.1", "localhost", "0.0.0.0"}:
        return f"http://{host}"
    port = host.split(":", 1)[1] if ":" in host else str(PORT)
    return f"http://{local_lan_ip()}:{port}"



def public_url(path):
    rel = Path(path).relative_to(PUBLIC_DIR).as_posix()
    return f"/public/{quote(rel, safe='/')}"

def create_run():
    run_id = time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8]
    run_dir = RUNS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    return run_id, run_dir


def safe_name(value, default="file"):
    return (re.sub(r"[^a-zA-Z0-9._-]+", "-", value or "").strip("-")[:80] or default)


def guess_pdf_url(url):
    parsed = urlparse(url)
    if "arxiv.org" in parsed.netloc and "/abs/" in parsed.path:
        return f"{parsed.scheme}://{parsed.netloc}/pdf/{parsed.path.split('/abs/', 1)[1].strip('/')}.pdf"
    return url


def download_pdf(input_url, run_dir):
    candidate = guess_pdf_url(input_url)
    body, headers, final_url = http_get(candidate)
    if "pdf" not in headers.get("content-type", "").lower() and body[:4] != b"%PDF":
        page = body.decode("utf-8", errors="ignore")
        links = re.findall(r'href=["\']([^"\']+\.pdf(?:\?[^"\']*)?)["\']', page, flags=re.I)
        if not links:
            raise ValueError("URL 没有直接返回 PDF，页面里也没有找到 PDF 链接")
        final_url = urljoin(final_url, links[0])
        body, headers, _ = http_get(final_url)
        if "pdf" not in headers.get("content-type", "").lower() and body[:4] != b"%PDF":
            raise ValueError("页面中的 PDF 链接下载结果不是 PDF")
    target = run_dir / "paper.pdf"
    target.write_bytes(body)
    return target, final_url


def extract_pdf_text(pdf_path):
    pdftotext = shutil.which("pdftotext")
    if not pdftotext:
        return ""
    out = pdf_path.with_suffix(".txt")
    try:
        subprocess.run([pdftotext, "-layout", str(pdf_path), str(out)], check=True, timeout=20)
        return out.read_text(encoding="utf-8", errors="ignore")[:MAX_PAPER_CHARS]
    except Exception:
        return ""


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


def fetch_url(url):
    body, _, _ = http_get(url, timeout=20)
    text = body.decode("utf-8", errors="ignore")
    text = re.sub(r"<script.*?</script>|<style.*?</style>", " ", text, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    return html.unescape(re.sub(r"\s+", " ", text)).strip()[:7000]


TOOLS = [
    {"type": "function", "function": {"name": "web_search", "description": "Search web pages for paper metadata, project pages, GitHub repositories, and related works.", "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}},
    {"type": "function", "function": {"name": "fetch_url", "description": "Fetch readable text from a public URL.", "parameters": {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]}}},
]


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


def chat(messages, tools=None):
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
    return http_json(f"{api_url}/chat/completions", payload)


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
    """
    兼容模型把 article_markdown 写错的情况。
    """
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

    # 更激进一点：自动找所有包含 article + markdown / mark / md 的字段
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

def image_section(url):
    return '<section style="text-align:center;margin-top:10px;margin-bottom:10px;line-height:0;box-sizing:border-box;"><section style="max-width:100%;vertical-align:middle;display:inline-block;line-height:0;width:90%;height:auto;box-sizing:border-box;"><img data-src="{0}" src="{0}" style="vertical-align:middle;max-width:100%;width:100%;box-sizing:border-box;" width="100%"></section></section>'.format(url)
def escape_html_text(text):
    return html.escape(text or "", quote=False)


def render_inline_markdown(text):
    """
    只处理 **加粗**。
    使用函数替换，避免 replacement string 因特殊字符出错。
    """
    text = escape_html_text(text)

    parts = []
    last = 0

    for match in re.finditer(r"\*\*(.+?)\*\*", text, flags=re.S):
        parts.append(f"<span>{text[last:match.start()]}</span>")

        bold_text = match.group(1)
        parts.append(
            '<strong style="box-sizing: border-box;">'
            f"<span>{bold_text}</span>"
            "</strong>"
        )

        last = match.end()

    parts.append(f"<span>{text[last:]}</span>")

    return "".join(part for part in parts if part != "<span></span>")


def paragraph_html(text):
    return (
        '<p style="margin: 0px 0px 12px;white-space: normal;padding: 0px;box-sizing: border-box;">'
        f"{render_inline_markdown(text)}"
        "</p>"
    )


def heading_html(text):
    return (
        '<p style="text-align: center;margin: 0px 0px 12px;white-space: normal;padding: 0px;box-sizing: border-box;">'
        '<strong style="box-sizing: border-box;">'
        f'<span><span style="font-size: 16px;">{escape_html_text(text)}</span></span>'
        "</strong>"
        "</p>"
    )


def paper_info_section(metadata):
    title = metadata.get("paper_title") or "未能自动识别标题"
    project_url = metadata.get("project_url") or "未找到"
    paper_url = metadata.get("paper_url") or ""

    def li(label, value, text_align=False):
        align = "text-align: left;" if text_align else ""
        return (
            '<li style="box-sizing: border-box;">'
            f'<p style="{align}margin: 0px;padding: 0px;box-sizing: border-box;">'
            '<strong style="box-sizing: border-box;">'
            f"<span>{escape_html_text(label)}</span>"
            "</strong>"
            "<span><br></span>"
            f"<span>{escape_html_text(value)}</span>"
            "</p>"
            "</li>"
        )

    items = "\n".join([
        li("论文标题", title, text_align=True),
        li("项目地址", project_url),
        li("论文地址", paper_url),
    ])

    return (
        '<section style="margin:20px 0 0;box-sizing:border-box;">'
        '<section style="font-size:14px;padding:0 10px;color:rgb(157,88,77);box-sizing:border-box;">'
        '<ul style="list-style-type:disc;box-sizing:border-box;padding-left:20px;list-style-position:outside;">'
        f"{items}"
        "</ul>"
        "</section>"
        "</section>"
    )


def markdown_to_wechat_html(markdown_text, metadata, head_url="", tail_url=""):
    """
    支持：
    [[HEAD_IMAGE]]
    [[TAIL_IMAGE]]
    [[PAPER_INFO]]
    [[IMAGE:xxx]]
    ## 二级标题
    普通段落
    **加粗**
    """
    markdown_text = markdown_text or ""

    blocks = []
    paragraph_buffer = []

    def flush_paragraph():
        nonlocal paragraph_buffer
        if paragraph_buffer:
            text = " ".join(x.strip() for x in paragraph_buffer if x.strip())
            if text:
                blocks.append(paragraph_html(text))
            paragraph_buffer = []

    lines = markdown_text.splitlines()

    for raw_line in lines:
        line = raw_line.strip()

        if not line:
            flush_paragraph()
            continue

        if line == "[[HEAD_IMAGE]]":
            flush_paragraph()
            if head_url:
                blocks.append(image_section(head_url))
            continue

        if line == "[[TAIL_IMAGE]]":
            flush_paragraph()
            if tail_url:
                blocks.append(image_section(tail_url))
            continue

        if line == "[[PAPER_INFO]]":
            flush_paragraph()
            blocks.append(paper_info_section(metadata))
            continue

        image_match = re.fullmatch(r"\[\[IMAGE:(.+?)\]\]", line)
        if image_match:
            flush_paragraph()
            desc = escape_html_text(image_match.group(1).strip())
            # 这里保持原占位符，方便前端点击后截图替换
            blocks.append(f"[[IMAGE:{desc}]]")
            continue
        if line.startswith("- "):
            flush_paragraph()
            item_text = line[2:].strip()
            blocks.append(
                '<p style="margin: 0px 0px 12px;white-space: normal;padding: 0px;box-sizing: border-box;">'
                '<span>• </span>'
                f"{render_inline_markdown(item_text)}"
                "</p>"
            )
            continue
        if line.startswith("## "):
            flush_paragraph()
            title = line[3:].strip()
            blocks.append(heading_html(title))
            continue
        
        # 忽略一级标题，防止模型把文章标题也写进正文
        if line.startswith("# "):
            flush_paragraph()
            continue

        paragraph_buffer.append(line)

    flush_paragraph()

    body = (
        '<section style="margin:20px 0 0;box-sizing:border-box;">'
        '<section style="font-size:14px;line-height:1.8;padding:0 10px;box-sizing:border-box;">'
        + "\n".join(blocks)
        + "</section>"
        "</section>"
    )

    return ensure_wrapper(
        '<section style="box-sizing:border-box;font-style:normal;font-weight:400;text-align:justify;font-size:16px;color:rgb(62,62,62);">'
        + body
        + "</section>"
    )

def ensure_wrapper(article_html):
    if "rich_media_content" in article_html:
        return article_html
    return f'<div class="rich_media_content js_underline_content defaultNoSetting" id="js_content">{article_html}</div>'


def fallback_article(metadata, paper_text, head_url, tail_url):
    title = html.escape(metadata.get("paper_title") or "未能自动识别标题")
    first = html.escape((paper_text.strip().splitlines() or [title])[0][:220])
    tail = image_section(tail_url) if tail_url else ""
    return ensure_wrapper(f"""
<section style="box-sizing:border-box;font-style:normal;font-weight:400;text-align:justify;font-size:16px;color:rgb(62,62,62);">
{image_section(head_url)}
<section style="margin:20px 0 0;box-sizing:border-box;"><section style="font-size:14px;line-height:1.8;padding:0 10px;box-sizing:border-box;">
<p style="margin:0 0 12px;white-space:normal;padding:0;box-sizing:border-box;"><strong>{title}</strong></p>
<p style="margin:0 0 12px;white-space:normal;padding:0;box-sizing:border-box;">{first}</p>
<p style="margin:0 0 12px;white-space:normal;padding:0;box-sizing:border-box;"><span style="color:rgb(67,117,185);box-sizing:border-box;"><strong>建议补一张论文方法图或实验结果图。</strong></span></p>
</section></section>
[[IMAGE:论文核心方法或主要实验结果截图]]
<section style="margin:20px 0 0;box-sizing:border-box;"><section style="font-size:14px;padding:0 10px;color:rgb(157,88,77);box-sizing:border-box;"><ul style="list-style-type:disc;box-sizing:border-box;padding-left:20px;list-style-position:outside;">
<li><p style="margin:0;padding:0;box-sizing:border-box;"><strong>论文标题</strong><br>{title}</p></li>
<li><p style="margin:0;padding:0;box-sizing:border-box;"><strong>项目地址</strong><br>{html.escape(metadata.get("project_url") or "未找到")}</p></li>
<li><p style="margin:0;padding:0;box-sizing:border-box;"><strong>论文地址</strong><br>{html.escape(metadata.get("paper_url") or "未找到")}</p></li>
</ul></section></section>
{tail}
</section>""")

SYSTEM_PROMPT = """
你是资深中文科技公众号作者和论文解读编辑。

你必须只输出一个合法 JSON 对象。
不要输出 Markdown 代码块。
不要输出解释。
不要输出工具调用。
不要输出 DSML。

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
9. 字数3k左右
10. 格式上，应当是一段leadingin-论文信息-前序研究不足或现状-核心设计-具体实验-亮点重现-总结展望，leadingin部分不需要二级标题，其他需要。leadingin要有一点故事性。
"""
def generate_article(paper_text, paper_url, focus_authors, head_url, tail_url):
    data = {
        "paper_title": "",
        "project_url": "",
        "paper_url": paper_url or "",
        "article_markdown": "",
        "article_html": "",
    }

    seed_search = web_search(f"{paper_url} project github paper") if paper_url else ""

    if not paper_text:
        paper_text = "本地未安装 pdftotext，需结合论文 URL 和联网检索理解论文。"

    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT,
        },
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
        first = chat(messages, TOOLS)["choices"][0]["message"]

        print(
            "[generate_article] first message =",
            json.dumps(first, ensure_ascii=False, indent=2)[:3000],
            flush=True,
        )

        tool_results = handle_tool_calls(messages, first, max_calls=6)

        if tool_results:
            print(f"[generate_article] handled {len(tool_results)} tool calls", flush=True)

            messages.append({
                "role": "user",
                "content": (
                    "工具调用已经完成。现在请不要再调用工具，不要输出 DSML，不要输出 Markdown 代码块。"
                    "请只输出一个合法 JSON 对象，字段必须包含 paper_title, project_url, paper_url, article_markdown。"
                ),
            })

            final = chat(messages, tools=None)["choices"][0]["message"]
        else:
            final = first

        final_content = final.get("content", "") or ""

        print(
            "[generate_article] final message =",
            json.dumps(final, ensure_ascii=False, indent=2)[:3000],
            flush=True,
        )
        print("[generate_article] final content =", repr(final_content)[:3000], flush=True)

        # 如果第二次还是 DSML，才重试一次
        if parse_dsml_tool_calls(final_content):
            print("[generate_article] final is still DSML, retrying once...", flush=True)

            messages.append({
                "role": "assistant",
                "content": final_content,
            })
            messages.append({
                "role": "user",
                "content": (
                    "上一次输出仍然是工具调用格式，这是错误的。"
                    "现在禁止调用工具，禁止输出 DSML，禁止输出任何解释。"
                    "请只输出一个合法 JSON 对象，字段必须包含 paper_title, project_url, paper_url, article_markdown。"
                ),
            })

            final = chat(messages, tools=None)["choices"][0]["message"]
            final_content = final.get("content", "") or ""

            print("[generate_article] retry final content =", repr(final_content)[:3000], flush=True)

        # 注意：这一段必须在 if parse_dsml_tool_calls(...) 外面
        parsed = parse_json_text(final_content)

        article_markdown = get_article_markdown(parsed)

        data.update({
            "paper_title": (
                parsed.get("paper_title")
                or parsed.get("title")
                or parsed.get("论文标题")
                or ""
            ),
            "project_url": (
                parsed.get("project_url")
                or parsed.get("project")
                or parsed.get("project_link")
                or parsed.get("项目地址")
                or ""
            ),
            "paper_url": (
                parsed.get("paper_url")
                or parsed.get("url")
                or parsed.get("论文地址")
                or paper_url
                or ""
            ),
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
            data["article_html"] = fallback_article(data, paper_text, head_url, tail_url)
        return data
    except Exception as exc:
        print("[generate_article] ERROR:", repr(exc), flush=True)

        data["_error"] = repr(exc)

        data["article_html"] = fallback_article(data, paper_text, head_url, tail_url)

        return data

INDEX_HTML = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>公众号论文写作工具</title>
  <link rel="stylesheet" href="/static/app.css">
</head>
<body>
  <div class="app-shell">
    <header class="topbar">
      <div><h1>公众号论文写作工具</h1><p>上传论文或输入 URL，生成可直接粘贴到微信公众平台的富文本。</p></div>
      <div class="actions"><button id="generateBtn" class="primary" type="button">开始生成</button><button id="copyBtn" type="button" disabled>复制</button></div>
    </header>
    <main class="workspace">
      <section class="left-pane">
        <form id="paperForm" class="input-panel">
          <div class="source-tabs"><label><input type="radio" name="source_type" value="url" checked> URL</label><label><input type="radio" name="source_type" value="pdf"> PDF</label></div>
          <input id="paperUrl" name="paper_url" type="url" placeholder="https://arxiv.org/abs/..." autocomplete="off">
          <input id="paperPdf" name="paper_pdf" type="file" accept="application/pdf">
          <div class="file-row"><label>头部图片 <input name="head_image" type="file" accept="image/*"></label><label>尾部图片 <input name="tail_image" type="file" accept="image/*"></label></div>
          <textarea name="focus_authors" rows="2" placeholder="重点关注作者，可用逗号分隔"></textarea>
        </form>
        <div class="pdf-panel">
          <div class="pdf-toolbar"><button id="prevPage" type="button">上一页</button><span><b id="pageNum">0</b> / <b id="pageCount">0</b></span><button id="nextPage" type="button">下一页</button><button id="zoomOut" type="button">缩小</button><button id="zoomIn" type="button">放大</button></div>
          <div id="pdfStage" class="pdf-stage"><canvas id="pdfCanvas"></canvas><div id="selectionBox" class="selection-box"></div><div class="empty-state">生成后论文会显示在这里</div></div>
        </div>
        <div class="meta-panel"><div><span>论文标题</span><strong id="metaTitle">-</strong></div><div><span>项目地址</span><a id="metaProject" href="#" target="_blank">-</a></div><div><span>论文地址</span><a id="metaPaper" href="#" target="_blank">-</a></div><p id="statusLine">等待输入。</p></div>
      </section>
      <section class="right-pane"><div class="preview-toolbar"><span>富文本预览</span><span id="copyStatus">生成完成后可复制</span></div><article id="copySource" class="wechat-preview" contenteditable="true"></article></section>
    </main>
  </div>
  <div id="shotModal" class="modal" hidden><div class="modal-card"><h2>截取论文图片</h2><p>在左侧 PDF 当前页拖拽选择区域，松开后点击保存。</p><div class="modal-actions"><button id="cancelShot" type="button">取消</button><button id="saveShot" class="primary" type="button" disabled>保存截图</button></div></div></div>
  <script type="module" src="/static/app.js"></script>
</body>
</html>"""




@app.get("/")
def index():
    return render_template("index.html")

@app.get("/public/<path:filename>")
def public_file(filename):
    return send_from_directory(PUBLIC_DIR, filename)


@app.post("/api/generate")
def api_generate():
    try:
        run_id, run_dir = create_run()
        source_type = request.form.get("source_type", "url")
        input_url = request.form.get("paper_url", "").strip()
        focus_authors = request.form.get("focus_authors", "").strip()
        if source_type == "url":
            if not input_url:
                return jsonify({"error": "请输入论文 URL"}), 400
            pdf_path, resolved_url = download_pdf(input_url, run_dir)
            display_paper_url = input_url
        else:
            pdf_file = request.files.get("paper_pdf")
            if not pdf_file or not pdf_file.filename:
                return jsonify({"error": "请上传 PDF 文件"}), 400
            pdf_path = run_dir / f"paper{Path(pdf_file.filename).suffix.lower() or '.pdf'}"
            pdf_path.write_bytes(pdf_file.read())
            resolved_url = input_url
            display_paper_url = resolved_url or ""
        head_file = request.files.get("head_image")
        head_path = None
        if head_file and head_file.filename:
            head_path = run_dir / f"head{Path(head_file.filename).suffix.lower() or '.bin'}"
            head_path.write_bytes(head_file.read())
        elif (ASSETS_DIR / "head-banner.png").exists():
            head_path = run_dir / "head-banner.png"
            shutil.copy2(ASSETS_DIR / "head-banner.png", head_path)
        tail_file = request.files.get("tail_image")
        tail_path = None
        if tail_file and tail_file.filename:
            tail_path = run_dir / f"tail{Path(tail_file.filename).suffix.lower() or '.bin'}"
            tail_path.write_bytes(tail_file.read())
        head_url = public_url(head_path) if head_path else ""
        tail_url = public_url(tail_path) if tail_path else ""
        paper_text = extract_pdf_text(pdf_path)
        ai_data = generate_article(paper_text, display_paper_url, focus_authors, head_url, tail_url)
        metadata = {
            "paper_title": ai_data.get("paper_title") or "未能自动识别标题",
            "project_url": ai_data.get("project_url") or "",
            "paper_url": ai_data.get("paper_url") or display_paper_url,
            "ai_error": ai_data.get("_error", ""),
        }
        article_html = ai_data.get("article_html") or fallback_article(metadata, paper_text, head_url, tail_url)
        print("[api_generate] article_html length:", len(article_html or ""), flush=True)
        print("[api_generate] article_html head:", repr((article_html or "")[:500]), flush=True)
        (run_dir / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
        (run_dir / "article.html").write_text(article_html, encoding="utf-8")
        (run_dir / "paper_text.txt").write_text(paper_text, encoding="utf-8")
        payload = {
            "run_id": run_id,
            "pdf_url": public_url(pdf_path),
            "run_public_url": public_url(run_dir),
            "metadata": metadata,
            "article_html": article_html,
        }
        return jsonify(payload)
    except Exception as exc:
        print("[api_generate] ERROR:", repr(exc), flush=True)
        traceback.print_exc()
        return jsonify({"error": repr(exc)}), 500


@app.post("/api/runs/<run_id>/screenshots")
def api_screenshot(run_id):
    try:
        data = request.get_json(force=True)
        run_dir = RUNS_DIR / safe_name(run_id)
        if not run_dir.exists():
            return jsonify({"error": "项目目录不存在"}), 404
        match = re.match(r"data:image/(png|jpeg|webp);base64,(.+)", data.get("image", ""))
        if not match:
            return jsonify({"error": "截图数据格式不正确"}), 400
        ext = "jpg" if match.group(1) == "jpeg" else match.group(1)
        target = run_dir / f"screenshot-{int(time.time())}-{uuid.uuid4().hex[:6]}.{ext}"
        target.write_bytes(base64.b64decode(match.group(2)))
        article_html = data.get("article_html", "")
        placeholder = data.get("placeholder", "")
        if placeholder:
            article_html = article_html.replace(placeholder, image_section(public_url(target)), 1)
        (run_dir / "article.html").write_text(article_html, encoding="utf-8")
        return jsonify({"image_url": public_url(target), "article_html": article_html})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


if __name__ == "__main__":
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    app.run(host="0.0.0.0", port=PORT, debug=False)
