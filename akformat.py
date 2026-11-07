#!/usr/bin/env python3
"""Reformat an Arknights story epub into a Kindle-friendly epub.

Usage:
    akformat.py BOOK.epub            # full run: extract, format, build
    akformat.py --rebuild BOOK.epub  # rebuild epub from existing final.md (keeps hand edits)

Creates, next to BOOK.epub:
    BOOK/                    working folder (kept)
        raw.md               pandoc's straight conversion of the epub
        final.md             reformatted markdown (edit this, then --rebuild)
        img_dir/             extracted images
        style.css            copy of the stylesheet used
    BOOK (formatted).epub    the result
"""

import argparse
import json
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
STYLE_CSS = SCRIPT_DIR / "style.css"


def read_epub_metadata(epub_path):
    """Return (title, author) from the epub's OPF, or None for missing fields."""
    ns = {
        "c": "urn:oasis:names:tc:opendocument:xmlns:container",
        "opf": "http://www.idpf.org/2007/opf",
        "dc": "http://purl.org/dc/elements/1.1/",
    }
    try:
        with zipfile.ZipFile(epub_path) as z:
            container = ET.fromstring(z.read("META-INF/container.xml"))
            opf_path = container.find(".//c:rootfile", ns).get("full-path")
            opf = ET.fromstring(z.read(opf_path))
    except (KeyError, AttributeError, ET.ParseError, zipfile.BadZipFile):
        return None, None

    def text(tag):
        el = opf.find(f".//dc:{tag}", ns)
        return el.text.strip() if el is not None and el.text and el.text.strip() else None

    return text("title"), text("creator")


# A markdown image line, e.g. "![](img_dir/images/x.png){.image}"
IMAGE_PATTERN = re.compile(r'^!\[[^\]]*\]\(([^)\s]+)\)')

# Dialogue: "Name：Content" (name up to 40 chars, full- or half-width colon)
DIALOGUE_PATTERN = re.compile(r'^([^:：\r\n]{1,40})[：:](.*)')

# Chapter titles, e.g. "11-1 Title", "BB-ST-1 Title"
CHAPTER_PATTERN = re.compile(
    r'^(?:#{1,6}\s+)?(?:\d{1,2}-\d{1,2}[A-Z]?|[A-Z0-9]{1,6}(?:-[A-Z0-9]{1,6})*-\d{1,3}[A-Z]?)\s+\S'
)

# Source-epub version info, e.g. "Script Version: 1.0.0"
VERSION_PATTERN = re.compile(r'^(Script|Game data) Version\b')


def is_image_caption(text, image_path):
    """True if text is the file-name caption the source epub puts under each image,
    e.g. "avg_4132_ascln_1#1\\$1" under ".../avg_4132_ascln_1_1$1.png"."""
    stem = image_path.rsplit("/", 1)[-1].rsplit(".", 1)[0]
    return text.replace("\\", "").replace("#", "_") == stem


def find_cover_image(lines):
    """Return the image path on the source epub's cover page, if there is one."""
    for i, line in enumerate(lines):
        if re.match(r'^\[\]\{#[^}]*cover[^}]*\}', line.strip()):
            for nxt in lines[i + 1:i + 4]:
                m = IMAGE_PATTERN.match(nxt.strip())
                if m:
                    return m.group(1)
    return None


