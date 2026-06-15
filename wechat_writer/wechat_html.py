import html
import re


BODY_FONT_SIZE = "14px"
BODY_LINE_HEIGHT = "26px"
PARAGRAPH_MARGIN_BOTTOM = "12px"
SECTION_TITLE_FONT_SIZE = "16px"
BODY_HORIZONTAL_PADDING = "10px"
IMAGE_WIDTH = "90%"
LETTER_SPACING = "0.3px"
TEXT_BLOCK_MARGIN = f"0 {BODY_HORIZONTAL_PADDING} {PARAGRAPH_MARGIN_BOTTOM} {BODY_HORIZONTAL_PADDING}"


def image_section(url):
    return (
        f'<section style="text-align:center;margin:{PARAGRAPH_MARGIN_BOTTOM} {BODY_HORIZONTAL_PADDING};line-height:0;box-sizing:border-box;">'
        '<section style="max-width:100%;vertical-align:middle;display:block;line-height:0;height:auto;box-sizing:border-box;">'
        f'<img data-src="{{0}}" src="{{0}}" style="display:block;margin-left:auto;margin-right:auto;vertical-align:middle;max-width:{IMAGE_WIDTH};width:{IMAGE_WIDTH};height:auto;box-sizing:border-box;" width="{IMAGE_WIDTH}">'
        "</section></section>"
    ).format(url)


def escape_html_text(text):
    return html.escape(text or "", quote=False)


def escape_plain_text(text):
    return escape_html_text(text).replace("\\$", "$")


def render_inline_markdown(text, formula_renderer=None, allow_bold=True):
    text = text or ""
    parts = []
    last = 0
    pattern = re.compile(r"(?<!\\)\$(?!\$)(.+?)(?<!\\)\$(?!\$)|\*\*(.+?)\*\*", flags=re.S)

    for match in pattern.finditer(text):
        parts.append(f"<span>{escape_plain_text(text[last:match.start()])}</span>")
        formula_text = match.group(1)
        bold_text = match.group(2)
        if formula_text is not None:
            rendered = formula_renderer.render_inline(formula_text.strip()) if formula_renderer else escape_plain_text(formula_text)
            parts.append(rendered)
        elif allow_bold and bold_text is not None:
            parts.append(
                '<strong style="box-sizing:border-box;">'
                f"{render_inline_markdown(bold_text, formula_renderer=formula_renderer, allow_bold=False)}"
                "</strong>"
            )
        else:
            parts.append(f"<span>{escape_html_text(match.group(0))}</span>")
        last = match.end()

    parts.append(f"<span>{escape_plain_text(text[last:])}</span>")
    return "".join(part for part in parts if part != "<span></span>")


def paragraph_html(text, formula_renderer=None):
    return (
        f'<p style="margin:{TEXT_BLOCK_MARGIN};white-space:normal;padding:0;box-sizing:border-box;font-size:{BODY_FONT_SIZE};line-height:{BODY_LINE_HEIGHT};letter-spacing:{LETTER_SPACING};">'
        f"{render_inline_markdown(text, formula_renderer=formula_renderer)}"
        "</p>"
    )


def heading_html(text):
    return (
        f'<p data-markdown-heading="2" style="text-align:center;margin:{TEXT_BLOCK_MARGIN};white-space:normal;padding:0;box-sizing:border-box;font-size:{SECTION_TITLE_FONT_SIZE};line-height:{BODY_LINE_HEIGHT};letter-spacing:{LETTER_SPACING};">'
        '<strong style="color:rgb(62,62,62);box-sizing: border-box;">'
        f'<span><span style="font-size:{SECTION_TITLE_FONT_SIZE};">{escape_html_text(text)}</span></span>'
        "</strong>"
        "</p>"
    )


def paper_info_section(metadata):
    items_data = [
        ("论文标题", metadata.get("paper_title") or "", True),
        ("项目地址", metadata.get("project_url") or "", False),
        ("论文地址", metadata.get("paper_url") or "", False),
    ]

    def li(label, value, text_align=False):
        align = "text-align: left;" if text_align else ""
        return (
            '<li style="box-sizing: border-box;">'
            f'<p style="{align}margin:0 {BODY_HORIZONTAL_PADDING};padding:0;box-sizing:border-box;font-size:{BODY_FONT_SIZE};line-height:{BODY_LINE_HEIGHT};letter-spacing:{LETTER_SPACING};">'
            '<strong style="box-sizing: border-box;">'
            f"<span>{escape_html_text(label)}</span>"
            "</strong>"
            "<span><br></span>"
            f"<span>{escape_html_text(value)}</span>"
            "</p>"
            "</li>"
        )

    items = "\n".join(li(label, value, text_align=text_align) for label, value, text_align in items_data if value)
    if not items:
        return ""

    return (
        '<section data-markdown-token="[[PAPER_INFO]]" contenteditable="false" style="margin:20px 0 0;box-sizing:border-box;">'
        f'<section style="font-size:{BODY_FONT_SIZE};line-height:{BODY_LINE_HEIGHT};padding:0;color:rgb(157,88,77);box-sizing:border-box;">'
        '<ul style="list-style-type:disc;box-sizing:border-box;padding-left:20px;list-style-position:outside;">'
        f"{items}"
        "</ul>"
        "</section>"
        "</section>"
    )


