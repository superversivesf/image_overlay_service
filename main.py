# main.py
from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.responses import StreamingResponse
from PIL import Image, ImageDraw, ImageFont
import io
from pathlib import Path
from typing import Optional
import re

app = FastAPI(
    title="Image Overlay Service",
    description="Add quotes with translucent overlays to images",
    version="0.2.0"
)

# Directory where fonts are stored (committed to repo)
FONTS_DIR = Path(__file__).parent / "fonts"

# Cache for discovered fonts
_font_cache = {}


def discover_fonts() -> dict:
    """
    Discover all fonts in the fonts directory that match *-Regular.ttf pattern.
    Returns a dict mapping font names to filenames.
    """
    if _font_cache:
        return _font_cache

    print(f"\n=== FONT DISCOVERY DEBUG ===")
    print(f"Looking for fonts in: {FONTS_DIR}")
    print(f"FONTS_DIR exists: {FONTS_DIR.exists()}")
    print(f"FONTS_DIR absolute path: {FONTS_DIR.absolute()}")

    if not FONTS_DIR.exists():
        print(f"Creating fonts directory...")
        FONTS_DIR.mkdir(parents=True, exist_ok=True)
        return {}

    # List all files in the directory
    print(f"\nAll files in fonts directory:")
    for item in FONTS_DIR.iterdir():
        print(f"  - {item.name} (is_file: {item.is_file()})")

    fonts = {}

    # Find all *-Regular.ttf files
    print(f"\nSearching for *-Regular.ttf files:")
    for font_file in FONTS_DIR.glob("*-Regular.ttf"):
        # Extract font name from filename
        # e.g., "PlayfairDisplay-Regular.ttf" -> "playfairdisplay"
        font_name = font_file.stem.replace("-Regular", "").lower()
        fonts[font_name] = font_file.name
        print(f"  Found: {font_file.name} -> {font_name}")

    # Also check for *Regular.ttf (without hyphen) like "OpenSansRegular.ttf"
    print(f"\nSearching for *Regular.ttf files (no hyphen):")
    for font_file in FONTS_DIR.glob("*Regular.ttf"):
        if not font_file.name.endswith("-Regular.ttf"):  # Skip ones we already got
            font_name = font_file.stem.replace("Regular", "").lower()
            fonts[font_name] = font_file.name
            print(f"  Found: {font_file.name} -> {font_name}")

    print(f"\nTotal fonts discovered: {len(fonts)}")
    print(f"Font mapping: {fonts}")
    print(f"=== END FONT DISCOVERY ===\n")

    _font_cache.update(fonts)
    return fonts


@app.on_event("startup")
async def startup_event():
    """Discover fonts on startup."""
    fonts = discover_fonts()
    print(f"\n*** SERVICE STARTED ***")
    print(f"Discovered {len(fonts)} fonts: {', '.join(fonts.keys()) if fonts else 'NONE'}")
    print(f"*** *** *** *** *** ***\n")


@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "service": "Image Overlay Service",
        "status": "running",
        "version": "0.2.0"
    }


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy"}


@app.get("/fonts")
async def list_fonts():
    """List all available fonts discovered in the fonts directory."""
    fonts = discover_fonts()

    available_fonts = {}
    for font_name, filename in fonts.items():
        font_path = FONTS_DIR / filename
        available_fonts[font_name] = {
            "name": font_name,
            "filename": filename,
            "available": font_path.exists(),
            "absolute_path": str(font_path.absolute())
        }

    default = "opensans" if "opensans" in fonts else (list(fonts.keys())[0] if fonts else None)

    return {
        "fonts": available_fonts,
        "default": default,
        "count": len(available_fonts),
        "fonts_directory": str(FONTS_DIR.absolute())
    }


@app.get("/debug/fonts")
async def debug_fonts():
    """Debug endpoint to see raw file system state"""
    return {
        "fonts_dir": str(FONTS_DIR.absolute()),
        "fonts_dir_exists": FONTS_DIR.exists(),
        "parent_dir": str(FONTS_DIR.parent.absolute()),
        "files_in_fonts_dir": [f.name for f in FONTS_DIR.iterdir()] if FONTS_DIR.exists() else [],
        "discovered_fonts": discover_fonts(),
        "cache": _font_cache
    }


