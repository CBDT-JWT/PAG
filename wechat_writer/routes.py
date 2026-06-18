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

from .agent import generate_title_and_question, iterate_article_markdown
from .config import PUBLIC_DIR, RUNS_DIR
from .files import public_base, public_url, safe_name
from .generation import build_generation_payload
from .theme_presets import create_empty_preset, get_preset, load_presets, normalize_preset, preview_markdown, preview_metadata, save_preset_asset, upsert_preset
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


def replace_article_image(article_html, article_markdown, image_url, placeholder="", target_url=""):
    if placeholder:
        article_html = article_html.replace(placeholder, image_section(image_url), 1)
        article_markdown = article_markdown.replace(
            placeholder,
            image_markdown_from_placeholder(placeholder, image_url),
            1,
        )
    elif target_url:
        article_html = article_html.replace(target_url, image_url)
        article_markdown = article_markdown.replace(target_url, image_url)
    return article_html, article_markdown


def run_created_at(run_dir):
    try:
        return time.strftime("%Y-%m-%d %H:%M:%S", time.strptime(run_dir.name[:15], "%Y%m%d-%H%M%S"))
    except ValueError:
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(run_dir.stat().st_mtime))


def run_payload(run_dir):
    metadata = read_json_file(run_dir / "metadata.json", {})
    article_path = run_dir / "article.html"
    markdown_path = run_dir / "article.md"
    pdf_path = run_dir / "paper.pdf"
    return {
        "run_id": run_dir.name,
        "created_at": run_created_at(run_dir),
        "metadata": metadata,
        "article_html": article_path.read_text(encoding="utf-8") if article_path.exists() else "",
        "article_markdown": markdown_path.read_text(encoding="utf-8") if markdown_path.exists() else "",
        "pdf_url": public_url(pdf_path) if pdf_path.exists() else "",
        "run_public_url": public_url(run_dir),
    }


