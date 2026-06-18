import json
from pathlib import Path

from .agent import emit_progress, extract_metadata, generate_article, generate_title_and_question
from .files import create_run, download_pdf, extract_pdf_text, public_url
from .theme_presets import get_preset
from .wechat_html import fallback_article, markdown_to_wechat_html


def build_generation_payload(form, files, progress=None, base_url=""):
    emit_progress(progress, 3, "正在创建本次生成目录")
    run_id, run_dir = create_run()
    source_type = form.get("source_type", "url")
    input_url = form.get("paper_url", "").strip()
    focus_authors = form.get("focus_authors", "").strip()
    preset_id = form.get("preset_id", "").strip()
    preset = get_preset(preset_id)

    if source_type == "url":
        if not input_url:
            raise ValueError("请输入论文 URL")
        emit_progress(progress, 12, "正在下载论文 PDF", input_url)
        pdf_path, _ = download_pdf(input_url, run_dir)
        display_paper_url = input_url
        emit_progress(progress, 24, "论文 PDF 已保存", pdf_path.name)
    else:
        pdf_file = files.get("paper_pdf")
        if not pdf_file or not pdf_file.filename:
            raise ValueError("请上传 PDF 文件")
        emit_progress(progress, 12, "正在保存上传的 PDF", pdf_file.filename)
        pdf_path = run_dir / f"paper{Path(pdf_file.filename).suffix.lower() or '.pdf'}"
        pdf_path.write_bytes(pdf_file.read())
        display_paper_url = input_url or ""
        emit_progress(progress, 24, "上传 PDF 已保存", pdf_path.name)

    head_url = (preset.get("images") or {}).get("head_url", "")
    tail_url = (preset.get("images") or {}).get("tail_url", "")
    if head_url:
        emit_progress(progress, 28, "已应用预设文首图片", preset.get("name", ""))
    if tail_url:
        emit_progress(progress, 31, "已应用预设文末图片", preset.get("name", ""))

    emit_progress(progress, 36, "正在提取 PDF 文本")
    paper_text = extract_pdf_text(pdf_path)
    emit_progress(progress, 43, f"PDF 文本提取完成：{len(paper_text)} 字")

    ai_data = generate_article(
        paper_text,
        display_paper_url,
        focus_authors,
        head_url,
        tail_url,
        preset_prompt=preset.get("prompt_hint", ""),
        progress=progress,
    )
    early_metadata = extract_metadata(ai_data, paper_url=display_paper_url)
    emit_progress(progress, 88, "论文信息已识别", metadata=early_metadata)
    title_question = generate_title_and_question(
        ai_data.get("article_markdown", ""),
        paper_title=ai_data.get("paper_title", ""),
        progress=progress,
    )
    metadata = {
        "paper_title": ai_data.get("paper_title") or "",
        "project_url": ai_data.get("project_url") or "",
        "paper_url": ai_data.get("paper_url") or display_paper_url,
        "article_titles": title_question.get("article_titles") or [],
        "article_title": title_question.get("article_title") or "",
        "reader_question": title_question.get("reader_question") or "",
        "preset_id": preset.get("id"),
        "preset_name": preset.get("name"),
        "ai_error": ai_data.get("_error", ""),
    }
    article_markdown = ai_data.get("article_markdown") or ""
    if article_markdown:
        article_html = markdown_to_wechat_html(
            article_markdown,
            metadata=metadata,
            head_url=head_url,
            tail_url=tail_url,
            theme=preset,
        )
    else:
        article_html = fallback_article(metadata, paper_text, head_url, tail_url, theme=preset)
    print("[api_generate] article_html length:", len(article_html or ""), flush=True)
    print("[api_generate] article_html head:", repr((article_html or "")[:500]), flush=True)

    emit_progress(progress, 100, "正在写入生成结果")
    (run_dir / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    (run_dir / "render_assets.json").write_text(
        json.dumps({"head_url": head_url, "tail_url": tail_url, "preset_id": preset.get("id")}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (run_dir / "article.md").write_text(article_markdown, encoding="utf-8")
    (run_dir / "article.html").write_text(article_html, encoding="utf-8")
    (run_dir / "paper_text.txt").write_text(paper_text, encoding="utf-8")
    payload = {
        "run_id": run_id,
        "pdf_url": public_url(pdf_path),
        "run_public_url": public_url(run_dir),
        "metadata": metadata,
        "article_markdown": article_markdown,
        "article_html": article_html,
    }
    emit_progress(progress, 100, "生成完成", f"public/runs/{run_id}")
    return payload