def get_font(size: int, font_name: str = "opensans") -> ImageFont.FreeTypeFont:
    """
    Load a font by name, fallback to system fonts if not available.

    Args:
        size: Font size in pixels
        font_name: Name of the font to use
    """
    print(f"\n--- GET FONT DEBUG ---")
    print(f"Requested font: {font_name}, size: {size}")

    fonts = discover_fonts()
    print(f"Available fonts: {list(fonts.keys())}")

    # Try to load the requested font
    if font_name in fonts:
        font_path = FONTS_DIR / fonts[font_name]
        print(f"Font found in cache: {fonts[font_name]}")
        print(f"Full path: {font_path.absolute()}")
        print(f"File exists: {font_path.exists()}")

        if font_path.exists():
            try:
                font = ImageFont.truetype(str(font_path), size)
                print(f"✓ Successfully loaded font: {font_name}")
                return font
            except Exception as e:
                print(f"✗ Error loading font {font_name}: {e}")
    else:
        print(f"✗ Font '{font_name}' not found in available fonts")

    # If requested font not found, try to use any available font
    if fonts:
        first_font = list(fonts.keys())[0]
        font_path = FONTS_DIR / fonts[first_font]
        print(f"Trying first available font: {first_font}")
        try:
            font = ImageFont.truetype(str(font_path), size)
            print(f"✓ Loaded fallback font: {first_font}")
            return font
        except Exception as e:
            print(f"✗ Error loading fallback font {first_font}: {e}")

    # Fallback to system fonts
    print("Falling back to system fonts...")
    font_paths = [
        "/System/Library/Fonts/Supplemental/Arial.ttf",  # macOS
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",  # Linux
        "C:\\Windows\\Fonts\\arial.ttf",  # Windows
    ]

    for font_path in font_paths:
        try:
            font = ImageFont.truetype(font_path, size)
            print(f"✓ Loaded system font: {font_path}")
            return font
        except:
            print(f"✗ System font not found: {font_path}")
            continue

    # Last resort fallback
    print("✓ Using PIL default font")
    return ImageFont.load_default()


def wrap_text(text: str, font: ImageFont.FreeTypeFont, max_width: int, draw: ImageDraw.ImageDraw) -> list:
    """
    Wrap text to fit within max_width.
    Returns list of lines.
    """
    words = text.split()
    lines = []
    current_line = []

    for word in words:
        test_line = ' '.join(current_line + [word])
        bbox = draw.textbbox((0, 0), test_line, font=font)
        width = bbox[2] - bbox[0]

        if width <= max_width:
            current_line.append(word)
        else:
            if current_line:
                lines.append(' '.join(current_line))
            current_line = [word]

    if current_line:
        lines.append(' '.join(current_line))

    return lines


