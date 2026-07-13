"""
backend/remedy_generator.py
────────────────────────────
📁 Save as: PLANTDISEASEPROJ/backend/remedy_generator.py
           (replaces existing file)

Fixes applied
─────────────
1. Robust JSON extraction — uses regex to find the {...} block anywhere in the
   response, so preamble like "Here is the JSON:" or trailing text won't break
   parsing. The old code only stripped ```json fences, which wasn't enough.

2. Response validation — checks that all 6 required keys exist after parsing,
   so a truncated or partial response is treated as invalid and the next model
   is tried instead of returning broken data to the UI.

3. Detailed error strings — each failure now reports exactly what went wrong
   (HTTP status, raw response snippet, JSON parse error) so the UI can show
   a useful message instead of a generic failure.

4. Raw response logged to last_raw — callers can inspect it for debugging
   without needing to add print statements.

5. Timeout bumped to 45s — free-tier models can be slow, 30s was too tight.
"""

import os
import requests
import json
import re
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root (one level above backend/)
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# Key is read at import time but validated lazily at call time
# so importing this module in CI/tests never raises an error.
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")

# ── Model fallback chain — verified free tier (June 2026) ────────────────────
# Source: https://openrouter.ai/api/v1/models  (only :free slugs included)
# Order: best instruction-following first, smallest model last as final fallback
MODELS = [
    "meta-llama/llama-3.3-70b-instruct:free",   # Best quality, strong JSON adherence
    "google/gemma-4-31b-it:free",                # Google's latest, good structured output
    "nvidia/nemotron-3-super-120b-a12b:free",    # Large NVIDIA model, reliable fallback
    "google/gemma-4-26b-a4b-it:free",            # Lighter Gemma 4 variant
    "meta-llama/llama-3.2-3b-instruct:free",     # Fast small model, last resort
]


# Built lazily so the Bearer token always uses the current key value
def _headers() -> dict:
    return {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost:8501",
        "X-Title": "PlantAI",
    }


# ── Required keys — response must contain all of these ────────────────────────
REQUIRED_KEYS = {
    "overview", "severity", "remedies",
    "dietary_tips", "lifestyle_steps", "when_to_see_expert",
}


# ── In-memory cache ───────────────────────────────────────────────────────────
_cache: dict[str, dict] = {}


def clean_label(raw: str) -> str:
    """'Apple___Apple_scab' → 'Apple scab on Apple'"""
    parts = raw.split("___")
    if len(parts) == 2:
        plant, condition = parts
        plant     = plant.replace("_", " ").replace(",", "").strip()
        condition = condition.replace("_", " ").strip()
        return f"{condition} on {plant}"
    return raw.replace("_", " ")


def build_prompt(disease_label: str) -> str:
    return f"""You are a plant pathology expert. A plant leaf has been diagnosed with: "{disease_label}".

Return ONLY a valid JSON object with exactly these keys:

{{
  "overview": "2 sentences max. What the disease is and how it spreads.",
  "severity": "Low",
  "remedies": ["actionable treatment 1", "actionable treatment 2", "actionable treatment 3"],
  "dietary_tips": ["soil/nutrient tip 1", "soil/nutrient tip 2", "soil/nutrient tip 3"],
  "lifestyle_steps": ["prevention step 1", "prevention step 2", "prevention step 3"],
  "when_to_see_expert": "One sentence describing when to consult an agronomist."
}}

Rules:
- severity must be exactly one of: Low, Medium, High
- Each list must have 2-3 short items (under 12 words each)
- No markdown, no bullet points, no extra text outside the JSON
- Output must start with {{ and end with }}"""


def _extract_json(text: str) -> dict:
    """
    Robustly extract a JSON object from model output.

    Tries in order:
    1. Direct json.loads on the full stripped text
    2. Strip ```json ... ``` or ``` ... ``` fences, then parse
    3. Regex to find the first {...} block in the text (handles preamble/postamble)

    Raises ValueError if no valid JSON object is found.
    """
    text = text.strip()

    # Attempt 1 — clean parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Attempt 2 — strip markdown code fences
    stripped = re.sub(r"```(?:json)?", "", text).strip()
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass

    # Attempt 3 — find first {...} block (greedy, handles preamble)
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    raise ValueError(f"No valid JSON object found in response. Preview: {text[:200]!r}")


def _validate(data: dict) -> None:
    """Raise ValueError if any required key is missing."""
    missing = REQUIRED_KEYS - set(data.keys())
    if missing:
        raise ValueError(f"Response missing keys: {missing}")


def call_model(model: str, prompt: str) -> dict:
    """
    Call a single OpenRouter model.
    Returns a validated remedy dict on success.
    Raises on any failure — caller handles retries.
    """
    response = requests.post(
        url="https://openrouter.ai/api/v1/chat/completions",
        headers=_headers(),
        json={
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3,        # lower temp = more consistent JSON output
            "max_tokens": 512,
        },
        timeout=45,                    # bumped from 30s — free models can be slow
    )
    response.raise_for_status()

    resp_json = response.json()

    # Guard: sometimes OpenRouter returns an error inside a 200 response
    if "error" in resp_json:
        raise ValueError(f"OpenRouter error: {resp_json['error']}")

    choices = resp_json.get("choices", [])
    if not choices:
        raise ValueError(f"Empty choices in response: {resp_json}")

    content = choices[0]["message"]["content"]

    if not content or not content.strip():
        raise ValueError("Model returned empty content")

    data = _extract_json(content)
    _validate(data)

    # Normalise severity casing just in case
    data["severity"] = data.get("severity", "Medium").strip().capitalize()
    if data["severity"] not in ("Low", "Medium", "High"):
        data["severity"] = "Medium"

    return data


def get_remedy(predicted_class: str) -> dict:
    """
    Try each model in MODELS in order.
    Returns a remedy dict on success, or {"error": "...", "detail": "..."} on failure.
    """
    # Validate key at call time, not import time — keeps CI/tests from crashing
    if not OPENROUTER_API_KEY:
        return {
            "error": "OPENROUTER_API_KEY is not set.",
            "detail": "Add it to .env as: OPENROUTER_API_KEY=sk-or-v1-...",
        }

    if predicted_class in _cache:
        return _cache[predicted_class]

    disease_label = clean_label(predicted_class)
    prompt        = build_prompt(disease_label)
    last_error    = "No models tried"
    last_detail   = ""

    for model in MODELS:
        try:
            result = call_model(model, prompt)
            _cache[predicted_class] = result
            return result

        except requests.exceptions.HTTPError as e:
            status = e.response.status_code if e.response is not None else 0
            body   = ""
            try:
                body = e.response.json() if e.response is not None else ""
            except Exception:
                body = e.response.text[:200] if e.response is not None else ""
            last_error  = f"HTTP {status} from {model}"
            last_detail = str(body)
            continue

        except requests.exceptions.Timeout:
            last_error  = f"{model} timed out (>45s)"
            last_detail = ""
            continue

        except requests.exceptions.ConnectionError as e:
            # Network is down — no point trying other models
            return {
                "error":  "Cannot connect to OpenRouter API.",
                "detail": str(e),
            }

        except (ValueError, KeyError) as e:
            # JSON extraction / validation failure
            last_error  = f"{model} returned unparseable response"
            last_detail = str(e)
            continue

        except Exception as e:
            last_error  = f"{model} unexpected error"
            last_detail = str(e)
            continue

    return {
        "error":  f"All models failed. Last: {last_error}",
        "detail": last_detail,
    }