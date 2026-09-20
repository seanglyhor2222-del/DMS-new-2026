import os
import re
import uuid
import time
import cv2
import numpy as np

from flask import (Blueprint, render_template, request, jsonify,
                   current_app, url_for)
from flask_login import login_required, current_user
from flask_socketio import join_room
from PIL import Image
import pytesseract
from google import genai

from extensions import socketio, db
from models import AuditLog

ocr_bp = Blueprint("ocr", __name__)

# In-memory pairing store: { code: {"created": ts, "user_id": int} }
_PAIRINGS = {}
PAIRING_TTL_SECONDS = 15 * 60


def _cleanup_pairings():
    now = time.time()
    expired = [c for c, v in _PAIRINGS.items() if now - v["created"] > PAIRING_TTL_SECONDS]
    for c in expired:
        _PAIRINGS.pop(c, None)


@ocr_bp.route("/api/ocr/session/new", methods=["POST"])
@login_required
def new_session():
    """PC page asks for a fresh pairing code + generates the phone URL."""
    if not current_user.permission("can_scan_ocr"):
        return jsonify({"error": "no_permission"}), 403

    _cleanup_pairings()
    code = uuid.uuid4().hex[:8]
    _PAIRINGS[code] = {"created": time.time(), "user_id": current_user.id}

    mobile_url = url_for("ocr.mobile_capture", code=code, _external=True)
    return jsonify({"code": code, "mobile_url": mobile_url})


@ocr_bp.route("/mobile/<code>")
def mobile_capture(code):
    _cleanup_pairings()
    valid = code in _PAIRINGS
    return render_template("mobile_capture.html", code=code, valid=valid)


@ocr_bp.route("/api/ocr/upload/<code>", methods=["POST"])
def upload_and_ocr(code):
    """
    Called from the phone. No login required here (phone isn't logged in) —
    the short-lived pairing code itself is the access control.
    """
    _cleanup_pairings()
    if code not in _PAIRINGS:
        return jsonify({"error": "session_expired"}), 400

    if "image" not in request.files:
        return jsonify({"error": "no_image"}), 400

    file = request.files["image"]
    upload_dir = current_app.config["UPLOAD_FOLDER"]
    os.makedirs(upload_dir, exist_ok=True)
    filename = f"{code}_{int(time.time())}.jpg"
    filepath = os.path.join(upload_dir, filename)
    file.save(filepath)

    text, engine, warning = _run_ocr(filepath)

    user_id = _PAIRINGS[code]["user_id"]
    detail = f"OCR scan via mobile ({engine}), {len(text)} chars extracted"
    if warning:
        detail += f" — {warning}"
    db.session.add(AuditLog(user_id=user_id, action="ocr_scan", detail=detail))
    db.session.commit()

    # Push the extracted text straight to the PC page listening on this room
    socketio.emit("ocr_result", {"text": text, "engine": engine, "warning": warning}, room=code)

    return jsonify({"success": True, "text": text, "engine": engine, "warning": warning})


@ocr_bp.route("/api/ocr/preview_status/<code>")
def preview_status(code):
    """Simple polling fallback if a client can't use WebSocket."""
    _cleanup_pairings()
    return jsonify({"valid": code in _PAIRINGS})


def _run_ocr(image_path):
    """
    Primary path: send the photo directly to Gemini's vision model and ask
    it to transcribe the Khmer/English text verbatim. A vision-capable model
    reading the actual image is far more accurate for Khmer script (subscripts,
    stacked consonants, old/legacy fonts) than classic Tesseract OCR — Tesseract
    alone tends to hallucinate stray Latin fragments on dense Khmer pages.

    Fallback path (no API key configured, or the API call fails / no internet):
    local Tesseract OCR with an improved preprocessing pipeline.

    Returns (text, engine, warning) so the caller can tell the user which
    engine actually produced the result, and why, if it had to fall back —
    silently degrading to Tesseract with no explanation is what made bad
    scans impossible to diagnose before.
    """
    api_key = current_app.config.get("GEMINI_API_KEY", "")
    if api_key:
        try:
            text = _run_gemini_vision_ocr(image_path, api_key)
            if text and text.strip():
                return text.strip(), "gemini", None
            print("Gemini Vision OCR returned empty text, falling back to Tesseract")
        except Exception as e:
            import traceback
            print(f"Gemini Vision OCR error, falling back to Tesseract: {e!r}")
            traceback.print_exc()
            text = _run_tesseract_ocr(image_path)
            return text, "tesseract", f"Gemini OCR failed ({e}), used lower-accuracy fallback"
    else:
        print("GEMINI_API_KEY not set, using Tesseract")

    text = _run_tesseract_ocr(image_path)
    warning = None if api_key else "No GEMINI_API_KEY configured — used lower-accuracy fallback"
    return text, "tesseract", warning


