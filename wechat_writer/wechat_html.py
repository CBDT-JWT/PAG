import html
import re


BODY_FONT_SIZE = "14px"
BODY_LINE_HEIGHT = "12px"
PARAGRAPH_MARGIN_BOTTOM = "12px"
SECTION_TITLE_FONT_SIZE = "16px"
BODY_HORIZONTAL_PADDING = "10px"
IMAGE_WIDTH = "90%"


def image_section(url):
    return (
        f'<section style="text-align:center;margin-top:{PARAGRAPH_MARGIN_BOTTOM};margin-bottom:{PARAGRAPH_MARGIN_BOTTOM};line-height:0;box-sizing:border-box;">'
        f'<section style="max-width:100%;vertical-align:middle;display:inline-block;line-height:0;width:{IMAGE_WIDTH};height:auto;box-sizing:border-box;">'
        '<img data-src="{0}" src="{0}" style="vertical-align:middle;max-width:100%;width:100%;box-sizing:border-box;" width="100%">'
        "</section></section>"
    ).format(url)


def escape_html_text(text):
    return html.escape(text or "", quote=False)


def render_inline_markdown(text):
    text = escape_html_text(text)
    parts = []
    last = 0

    for match in re.finditer(r"\*\*(.+?)\*\*", text, flags=re.S):
        parts.append(f"<span>{text[last:match.start()]}</span>")
        bold_text = match.group(1)
        parts.append(
            '<strong style="color:rgb(67, 117, 185);box-sizing: border-box;">'
            f"<span>{bold_text}</span>"
            "</strong>"
        )
        last = match.end()

    parts.append(f"<span>{text[last:]}</span>")
    return "".join(part for part in parts if part != "<span></span>")


def paragraph_html(text):
    return (
        f'<p style="margin:0 0 {PARAGRAPH_MARGIN_BOTTOM};white-space:normal;padding:0;box-sizing:border-box;font-size:{BODY_FONT_SIZE};line-height:{BODY_LINE_HEIGHT};">'
        f"{render_inline_markdown(text)}"
        "</p>"
    )


def heading_html(text):
    return (
        f'<p style="text-align:center;margin:0 0 {PARAGRAPH_MARGIN_BOTTOM};white-space:normal;padding:0;box-sizing:border-box;font-size:{SECTION_TITLE_FONT_SIZE};line-height:{BODY_LINE_HEIGHT};">'
        '<strong style="color:rgb(62,62,62);box-sizing: border-box;">'
        f'<span><span style="font-size:{SECTION_TITLE_FONT_SIZE};">{escape_html_text(text)}</span></span>'
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
            f'<p style="{align}margin:0;padding:0;box-sizing:border-box;font-size:{BODY_FONT_SIZE};line-height:{BODY_LINE_HEIGHT};">'
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
        f'<section style="font-size:{BODY_FONT_SIZE};line-height:{BODY_LINE_HEIGHT};padding:0;color:rgb(157,88,77);box-sizing:border-box;">'
        '<ul style="list-style-type:disc;box-sizing:border-box;padding-left:20px;list-style-position:outside;">'
        f"{items}"
        "</ul>"
        "</section>"
        "</section>"
    )


