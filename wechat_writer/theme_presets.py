import json
import time
import uuid
from copy import deepcopy
from pathlib import Path

from .agent import DEFAULT_ARTICLE_STYLE_PROMPT, TITLE_QUESTION_PROMPT
from .config import (
    ASSETS_DIR,
    PRESET_ASSETS_DIR,
    PRESETS_DIR,
    PRESETS_EXAMPLE_FILE,
    PRESETS_FILE,
    PRESETS_LEGACY_FILE,
)
from .files import public_url, safe_name


DEFAULT_PRESET_ID = "default-journal"


def default_theme_preset():
    head_url = ensure_default_preset_head()
    return {
        "id": DEFAULT_PRESET_ID,
        "name": "默认科技蓝",
        "article_style_prompt": DEFAULT_ARTICLE_STYLE_PROMPT.strip(),
        "title_question_prompt": TITLE_QUESTION_PROMPT.strip(),
        "colors": {
            "primary": "#2d6cdf",
            "secondary": "#8b6b4a",
            "text": "#2a2f36",
            "muted": "#6b7280",
            "surface": "#ffffff",
            "paper_info_bg": "#f7f3eb",
            "heading_bg": "#edf3ff",
            "heading_text": "#2d6cdf",
            "bold": "#2d6cdf",
            "left_line": "#2d6cdf",
        },
        "images": {
            "head_url": head_url,
            "tail_url": "",
        },
        "render": {
            "body_align": "justify",
            "body_font_size": 14,
            "heading_align": "center",
            "heading_font_size": 16,
            "heading_style": "card",
            "paper_info_style": "card",
            "show_heading_shadow": False,
            "line_height": 26,
        },
        "updated_at": int(time.time()),
    }


def preview_markdown():
    return """[[HEAD_IMAGE]]

写公众号文章时，版式并不只是“把字摆上去”。

一套稳定的**主题预设**，会决定这篇内容看起来更像实验记录、像研究笔记，还是像成熟的科技媒体解读。

[[PAPER_INFO]]

预设不仅影响颜色，也会影响标题的节奏、强调信息的方式，以及读者第一眼看到内容时的心理预期。

## 标题样式会改变阅读节奏

如果标题更像卡片，读者会更容易把每一节当成一个明确段落来吸收。

如果标题是左侧竖线或纯文字，整篇文章会更克制，也更像连续叙事。

[[IMAGE:示例配图 Figure 3 系统结构图]]

## 粗体与配色决定重点是否被看见

同一句话里，**重点术语**、**模型名称**、**实验结论** 的强调方式不同，读者的视线落点也会不同。

当一套风格能稳定地处理标题、正文、信息卡片与文首文末图片时，文章的完成度会明显上一个层级。

[[TAIL_IMAGE]]"""


def preview_metadata():
    return {
        "paper_title": "PreviewMA: Theme Presets for WeChat Articles",
        "project_url": "https://example.com/project",
        "paper_url": "https://arxiv.org/abs/2501.01234",
        "article_title": "一套主题预设，能把论文解读的完成度拉开多大差距？",
        "reader_question": "如果你经常发布技术内容，你会更偏好强风格主题，还是尽量让样式退到内容背后？",
        "article_titles": [
            "一套主题预设，能把论文解读的完成度拉开多大差距？",
            "同一篇论文，为什么换个版式就像换了个编辑？",
            "当标题、卡片和配图都统一以后，技术文章会更好读吗？",
        ],
    }


def ensure_preset_store():
    PRESETS_DIR.mkdir(parents=True, exist_ok=True)
    PRESET_ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    ensure_default_preset_head()
    if not PRESETS_FILE.exists():
        if PRESETS_LEGACY_FILE.exists():
            PRESETS_FILE.write_text(PRESETS_LEGACY_FILE.read_text(encoding="utf-8"), encoding="utf-8")
        elif PRESETS_EXAMPLE_FILE.exists():
            PRESETS_FILE.write_text(PRESETS_EXAMPLE_FILE.read_text(encoding="utf-8"), encoding="utf-8")
        else:
            PRESETS_FILE.write_text(
                json.dumps({"presets": [default_theme_preset()]}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )


def ensure_default_preset_head():
    source = ASSETS_DIR / "head-banner.png"
    if not source.exists():
        return ""
    target = PRESET_ASSETS_DIR / "default-head-banner.png"
    if not target.exists():
        target.write_bytes(source.read_bytes())
    return public_url(target)


def load_presets():
    ensure_preset_store()
    try:
        payload = json.loads(PRESETS_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        payload = {"presets": [default_theme_preset()]}
    presets = payload.get("presets") or []
    if not presets:
        presets = [default_theme_preset()]
    return [normalize_preset(preset) for preset in presets]


def save_presets(presets):
    ensure_preset_store()
    PRESETS_FILE.write_text(json.dumps({"presets": presets}, ensure_ascii=False, indent=2), encoding="utf-8")


def normalize_preset(preset):
    preset = preset or {}
    merged = deepcopy(default_theme_preset())
    merged.update({k: v for k, v in preset.items() if k not in {"colors", "images", "render"}})
    for section in ("colors", "images", "render"):
        merged[section].update(preset.get(section) or {})
    if "article_style_prompt" in preset:
        merged["article_style_prompt"] = (preset.get("article_style_prompt") or "").strip()
    elif not merged.get("article_style_prompt"):
        merged["article_style_prompt"] = DEFAULT_ARTICLE_STYLE_PROMPT.strip()
    if "title_question_prompt" in preset:
        merged["title_question_prompt"] = (preset.get("title_question_prompt") or "").strip()
    elif not merged.get("title_question_prompt"):
        merged["title_question_prompt"] = TITLE_QUESTION_PROMPT.strip()
    if not merged.get("id"):
        merged["id"] = "preset-" + uuid.uuid4().hex[:8]
    return merged


def get_preset(preset_id):
    presets = load_presets()
    for preset in presets:
        if preset["id"] == preset_id:
            return preset
    return presets[0]


def upsert_preset(data):
    presets = load_presets()
    incoming = normalize_preset(data)
    incoming["updated_at"] = int(time.time())
    for index, preset in enumerate(presets):
        if preset["id"] == incoming["id"]:
            presets[index] = incoming
            save_presets(presets)
            return incoming
    presets.append(incoming)
    save_presets(presets)
    return incoming


def create_empty_preset():
    preset = default_theme_preset()
    preset["id"] = "preset-" + uuid.uuid4().hex[:8]
    preset["name"] = "新预设"
    preset["images"]["tail_url"] = ""
    return preset


def save_preset_asset(file_storage, prefix):
    ensure_preset_store()
    suffix = Path(file_storage.filename or "").suffix.lower() or ".bin"
    filename = f"{prefix}-{int(time.time())}-{uuid.uuid4().hex[:6]}{suffix}"
    target = PRESET_ASSETS_DIR / safe_name(filename)
    target.write_bytes(file_storage.read())
    return public_url(target)
