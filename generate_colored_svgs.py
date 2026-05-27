import json
import re
import os
import argparse

def parse_acjk_counts(acjk_str):
    """Extract stroke counts from ACJK component string (e.g., '尤4丿1' -> [4, 1])."""
    if not acjk_str: return []
    return [int(n) for n in re.findall(r'\d+', acjk_str)]

def transform_graphics_d(d_string):
    """
    Transform Y coordinates (y_new = 900 - y_old) and ensure proper spacing.
    The coordinate system in make-me-a-hanzi is inverted relative to standard SVG.
    """
    tokens = re.findall(r'[A-Za-z]|[+-]?\d+', d_string.replace(',', ' '))
    result = []
    i = 0
    while i < len(tokens):
        token = tokens[i]
        if token.isalpha():
            result.append(token)
            i += 1
            coord_count = 0
            while i < len(tokens) and not tokens[i].isalpha():
                val = tokens[i]
                # Even index is X, Odd index is Y
                if coord_count % 2 == 1:
                    result.append(str(900 - int(val)))
                else:
                    result.append(val)
                i += 1
                coord_count += 1
        else:
            i += 1
    return " ".join(result)

def build_median_path(median_list):
    """Convert median coordinate points into an SVG path for drawing animation."""
    return " ".join([f"{'M' if i == 0 else 'L'} {pt[0]} {900 - pt[1]}" for i, pt in enumerate(median_list)])

def generate_svg_content(char_data, acjk_str, radical_color):
    """Generate SVG content with distinct layers for background and animation."""
    char = char_data['character']
    strokes = char_data['strokes']
    medians = char_data['medians']
    svg_id = f"z{ord(char)}"

    # Determine which strokes belong to the radical based on ACJK data
    stroke_counts = parse_acjk_counts(acjk_str)
    radical_limit = stroke_counts[0] if stroke_counts else 0
    num_strokes = len(strokes)

    # Animation timing: 0.8s per stroke, then hold and erase
    # Total: 6.5s (5 * 0.8s = 4.0s drawing + 1.0s hold + 1.5s erase)
    stroke_duration = 0.8
    hold_duration = 1.0
    erase_duration = 1.5
    total_duration = num_strokes * stroke_duration + hold_duration + erase_duration
    draw_end_time = num_strokes * stroke_duration
    erase_start_pct = draw_end_time / total_duration * 100

    # Build path IDs and data
    path_defs = []
    clip_defs = ""
    bg_uses = ""
    anim_paths = ""

    for i in range(num_strokes):
        idx = i + 1
        pid = f"p{idx}"
        cid = f"{svg_id}c{idx}"
        d_transformed = transform_graphics_d(strokes[i])
        m_transformed = build_median_path(medians[i])
        stroke_color = radical_color if i < radical_limit else "#000"

        path_defs.append((pid, d_transformed))
        clip_defs += f'    <clipPath id="{cid}"><use href="#{pid}"/></clipPath>\n'
        bg_uses += f'<use href="#{pid}"/>\n'
        anim_paths += f'    <path id="stroke-{pid}" style="stroke:{stroke_color}" pathLength="3333" clip-path="url(#{cid})" d="{m_transformed}"/>\n'

    # Generate keyframes for each stroke
    keyframes = ""
    for i in range(num_strokes):
        start_time = i * stroke_duration
        end_time = (i + 1) * stroke_duration
        start_pct = start_time / total_duration * 100
        end_pct = end_time / total_duration * 100

        keyframes += f"""/* Stroke {i+1}: Starts at {start_pct:.1f}%, finishes at {end_pct:.1f}%, holds until {erase_start_pct:.1f}% */
@keyframes zk{i+1} {{
    0%, {start_pct:.1f}% {{ stroke-dashoffset: 3339; }}
    {end_pct:.1f}%, {erase_start_pct:.1f}% {{ stroke-dashoffset: 0; }}
    {erase_start_pct+0.1:.1f}%, 100% {{ stroke-dashoffset: 3339; }}
}}
svg.acjk #stroke-p{i+1} {{ animation-name: zk{i+1}; }}
"""

    # Generate path definitions
    path_defs_str = "\n".join([f'    <path id="{pid}" d="{pd}"/>' for pid, pd in path_defs])

    style = f"""<style>
<![CDATA[
svg.acjk path[clip-path] {{
    animation-duration: {total_duration}s;
    animation-timing-function: linear;
    animation-iteration-count: infinite;
    stroke-dasharray: 3337;
    stroke-dashoffset: 3339;
    stroke-width: 128;
    stroke-linecap: round;
    fill: none;
    stroke: {radical_color};
}}
svg.acjk .bg {{ fill: #ccc; opacity: 0.5; }}

{keyframes}]]>
</style>"""

    return f"""<svg id="{svg_id}" class="acjk" viewBox="0 0 1024 1024" xmlns="http://www.w3.org/2000/svg">
{style}
<defs>
{path_defs_str}

{clip_defs}</defs>
<g id="bg-layer" class="bg">
{bg_uses}</g>
<g id="anim-layer">
{anim_paths}</g>
</svg>"""

def main():
    parser = argparse.ArgumentParser(description="Generate colored Chinese character SVGs.")
    parser.add_argument("--dict", default="dictionaryZhHans.txt", help="Path to dictionary data")
    parser.add_argument("--graphics", default="graphicsZhHans.txt", help="Path to graphics data")
    parser.add_argument("--output", default="svgsZhHans-colored", help="Output directory")
    parser.add_argument("--chars", default=None, help="Comma-separated characters to process")
    parser.add_argument("--radical-color", default="#FF4444", help="CSS color for the radical, default #FF4444")
    args = parser.parse_args()

    if not os.path.exists(args.output): 
        os.makedirs(args.output)
    
    # Load ACJK mapping from dictionary
    acjk_map = {}
    if os.path.exists(args.dict):
        with open(args.dict, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    item = json.loads(line)
                    acjk_map[item['character']] = item.get('acjk', '')

    # Process graphics and generate SVGs
    with open(args.graphics, 'r', encoding='utf-8') as f:
        for line in f:
            if not line.strip(): continue
            data = json.loads(line)
            char = data['character']
            if args.chars and char not in args.chars.split(','): continue
            
            svg = generate_svg_content(data, acjk_map.get(char, ''), args.radical_color)
            output_file = os.path.join(args.output, f"{ord(char)}.svg")
            with open(output_file, "w", encoding='utf-8') as out:
                out.write(svg)
    
    print(f"Success: SVGs generated in '{args.output}'")

if __name__ == "__main__":
    main()