def _run_gemini_vision_ocr(image_path, api_key):
    from google.genai import types
    from google.genai import errors

    with open(image_path, "rb") as f:
        image_bytes = f.read()

    ext = os.path.splitext(image_path)[1].lower()
    mime_type = "image/png" if ext == ".png" else "image/jpeg"

    client = genai.Client(api_key=api_key)
    prompt = (
        "អ្នកគឺជាអ្នកជំនាញផ្នែកអានអត្ថបទពីរូបភាពឯកសារភាសាខ្មែរ។ "
        "សូមចម្លង (transcribe) អត្ថបទទាំងអស់ដែលមាននៅក្នុងរូបភាពនេះឲ្យបានត្រឹមត្រូវ ១០០% "
        "តាមអក្សរដើម រួមទាំងសញ្ញាវណ្ណយុត្តិ លេខ និងចន្លោះកថាខណ្ឌ។ "
        "កុំបកប្រែ កុំសង្ខេប កុំបន្ថែម ឬកាត់ចេញអ្វីទាំងអស់ — ចម្លងឲ្យដូចអត្ថបទក្នុងរូបភាពបេះបិទ។ "
        "សូមឆ្លើយតបជាអត្ថបទសុទ្ធ (plain text) តែប៉ុណ្ណោះ គ្មានចំណារពន្យល់ ឬសញ្ញា markdown ។"
    )

    # Try the configured model first; if it's unavailable on this key/API
    # version (a 404 NOT_FOUND from the API, e.g. after a model rename or
    # deprecation), fall back to progressively safer model names instead of
    # dropping all the way to Tesseract for a problem that has nothing to do
    # with image quality.
    model_candidates = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-flash-latest"]
    last_error = None
    for model_name in model_candidates:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=[
                    types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                    prompt,
                ],
            )
            return response.text if response else ""
        except errors.APIError as e:
            last_error = e
            if getattr(e, "code", None) == 404:
                print(f"Model '{model_name}' not available, trying next candidate")
                continue
            raise  # auth / quota / other real errors shouldn't be masked by retrying
    raise last_error


def _run_tesseract_ocr(image_path):
    pytesseract.pytesseract.tesseract_cmd = current_app.config["TESSERACT_CMD"]

    img = cv2.imread(image_path)
    if img is None:
        image = Image.open(image_path)
        raw_text = pytesseract.image_to_string(image, lang='khm+eng')
    else:
        gray = _preprocess_for_ocr(img)
        raw_text = pytesseract.image_to_string(gray, lang='khm+eng', config=r'--oem 3 --psm 3')

    return _clean_text(raw_text)


def _preprocess_for_ocr(img):
    """
    Sharper preprocessing pipeline for Khmer document photos:
    grayscale -> upscale -> denoise -> deskew -> adaptive threshold.
    This gives Tesseract cleaner glyph edges, which matters a lot for
    Khmer subscript/stacked consonants that are easy to mis-read on a
    blurry or unevenly-lit phone photo.
    """
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Upscale small photos — Tesseract likes ~300dpi-equivalent detail
    if gray.shape[1] < 2200:
        ratio = 2200 / gray.shape[1]
        gray = cv2.resize(gray, None, fx=ratio, fy=ratio, interpolation=cv2.INTER_CUBIC)

    # Denoise while keeping edges (bilateral keeps character strokes sharp)
    gray = cv2.bilateralFilter(gray, 9, 75, 75)

    # Deskew based on the dominant text angle
    gray = _deskew(gray)

    # Adaptive threshold handles uneven phone-camera lighting better
    # than a single global threshold across the whole page.
    thresh = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 11
    )
    return thresh


def _deskew(gray):
    """Estimate and correct small rotation from an off-angle phone photo."""
    try:
        inverted = cv2.bitwise_not(gray)
        thresh = cv2.threshold(inverted, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)[1]
        coords = np.column_stack(np.where(thresh > 0))
        if coords.shape[0] < 50:
            return gray
        angle = cv2.minAreaRect(coords)[-1]
        if angle < -45:
            angle = -(90 + angle)
        else:
            angle = -angle
        if abs(angle) < 0.3 or abs(angle) > 15:
            return gray  # not worth rotating / probably a bad estimate
        (h, w) = gray.shape[:2]
        center = (w // 2, h // 2)
        M = cv2.getRotationMatrix2D(center, angle, 1.0)
        return cv2.warpAffine(gray, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
    except Exception:
        return gray


def _clean_text(text):
    text = text.replace("\r", "")
    text = text.replace("。", ".")
    text = text.replace("៖", ":")
    text = text.replace("  ", " ")
    lines = [ln.strip() for ln in text.split("\n")]
    lines = [ln for ln in lines if ln != ""]
    cleaned = "\n".join(lines)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    return cleaned.strip()


# ---- SocketIO events ----
@socketio.on("join")
def handle_join(data):
    room = data.get("room")
    if room:
        join_room(room)