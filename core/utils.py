import re
import time
import requests
import logging
from django.conf import settings
from requests.adapters import HTTPAdapter, Retry
from PyPDF2 import PdfReader

logger = logging.getLogger(__name__)


# ✅ Extract text from PDF
def extract_text_from_pdf(file_path: str) -> str:
    reader = PdfReader(file_path)
    texts = []
    for page in reader.pages:
        txt = page.extract_text()
        if txt:
            texts.append(txt)
    return "\n".join(texts)


# ✅ Split into chunks under HF token/size limit
def chunk_text(text: str, max_chars: int = 4500) -> list[str]:
    sentences = re.split(r"(?<=[\.\?\!])\s+", text)
    chunks, current = [], ""

    for sent in sentences:
        if len(current) + len(sent) + 1 <= max_chars:
            current += sent + " "
        else:
            chunks.append(current.strip())
            current = sent + " "
    if current:
        chunks.append(current.strip())

    return chunks


# ✅ Session w/ retry logic so fewer sudden random errors
def _requests_session_with_retries() -> requests.Session:
    session = requests.Session()
    retries = Retry(
        total=3,
        backoff_factor=0.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["POST"]
    )
    adapter = HTTPAdapter(max_retries=retries)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


# ✅ Robust flexible summarizer
def generate_summary(text: str, max_length: int = 200, min_length: int = 50) -> str:
    api_token = getattr(settings, "HF_API_TOKEN", None)
    # Hardcode models to ensure they are correct and available, bypassing .env issues.
    models = [
        "facebook/bart-large-cnn",  # Primary
        "t5-base",                  # Fallback
    ]

    if not api_token:
        raise RuntimeError("HF Summarization models or API Token missing")

    headers = {"Authorization": f"Bearer {api_token}", "Content-Type": "application/json"}
    chunks = chunk_text(text)
    session = _requests_session_with_retries()

    for model in models:
        summaries = []
        api_url = f"https://api-inference.huggingface.co/models/{model}"
        logger.info(f"Trying summarization with model: {model}")

        success = True

        for i, chunk in enumerate(chunks):
            payload = {
                "inputs": chunk,
                "options": {"use_cache": False},
                "parameters": {
                    "max_new_tokens": max_length,
                    "min_length": min_length,
                    "do_sample": False
                }
            }
            try:
                resp = session.post(api_url, headers=headers, json=payload, timeout=60)
                resp.raise_for_status()
                data = resp.json()

                text_out = data[0].get("summary_text") or data[0].get("generated_text", "")
                summaries.append(text_out.strip())

                time.sleep(0.4)

            except Exception as e:
                logger.error(f"❌ HF model failed [{model}] | Chunk {i+1}: {e}")
                success = False
                break

        if success:
            logger.info(f"✅ Summarization success using model: {model}")
            return "\n".join(summaries)

        logger.warning(f"⚠️ Model failed: {model} — trying fallback")

    return "Summary unavailable. All models failed."


# ✅ Cleaning the explanation
def clean_explanation(text: str, concept: str) -> str:
    sentences = re.split(r"(?<=[.!?])\s+", text)
    cleaned = []

    for s in sentences:
        s = s.strip()
        if len(s) < 12:
            continue
        if "http" in s or "www" in s:
            continue
        cleaned.append(s)
        if len(cleaned) >= 4:
            break

    result = " ".join(cleaned).strip()
    if not result.endswith("."):
        result += "."
    return result


# ✅ Explanation generator with fallback
def generate_explanation(text: str) -> str:
    api_token = getattr(settings, "HF_API_TOKEN", None)
    # Hardcode models to ensure they are correct and available, bypassing .env issues.
    models = [
        "google/flan-t5-small", # Primary
        "t5-small",             # Fallback
    ]

    if not api_token:
        return "Explanation unavailable (API not configured)"

    headers = {"Authorization": f"Bearer {api_token}", "Content-Type": "application/json"}
    session = _requests_session_with_retries()
    concept = text[:200]

    for model in models:
        api_url = f"https://api-inference.huggingface.co/models/{model}"
        payload = {"inputs": concept, "options": {"use_cache": False}}

        try:
            resp = session.post(api_url, headers=headers, json=payload, timeout=40)
            resp.raise_for_status()
            data = resp.json()

            output = data[0].get("generated_text", "") or data[0].get("summary_text", "")
            if output:
                return clean_explanation(output, concept)

        except Exception as e:
            logger.error(f"Explanation API failed [{model}]: {e}")

    return "Explanation unavailable. All models failed."


# ✅ HF Test Function for debug view
def test_api_connection():
    token = getattr(settings, "HF_API_TOKEN", None)
    model = getattr(settings, "HF_EXPLAIN_MODEL_PRIMARY", None)

    if not token or not model:
        return False, "Missing HF Token or model settings"

    url = f"https://api-inference.huggingface.co/models/{model}"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    try:
        resp = requests.post(url, headers=headers, json={"inputs": "Test"}, timeout=10)
        resp.raise_for_status()
        return True, "Connection OK ✔"
    except Exception as e:
        return False, f"Connection error: {e}"
