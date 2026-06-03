#!/usr/bin/env python3
import argparse
from pathlib import Path

from wechat_writer.routes import MAX_SCREENSHOT_BYTES, compress_screenshot


IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}


def compress_run(run_dir):
    article_path = run_dir / "article.html"
    article_html = article_path.read_text(encoding="utf-8") if article_path.exists() else ""
    changed_article = False
    changed_images = 0

    for image_path in sorted(run_dir.glob("screenshot-*")):
        if image_path.suffix.lower() not in IMAGE_SUFFIXES:
            continue

        compressed = compress_screenshot(image_path.read_bytes())
        target = image_path.with_suffix(".jpg")
        target.write_bytes(compressed)
        changed_images += 1

        if image_path != target and article_html:
            article_html = article_html.replace(image_path.name, target.name)
            changed_article = True

        if image_path != target:
            image_path.unlink()

        size = len(compressed)
        status = "ok" if size <= MAX_SCREENSHOT_BYTES else "large"
        print(f"{status}\t{size}\t{target}")

    if changed_article:
        article_path.write_text(article_html, encoding="utf-8")

    return changed_images


def iter_run_dirs(path):
    if (path / "article.html").exists():
        yield path
        return
    for child in sorted(path.iterdir()):
        if child.is_dir() and (child / "article.html").exists():
            yield child


def main():
    parser = argparse.ArgumentParser(description="Compress saved screenshot images to JPG files around 250KB.")
    parser.add_argument("path", nargs="?", default="public/runs", help="A run directory or public/runs directory.")
    args = parser.parse_args()

    root = Path(args.path)
    total = 0
    for run_dir in iter_run_dirs(root):
        total += compress_run(run_dir)
    print(f"compressed {total} screenshot files")


if __name__ == "__main__":
    main()
