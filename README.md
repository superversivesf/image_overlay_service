# Image Overlay Service

A simple HTTP service that adds quotes with translucent overlays to images.

## Features

- Accepts an image file, quote text, and attribution
- Adds a translucent box overlay (80% image width)
- Overlays the quote and attribution on the box
- Returns the processed image

## Setup

1. Install dependencies:
```bash
poetry install
```

2. Run the service:
```bash
poetry run python main.py
```

Or:
```bash
poetry run uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## API Endpoints

- `GET /` - Service info
- `GET /health` - Health check
- `POST /overlay` - Add quote overlay to image (coming soon)

## Testing

Import the `postman_collection.json` file into Postman to test the API.