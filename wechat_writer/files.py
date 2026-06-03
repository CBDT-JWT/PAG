import os
import re
import shutil
import socket
import subprocess
import time
import uuid
from pathlib import Path
from urllib.parse import quote, urljoin, urlparse

from flask import request

from .config import MAX_PAPER_CHARS, PORT, PUBLIC_DIR, RUNS_DIR
from .http_client import http_get


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


def public_asset_url(path, base_url=""):
    url = public_url(path)
    return f"{base_url.rstrip('/')}{url}" if base_url else url


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