def add_translucent_box_with_text(
        image: Image.Image,
        quote: str,
        attribution: str,
        font_name: str = "opensans"
) -> Image.Image:
    """
    Add a translucent box overlay with quote and attribution text.
    Box is 80% of image width, centered, with height based on text content.

    Args:
        image: PIL Image object
        quote: Quote text to display
        attribution: Attribution text to display
        font_name: Name of the font to use

    Returns:
        Modified PIL Image object with translucent box and text
    """
    # Get image dimensions
    img_width, img_height = image.size

    # Calculate box dimensions
    box_width = int(img_width * 0.8)
    box_padding = 40  # Padding inside the box

    # Create fonts
    quote_font_size = max(24, int(img_width * 0.03))  # Scale with image size
    attribution_font_size = max(18, int(img_width * 0.022))

    quote_font = get_font(quote_font_size, font_name)
    attribution_font = get_font(attribution_font_size, font_name)

    # Create a temporary draw object to calculate text size
    temp_img = Image.new('RGBA', (1, 1))
    temp_draw = ImageDraw.Draw(temp_img)

    # Wrap quote text
    max_text_width = box_width - (box_padding * 2)
    quote_lines = wrap_text(quote, quote_font, max_text_width, temp_draw)

    # Calculate total text height
    line_spacing = 10
    quote_height = 0
    for line in quote_lines:
        bbox = temp_draw.textbbox((0, 0), line, font=quote_font)
        quote_height += (bbox[3] - bbox[1]) + line_spacing

    # Attribution height
    attr_bbox = temp_draw.textbbox((0, 0), f"— {attribution}", font=attribution_font)
    attribution_height = attr_bbox[3] - attr_bbox[1]

    # Calculate total box height
    box_height = quote_height + attribution_height + (box_padding * 2) + 20  # Extra space between quote and attribution

    # Calculate box position (centered)
    box_x = (img_width - box_width) // 2
    box_y = (img_height - box_height) // 2

    # Create a copy of the image to work with
    result_image = image.copy()

    # Create a transparent overlay
    overlay = Image.new('RGBA', image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # Draw the translucent grey box (128, 128, 128 with 60% opacity)
    draw.rectangle(
        [box_x, box_y, box_x + box_width, box_y + box_height],
        fill=(128, 128, 128, 153)
    )

    # Convert original image to RGBA if needed
    if result_image.mode != 'RGBA':
        result_image = result_image.convert('RGBA')

    # Composite the overlay onto the image
    result_image = Image.alpha_composite(result_image, overlay)

    # Now draw the text on top
    draw = ImageDraw.Draw(result_image)

    # Draw quote lines
    current_y = box_y + box_padding
    for line in quote_lines:
        # Center each line horizontally
        bbox = draw.textbbox((0, 0), line, font=quote_font)
        line_width = bbox[2] - bbox[0]
        line_x = box_x + (box_width - line_width) // 2

        draw.text((line_x, current_y), line, fill=(0, 0, 0, 255), font=quote_font)
        current_y += (bbox[3] - bbox[1]) + line_spacing

    # Draw attribution (right-aligned)
    attribution_text = f"— {attribution}"
    attr_bbox = draw.textbbox((0, 0), attribution_text, font=attribution_font)
    attr_width = attr_bbox[2] - attr_bbox[0]
    attr_x = box_x + box_width - attr_width - box_padding  # Right-aligned
    attr_y = current_y + 20

    draw.text((attr_x, attr_y), attribution_text, fill=(0, 0, 0, 255), font=attribution_font)

    return result_image


@app.post("/overlay")
async def create_overlay(
        image: UploadFile = File(..., description="Image file to overlay quote on"),
        quote: str = Form(..., description="Quote text to overlay"),
        attribution: str = Form(..., description="Attribution for the quote"),
        font: str = Form(None,
                         description="Font name to use (see /fonts for available fonts). If not specified, uses default.")
):
    """
    Add a quote overlay to an image with a translucent grey box and black text.
    Supports custom fonts.
    """
    # Validate file type
    if not image.content_type.startswith('image/'):
        raise HTTPException(status_code=400, detail="File must be an image")

    # Get available fonts
    fonts = discover_fonts()

    # Determine which font to use
    if font is None:
        # Use default
        font = "opensans" if "opensans" in fonts else (list(fonts.keys())[0] if fonts else "opensans")
        print(f"No font specified, using default: {font}")
    else:
        print(f"Font requested: {font}")
        # Validate font
        if font not in fonts:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid font '{font}'. Available fonts: {', '.join(fonts.keys())}. Use /fonts endpoint to see all available fonts."
            )

    try:
        # Read the uploaded image
        image_data = await image.read()
        img = Image.open(io.BytesIO(image_data))

        # Add the translucent box with text
        result_img = add_translucent_box_with_text(img, quote, attribution, font)

        # Convert back to RGB for JPEG output
        if result_img.mode == 'RGBA':
            # Create white background
            background = Image.new('RGB', result_img.size, (255, 255, 255))
            background.paste(result_img, mask=result_img.split()[3])  # Use alpha channel as mask
            result_img = background

        # Save to bytes
        img_byte_arr = io.BytesIO()
        result_img.save(img_byte_arr, format='JPEG', quality=95)
        img_byte_arr.seek(0)

        # Return the image
        return StreamingResponse(
            img_byte_arr,
            media_type="image/jpeg",
            headers={
                "Content-Disposition": f"attachment; filename=overlay_{image.filename}"
            }
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing image: {str(e)}")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)