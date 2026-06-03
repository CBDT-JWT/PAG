import base64
import io
import json
import re
import threading
import time
import traceback
import uuid
from queue import Empty, Queue

from flask import Response, jsonify, render_template, request, send_from_directory, stream_with_context
from PIL import Image, ImageOps

from .agent import iterate_article_markdown
from .config import PUBLIC_DIR, RUNS_DIR
from .files import public_asset_url, public_base, safe_name
from .generation import build_generation_payload
from .wechat_html import image_section, markdown_to_wechat_html

MAX_SCREENSHOT_BYTES = 250 * 1024


def read_json_file(path, default=None):
    if not path.exists():
        return default if default is not None else {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default if default is not None else {}


def image_markdown_from_placeholder(placeholder, image_url):
    placeholder = (placeholder or "").strip()
    match = re.fullmatch(r"\[\[IMAGE:(.+?)\]\]", placeholder)
    alt = match.group(1).strip() if match else "截图"
    return f"![{alt}]({image_url})"


def register_routes(app):
    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/public/<path:filename>")
    def public_file(filename):
        return send_from_directory(PUBLIC_DIR, filename)

    @app.post("/api/generate")
    def api_generate():
        try:
            return jsonify(build_generation_payload(request.form, request.files, base_url=public_base()))
        except Exception as exc:
            print("[api_generate] ERROR:", repr(exc), flush=True)
            traceback.print_exc()
            return jsonify({"error": repr(exc)}), 500

    @app.post("/api/generate/stream")
    def api_generate_stream():
        form = request.form.copy()
        files = request.files.copy()
        base_url = public_base()

        @stream_with_context
        def generate():
            event_queue = Queue()

            def progress(percent, message, detail=""):
                payload = {"percent": max(0, min(100, int(percent))), "message": message}
                if detail:
                    payload["detail"] = detail
                event_queue.put(sse_line("progress", **payload))

            def worker():
                try:
                    payload = build_generation_payload(form, files, progress=progress, base_url=base_url)
                    event_queue.put(sse_line("done", data=payload))
                except Exception as exc:
                    print("[api_generate_stream] ERROR:", repr(exc), flush=True)
                    traceback.print_exc()
                    event_queue.put(sse_line("error", message=repr(exc)))
                finally:
                    event_queue.put(None)

            yield sse_line("progress", percent=0, message="开始生成")
            threading.Thread(target=worker, daemon=True).start()

            while True:
                try:
                    event = event_queue.get(timeout=15)
                except Empty:
                    yield sse_line("heartbeat", message="仍在处理中")
                    continue
                if event is None:
                    break
                yield event

        return Response(
            generate(),
            mimetype="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    @app.post("/api/runs/<run_id>/screenshots")
    def api_screenshot(run_id):
        try:
            data = request.get_json(force=True)
            run_dir = RUNS_DIR / safe_name(run_id)
            if not run_dir.exists():
                return jsonify({"error": "项目目录不存在"}), 404
            match = re.match(r"data:image/([a-zA-Z0-9.+-]+);base64,\s*(.+)", data.get("image", ""), flags=re.S)
            if not match:
                return jsonify({"error": "截图数据格式不正确"}), 400
            raw_image = base64.b64decode(re.sub(r"\s+", "", match.group(2)))
            compressed = compress_screenshot(raw_image)
            target = run_dir / f"screenshot-{int(time.time())}-{uuid.uuid4().hex[:6]}.jpg"
            target.write_bytes(compressed)
            article_path = run_dir / "article.html"
            article_html = data.get("article_html") or (
                article_path.read_text(encoding="utf-8") if article_path.exists() else ""
            )
            placeholder = data.get("placeholder", "")
            image_url = public_asset_url(target, public_base())
            if placeholder:
                article_html = article_html.replace(placeholder, image_section(image_url), 1)
            article_path.write_text(article_html, encoding="utf-8")

            markdown_path = run_dir / "article.md"
            article_markdown = data.get("article_markdown") or (
                markdown_path.read_text(encoding="utf-8") if markdown_path.exists() else ""
            )
            if placeholder and article_markdown:
                article_markdown = article_markdown.replace(
                    placeholder,
                    image_markdown_from_placeholder(placeholder, image_url),
                    1,
                )
                markdown_path.write_text(article_markdown, encoding="utf-8")

            return jsonify({
                "image_url": image_url,
                "article_html": article_html,
                "article_markdown": article_markdown,
            })
        except Exception as exc:
            return jsonify({"error": str(exc)}), 500

    @app.post("/api/runs/<run_id>/iterate")
    def api_iterate(run_id):
        try:
            data = request.get_json(force=True)
            run_dir = RUNS_DIR / safe_name(run_id)
            if not run_dir.exists():
                return jsonify({"error": "项目目录不存在"}), 404

            markdown_path = run_dir / "article.md"
            article_markdown = data.get("article_markdown") or (
                markdown_path.read_text(encoding="utf-8") if markdown_path.exists() else ""
            )
            updated_markdown = iterate_article_markdown(
                article_markdown=article_markdown,
                instruction=data.get("prompt", ""),
                selected_text=data.get("selected_text", ""),
            )
            metadata = read_json_file(run_dir / "metadata.json", {})
            assets = read_json_file(run_dir / "render_assets.json", {})
            updated_html = markdown_to_wechat_html(
                updated_markdown,
                metadata=metadata,
                head_url=assets.get("head_url", ""),
                tail_url=assets.get("tail_url", ""),
            )
            markdown_path.write_text(updated_markdown, encoding="utf-8")
            article_path = run_dir / "article.html"
            article_path.write_text(updated_html, encoding="utf-8")
            return jsonify({"article_html": updated_html, "article_markdown": updated_markdown})
        except Exception as exc:
            return jsonify({"error": str(exc)}), 500


def sse_line(event_type, **payload):
    payload["type"] = event_type
    return "data: " + json.dumps(payload, ensure_ascii=False) + "\n\n"


def compress_screenshot(raw_image):
    with Image.open(io.BytesIO(raw_image)) as image:
        image = ImageOps.exif_transpose(image)
        if image.mode in {"RGBA", "LA"} or (image.mode == "P" and "transparency" in image.info):
            background = Image.new("RGB", image.size, "white")
            background.paste(image.convert("RGBA"), mask=image.convert("RGBA").split()[-1])
            image = background
        else:
            image = image.convert("RGB")

        max_side = max(image.size)
        while max_side >= 120:
            candidate = resize_to_max_side(image, max_side)
            for quality in (88, 80, 72, 64, 56, 48, 40, 34, 28, 22, 16):
                output = io.BytesIO()
                candidate.save(output, format="JPEG", quality=quality, optimize=True, progressive=True)
                data = output.getvalue()
                if len(data) <= MAX_SCREENSHOT_BYTES:
                    return data
            max_side = int(max_side * 0.75)

        output = io.BytesIO()
        resize_to_max_side(image, 120).save(output, format="JPEG", quality=12, optimize=True, progressive=True)
        return output.getvalue()


def resize_to_max_side(image, max_side):
    width, height = image.size
    current_max = max(width, height)
    if current_max <= max_side:
        return image
    ratio = max_side / current_max
    size = (max(1, int(width * ratio)), max(1, int(height * ratio)))
    return image.resize(size, Image.Resampling.LANCZOS)
