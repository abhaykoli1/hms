import cv2
from fastapi.responses import JSONResponse
import pytesseract
import re
import numpy as np
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException

from aadhaar_service import AadhaarService as aadhaar
from core.dependencies import get_current_user
from models import NurseProfile

# 🔥 IMPORTANT: Explicit Tesseract path (SERVER FIX)
pytesseract.pytesseract.tesseract_cmd = "/usr/bin/tesseract"

router = APIRouter(prefix="/adhar", tags=["adhar"])


# ============================================================
# 🔥 ROBUST AADHAAR OCR (DEBUG + FALLBACK INCLUDED)
# ============================================================
def extract_aadhaar_from_image(image_bytes):
    try:
        # Convert bytes → numpy array
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if img is None:
            print("❌ Image decode failed")
            return None

        h, w, _ = img.shape

        # ---------- AUTO-ROTATE IF NEEDED ----------
        if h < w:  # landscape image fix
            img = cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)
            h, w, _ = img.shape

        # ---------- SMART CROP (AADHAAR ZONE) ----------
        crop = img[int(h * 0.55): h, int(w * 0.10): int(w * 0.90)]

        # 🔥 DEBUG — Save images on server (CHECK THESE)
        cv2.imwrite("/tmp/aadhaar_original.jpg", img)
        cv2.imwrite("/tmp/aadhaar_crop.jpg", crop)

        # ---------- PREPROCESSING (STRONG) ----------
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        gray = cv2.normalize(gray, None, 0, 255, cv2.NORM_MINMAX)
        gray = cv2.medianBlur(gray, 5)

        thresh = cv2.adaptiveThreshold(
            gray, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY_INV,
            15, 3
        )

        # ---------- BEST TESSERACT CONFIG ----------
        custom_config = r"""
        --oem 3
        --psm 6
        -c tessedit_char_whitelist=0123456789
        """

        text = pytesseract.image_to_string(thresh, config=custom_config)

        print("🔍 OCR RAW:\n", text)

        # Keep only digits
        digits = re.sub(r"[^0-9]", "", text)
        print("🔢 CLEAN DIGITS:", digits)

        # Find 12-digit Aadhaar anywhere in string
        match = re.search(r"\d{12}", digits)
        if match:
            return match.group()

        # --------- FALLBACK: Try full image OCR if crop fails ---------
        print("⚠️ Crop OCR failed, trying full image...")

        full_gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        full_text = pytesseract.image_to_string(
            full_gray, config=custom_config
        )

        print("🔍 FULL IMAGE OCR:", full_text)

        full_digits = re.sub(r"[^0-9]", "", full_text)
        match = re.search(r"\d{12}", full_digits)

        if match:
            return match.group()

        return None

    except Exception as e:
        print("❌ OCR ERROR:", str(e))
        return None


# ============================================================
# 🔹 EXTRACT AADHAAR API
# ============================================================
@router.post("/extract-aadhaar")
async def extract_aadhaar(file: UploadFile = File(...)):
    contents = await file.read()

    aadhaar_number = extract_aadhaar_from_image(contents)

    if aadhaar_number:
        return {"aadhaar_number": aadhaar_number}

    return JSONResponse(
        status_code=404,
        content={"message": "Aadhaar number not found"}
    )


# ============================================================
# 🔹 GENERATE OTP
# ============================================================
@router.post("/generate-otp")
def generate(aadhaar_number: str):
    return aadhaar.generate_otp(aadhaar_number)


# ============================================================
# 🔹 VERIFY OTP
# ============================================================
@router.post("/verify-otp")
def verify(reference_id: str, otp: str, user=Depends(get_current_user)):
    try:
        nurse = NurseProfile.objects.get(user=user)
        result = aadhaar.verify_otp(reference_id, otp)

        if not result or "data" not in result:
            raise HTTPException(
                status_code=500,
                detail="Invalid response from Aadhaar service"
            )

        data = result.get("data", {})

        # ===== ONLY VALID CASE =====
        if data.get("status") == "VALID":
            nurse.aadhaar_verified = True
            nurse.aadharData = {
                "reference_id": data.get("reference_id"),
                "name": data.get("name"),
                "date_of_birth": data.get("date_of_birth"),
                "gender": data.get("gender"),
                "full_address": data.get("full_address"),
                "care_of": data.get("care_of"),
                "photo": data.get("photo"),
            }
            nurse.save()

            return {
                "success": True,
                "message": "Aadhaar Verified Successfully",
                "data": nurse.aadharData,
            }

        # ===== ERROR CASES =====
        msg = data.get("message", "Verification failed")

        error_map = {
            "Invalid OTP": ("INVALID_OTP", "OTP is incorrect"),
            "OTP Expired": ("OTP_EXPIRED", "OTP has expired, please resend"),
            "Request under process, please try after 30 seconds": (
                "IN_PROGRESS",
                "Please wait 30 seconds and try again",
            ),
            "Invalid Reference Id": (
                "INVALID_REF_ID",
                "Session expired, please resend OTP",
            ),
        }

        code, message = error_map.get(msg, ("FAILED", msg))

        return {
            "success": False,
            "error_code": code,
            "message": message,
        }

    except NurseProfile.DoesNotExist:
        raise HTTPException(status_code=404, detail="Nurse profile not found")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
