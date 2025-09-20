from PIL import Image, ImageDraw, ImageFont
import os
import random

CANDIDATE_FONTS = [
    # Linux (Debian/Ubuntu) Noto fonts - these should be available after Docker install
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc", 
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSerifCJK-Regular.ttc",
    # Windows fonts
    r"C:\Windows\Fonts\simsun.ttc",
    r"C:\Windows\Fonts\simsunb.ttf", 
    r"C:\Windows\Fonts\mingliu.ttc",
    r"C:\Windows\Fonts\msjh.ttc",
    r"C:\Windows\Fonts\msyh.ttc",
    # macOS fonts
    "/System/Library/Fonts/STSong.ttf",
    "/System/Library/Fonts/Songti.ttc",
    "/System/Library/Fonts/Songti SC.ttc",
]

def find_font():
    for p in CANDIDATE_FONTS:
        if os.path.exists(p):
            return p
    return None

def load_font(size, font_path=None):
    try:
        if font_path is None:
            font_path = find_font()
        if font_path:
            print(f"[FONT] Loading font: {font_path} size {size}")
            return ImageFont.truetype(font_path, size=size)
        else:
            print(f"[FONT] No suitable font found, using default font size {size}")
    except Exception as e:
        print(f"[FONT] Error loading font {font_path}: {e}")
    
    # Try to load a basic font that supports some Unicode
    try:
        # Try to use DejaVu Sans which often supports more characters
        return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", size=size)
    except:
        pass
    
    print(f"[FONT] Falling back to default font")
    return ImageFont.load_default()

def corner_xy(W, H, w, h, corner, margin):
    if corner == "top_left":
        return margin, margin
    if corner == "top_right":
        return W - margin - w, margin
    if corner == "bottom_left":
        return margin, H - margin - h
    if corner == "bottom_right":
        return W - margin - w, H - margin - h
    return W - margin - w, margin

def size_text_to_target_width(draw, text, init_px, target_w_ratio, W, stroke_ratio, font_path):
    font = load_font(init_px, font_path)
    stroke = max(1, int(font.size * stroke_ratio))
    for _ in range(12):
        bbox = draw.textbbox((0, 0), text, font=font, stroke_width=stroke)
        tw = bbox[2] - bbox[0]
        if tw <= W * target_w_ratio or font.size <= 12:
            break
        scale = (W * target_w_ratio) / max(1, tw)
        new_size = max(12, int(font.size * scale))
        font = load_font(new_size, font_path)
        stroke = max(1, int(font.size * stroke_ratio))
    bbox = draw.textbbox((0, 0), text, font=font, stroke_width=stroke)
    return font, stroke, (bbox[2] - bbox[0], bbox[3] - bbox[1])

def size_vertical_text_to_target_height(draw, text, init_px, target_h_ratio, W, H, line_spacing_ratio, stroke_ratio, font_path):
    n = max(1, len(text))
    
    # Calculate minimum font size based on what 7 characters would use
    target_chars = 7
    min_guess = init_px
    for _ in range(12):
        f = load_font(min_guess, font_path)
        line_spacing = int(f.size * line_spacing_ratio)
        bb = draw.textbbox((0, 0), "字", font=f)
        ch_h = (bb[3] - bb[1])
        total_h = target_chars * ch_h + (target_chars - 1) * line_spacing
        if total_h <= int(H * target_h_ratio) or min_guess <= 16:
            break
        scale = (H * target_h_ratio) / max(1, total_h)
        min_guess = max(16, int(f.size * (0.9 * scale + 0.1)))
    
    # Now calculate font size for actual text, using the 6-char size as minimum
    min_font_size = min_guess
    guess = init_px
    for _ in range(12):
        f = load_font(guess, font_path)
        line_spacing = int(f.size * line_spacing_ratio)
        bb = draw.textbbox((0, 0), "字", font=f)
        ch_h = (bb[3] - bb[1])
        total_h = n * ch_h + (n - 1) * line_spacing
        if total_h <= int(H * target_h_ratio) or guess <= min_font_size:
            break
        scale = (H * target_h_ratio) / max(1, total_h)
        guess = max(min_font_size, int(f.size * (0.9 * scale + 0.1)))
    f = load_font(guess, font_path)
    line_spacing = int(f.size * line_spacing_ratio)
    stroke = max(1, int(f.size * stroke_ratio))
    vt = "\n".join(list(text))
    vb = draw.multiline_textbbox((0, 0), vt, font=f, spacing=line_spacing, stroke_width=stroke)
    return f, stroke, line_spacing, vt, (vb[2] - vb[0], vb[3] - vb[1])

def size_text_to_target_width_min(draw, text, init_px, min_px, target_w_ratio, W, stroke_ratio, font_path):
    font = load_font(init_px, font_path)
    stroke = max(1, int(font.size * (stroke_ratio * 0.8)))
    for _ in range(12):
        bb = draw.textbbox((0, 0), text, font=font, stroke_width=stroke)
        bw = bb[2] - bb[0]
        if bw <= W * target_w_ratio or font.size <= min_px:
            break
        scale = (W * target_w_ratio) / max(1, bw)
        new_size = max(min_px, int(font.size * scale))
        font = load_font(new_size, font_path)
        stroke = max(1, int(font.size * (stroke_ratio * 0.8)))
    bb = draw.textbbox((0, 0), text, font=font, stroke_width=stroke)
    return font, stroke, (bb[2] - bb[0], bb[3] - bb[1])