def reader_question_section(question, formula_renderer=None):
    question = (question or "").strip()
    if not question:
        return ""
    return (
        '<section data-generated-question="true" contenteditable="false" style="margin:28px 10px 0 10px;padding:16px 14px;border-radius:12px;'
        'background:rgb(247,244,238);box-sizing:border-box;">'
        f'<p style="margin:0 0 8px 0;padding:0;box-sizing:border-box;font-size:13px;line-height:22px;'
        'letter-spacing:0.3px;color:rgb(157,88,77);"><strong style="box-sizing:border-box;">留给读者的问题</strong></p>'
        f'<p style="margin:0;padding:0;box-sizing:border-box;font-size:{BODY_FONT_SIZE};line-height:{BODY_LINE_HEIGHT};'
        f'letter-spacing:{LETTER_SPACING};color:rgb(62,62,62);">{render_inline_markdown(question, formula_renderer=formula_renderer)}</p>'
        "</section>"
    )


def markdown_to_wechat_html(markdown_text, metadata, head_url="", tail_url="", formula_renderer=None):
    markdown_text = markdown_text or ""
    blocks = []
    paragraph_buffer = []
    lines = markdown_text.splitlines()

    def flush_paragraph():
        nonlocal paragraph_buffer
        if paragraph_buffer:
            text = " ".join(x.strip() for x in paragraph_buffer if x.strip())
            if text:
                blocks.append(paragraph_html(text, formula_renderer=formula_renderer))
            paragraph_buffer = []

    index = 0
    while index < len(lines):
        raw_line = lines[index]
        line = raw_line.strip()

        if not line:
            flush_paragraph()
            index += 1
            continue
        if line == "$$":
            flush_paragraph()
            formula_lines = []
            index += 1
            while index < len(lines) and lines[index].strip() != "$$":
                formula_lines.append(lines[index].rstrip())
                index += 1
            formula = "\n".join(formula_lines).strip()
            if formula:
                if formula_renderer:
                    blocks.append(formula_renderer.render_block(formula))
                else:
                    blocks.append(paragraph_html(formula))
            index += 1
            continue
        if line.startswith("$$") and line.endswith("$$") and len(line) > 4:
            flush_paragraph()
            formula = line[2:-2].strip()
            if formula:
                if formula_renderer:
                    blocks.append(formula_renderer.render_block(formula))
                else:
                    blocks.append(paragraph_html(formula))
            index += 1
            continue
        if line == "[[HEAD_IMAGE]]":
            flush_paragraph()
            if head_url:
                blocks.append(image_section(head_url))
            index += 1
            continue
        if line == "[[TAIL_IMAGE]]":
            flush_paragraph()
            if tail_url:
                blocks.append(image_section(tail_url))
            index += 1
            continue
        if line == "[[PAPER_INFO]]":
            flush_paragraph()
            info_section = paper_info_section(metadata)
            if info_section:
                blocks.append(info_section)
            blocks.append("[[IMAGE:论文开头部分截图]]")
            index += 1
            continue

        markdown_image = re.fullmatch(r"!\[(.*?)\]\((.+?)\)", line)
        if markdown_image:
            flush_paragraph()
            blocks.append(image_section(markdown_image.group(2).strip()))
            index += 1
            continue

        image_match = re.fullmatch(r"\[\[IMAGE:(.+?)\]\]", line)
        if image_match:
            flush_paragraph()
            desc = escape_html_text(image_match.group(1).strip())
            blocks.append(f"[[IMAGE:{desc}]]")
            index += 1
            continue
        if line.startswith("- "):
            flush_paragraph()
            item_text = line[2:].strip()
            blocks.append(
                f'<p style="margin:{TEXT_BLOCK_MARGIN};white-space:normal;padding:0;box-sizing:border-box;font-size:{BODY_FONT_SIZE};line-height:{BODY_LINE_HEIGHT};letter-spacing:{LETTER_SPACING};">'
                '<span>• </span>'
                f"{render_inline_markdown(item_text, formula_renderer=formula_renderer)}"
                "</p>"
            )
            index += 1
            continue
        if line.startswith("## "):
            flush_paragraph()
            blocks.append(heading_html(line[3:].strip()))
            index += 1
            continue
        if line.startswith("# "):
            flush_paragraph()
            index += 1
            continue

        paragraph_buffer.append(line)
        index += 1

    flush_paragraph()
    question_section = reader_question_section(metadata.get("reader_question", ""), formula_renderer=formula_renderer)
    if question_section:
        blocks.append(question_section)
    body = (
        '<section style="margin:20px 0 0;box-sizing:border-box;">'
        f'<section style="font-size:{BODY_FONT_SIZE};line-height:{BODY_LINE_HEIGHT};padding:0;box-sizing:border-box;">'
        + "\n".join(blocks)
        + "</section>"
        "</section>"
    )
    return ensure_wrapper(
        f'<section style="box-sizing:border-box;font-style:normal;font-weight:400;text-align:justify;font-size:{BODY_FONT_SIZE};line-height:{BODY_LINE_HEIGHT};letter-spacing:{LETTER_SPACING};color:rgb(62,62,62);">'
        + body
        + "</section>"
    )


