import torch
import torch.nn as nn
from torchvision import models, transforms
from PIL import Image
import io
import os

# ── Device ──────────────────────────────────────────────────────────────────
DEVICE = torch.device("cpu")

# ── Class names (38 classes, same order as ImageFolder on PlantVillage) ─────
CLASS_NAMES = [
    "Apple___Apple_scab",
    "Apple___Black_rot",
    "Apple___Cedar_apple_rust",
    "Apple___healthy",
    "Blueberry___healthy",
    "Cherry_(including_sour)___Powdery_mildew",
    "Cherry_(including_sour)___healthy",
    "Corn_(maize)___Cercospora_leaf_spot Gray_leaf_spot",
    "Corn_(maize)___Common_rust_",
    "Corn_(maize)___Northern_Leaf_Blight",
    "Corn_(maize)___healthy",
    "Grape___Black_rot",
    "Grape___Esca_(Black_Measles)",
    "Grape___Leaf_blight_(Isariopsis_Leaf_Spot)",
    "Grape___healthy",
    "Orange___Haunglongbing_(Citrus_greening)",
    "Peach___Bacterial_spot",
    "Peach___healthy",
    "Pepper,_bell___Bacterial_spot",
    "Pepper,_bell___healthy",
    "Potato___Early_blight",
    "Potato___Late_blight",
    "Potato___healthy",
    "Raspberry___healthy",
    "Soybean___healthy",
    "Squash___Powdery_mildew",
    "Strawberry___Leaf_scorch",
    "Strawberry___healthy",
    "Tomato___Bacterial_spot",
    "Tomato___Early_blight",
    "Tomato___Late_blight",
    "Tomato___Leaf_Mold",
    "Tomato___Septoria_leaf_spot",
    "Tomato___Spider_mites Two-spotted_spider_mite",
    "Tomato___Target_Spot",
    "Tomato___Tomato_Yellow_Leaf_Curl_Virus",
    "Tomato___Tomato_mosaic_virus",
    "Tomato___healthy",
]

# ── Preprocessing transform (matches val_transform in notebook) ──────────────
TRANSFORM = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
])

# ── Model path ───────────────────────────────────────────────────────────────
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(_SCRIPT_DIR, "plant_disease_model_fixed.pth")


def load_model() -> nn.Module:
    """Load EfficientNet-B0 with the fine-tuned weights."""
    model = models.efficientnet_b0(weights=None)
    num_features = model.classifier[1].in_features
    model.classifier[1] = nn.Linear(num_features, len(CLASS_NAMES))
    model.load_state_dict(torch.load(MODEL_PATH, map_location=DEVICE))
    model.to(DEVICE)
    model.eval()
    return model


# Load once at import time so every request reuses the same model instance
_model = load_model()


def predict(image_bytes: bytes) -> dict:
    """
    Run inference on raw image bytes.

    Parameters
    ----------
    image_bytes : bytes
        Raw bytes of the uploaded image file.

    Returns
    -------
    dict with keys:
        - predicted_class (str)  : human-readable label
        - confidence (float)     : probability 0-100 (rounded to 2 dp)
        - all_scores (dict)      : {class_name: probability %} for all 38 classes
    """
    # 1. Decode bytes → PIL Image (force RGB so grayscale / RGBA images work)
    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")

    # 2. Preprocess
    tensor = TRANSFORM(image).unsqueeze(0).to(DEVICE)   # (1, 3, 224, 224)

    # 3. Inference
    with torch.no_grad():
        outputs = _model(tensor)                                   # logits
        probabilities = torch.nn.functional.softmax(outputs, dim=1)[0]  # (38,)

    # 4. Top prediction
    confidence, pred_idx = torch.max(probabilities, dim=0)
    predicted_class = CLASS_NAMES[pred_idx.item()]
    confidence_pct  = round(confidence.item() * 100, 2)

    # 5. All scores (useful for showing a probability bar chart in the UI)
    all_scores = {
        name: round(prob.item() * 100, 2)
        for name, prob in zip(CLASS_NAMES, probabilities)
    }

    return {
        "predicted_class": predicted_class,
        "confidence":       confidence_pct,
        "all_scores":       all_scores,
    }
