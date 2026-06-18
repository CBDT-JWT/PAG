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


def theme_value(theme, section, key, default):
    return ((theme or {}).get(section) or {}).get(key, default)


def body_style(theme):
    font_size = theme_value(theme, "render", "body_font_size", 14)
    line_height = theme_value(theme, "render", "line_height", 26)
    align = theme_value(theme, "render", "body_align", "justify")
    text_color = theme_value(theme, "colors", "text", "#2a2f36")
    return {
        "font_size": f"{font_size}px",
        "line_height": f"{line_height}px",
        "align": align,
        "text_color": text_color,
    }


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


def render_inline_markdown(text, theme=None, formula_renderer=None, allow_bold=True):
    text = text or ""
    parts = []
    last = 0
    pattern = re.compile(r"\*\*(.+?)\*\*", flags=re.S)
    bold_color = theme_value(theme, "colors", "bold", "#4375b9")

    for match in pattern.finditer(text):
        parts.append(f"<span>{escape_plain_text(text[last:match.start()])}</span>")
        bold_text = match.group(1)
        if allow_bold and bold_text is not None:
            parts.append(
                f'<strong style="color:{bold_color};box-sizing:border-box;">'
                f"{render_inline_markdown(bold_text, theme=theme, formula_renderer=formula_renderer, allow_bold=False)}"
                "</strong>"
            )
        else:
            parts.append(f"<span>{escape_html_text(match.group(0))}</span>")
        last = match.end()

    parts.append(f"<span>{escape_plain_text(text[last:])}</span>")
    return "".join(part for part in parts if part != "<span></span>")


def paragraph_html(text, theme=None, formula_renderer=None):
    styles = body_style(theme)
    return (
        f'<p style="margin:{TEXT_BLOCK_MARGIN};white-space:normal;padding:0;box-sizing:border-box;font-size:{styles["font_size"]};line-height:{styles["line_height"]};letter-spacing:{LETTER_SPACING};text-align:{styles["align"]};color:{styles["text_color"]};">'
        f"{render_inline_markdown(text, theme=theme, formula_renderer=formula_renderer)}"
        "</p>"
    )


def heading_html(text, theme=None):
    font_size = theme_value(theme, "render", "heading_font_size", 16)
    line_height = theme_value(theme, "render", "line_height", 26)
    align = theme_value(theme, "render", "heading_align", "center")
    style = theme_value(theme, "render", "heading_style", "card")
    heading_text = theme_value(theme, "colors", "heading_text", "#2d6cdf")
    heading_bg = theme_value(theme, "colors", "heading_bg", "#edf3ff")
    left_line = theme_value(theme, "colors", "left_line", "#2d6cdf")
    shadow = "box-shadow:0 6px 18px rgba(0,0,0,.06);" if theme_value(theme, "render", "show_heading_shadow", False) else ""
    escaped = escape_html_text(text)
    common = f'font-size:{font_size}px;line-height:{line_height}px;letter-spacing:{LETTER_SPACING};'
    if style == "left-line":
        return (
            f'<section data-markdown-heading="2" style="margin:{TEXT_BLOCK_MARGIN};padding:0;box-sizing:border-box;">'
            f'<p style="margin:0;padding:0 0 0 12px;border-left:4px solid {left_line};text-align:{align};{common}color:{heading_text};box-sizing:border-box;">'
            f'<strong style="color:{heading_text};box-sizing:border-box;">{escaped}</strong></p></section>'
        )
    if style == "plain":
        return (
            f'<p data-markdown-heading="2" style="text-align:{align};margin:{TEXT_BLOCK_MARGIN};white-space:normal;padding:0;box-sizing:border-box;{common}">'
            f'<strong style="color:{heading_text};box-sizing:border-box;">{escaped}</strong></p>'
        )
    return (
        f'<section data-markdown-heading="2" style="margin:{TEXT_BLOCK_MARGIN};padding:0;box-sizing:border-box;">'
        f'<p style="margin:0;padding:8px 14px;border-radius:12px;background:{heading_bg};text-align:{align};{common}{shadow}box-sizing:border-box;">'
        f'<strong style="color:{heading_text};box-sizing:border-box;">{escaped}</strong></p></section>'
    )


