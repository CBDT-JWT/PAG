import json
import os
from http.client import IncompleteRead
from urllib.request import Request, urlopen, ProxyHandler, build_opener, install_opener

# 设置代理地址
PROXY_URL = os.environ.get("HTTP_PROXY") or "http://127.0.0.1:7890"

def http_get(url, timeout=40, headers=None):
    req_headers = {
        "User-Agent": "Mozilla/5.0 paper-wechat-writer/1.0",
        "Accept": "application/pdf,text/html;q=0.8,*/*;q=0.6",
    }
    if headers:
        req_headers.update(headers)

    # 通过代理访问
    proxy_handler = ProxyHandler({"http": PROXY_URL, "https": PROXY_URL})
    opener = build_opener(proxy_handler)
    install_opener(opener)

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


def http_json_stream(url, payload, on_delta=None, timeout=300):
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = Request(
        url,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
            "Authorization": f"Bearer {os.environ.get('OPENAI_API_KEY') or os.environ.get('API_KEY', '')}",
        },
    )
    message = {"role": "assistant", "content": ""}
    with urlopen(req, timeout=timeout) as resp:
        for raw in resp:
            line = raw.decode("utf-8", errors="ignore").strip()
            if not line or line.startswith(":") or not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                break
            try:
                chunk = json.loads(data)
            except json.JSONDecodeError:
                continue
            choices = chunk.get("choices") or []
            if not choices:
                continue
            delta = choices[0].get("delta") or {}
            content = delta.get("content") or ""
            if content:
                message["content"] += content
                if on_delta:
                    on_delta(content, len(message["content"]))
    return {"choices": [{"message": message}]}