def register_routes(app):
    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/public/<path:filename>")
    def public_file(filename):
        return send_from_directory(PUBLIC_DIR, filename)

    @app.get("/api/runs")
    @app.get("/api/runs/")
    @app.get("/api/runs/history")
    def api_runs():
        runs = []
        if RUNS_DIR.exists():
            for run_dir in sorted((path for path in RUNS_DIR.iterdir() if path.is_dir()), reverse=True):
                metadata = read_json_file(run_dir / "metadata.json", {})
                runs.append({
                    "run_id": run_dir.name,
                    "paper_title": metadata.get("paper_title") or "未命名论文",
                    "created_at": run_created_at(run_dir),
                })
        return jsonify({"runs": runs})

    @app.get("/api/runs/<run_id>")
    def api_run(run_id):
        run_dir = RUNS_DIR / safe_name(run_id)
        if not run_dir.exists():
            return jsonify({"error": "项目目录不存在"}), 404
        return jsonify(run_payload(run_dir))

    @app.get("/api/presets")
    @app.get("/api/runs/presets")
    def api_presets():
        return jsonify({"presets": load_presets(), "template": create_empty_preset()})

    @app.post("/api/presets")
    @app.post("/api/runs/presets")
    def api_save_preset():
        try:
            data = request.get_json(force=True)
            preset = upsert_preset(data or {})
            return jsonify({"preset": preset, "presets": load_presets()})
        except Exception as exc:
            return jsonify({"error": str(exc)}), 500

    @app.post("/api/presets/assets")
    @app.post("/api/runs/presets/assets")
    def api_preset_asset():
        try:
            upload = request.files.get("image")
            prefix = request.form.get("prefix", "preset")
            if not upload or not upload.filename:
                return jsonify({"error": "请选择图片"}), 400
            return jsonify({"url": save_preset_asset(upload, prefix=prefix)})
        except Exception as exc:
            return jsonify({"error": str(exc)}), 500

    @app.post("/api/presets/preview")
    @app.post("/api/runs/presets/preview")
    def api_preset_preview():
        try:
            theme = normalize_preset(request.get_json(force=True) or {})
            html = markdown_to_wechat_html(
                preview_markdown(),
                metadata=preview_metadata(),
                head_url=((theme.get("images") or {}).get("head_url", "")),
                tail_url=((theme.get("images") or {}).get("tail_url", "")),
                theme=theme,
            )
            return jsonify({"html": html})
        except Exception as exc:
            return jsonify({"error": str(exc)}), 500

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

            def progress(percent, message, detail="", **extra):
                payload = {"percent": max(0, min(100, int(percent))), "message": message}
                if detail:
                    payload["detail"] = detail
                payload.update(extra)
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
            image_url = public_url(target)
            markdown_path = run_dir / "article.md"
            article_markdown = data.get("article_markdown") or (
                markdown_path.read_text(encoding="utf-8") if markdown_path.exists() else ""
            )
            article_html, article_markdown = replace_article_image(
                article_html,
                article_markdown,
                image_url,
                placeholder=placeholder,
                target_url=data.get("target_url", ""),
            )
            article_path.write_text(article_html, encoding="utf-8")
            markdown_path.write_text(article_markdown, encoding="utf-8")

            return jsonify({
                "image_url": image_url,
                "article_html": article_html,
                "article_markdown": article_markdown,
            })
        except Exception as exc:
            return jsonify({"error": str(exc)}), 500

    @app.post("/api/runs/<run_id>/images")
    def api_upload_image(run_id):
        try:
            run_dir = RUNS_DIR / safe_name(run_id)
            if not run_dir.exists():
                return jsonify({"error": "项目目录不存在"}), 404
            upload = request.files.get("image")
            if not upload or not upload.filename:
                return jsonify({"error": "请选择图片"}), 400
            compressed = compress_screenshot(upload.read())
            target = run_dir / f"image-{int(time.time())}-{uuid.uuid4().hex[:6]}.jpg"
            target.write_bytes(compressed)
            image_url = public_url(target)
            article_path = run_dir / "article.html"
            markdown_path = run_dir / "article.md"
            article_html = request.form.get("article_html") or (
                article_path.read_text(encoding="utf-8") if article_path.exists() else ""
            )
            article_markdown = request.form.get("article_markdown") or (
                markdown_path.read_text(encoding="utf-8") if markdown_path.exists() else ""
            )
            article_html, article_markdown = replace_article_image(
                article_html,
                article_markdown,
                image_url,
                placeholder=request.form.get("placeholder", ""),
                target_url=request.form.get("target_url", ""),
            )
            article_path.write_text(article_html, encoding="utf-8")
            markdown_path.write_text(article_markdown, encoding="utf-8")
            return jsonify({
                "image_url": image_url,
                "article_html": article_html,
                "article_markdown": article_markdown,
            })
        except Exception as exc:
            return jsonify({"error": str(exc)}), 500

    @app.post("/api/runs/<run_id>/sync")
    def api_sync_run(run_id):
        try:
            data = request.get_json(force=True)
            run_dir = RUNS_DIR / safe_name(run_id)
            if not run_dir.exists():
                return jsonify({"error": "项目目录不存在"}), 404
            article_html = data.get("article_html", "")
            article_markdown = data.get("article_markdown", "")
            (run_dir / "article.html").write_text(article_html, encoding="utf-8")
            (run_dir / "article.md").write_text(article_markdown, encoding="utf-8")
            return jsonify({"ok": True})
        except Exception as exc:
            return jsonify({"error": str(exc)}), 500

    @app.post("/api/runs/<run_id>/preset")
    def api_apply_preset(run_id):
        try:
            run_dir = RUNS_DIR / safe_name(run_id)
            if not run_dir.exists():
                return jsonify({"error": "项目目录不存在"}), 404
            data = request.get_json(force=True)
            preset = get_preset((data or {}).get("preset_id", ""))
            metadata = read_json_file(run_dir / "metadata.json", {})
            metadata["preset_id"] = preset.get("id")
            metadata["preset_name"] = preset.get("name")
            markdown_path = run_dir / "article.md"
            article_markdown = markdown_path.read_text(encoding="utf-8") if markdown_path.exists() else ""
            assets = {
                "head_url": (preset.get("images") or {}).get("head_url", ""),
                "tail_url": (preset.get("images") or {}).get("tail_url", ""),
                "preset_id": preset.get("id"),
            }
            updated_html = markdown_to_wechat_html(
                article_markdown,
                metadata=metadata,
                head_url=assets["head_url"],
                tail_url=assets["tail_url"],
                theme=preset,
            )
            (run_dir / "article.html").write_text(updated_html, encoding="utf-8")
            (run_dir / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
            (run_dir / "render_assets.json").write_text(json.dumps(assets, ensure_ascii=False, indent=2), encoding="utf-8")
            return jsonify({"article_html": updated_html, "article_markdown": article_markdown, "metadata": metadata})
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
            title_question = generate_title_and_question(
                updated_markdown,
                paper_title=metadata.get("paper_title", ""),
                prompt_override=get_preset(metadata.get("preset_id", "")).get("title_question_prompt", ""),
            )
            metadata["article_titles"] = title_question.get("article_titles") or metadata.get("article_titles", [])
            metadata["article_title"] = title_question.get("article_title") or metadata.get("article_title", "")
            metadata["reader_question"] = title_question.get("reader_question") or metadata.get("reader_question", "")
            assets = read_json_file(run_dir / "render_assets.json", {})
            updated_html = markdown_to_wechat_html(
                updated_markdown,
                metadata=metadata,
                head_url=assets.get("head_url", ""),
                tail_url=assets.get("tail_url", ""),
                theme=get_preset(metadata.get("preset_id", assets.get("preset_id", ""))),
            )
            markdown_path.write_text(updated_markdown, encoding="utf-8")
            article_path = run_dir / "article.html"
            article_path.write_text(updated_html, encoding="utf-8")
            (run_dir / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
            return jsonify({"article_html": updated_html, "article_markdown": updated_markdown, "metadata": metadata})
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
