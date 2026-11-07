# akformat

Reformats Arknights story epubs into a cleaner, Kindle-friendly epub:

- Consecutive lines from the same speaker are merged into one block: the name as a small
  sans-serif label, then the lines with a thin bar down the left so dialogue stands apart
  from narration. Tweak the look in the `DIALOGUE` section of `style.css`.
- Chapter lines like `BB-1 宏伟愿景` become chapters. Their parts (`行动前`, `行动后`, `幕间`)
  become sub-sections, so the table of contents nests properly. Each chapter starts on a new page.
- The file-name captions the source epub puts under every image (`bg_thundercloud` etc.) are removed.
- Title, author and cover image are taken from the source epub.

Requires `python3` and `pandoc` (`brew install pandoc`).

## Usage

```bash
~/bin/akformat/akformat.py "act33side - 巴别塔.epub"
```

This creates, next to the input epub:

```
act33side - 巴别塔 (formatted).epub   <- the result
act33side - 巴别塔/                    <- working files, kept
    raw.md       pandoc's straight conversion of the original epub
    final.md     the reformatted markdown
    img_dir/     extracted images
    style.css    copy of the stylesheet used
```

### Hand-editing the markdown

To fix something by hand, edit `final.md` in the working folder, then rebuild without
re-extracting (a full run overwrites `raw.md` and `final.md`):

```bash
~/bin/akformat/akformat.py --rebuild "act33side - 巴别塔.epub"
```

`--rebuild` uses the `style.css` in the working folder, so you can tweak that per book too.

## Page numbers (optional, untested)

1. Import the formatted epub into Calibre.
2. Run the "Count Pages" plugin (algorithm: APNX).
3. "Send to device" over USB to put the page map on the Kindle.

## Notes

- The pandoc warning `Could not load translations for zh-CN` is harmless.
- Fuller original notes: [Reproducing Arknights Formatter](simplenote://note/9f8e4b5aa4c24c5da2512d684b9cd797) (Simplenote; the script there is an older version).
