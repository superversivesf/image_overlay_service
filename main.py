# main.py
from fastapi import FastAPI, File, UploadFile, Form
from fastapi.responses import StreamingResponse
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)