def format_markdown(lines, title, author, cover=None):
    """Merge consecutive dialogue lines per speaker and turn chapter lines into headings.

    Chapter lines become # headings; a following line that extends the chapter title
    (e.g. "BB-1 宏伟愿景 行动前") becomes a ## heading with just the suffix ("行动前").
    """
    output_lines = []

    # --- Metadata for Pandoc (JSON strings are valid YAML, so quoting is safe) ---
    output_lines.append("---\n")
    output_lines.append(f"title: {json.dumps(title, ensure_ascii=False)}\n")
    output_lines.append(f"author: {json.dumps(author, ensure_ascii=False)}\n")
    output_lines.append("lang: zh-CN\n")
    if cover:
        output_lines.append(f"cover-image: {json.dumps(cover, ensure_ascii=False)}\n")
    output_lines.append("---\n\n")

    current_speaker = None
    dialogue_buffer = []
    current_chapter = None
    last_image = None  # path of the image on the previous line, if any

    def flush_buffer():
        nonlocal current_speaker, dialogue_buffer

        if current_speaker and dialogue_buffer:
            # <div class="speech"><div class="speaker">Name</div><div class="lines">...</div></div>
            output_lines.append(f"\n:::: speech\n::: speaker\n{current_speaker}\n:::\n\n::: lines\n")
            for text in dialogue_buffer:
                output_lines.append(f"{text}\n\n")
            output_lines.append(":::\n::::\n")

        current_speaker = None
        dialogue_buffer = []

    for line in lines:
        stripped = line.strip()

        if not stripped:
            continue

        # Drop the file-name caption under each image
        prev_image, last_image = last_image, None
        if prev_image and is_image_caption(stripped, prev_image):
            continue

        # The cover image goes in the metadata instead (avoids a duplicate cover page)
        image = IMAGE_PATTERN.match(stripped)
        if image:
            last_image = image.group(1)
            if cover and last_image == cover:
                continue

        # Check for Dialogue. Needs actual speech after the colon, and a name without
        # sentence punctuation, so narration like "史书上写着：" stays narration.
        match_dialogue = DIALOGUE_PATTERN.match(stripped)
        if match_dialogue:
            name = match_dialogue.group(1).strip()
            content = match_dialogue.group(2).strip()
            if (not content or not name or "，" in name or "。" in name
                    or VERSION_PATTERN.match(stripped)):
                match_dialogue = None

        if match_dialogue:
            if name != current_speaker:
                flush_buffer()
                current_speaker = name
            dialogue_buffer.append(content)
            continue

        # If not dialogue, flush any pending speech first
        flush_buffer()

        if CHAPTER_PATTERN.match(stripped):
            heading = stripped.lstrip("#").strip()
            if current_chapter and heading.startswith(current_chapter + " "):
                # Section of the current chapter: "BB-1 宏伟愿景 行动前" -> "## 行动前"
                output_lines.append(f"\n## {heading[len(current_chapter):].strip()}\n")
            else:
                current_chapter = heading
                output_lines.append(f"\n# {heading}\n")
        else:
            # Narration, existing # headers, images... keep as-is
            output_lines.append(f"\n{stripped}\n")

    flush_buffer()
    return ''.join(output_lines)


def run(cmd, cwd):
    try:
        subprocess.run(cmd, cwd=cwd, check=True)
    except FileNotFoundError:
        sys.exit(f"Error: '{cmd[0]}' not found. Install it (e.g. `brew install pandoc`).")
    except subprocess.CalledProcessError as e:
        sys.exit(f"Error: {cmd[0]} failed with exit code {e.returncode}.")


def main():
    parser = argparse.ArgumentParser(
        description="Reformat an Arknights story epub into a Kindle-friendly epub.")
    parser.add_argument("epub", type=Path, help="input epub")
    parser.add_argument("--rebuild", action="store_true",
                        help="skip extraction/formatting; rebuild the epub from the existing final.md")
    args = parser.parse_args()

    epub = args.epub.resolve()
    if not epub.is_file():
        sys.exit(f"Error: {args.epub} not found.")

    work_dir = epub.with_suffix("")
    out_epub = epub.with_name(f"{epub.stem} (formatted).epub")
    final_md = work_dir / "final.md"

    if args.rebuild:
        if not final_md.is_file():
            sys.exit(f"Error: {final_md} not found; run without --rebuild first.")
    else:
        work_dir.mkdir(exist_ok=True)

        # 1. epub -> raw markdown + images
        print(f"[1/3] Extracting {epub.name} ...")
        run(["pandoc", "-f", "epub", "-t", "markdown",
             "--extract-media=img_dir", "-o", "raw.md", str(epub)], cwd=work_dir)

        # 2. raw.md -> final.md
        print("[2/3] Formatting raw.md -> final.md ...")
        title, author = read_epub_metadata(epub)
        lines = (work_dir / "raw.md").read_text(encoding="utf-8").splitlines()
        final_md.write_text(
            format_markdown(lines, title or epub.stem, author or "Arknights",
                            cover=find_cover_image(lines)),
            encoding="utf-8")

        shutil.copy(STYLE_CSS, work_dir / "style.css")

    # 3. final.md -> epub
    print(f"[3/3] Building {out_epub.name} ...")
    css = "style.css" if (work_dir / "style.css").is_file() else str(STYLE_CSS)
    run(["pandoc", "final.md", "-o", str(out_epub), f"--css={css}",
         "--toc", "--toc-depth=2", "--resource-path=."], cwd=work_dir)

    print(f"Done: {out_epub}\nWorking files: {work_dir}/")


if __name__ == "__main__":
    main()
