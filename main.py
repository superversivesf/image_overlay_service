# main.py
from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.responses import StreamingResponse
from PIL import Image, ImageDraw
import io

app = FastAPI(
    title="Image Overlay Service",
    description="Add quotes with translucent overlays to images",
    version="0.1.0"
)


@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "service": "Image Overlay Service",
        "status": "running",
        "version": "0.1.0"
    }


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy"}


def add_translucent_box(image: Image.Image, quote: str, attribution: str) -> Image.Image:
    """
    Add a translucent box overlay to the image.
    Box is 80% of image width and centered.
    Height will be calculated based on text (for now, we'll use a fixed height).

    Args:
        image: PIL Image object
        quote: Quote text (not used yet, but included for future)
        attribution: Attribution text (not used yet, but included for future)

    Returns:
        Modified PIL Image object with translucent box
    """
    # Get image dimensions
    img_width, img_height = image.size

    # Calculate box dimensions
    box_width = int(img_width * 0.8)
    box_height = int(img_height * 0.3)  # Temporary: 30% of height, will adjust based on text later

    # Calculate box position (centered)
    box_x = (img_width - box_width) // 2
    box_y = (img_height - box_height) // 2

    # Create a copy of the image to work with
    result_image = image.copy()

    # Create a transparent overlay
    overlay = Image.new('RGBA', image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # Draw the translucent box (black with 60% opacity)
    # RGBA: (0, 0, 0, 153) where 153 = 255 * 0.6
    draw.rectangle(
        [box_x, box_y, box_x + box_width, box_y + box_height],
        fill=(0, 0, 0, 153)
    )

    # Convert original image to RGBA if needed
    if result_image.mode != 'RGBA':
        result_image = result_image.convert('RGBA')

    # Composite the overlay onto the image
    result_image = Image.alpha_composite(result_image, overlay)

    return result_image


@app.post("/overlay")
async def create_overlay(
        image: UploadFile = File(..., description="Image file to overlay quote on"),
        quote: str = Form(..., description="Quote text to overlay"),
        attribution: str = Form(..., description="Attribution for the quote")
):
    """
    Add a quote overlay to an image.
    Currently only adds the translucent box, text overlay coming soon.
    """
    # Validate file type
    if not image.content_type.startswith('image/'):
        raise HTTPException(status_code=400, detail="File must be an image")

    try:
        # Read the uploaded image
        image_data = await image.read()
        img = Image.open(io.BytesIO(image_data))

        # Add the translucent box
        result_img = add_translucent_box(img, quote, attribution)

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