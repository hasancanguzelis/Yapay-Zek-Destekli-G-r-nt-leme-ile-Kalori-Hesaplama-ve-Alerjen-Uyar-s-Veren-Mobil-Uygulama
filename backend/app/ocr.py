from __future__ import annotations

import io
import os
import shutil
import sys
from pathlib import Path
from typing import Any
from urllib.request import urlopen

from .config import Settings


class OcrUnavailableError(RuntimeError):
    """Raised when OCR cannot run due to missing system dependencies (e.g. Tesseract binary)."""


def _require_ocr_deps() -> tuple[Any, Any, Any, Any]:
    """
    OCR dependencies are optional at import time so the API can still run
    (e.g., allergen classifier endpoint) even if OpenCV/Tesseract deps are missing.
    """
    try:
        import cv2  # type: ignore
        import numpy as np  # type: ignore
        import pytesseract  # type: ignore
        from PIL import Image  # type: ignore

        return cv2, np, pytesseract, Image
    except ModuleNotFoundError as e:
        raise RuntimeError(
            "OCR bağımlılıkları eksik. Kurulum için backend klasöründe şunu çalıştırın: "
            "pip install -r requirements.txt "
            f"(Eksik modül: {e.name})"
        ) from e


def _resolve_tesseract_cmd(settings: Settings) -> str | None:
    # 1) Explicit env setting
    if settings.tesseract_cmd:
        p = Path(settings.tesseract_cmd)
        if p.exists():
            return str(p)

    # 2) PATH
    which = shutil.which("tesseract") or shutil.which("tesseract.exe")
    if which:
        return which

    # 3) Common Windows install locations
    if sys.platform.startswith("win"):
        candidates = [
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
            # Some installers may use a shorter folder name
            r"C:\Tesseract-OCR\tesseract.exe",
        ]
        for c in candidates:
            if Path(c).exists():
                return c

    return None


def configure_tesseract(settings: Settings) -> None:
    _cv2, _np, pytesseract, _Image = _require_ocr_deps()
    cmd = _resolve_tesseract_cmd(settings)
    if cmd:
        pytesseract.pytesseract.tesseract_cmd = cmd

    # Validate binary availability early so we can return a clean error instead of 500.
    try:
        _ = pytesseract.get_tesseract_version()
    except Exception as e:
        raise OcrUnavailableError(
            "Tesseract bulunamadı. Windows için kurulumdan sonra "
            "backend/.env içine TESSERACT_CMD yolunu yazın (örn: "
            r"C:\Program Files\Tesseract-OCR\tesseract.exe) "
            "ve backend'i yeniden başlatın."
        ) from e


def _read_image_bytes(image_bytes: bytes):
    cv2, np, _pytesseract, Image = _require_ocr_deps()
    pil = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    arr = np.array(pil)
    # PIL RGB -> OpenCV BGR
    return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)


def preprocess_for_ocr(bgr):
    cv2, np, _pytesseract, _Image = _require_ocr_deps()
    """
    Lightweight preprocessing tuned for label text:
    - grayscale
    - contrast normalization
    - denoise
    - adaptive threshold
    """
    # Emülatör/webcam gibi düşük çözünürlüklü kaynaklarda OCR başarımı için upscaling yardımcı olur.
    h, w = bgr.shape[:2]
    if max(h, w) < 1600:
        scale = 2.0
        bgr = cv2.resize(bgr, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_CUBIC)

    # Hafif keskinleştirme (metin kenarlarını belirginleştirir)
    blur = cv2.GaussianBlur(bgr, (0, 0), sigmaX=1.0)
    bgr = cv2.addWeighted(bgr, 1.6, blur, -0.6, 0)

    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)

    # Normalize lighting
    gray = cv2.bilateralFilter(gray, d=7, sigmaColor=75, sigmaSpace=75)

    # Improve contrast
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    gray = clahe.apply(gray)

    # Adaptive thresholding tends to work well with uneven lighting
    thr = cv2.adaptiveThreshold(
        gray,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        31,
        8,
    )

    # Remove small noise
    kernel = np.ones((2, 2), np.uint8)
    thr = cv2.morphologyEx(thr, cv2.MORPH_OPEN, kernel, iterations=1)
    return thr


_TESSDATA_FAST_BASE = "https://github.com/tesseract-ocr/tessdata_fast/raw/main"


