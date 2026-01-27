import re

def process_arknights_kindle_toc(input_file, output_md_file):
    
    # --- 1. Read Input ---
    with open(input_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    output_lines = []
    
    # --- 2. Add Metadata for Pandoc ---
    output_lines.append("---\n")
    output_lines.append("title: Arknights Story\n")
    output_lines.append("author: Arknights\n")
    
    # === FIX IS HERE: Changed 'zh' to 'zh-CN' ===
    output_lines.append("lang: zh-CN\n") 
    output_lines.append("---\n\n")

    current_speaker = None
    dialogue_buffer = []
    
    # Regex 1: Dialogue ("Name: Content")
    dialogue_pattern = re.compile(r'^([^:：\r\n]{1,40})[：:](.*)')

    # # Regex 2: Chapter Titles (e.g., "11-1 Title")
    chapter_pattern = re.compile(
        r'^(?:#{1,6}\s+)?(?:\d{1,2}-\d{1,2}[A-Z]?|[A-Z0-9]{1,6}(?:-[A-Z0-9]{1,6})*-\d{1,3}[A-Z]?)\s+\S'
    )

def flush_buffer():
    nonlocal current_speaker, dialogue_buffer
    if current_speaker:
        # === KINDLE-SAFE TABLE STRUCTURE ===
        output_lines.append('\n<table class="speech-table">\n')
        output_lines.append('  <tr>\n')

        # Col 1: Name (No wrapping on Kindle)
        output_lines.append(f'    <td class="td-name" valign="top">{current_speaker}</td>\n')

        # Col 2: Text
        output_lines.append('    <td class="td-text" valign="top">\n')
        for text in dialogue_buffer:
            output_lines.append(f'      <p>{text}</p>\n')
            output_lines.append('    </td>\n')
            output_lines.append('  </tr>\n')
            output_lines.append('</table>\n')

            current_speaker = None
            dialogue_buffer = []

    for line in lines:
        stripped = line.strip()
        
        if not stripped:
            continue

        # Check for Dialogue
        match_dialogue = dialogue_pattern.match(stripped)
        is_metadata = "Version" in line or "Game data" in line

        if match_dialogue and not is_metadata:
            name = match_dialogue.group(1).strip()
            content = match_dialogue.group(2).strip()

            if name == current_speaker:
                dialogue_buffer.append(content)
            else:
                flush_buffer()
                current_speaker = name
                dialogue_buffer.append(content)
        
        else:
            # If not dialogue, flush any pending speech first
            flush_buffer()

            # === CHECK FOR HEADERS ===
            # If line starts with "11-1 ", make it a Header 2 (##)
            if chapter_pattern.match(stripped):
                output_lines.append(f"\n## {stripped}\n")
            
            # If line already has a #, leave it alone
            elif stripped.startswith("#"):
                output_lines.append(f"\n{stripped}\n")
            
            # Otherwise, it's just narration/text
            else:
                output_lines.append(f"\n{stripped}\n")

    flush_buffer()

    with open(output_md_file, 'w', encoding='utf-8') as f:
        f.write(''.join(output_lines))
    print(f"Success! Created {output_md_file} with 'zh-CN' fixed.")

# --- Run it ---
try:
    process_arknights_kindle_toc('raw.md', 'final.md')
except FileNotFoundError:
    print("Could not find sample.md")