def overlay_greeting(
    image_path: str,
    top_text: str,
    small_vertical_text: str,
    output_path: str = "out.jpg",
    font_path: str | None = None,
    layout: int | str = "random",
    top_color=(255, 255, 255),
    bottom_color=(255, 255, 255),
    br_color=(255, 255, 255),
    br_text="認同請分享",
    margin_ratio=0.04,
    top_target_width_ratio=0.85,
    bottom_target_height_ratio=0.45,
    br_target_width_ratio=0.35,
    stroke_ratio=0.06,
    line_spacing_ratio=0.18,
):
    print(f"[TEXT_OVERLAY] Starting overlay: top_text='{top_text}', small_text='{small_vertical_text}'")
    print(f"[TEXT_OVERLAY] Input image: {image_path}")
    print(f"[TEXT_OVERLAY] Output path: {output_path}")
    img = Image.open(image_path).convert("RGBA")
    W, H = img.size
    assert W == H, "請提供 1:1 方形圖片。"
    draw = ImageDraw.Draw(img)
    margin = int(W * margin_ratio)
    if layout == "random":
        layout = random.choice([1, 2, 3, 4])
    if layout not in (1, 2, 3, 4):
        raise ValueError("layout 只能是 1~4 或 'random'。")
    if layout == 1:
        big_corner = "top_right"
        v_corner = "bottom_left"
        br_corner = "bottom_right"
    elif layout == 2:
        big_corner = "bottom_right"
        v_corner = "top_left"
        br_corner = "top_right"
    elif layout == 3:
        big_corner = "top_left"
        v_corner = "bottom_right"
        br_corner = "bottom_left"
    else:  # layout == 4
        big_corner = "bottom_left"
        v_corner = "top_right"
        br_corner = "top_left"
    font_top, stroke_top, (tw, th) = size_text_to_target_width(
        draw, top_text, init_px=int(W * 0.20),  # Increased from 0.16 to 0.20 to make greeting text bigger
        target_w_ratio=0.75, W=W,  # Increased from 0.65 to 0.75 for bigger text
        stroke_ratio=stroke_ratio, font_path=font_path
    )
    # Reduce margin further to align closer to edges, especially top alignment
    reduced_margin = int(margin * 0.1)  # Much smaller margin for tighter edge alignment
    
    # Custom positioning logic for better bottom alignment
    if big_corner == "top_left":
        top_x, top_y = reduced_margin, reduced_margin
    elif big_corner == "top_right":
        top_x, top_y = W - reduced_margin - tw, reduced_margin
    elif big_corner == "bottom_left":
        # For bottom positioning, use same margin calculation as br_text for consistency
        top_x = reduced_margin
        top_y = H - margin - th  # Use standard margin like br_text for proper bottom alignment
    elif big_corner == "bottom_right":
        # For bottom-right, use same margin calculation as br_text for consistency  
        top_x = W - reduced_margin - tw
        top_y = H - margin - th  # Use standard margin like br_text for proper bottom alignment
    else:
        top_x, top_y = W - reduced_margin - tw, reduced_margin
    draw.text((top_x, top_y), top_text, font=font_top,
              fill=top_color, stroke_width=stroke_top, stroke_fill=(0, 0, 0))
    f_v, stroke_v, line_spacing, v_text, (vw, vh) = size_vertical_text_to_target_height(
        draw, small_vertical_text, init_px=int(W * 0.12),
        target_h_ratio=bottom_target_height_ratio, W=W, H=H,
        line_spacing_ratio=line_spacing_ratio, stroke_ratio=stroke_ratio, font_path=font_path
    )
    vx, vy = corner_xy(W, H, vw, vh, v_corner, margin)
    draw.multiline_text((vx, vy), v_text, font=f_v, spacing=line_spacing,
                        fill=bottom_color, stroke_width=stroke_v, stroke_fill=(0, 0, 0), align="left")
    f_br, stroke_br, (bw, bh) = size_text_to_target_width_min(
        draw, br_text, init_px=int(W * 0.06), min_px=max(14, int(W * 0.03)),
        target_w_ratio=br_target_width_ratio, W=W,
        stroke_ratio=stroke_ratio, font_path=font_path
    )
    br_x, br_y = corner_xy(W, H, bw, bh, br_corner, margin)
    draw.text((br_x, br_y), br_text, font=f_br,
              fill=br_color, stroke_width=stroke_br, stroke_fill=(0, 0, 0))
    img.convert("RGB").save(output_path, quality=95)
    print(f"已輸出：{output_path}（版面 {layout}）")

if __name__ == "__main__":
    overlay_greeting(
        image_path="background.jpg",
        top_text="早安",
        small_vertical_text="順心如意",
        output_path="greeting_out.jpg",
        font_path=r"C:\Windows\Fonts\simsun.ttc",
        layout="random",
    )
