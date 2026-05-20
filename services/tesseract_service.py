"""
OmniIntelOS OCR Service — Specialized FastAPI service for document extraction.
Hardware: CPU-friendly, uses Tesseract-OCR.
"""
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import os
import pytesseract
from PIL import Image
import io
import time
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ocr-service")

app = FastAPI(title="OmniIntelOS OCR Service", version="1.0.0")

cors_origins = [
    origin.strip()
    for origin in os.getenv("CORS_ALLOWED_ORIGINS", "http://localhost:5173").split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "ocr", "timestamp": time.time()}

@app.post("/extract")
async def extract_text(file: UploadFile = File(...)):
    """Extract text from an image file using Tesseract."""
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")
    
    start_time = time.time()
    try:
        content = await file.read()
        image = Image.open(io.BytesIO(content))
        
        # Performance optimization: Convert to grayscale if needed
        # image = image.convert('L')
        
        text = pytesseract.image_to_string(image)
        
        latency = time.time() - start_time
        logger.info(f"OCR processed in {latency:.3f}s")
        
        return {
            "filename": file.filename,
            "text": text.strip(),
            "latency_seconds": latency,
            "method": "tesseract-offline"
        }
    except Exception as e:
        logger.error(f"OCR mismatch: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