def markdown_to_wechat_html(markdown_text, metadata, head_url="", tail_url=""):
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

    for raw_line in markdown_text.splitlines():
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
            blocks.append("[[IMAGE:论文开头部分截图]]")
            continue

        image_match = re.fullmatch(r"\[\[IMAGE:(.+?)\]\]", line)
        if image_match:
            flush_paragraph()
            desc = escape_html_text(image_match.group(1).strip())
            blocks.append(f"[[IMAGE:{desc}]]")
            continue
        if line.startswith("- "):
            flush_paragraph()
            item_text = line[2:].strip()
            blocks.append(
                f'<p style="margin:0 0 {PARAGRAPH_MARGIN_BOTTOM};white-space:normal;padding:0;box-sizing:border-box;font-size:{BODY_FONT_SIZE};line-height:{BODY_LINE_HEIGHT};">'
                '<span>• </span>'
                f"{render_inline_markdown(item_text)}"
                "</p>"
            )
            continue
        if line.startswith("## "):
            flush_paragraph()
            blocks.append(heading_html(line[3:].strip()))
            continue
        if line.startswith("# "):
            flush_paragraph()
            continue

        paragraph_buffer.append(line)

    flush_paragraph()
    body = (
        '<section style="margin:20px 0 0;box-sizing:border-box;">'
        f'<section style="font-size:{BODY_FONT_SIZE};line-height:{BODY_LINE_HEIGHT};padding:0;box-sizing:border-box;">'
        + "\n".join(blocks)
        + "</section>"
        "</section>"
    )
    return ensure_wrapper(
        f'<section style="box-sizing:border-box;font-style:normal;font-weight:400;text-align:justify;font-size:{BODY_FONT_SIZE};line-height:{BODY_LINE_HEIGHT};padding-left:{BODY_HORIZONTAL_PADDING};padding-right:{BODY_HORIZONTAL_PADDING};color:rgb(62,62,62);">'
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
<section style="box-sizing:border-box;font-style:normal;font-weight:400;text-align:justify;font-size:{BODY_FONT_SIZE};line-height:{BODY_LINE_HEIGHT};padding-left:{BODY_HORIZONTAL_PADDING};padding-right:{BODY_HORIZONTAL_PADDING};color:rgb(62,62,62);">
{image_section(head_url)}
<section style="margin:20px 0 0;box-sizing:border-box;"><section style="font-size:{BODY_FONT_SIZE};line-height:{BODY_LINE_HEIGHT};padding:0;box-sizing:border-box;">
<p style="margin:0 0 {PARAGRAPH_MARGIN_BOTTOM};white-space:normal;padding:0;box-sizing:border-box;font-size:{BODY_FONT_SIZE};line-height:{BODY_LINE_HEIGHT};"><strong style="color:rgb(67, 117, 185);box-sizing:border-box;">{title}</strong></p>
<p style="margin:0 0 {PARAGRAPH_MARGIN_BOTTOM};white-space:normal;padding:0;box-sizing:border-box;font-size:{BODY_FONT_SIZE};line-height:{BODY_LINE_HEIGHT};">{first}</p>
<p style="margin:0 0 {PARAGRAPH_MARGIN_BOTTOM};white-space:normal;padding:0;box-sizing:border-box;font-size:{BODY_FONT_SIZE};line-height:{BODY_LINE_HEIGHT};"><span style="color:rgb(67, 117, 185);box-sizing:border-box;"><strong>建议补一张论文方法图或实验结果图。</strong></span></p>
</section></section>
[[IMAGE:论文核心方法或主要实验结果截图]]
<section style="margin:20px 0 0;box-sizing:border-box;"><section style="font-size:{BODY_FONT_SIZE};line-height:{BODY_LINE_HEIGHT};padding:0;color:rgb(157,88,77);box-sizing:border-box;"><ul style="list-style-type:disc;box-sizing:border-box;padding-left:20px;list-style-position:outside;">
<li><p style="margin:0;padding:0;box-sizing:border-box;font-size:{BODY_FONT_SIZE};line-height:{BODY_LINE_HEIGHT};"><strong>论文标题</strong><br>{title}</p></li>
<li><p style="margin:0;padding:0;box-sizing:border-box;font-size:{BODY_FONT_SIZE};line-height:{BODY_LINE_HEIGHT};"><strong>项目地址</strong><br>{html.escape(metadata.get("project_url") or "未找到")}</p></li>
<li><p style="margin:0;padding:0;box-sizing:border-box;font-size:{BODY_FONT_SIZE};line-height:{BODY_LINE_HEIGHT};"><strong>论文地址</strong><br>{html.escape(metadata.get("paper_url") or "未找到")}</p></li>
</ul></section></section>
[[IMAGE:论文开头部分截图]]
{tail}
</section>""")
