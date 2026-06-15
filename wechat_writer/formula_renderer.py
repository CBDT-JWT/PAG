import hashlib
import html
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
        try:
            plt = self._load_pyplot()
        except Exception:
            return self._fallback(formula, display=display)

        digest = hashlib.sha1(f"{display}:{formula}".encode("utf-8")).hexdigest()[:16]
        path = self.output_dir / f"formula-{digest}.png"
        if not path.exists():
            dpi = 220 if display else 200
            fontsize = 17 if display else 15
            figure = plt.figure(figsize=(0.01, 0.01), dpi=dpi)
            figure.patch.set_alpha(0)
            text = figure.text(
                0,
                0,
                f"${formula}$" if not display else f"$\\displaystyle {formula}$",
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
