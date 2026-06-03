import base64
import json
import re
import threading
import time
import traceback
import uuid
from queue import Empty, Queue

from flask import Response, jsonify, render_template, request, send_from_directory, stream_with_context

from .config import PUBLIC_DIR, RUNS_DIR
from .files import public_asset_url, public_base, safe_name
from .generation import build_generation_payload
from .wechat_html import image_section


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
            subtype = match.group(1).lower()
            ext = "jpg" if subtype in {"jpeg", "jpg", "pjpeg"} else subtype.split("+", 1)[0]
            target = run_dir / f"screenshot-{int(time.time())}-{uuid.uuid4().hex[:6]}.{ext}"
            target.write_bytes(base64.b64decode(match.group(2)))
            article_html = data.get("article_html", "")
            placeholder = data.get("placeholder", "")
            image_url = public_asset_url(target, public_base())
            if placeholder:
                article_html = article_html.replace(placeholder, image_section(image_url), 1)
            (run_dir / "article.html").write_text(article_html, encoding="utf-8")
            return jsonify({"image_url": image_url, "article_html": article_html})
        except Exception as exc:
            return jsonify({"error": str(exc)}), 500


def sse_line(event_type, **payload):
    payload["type"] = event_type
    return "data: " + json.dumps(payload, ensure_ascii=False) + "\n\n"
