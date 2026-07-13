<div align="center">

# 🌿 VerdantAI

**AI-powered plant disease diagnostics — from leaf image to treatment plan in seconds.**

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.30%2B-FF4B4B?style=flat-square&logo=streamlit&logoColor=white)](https://streamlit.io)
[![PyTorch](https://img.shields.io/badge/PyTorch-EfficientNet--B0-EE4C2C?style=flat-square&logo=pytorch&logoColor=white)](https://pytorch.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-22C55E?style=flat-square)](LICENSE)
[![CI](https://img.shields.io/badge/CI-GitHub%20Actions-2088FF?style=flat-square&logo=githubactions&logoColor=white)](https://github.com/features/actions)

[Overview](#-overview) · [Features](#-features) · [Architecture](#-architecture) · [Quickstart](#-quickstart) · [Configuration](#-configuration) · [Project Structure](#-project-structure) · [API Reference](#-api-reference)

<img src="https://raw.githubusercontent.com/github/explore/main/topics/python/python.png" width="0" height="0">

</div>

---

## 📌 Overview

VerdantAI is a full-stack, AI-driven plant diagnostics platform. Upload a leaf photo and receive an instant disease diagnosis backed by a fine-tuned **EfficientNet-B0** model trained on the **PlantVillage dataset** (38 classes, 54,000+ images).

Beyond a raw prediction, VerdantAI explains *why* it made that call (GradCAM heatmaps), tells you *what to do about it* (LLM-generated treatment guides via OpenRouter), and keeps a personal history of every scan — exportable as a polished PDF report.

Built for farmers, agronomists, hobbyist gardeners, and researchers who need a fast second opinion in the field.

---

## ✨ Features

| Feature | Details |
|---|---|
| 🔬 **Disease Detection** | EfficientNet-B0 — 38 PlantVillage classes, confidence scores for all |
| 🔥 **GradCAM Heatmaps** | Overlay visualisation showing which leaf regions drove the prediction |
| 💊 **AI Remedy Guides** | LLM-generated treatment plans via OpenRouter (Gemma-3 fallback chain) |
| 📊 **Dashboard** | Scan stats, 7-day trends, top diseases — all live from SQLite |
| 📜 **Scan History** | Filterable log with expandable remedy cards and CSV export |
| 📄 **PDF Reports** | One-click ReportLab-generated reports per scan |
| 🔐 **Secure Auth** | bcrypt passwords, IP-bound sessions, rate limiting, auto token rotation |
| 🏗️ **Modular Stack** | FastAPI backend + Streamlit frontend — independently runnable |

---

## 🏛 Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     Streamlit Frontend                   │
│  app.py  ·  Dashboard  ·  Analyse  ·  History  ·  Reports │
└────────────────────────┬────────────────────────────────┘
                         │  HTTP (localhost:8000)
┌────────────────────────▼────────────────────────────────┐
│                      FastAPI Backend                     │
│   /predict (EfficientNet-B0)  ·  /gradcam  ·  /health   │
└────────────────────────┬────────────────────────────────┘
                         │
       ┌─────────────────┼──────────────────┐
       ▼                 ▼                  ▼
  PyTorch Model    OpenRouter API      SQLite DBs
  (plant_disease   (Gemma-3 remedy    (auth/users.db
   _model.pth)      generation)        frontend/scans.db)
```

**Request flow — Analyse page:**
1. User uploads leaf image → Streamlit sends bytes to FastAPI `/predict`
2. FastAPI runs EfficientNet-B0 inference → returns top class + all 38 probabilities
3. If diseased → second call to `/gradcam` generates heatmap overlay
4. `remedy_generator.py` calls OpenRouter (Gemma-3-27b → 12b → 4b fallback) for treatment JSON
5. Scan auto-saved to SQLite with compressed image blob

---

## ⚡ Quickstart

### Prerequisites

| Requirement | Version |
|---|---|
| Python | 3.10 or higher |
| pip | latest |
| Git | any |

> **Model file required:** The trained model (`backend/plant_disease_model_fixed.pth`) is excluded from this repo due to size. Download it separately and place it in `backend/`.

### 1 — Clone the repo

```bash
git clone https://github.com/aeitro/verdantai.git
cd verdantai
```

### 2 — Create and activate a virtual environment

```bash
# macOS / Linux
python -m venv .venv
source .venv/bin/activate

# Windows
python -m venv .venv
.venv\Scripts\activate
```

### 3 — Install dependencies

```bash
pip install -r requirements.txt
```

### 4 — Configure environment variables

```bash
cp .env.example .env
```

Open `.env` and set your OpenRouter key:

```env
OPENROUTER_API_KEY=sk-or-v1-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

> Don't have a key? Get one free at [openrouter.ai](https://openrouter.ai). Remedy generation will be skipped without it — all other features work normally.

### 5 — Start the FastAPI backend

```bash
cd backend
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

Verify it's running: [http://localhost:8000/health](http://localhost:8000/health)

```json
{ "status": "ok", "model": "EfficientNet-B0 (PlantVillage 38-class)" }
```

### 6 — Start the Streamlit frontend

Open a **new terminal** (keep the backend running):

```bash
cd frontend
streamlit run app.py
```

Open [http://localhost:8501](http://localhost:8501) → create an account → start diagnosing. 🌱

---

## ⚙️ Configuration

All configuration lives in `.env` at the project root.

| Variable | Required | Description |
|---|---|---|
| `OPENROUTER_API_KEY` | No* | API key for LLM remedy generation |

*App functions fully without it — remedy cards will be unavailable but detection, heatmaps, history, and reports all work.

**Backend URL** — if you move the FastAPI server off `localhost:8000`, update this constant in `frontend/pages/2_Analyse.py`:

```python
BACKEND_URL = "http://localhost:8000"
```

---

## 🗂 Project Structure

```
verdantai/
├── .github/
│   └── workflows/
│       └── ci.yml              # CI — lint + import checks on push/PR
│
├── auth/
│   ├── auth_ui.py              # Streamlit login/signup UI + session management
│   ├── database.py             # SQLite auth layer (bcrypt, sessions, rate limiting)
│   └── sanitize.py             # Input validation and password strength scoring
│
├── backend/
│   ├── app.py                  # FastAPI app — /predict, /gradcam, /health endpoints
│   ├── predict.py              # EfficientNet-B0 inference + 38-class labels
│   ├── gradcam.py              # GradCAM heatmap generation + overlay
│   ├── remedy_generator.py     # OpenRouter LLM calls with fallback chain + cache
│   └── plant_disease_model_fixed.pth  # ← place model file here (not tracked)
│
├── frontend/
│   ├── app.py                  # Entry point — auth gate + redirect to Dashboard
│   ├── sidebar.py              # Shared sidebar component (nav + user card)
│   ├── db.py                   # SQLite scan history layer (save, query, stats)
│   └── pages/
│       ├── 1_Dashboard.py      # Stats cards, Plotly charts, recent scans
│       ├── 2_Analyse.py        # Full scan flow — upload → diagnose → remedy
│       ├── 3_History.py        # Filterable scan log + CSV export
│       ├── 4_Reports.py        # PDF report generation + download
│       └── 5_Profile.py        # Account info, donut chart, danger zone
│
├── .env.example                # Environment variable template
├── .gitignore
├── LICENSE
├── pyrightconfig.json
├── README.md
└── requirements.txt
```

---

## 🔌 API Reference

The FastAPI backend exposes three endpoints. Interactive docs available at `http://localhost:8000/docs`.

### `GET /health`

Health check — confirms server is up and model is loaded.

```bash
curl http://localhost:8000/health
```

```json
{ "status": "ok", "model": "EfficientNet-B0 (PlantVillage 38-class)" }
```

---

### `POST /predict`

Run disease classification on a leaf image.

```bash
curl -X POST http://localhost:8000/predict \
  -F "file=@leaf.jpg"
```

**Response:**

```json
{
  "filename": "leaf.jpg",
  "predicted_class": "Tomato___Early_blight",
  "confidence": 94.31,
  "all_scores": {
    "Tomato___Early_blight": 94.31,
    "Tomato___Late_blight": 3.12,
    "..."
  }
}
```

| Field | Type | Description |
|---|---|---|
| `predicted_class` | `string` | Raw PlantVillage class label |
| `confidence` | `float` | Top-1 confidence (0–100) |
| `all_scores` | `object` | Probability % for all 38 classes |

**Accepted formats:** JPEG, PNG, WEBP

---

### `POST /gradcam`

Generate a GradCAM heatmap overlay for the uploaded image.

```bash
curl -X POST http://localhost:8000/gradcam \
  -F "file=@leaf.jpg" \
  --output heatmap.png
```

Returns a PNG image stream with the heatmap blended onto the original.

---

## 🧪 Running Tests

The CI pipeline runs on every push to `main` and `dev`:

```bash
# Lint with flake8
pip install flake8
flake8 backend/ frontend/ --max-line-length=120

# Check backend imports load cleanly
cd backend
python -c "from remedy_generator import get_remedy; print('OK')"
python -c "from gradcam import GradCAM, apply_heatmap; print('OK')"
```

---

## 🌱 Supported Plant Classes

VerdantAI covers **38 classes** across 14 plant species from the PlantVillage dataset:

<details>
<summary>View all 38 classes</summary>

| Plant | Conditions |
|---|---|
| Apple | Apple Scab, Black Rot, Cedar Apple Rust, Healthy |
| Blueberry | Healthy |
| Cherry | Powdery Mildew, Healthy |
| Corn (Maize) | Cercospora Leaf Spot, Common Rust, Northern Leaf Blight, Healthy |
| Grape | Black Rot, Esca (Black Measles), Leaf Blight, Healthy |
| Orange | Huanglongbing (Citrus Greening) |
| Peach | Bacterial Spot, Healthy |
| Pepper (Bell) | Bacterial Spot, Healthy |
| Potato | Early Blight, Late Blight, Healthy |
| Raspberry | Healthy |
| Soybean | Healthy |
| Squash | Powdery Mildew |
| Strawberry | Leaf Scorch, Healthy |
| Tomato | Bacterial Spot, Early Blight, Late Blight, Leaf Mold, Septoria Leaf Spot, Spider Mites, Target Spot, Yellow Leaf Curl Virus, Mosaic Virus, Healthy |

</details>

---

## 🔐 Security Notes

- Passwords hashed with **bcrypt** — never stored in plaintext
- Sessions are **IP-bound** — token is revoked if the client IP changes mid-session
- **Single active session** per user — new login revokes all prior tokens
- **Rate limiting** — 5 failed attempts per 5 minutes, per username and IP
- All user inputs pass through `auth/sanitize.py` before touching the database
- XSS mitigation via `html.escape()` on all values rendered back to the UI

---

## 🤝 Contributing

Pull requests are welcome. For major changes, please open an issue first to discuss what you'd like to change.

1. Fork the repository
2. Create your feature branch: `git checkout -b feat/your-feature`
3. Commit your changes: `git commit -m 'feat: add your feature'`
4. Push to the branch: `git push origin feat/your-feature`
5. Open a pull request

Please make sure CI passes (`flake8` + import checks) before requesting review.

---

## 📄 License

[MIT](LICENSE) © 2026 aeitro

---

<div align="center">
<sub>Built with Python, FastAPI, Streamlit, PyTorch, and OpenRouter · Trained on PlantVillage</sub>
</div>