def paper_info_section(metadata, theme=None):
    items_data = [
        ("论文标题", metadata.get("paper_title") or "", True),
        ("项目地址", metadata.get("project_url") or "", False),
        ("论文地址", metadata.get("paper_url") or "", False),
    ]
    font_size = theme_value(theme, "render", "body_font_size", 14)
    line_height = theme_value(theme, "render", "line_height", 26)
    secondary = theme_value(theme, "colors", "secondary", "#9d584d")
    paper_info_style = theme_value(theme, "render", "paper_info_style", "card")
    paper_info_bg = theme_value(theme, "colors", "paper_info_bg", "#f7f3eb")

    def li(label, value, text_align=False):
        align = "text-align: left;" if text_align else ""
        return (
            '<li style="box-sizing: border-box;">'
            f'<p style="{align}margin:0 {BODY_HORIZONTAL_PADDING};padding:0;box-sizing:border-box;font-size:{font_size}px;line-height:{line_height}px;letter-spacing:{LETTER_SPACING};">'
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
    wrapper_style = (
        f"font-size:{font_size}px;line-height:{line_height}px;padding:12px 10px;color:{secondary};"
        f"background:{paper_info_bg};border-radius:12px;box-sizing:border-box;"
        if paper_info_style == "card"
        else f"font-size:{font_size}px;line-height:{line_height}px;padding:0;color:{secondary};box-sizing:border-box;"
    )
    return (
        '<section data-markdown-token="[[PAPER_INFO]]" contenteditable="false" style="margin:20px 0 0;box-sizing:border-box;">'
        f'<section style="{wrapper_style}">'
        '<ul style="list-style-type:disc;box-sizing:border-box;padding-left:20px;list-style-position:outside;">'
        f"{items}"
        "</ul>"
        "</section>"
        "</section>"
    )


def reader_question_section(question, theme=None, formula_renderer=None):
    question = (question or "").strip()
    if not question:
        return ""
    body = body_style(theme)
    secondary = theme_value(theme, "colors", "secondary", "#9d584d")
    paper_info_bg = theme_value(theme, "colors", "paper_info_bg", "#f7f3eb")
    return (
        '<section data-generated-question="true" contenteditable="false" style="margin:28px 10px 0 10px;padding:16px 14px;border-radius:12px;'
        f'background:{paper_info_bg};box-sizing:border-box;">'
        f'<p style="margin:0 0 8px 0;padding:0;box-sizing:border-box;font-size:13px;line-height:22px;'
        f'letter-spacing:0.3px;color:{secondary};"><strong style="box-sizing:border-box;">留给读者的问题</strong></p>'
        f'<p style="margin:0;padding:0;box-sizing:border-box;font-size:{body["font_size"]};line-height:{body["line_height"]};'
        f'letter-spacing:{LETTER_SPACING};color:{body["text_color"]};text-align:{body["align"]};">{render_inline_markdown(question, theme=theme, formula_renderer=formula_renderer)}</p>'
        "</section>"
    )


def markdown_to_wechat_html(markdown_text, metadata, head_url="", tail_url="", theme=None, formula_renderer=None):
    markdown_text = markdown_text or ""
    blocks = []
    paragraph_buffer = []
    lines = markdown_text.splitlines()
    body_conf = body_style(theme)
    surface = theme_value(theme, "colors", "surface", "#ffffff")

    def flush_paragraph():
        nonlocal paragraph_buffer
        if paragraph_buffer:
            text = " ".join(x.strip() for x in paragraph_buffer if x.strip())
            if text:
                blocks.append(paragraph_html(text, theme=theme, formula_renderer=formula_renderer))
            paragraph_buffer = []

    index = 0
    while index < len(lines):
        raw_line = lines[index]
        line = raw_line.strip()

        if not line:
            flush_paragraph()
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
            info_section = paper_info_section(metadata, theme=theme)
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
                f'<p style="margin:{TEXT_BLOCK_MARGIN};white-space:normal;padding:0;box-sizing:border-box;font-size:{body_conf["font_size"]};line-height:{body_conf["line_height"]};letter-spacing:{LETTER_SPACING};text-align:{body_conf["align"]};color:{body_conf["text_color"]};">'
                '<span>• </span>'
                f"{render_inline_markdown(item_text, theme=theme, formula_renderer=formula_renderer)}"
                "</p>"
            )
            index += 1
            continue
        if line.startswith("## "):
            flush_paragraph()
            blocks.append(heading_html(line[3:].strip(), theme=theme))
            index += 1
            continue
        if line.startswith("# "):
            flush_paragraph()
            index += 1
            continue

        paragraph_buffer.append(line)
        index += 1

    flush_paragraph()
    question_section = reader_question_section(metadata.get("reader_question", ""), theme=theme, formula_renderer=formula_renderer)
    if question_section:
        blocks.append(question_section)
    body_html = (
        '<section style="margin:20px 0 0;box-sizing:border-box;">'
        f'<section style="font-size:{body_conf["font_size"]};line-height:{body_conf["line_height"]};padding:0;box-sizing:border-box;">'
        + "\n".join(blocks)
        + "</section>"
        "</section>"
    )
    return ensure_wrapper(
        f'<section style="box-sizing:border-box;font-style:normal;font-weight:400;text-align:{body_conf["align"]};font-size:{body_conf["font_size"]};line-height:{body_conf["line_height"]};letter-spacing:{LETTER_SPACING};color:{body_conf["text_color"]};background:{surface};">'
        + body_html
        + "</section>"
    )


