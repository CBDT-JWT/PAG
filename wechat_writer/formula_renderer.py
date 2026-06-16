import hashlib
import html
from pathlib import Path
from xml.etree import ElementTree

from .files import public_url


class FormulaRenderer:
    def __init__(self, output_dir):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._zm = None

    def render_inline(self, formula):
        return self._render(formula, display=False)

    def render_block(self, formula):
        return self._render(formula, display=True)

    def _render(self, formula, display=False):
        formula = (formula or "").strip()
        if not formula:
            return ""

        digest = hashlib.sha1(f"{display}:{formula}".encode("utf-8")).hexdigest()[:16]
        svg_path = self.output_dir / f"formula-{digest}.svg"
        if not svg_path.exists():
            if not self._render_with_ziamath(formula, display=display, output_path=svg_path):
                return self._fallback(formula, display=display)

        return self._html_for_svg(svg_path, formula, display=display)

    def _render_with_ziamath(self, formula, display, output_path):
        try:
            zm = self._load_ziamath()
            math = zm.Latex(formula, inline=not display)
            svg_text = math.svg()
            output_path.write_text(self._normalize_svg(svg_text), encoding="utf-8")
            return True
        except Exception:
            return False

    def _load_ziamath(self):
        if self._zm is not None:
            return self._zm
        import ziamath as zm

        self._zm = zm
        return zm

    def _html_for_svg(self, svg_path, formula, display):
        url = public_url(svg_path)
        escaped = html.escape(formula)
        if display:
            return (
                '<section data-formula-block="true" contenteditable="false" '
                f'data-formula-source="{escaped}" '
                'style="margin:20px 10px;text-align:center;box-sizing:border-box;">'
                f'<img src="{url}" data-src="{url}" alt="{escaped}" '
                'style="display:inline-block;max-width:100%;height:auto;vertical-align:middle;" />'
                "</section>"
            )
        return (
            f'<img src="{url}" data-src="{url}" alt="{escaped}" data-formula-inline="true" data-formula-source="{escaped}" '
            'style="display:inline-block;vertical-align:-0.34em;height:1.55em;max-width:100%;" />'
        )

    def _normalize_svg(self, svg_text):
        root = ElementTree.fromstring(svg_text)
        if not root.tag.endswith("svg"):
            return svg_text

        root.attrib.pop("style", None)
        root.set("xmlns", "http://www.w3.org/2000/svg")
        root.set("preserveAspectRatio", "xMidYMid meet")

        for element in root.iter():
            style = element.attrib.pop("style", "")
            if style:
                style_map = self._parse_style(style)
                fill = style_map.get("fill")
                if fill and fill.lower() not in {"none", "transparent"}:
                    element.set("fill", fill)
            if element.tag.endswith("path") and "fill" not in element.attrib:
                element.set("fill", "#1f2933")

        return ElementTree.tostring(root, encoding="unicode")

    def _parse_style(self, style_text):
        mapping = {}
        for part in [item.strip() for item in style_text.split(";") if item.strip()]:
            if ":" not in part:
                continue
            key, value = part.split(":", 1)
            mapping[key.strip()] = value.strip()
        return mapping

    def _fallback(self, formula, display=False):
        escaped = html.escape(formula)
        if display:
            return (
                '<section data-formula-block="true" contenteditable="false" '
                f'data-formula-source="{escaped}" '
                'style="margin:20px 10px;text-align:center;box-sizing:border-box;">'
                f'<p style="display:inline-block;margin:0;padding:10px 14px;border-radius:12px;background:#f8fafc;'
                'font-family:STIX Two Math, Cambria Math, Times New Roman, serif;font-size:18px;line-height:1.5;color:#1f2933;">'
                f"{escaped}</p>"
                "</section>"
            )
        return (
            f'<code data-formula-source="{escaped}" style="padding:0 4px;border-radius:4px;background:#f8fafc;'
            'font-family:STIX Two Math, Cambria Math, Times New Roman, serif;font-size:0.95em;">'
            f"{escaped}</code>"
        )