def _ensure_local_traineddata(local_tessdata_dir: Path, lang: str) -> bool:
    """
    Ensures <lang>.traineddata exists under backend/tessdata.
    This avoids requiring admin rights to write into Program Files.
    """
    if lang not in {"tur", "eng", "osd"}:
        return False

    try:
        local_tessdata_dir.mkdir(parents=True, exist_ok=True)
    except Exception:
        return False

    target = local_tessdata_dir / f"{lang}.traineddata"
    if target.exists() and target.stat().st_size > 1024:
        return True

    url = f"{_TESSDATA_FAST_BASE}/{lang}.traineddata"
    tmp = target.with_suffix(".traineddata.tmp")
    try:
        with urlopen(url, timeout=20) as r:  # nosec - controlled URL above
            data = r.read()
        if not data or len(data) < 1024:
            return False
        tmp.write_bytes(data)
        tmp.replace(target)
        return True
    except Exception:
        try:
            if tmp.exists():
                tmp.unlink()
        except Exception:
            pass
        return False


def _pick_ocr_lang(pytesseract: Any, requested: str | None, local_tessdata_dir: Path) -> tuple[str, str]:
    """
    Returns (lang, tessdata_flag) where tessdata_flag may include --tessdata-dir.
    Prefers requested lang if available either in system tessdata or backend/tessdata.
    """
    req = (requested or "").strip() or "eng"

    # If requested is Turkish, attempt to ensure local traineddata to improve accuracy.
    if req == "tur":
        _ensure_local_traineddata(local_tessdata_dir, "tur")
        _ensure_local_traineddata(local_tessdata_dir, "eng")
        _ensure_local_traineddata(local_tessdata_dir, "osd")

    tessdata_flag = ""
    available: set[str] = set()
    try:
        available |= set(pytesseract.get_languages(config=""))
    except Exception:
        pass

    # If we have local tessdata, force tesseract to look there.
    if local_tessdata_dir.exists():
        local_available = {p.stem for p in local_tessdata_dir.glob("*.traineddata")}
        if local_available:
            tessdata_flag = f' --tessdata-dir "{local_tessdata_dir}"'
            available |= local_available

    if req in available:
        return req, tessdata_flag
    return "eng", tessdata_flag


def ocr_image_bytes(image_bytes: bytes, settings: Settings, lang: str | None = None) -> str:
    _cv2, _np, pytesseract, _Image = _require_ocr_deps()
    configure_tesseract(settings)
    bgr = _read_image_bytes(image_bytes)
    pre = preprocess_for_ocr(bgr)
    backend_root = Path(__file__).resolve().parents[1]
    local_tessdata_dir = backend_root / "tessdata"
    ocr_lang, tessdata_flag = _pick_ocr_lang(pytesseract, lang or settings.tesseract_lang, local_tessdata_dir)

    # Label tables are often multi-column; try multiple page segmentation modes and pick best output.
    def _score(s: str) -> int:
        s2 = (s or "").strip()
        if not s2:
            return 0
        digits = sum(ch.isdigit() for ch in s2)
        low = s2.lower()
        hints = 0
        for kw in (
            "kcal",
            "enerji",
            "energy",
            "yağ",
            "yag",
            "karbonhidrat",
            "protein",
            "şeker",
            "seker",
            "tuz",
            "sodyum",
        ):
            if kw in low:
                hints += 20
        return len(s2) + digits * 2 + hints

    base = f"--oem 3 --dpi 300{tessdata_flag}"
    best_text = ""
    best_score = 0
    for psm in (6, 4, 11):
        cfg = f"{base} --psm {psm}"
        try:
            txt = pytesseract.image_to_string(pre, lang=ocr_lang, config=cfg)
        except Exception:
            txt = ""
        sc = _score(txt)
        if sc > best_score:
            best_score = sc
            best_text = txt

    if best_text.strip():
        return best_text

    # Last resort: try English even if requested differs.
    if ocr_lang != "eng":
        for psm in (6, 4, 11):
            cfg = f"{base} --psm {psm}"
            try:
                txt = pytesseract.image_to_string(pre, lang="eng", config=cfg)
            except Exception:
                txt = ""
            sc = _score(txt)
            if sc > best_score:
                best_score = sc
                best_text = txt
        if best_text.strip():
            return best_text

    return ""