def ensure_wrapper(article_html):
    if "rich_media_content" in article_html:
        return article_html
    return f'<div class="rich_media_content js_underline_content defaultNoSetting" id="js_content">{article_html}</div>'


def fallback_article(metadata, paper_text, head_url, tail_url, theme=None):
    title = html.escape(metadata.get("paper_title") or "论文信息待补充")
    first = html.escape((paper_text.strip().splitlines() or [title])[0][:220])
    tail = image_section(tail_url) if tail_url else ""
    body = body_style(theme)
    secondary = theme_value(theme, "colors", "secondary", "#9d584d")
    paper_info_bg = theme_value(theme, "colors", "paper_info_bg", "#f7f3eb")
    surface = theme_value(theme, "colors", "surface", "#ffffff")
    info_items = []
    if metadata.get("paper_title"):
        info_items.append(
            f'<li><p style="margin:0 {BODY_HORIZONTAL_PADDING};padding:0;box-sizing:border-box;font-size:{body["font_size"]};line-height:{body["line_height"]};letter-spacing:{LETTER_SPACING};"><strong>论文标题</strong><br>{html.escape(metadata.get("paper_title") or "")}</p></li>'
        )
    if metadata.get("project_url"):
        info_items.append(
            f'<li><p style="margin:0 {BODY_HORIZONTAL_PADDING};padding:0;box-sizing:border-box;font-size:{body["font_size"]};line-height:{body["line_height"]};letter-spacing:{LETTER_SPACING};"><strong>项目地址</strong><br>{html.escape(metadata.get("project_url") or "")}</p></li>'
        )
    if metadata.get("paper_url"):
        info_items.append(
            f'<li><p style="margin:0 {BODY_HORIZONTAL_PADDING};padding:0;box-sizing:border-box;font-size:{body["font_size"]};line-height:{body["line_height"]};letter-spacing:{LETTER_SPACING};"><strong>论文地址</strong><br>{html.escape(metadata.get("paper_url") or "")}</p></li>'
        )
    info_block = ""
    if info_items:
        info_block = (
            f'<section style="margin:20px 0 0;box-sizing:border-box;"><section style="font-size:{body["font_size"]};line-height:{body["line_height"]};padding:12px 10px;color:{secondary};background:{paper_info_bg};border-radius:12px;box-sizing:border-box;"><ul style="list-style-type:disc;box-sizing:border-box;padding-left:20px;list-style-position:outside;">'
            + "".join(info_items)
            + "</ul></section></section>"
        )
    question_block = reader_question_section(metadata.get("reader_question", ""), theme=theme)
    return ensure_wrapper(f"""
<section style="box-sizing:border-box;font-style:normal;font-weight:400;text-align:{body["align"]};font-size:{body["font_size"]};line-height:{body["line_height"]};letter-spacing:{LETTER_SPACING};color:{body["text_color"]};background:{surface};">
{image_section(head_url)}
<section style="margin:20px 0 0;box-sizing:border-box;"><section style="font-size:{body["font_size"]};line-height:{body["line_height"]};padding:0;box-sizing:border-box;">
<p style="margin:{TEXT_BLOCK_MARGIN};white-space:normal;padding:0;box-sizing:border-box;font-size:{body["font_size"]};line-height:{body["line_height"]};letter-spacing:{LETTER_SPACING};"><strong style="box-sizing:border-box;">{title}</strong></p>
<p style="margin:{TEXT_BLOCK_MARGIN};white-space:normal;padding:0;box-sizing:border-box;font-size:{body["font_size"]};line-height:{body["line_height"]};letter-spacing:{LETTER_SPACING};">{first}</p>
<p style="margin:{TEXT_BLOCK_MARGIN};white-space:normal;padding:0;box-sizing:border-box;font-size:{body["font_size"]};line-height:{body["line_height"]};letter-spacing:{LETTER_SPACING};"><strong style="box-sizing:border-box;">建议补一张论文方法图或实验结果图。</strong></p>
</section></section>
[[IMAGE:论文核心方法或主要实验结果截图]]
{info_block}
[[IMAGE:论文开头部分截图]]
{question_block}
{tail}
</section>""")
