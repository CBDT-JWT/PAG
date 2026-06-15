import hashlib
import html
import re
from pathlib import Path

from .files import public_url


class FormulaRenderer:
    def __init__(self, output_dir):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._matplotlib = None
        self._plt = None

    def render_inline(self, formula):
        return self._render(formula, display=False)

    def render_block(self, formula):
        return self._render(formula, display=True)

    def _render(self, formula, display=False):
        formula = (formula or "").strip()
        if not formula:
            return ""
        prepared = self._normalize_for_mathtext(formula)
        try:
            plt = self._load_pyplot()
        except Exception:
            return self._fallback(formula, display=display)

        digest = hashlib.sha1(f"{display}:{formula}".encode("utf-8")).hexdigest()[:16]
        path = self.output_dir / f"formula-{digest}.png"
        if not path.exists():
            try:
                dpi = 220 if display else 200
                fontsize = 17 if display else 15
                figure = plt.figure(figsize=(0.01, 0.01), dpi=dpi)
                figure.patch.set_alpha(0)
                text = figure.text(
                    0,
                    0,
                    f"${prepared}$" if not display else f"$\\displaystyle {prepared}$",
                    fontsize=fontsize,
                    color="#1f2933",
                )
                figure.canvas.draw()
                bbox = text.get_window_extent(renderer=figure.canvas.get_renderer()).expanded(1.08, 1.22)
                width = max(0.01, bbox.width / dpi)
                height = max(0.01, bbox.height / dpi)
                figure.set_size_inches(width, height)
                text.set_position((0, 0))
                figure.savefig(
                    path,
                    dpi=dpi,
                    transparent=True,
                    bbox_inches="tight",
                    pad_inches=0.03 if display else 0.01,
                )
                plt.close(figure)
            except Exception:
                try:
                    plt.close(figure)
                except Exception:
                    pass
                return self._fallback(formula, display=display)

        url = public_url(path)
        escaped = html.escape(formula)
        if display:
            return (
                '<section data-formula-block="true" contenteditable="false" '
                f'data-formula-source="{escaped}" '
                'style="margin:18px 10px;text-align:center;box-sizing:border-box;">'
                f'<img src="{url}" data-src="{url}" alt="{escaped}" '
                'style="display:inline-block;max-width:100%;height:auto;vertical-align:middle;" />'
                "</section>"
            )
        return (
            f'<img src="{url}" data-src="{url}" alt="{escaped}" data-formula-inline="true" data-formula-source="{escaped}" '
            'style="display:inline-block;vertical-align:-0.28em;max-height:1.7em;" />'
        )

    def _load_pyplot(self):
        if self._plt is not None:
            return self._plt
        import matplotlib

        matplotlib.use("Agg")
        from matplotlib import pyplot as plt

        self._matplotlib = matplotlib
        self._plt = plt
        return plt

    def _fallback(self, formula, display=False):
        escaped = html.escape(formula)
        if display:
            return (
                '<section data-formula-block="true" contenteditable="false" '
                f'data-formula-source="{escaped}" '
                'style="margin:18px 10px;padding:10px 12px;border-radius:10px;background:#f8fafc;'
                'font-family:Menlo, Monaco, Consolas, monospace;font-size:14px;line-height:24px;'
                'text-align:center;box-sizing:border-box;">'
                f"{escaped}"
                "</section>"
            )
        return (
            f'<code data-formula-source="{escaped}" style="padding:0 4px;border-radius:4px;background:#f8fafc;'
            'font-family:Menlo, Monaco, Consolas, monospace;font-size:0.95em;">'
            f"{escaped}"
            "</code>"
        )

    def _normalize_for_mathtext(self, formula):
        normalized = formula
        normalized = self._replace_text_like_command(normalized, "text", "mathrm")
        normalized = self._replace_text_like_command(normalized, "operatorname", "mathrm")
        normalized = re.sub(r"\\bm\s*\{", r"\\mathbf{", normalized)
        normalized = re.sub(r"\\boldsymbol\s*\{", r"\\mathbf{", normalized)
        return normalized

    def _replace_text_like_command(self, formula, source_command, target_command):
        marker = f"\\{source_command}"
        index = 0
        parts = []
        while True:
            start = formula.find(marker, index)
            if start < 0:
                parts.append(formula[index:])
                break
            parts.append(formula[index:start])
            brace_start = start + len(marker)
            while brace_start < len(formula) and formula[brace_start].isspace():
                brace_start += 1
            if brace_start >= len(formula) or formula[brace_start] != "{":
                parts.append(marker)
                index = start + len(marker)
                continue
            content, brace_end = self._read_braced(formula, brace_start)
            if brace_end < 0:
                parts.append(formula[start:])
                break
            converted = self._normalize_text_content(content)
            parts.append(f"\\{target_command}{{{converted}}}")
            index = brace_end + 1
        return "".join(parts)

    def _read_braced(self, text, brace_start):
        depth = 0
        content = []
        for index in range(brace_start, len(text)):
            char = text[index]
            if char == "{":
                depth += 1
                if depth > 1:
                    content.append(char)
            elif char == "}":
                depth -= 1
                if depth == 0:
                    return "".join(content), index
                content.append(char)
            else:
                content.append(char)
        return "", -1

    def _normalize_text_content(self, text):
        text = text.strip()
        text = re.sub(r"\s+", r"\\ ", text)
        return text
