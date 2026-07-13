from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from PIL import Image
import io

try:
    from .predict import predict, _model, TRANSFORM
    from .gradcam import GradCAM, apply_heatmap
except ImportError:
    if __package__:
        raise
    from predict import predict, _model, TRANSFORM
    from gradcam import GradCAM, apply_heatmap

# ── App setup ────────────────────────────────────────────────────────────────
app = FastAPI(
    title="PlantAI Disease Detector",
    description="Upload a leaf image and get a plant disease diagnosis.",
    version="1.0.0",
)

# ── CORS — allow Streamlit (running on any port) to call this API ─────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],       # tighten this in production
    allow_methods=["POST"],
    allow_headers=["*"],
)

# ── Allowed image types ───────────────────────────────────────────────────────
ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/jpg", "image/webp"}


# ── Health check ─────────────────────────────────────────────────────────────
@app.get("/health", summary="Health check")
def health():
    """Returns 200 OK when the server is up and the model is loaded."""
    return {"status": "ok", "model": "EfficientNet-B0 (PlantVillage 38-class)"}


# ── Prediction endpoint ───────────────────────────────────────────────────────
@app.post("/predict", summary="Predict plant disease from a leaf image")
async def predict_disease(file: UploadFile = File(...)):
    """
    Upload a leaf image (JPEG / PNG / WEBP) and receive:
    - **predicted_class**: disease name
    - **confidence**: confidence % of the top prediction
    - **all_scores**: probability % for every one of the 38 classes
    """
    # 1. Validate file type
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type '{file.content_type}'. "
                   f"Please upload a JPEG or PNG image.",
        )

    # 2. Read raw bytes
    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    # 3. Run inference
    try:
        result = predict(image_bytes)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Inference failed: {str(e)}",
        )

    # 4. Return result
    return {
        "filename":        file.filename,
        "predicted_class": result["predicted_class"],
        "confidence":      result["confidence"],
        "all_scores":      result["all_scores"],
    }

# ── GradCAM endpoint ──────────────────────────────────────────────────────────
@app.post("/gradcam", summary="Return GradCAM heatmap overlay image")
async def gradcam_endpoint(file: UploadFile = File(...)):
    # 1. Validate
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=415, detail="Unsupported file type.")

    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Empty file.")

    try:
        # 2. Open image
        original_image = Image.open(io.BytesIO(image_bytes)).convert("RGB")

        # 3. Preprocess — same as predict.py but WITHOUT torch.no_grad()
        input_tensor = TRANSFORM(original_image).unsqueeze(0) # type: ignore

        # 4. Generate GradCAM
        gradcam = GradCAM(_model)
        cam, _ = gradcam.generate(input_tensor)

        # 5. Overlay heatmap on original full-resolution image
        heatmap_img = apply_heatmap(cam, original_image)

        # 6. Return as PNG
        buf = io.BytesIO()
        heatmap_img.save(buf, format="PNG")
        buf.seek(0)
        return StreamingResponse(buf, media_type="image/png")

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"GradCAM failed: {str(e)}")
# ── Entry point (run with: uvicorn app:app --host 0.0.0.0 --port 8000) ───────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app:app", host="0.0.0.0", port=8000, reload=False)