def ensure_wrapper(article_html):
    if "rich_media_content" in article_html:
        return article_html
    return f'<div class="rich_media_content js_underline_content defaultNoSetting" id="js_content">{article_html}</div>'


def fallback_article(metadata, paper_text, head_url, tail_url):
    title = html.escape(metadata.get("paper_title") or "论文信息待补充")
    first = html.escape((paper_text.strip().splitlines() or [title])[0][:220])
    tail = image_section(tail_url) if tail_url else ""
    info_items = []
    if metadata.get("paper_title"):
        info_items.append(
            f'<li><p style="margin:0 {BODY_HORIZONTAL_PADDING};padding:0;box-sizing:border-box;font-size:{BODY_FONT_SIZE};line-height:{BODY_LINE_HEIGHT};letter-spacing:{LETTER_SPACING};"><strong>论文标题</strong><br>{html.escape(metadata.get("paper_title") or "")}</p></li>'
        )
    if metadata.get("project_url"):
        info_items.append(
            f'<li><p style="margin:0 {BODY_HORIZONTAL_PADDING};padding:0;box-sizing:border-box;font-size:{BODY_FONT_SIZE};line-height:{BODY_LINE_HEIGHT};letter-spacing:{LETTER_SPACING};"><strong>项目地址</strong><br>{html.escape(metadata.get("project_url") or "")}</p></li>'
        )
    if metadata.get("paper_url"):
        info_items.append(
            f'<li><p style="margin:0 {BODY_HORIZONTAL_PADDING};padding:0;box-sizing:border-box;font-size:{BODY_FONT_SIZE};line-height:{BODY_LINE_HEIGHT};letter-spacing:{LETTER_SPACING};"><strong>论文地址</strong><br>{html.escape(metadata.get("paper_url") or "")}</p></li>'
        )
    info_block = ""
    if info_items:
        info_block = (
            f'<section style="margin:20px 0 0;box-sizing:border-box;"><section style="font-size:{BODY_FONT_SIZE};line-height:{BODY_LINE_HEIGHT};padding:0;color:rgb(157,88,77);box-sizing:border-box;"><ul style="list-style-type:disc;box-sizing:border-box;padding-left:20px;list-style-position:outside;">'
            + "".join(info_items)
            + "</ul></section></section>"
        )
    question_block = reader_question_section(metadata.get("reader_question", ""))
    return ensure_wrapper(f"""
<section style="box-sizing:border-box;font-style:normal;font-weight:400;text-align:justify;font-size:{BODY_FONT_SIZE};line-height:{BODY_LINE_HEIGHT};letter-spacing:{LETTER_SPACING};color:rgb(62,62,62);">
{image_section(head_url)}
<section style="margin:20px 0 0;box-sizing:border-box;"><section style="font-size:{BODY_FONT_SIZE};line-height:{BODY_LINE_HEIGHT};padding:0;box-sizing:border-box;">
<p style="margin:{TEXT_BLOCK_MARGIN};white-space:normal;padding:0;box-sizing:border-box;font-size:{BODY_FONT_SIZE};line-height:{BODY_LINE_HEIGHT};letter-spacing:{LETTER_SPACING};"><strong style="box-sizing:border-box;">{title}</strong></p>
<p style="margin:{TEXT_BLOCK_MARGIN};white-space:normal;padding:0;box-sizing:border-box;font-size:{BODY_FONT_SIZE};line-height:{BODY_LINE_HEIGHT};letter-spacing:{LETTER_SPACING};">{first}</p>
<p style="margin:{TEXT_BLOCK_MARGIN};white-space:normal;padding:0;box-sizing:border-box;font-size:{BODY_FONT_SIZE};line-height:{BODY_LINE_HEIGHT};letter-spacing:{LETTER_SPACING};"><strong style="box-sizing:border-box;">建议补一张论文方法图或实验结果图。</strong></p>
</section></section>
[[IMAGE:论文核心方法或主要实验结果截图]]
{info_block}
[[IMAGE:论文开头部分截图]]
{question_block}
{tail}
</section>""")
