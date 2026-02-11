import os
import cv2
import re
import numpy as np
import pytesseract

from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from fastapi.responses import JSONResponse

from aadhaar_service import AadhaarService as aadhaar
from core.dependencies import get_current_user
from models import NurseProfile

# ===========================
# 🔥 TESSERACT CONFIG (AWS FIX)
# ===========================
pytesseract.pytesseract.tesseract_cmd = "/usr/bin/tesseract"
os.environ["TESSDATA_PREFIX"] = "/usr/share/tesseract-ocr/5/tessdata/"

router = APIRouter(prefix="/adhar", tags=["adhar"])


# ============================================================
# 🔥 ROBUST AADHAAR OCR (FINAL VERSION)
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

        # ---------- AUTO ROTATE IF LANDSCAPE ----------
        if w > h:
            img = cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)
            h, w, _ = img.shape

        # ===================================================
        # ✅ NEW CROP (WORKS FOR YOUR SHARED AADHAAR IMAGE)
        # Bottom 30% height + center 80% width
        # ===================================================
        crop = img[int(h * 0.70): h, int(w * 0.10): int(w * 0.90)]

        # 🔥 DEBUG — save images on server (check these)
        cv2.imwrite("/tmp/aadhaar_original.jpg", img)
        cv2.imwrite("/tmp/aadhaar_crop.jpg", crop)

        # ---------- PREPROCESSING (BEST FOR PRINTED NUMBERS) ----------
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)

        # Increase contrast
        gray = cv2.normalize(gray, None, 0, 255, cv2.NORM_MINMAX)

        # Smooth noise but keep edges
        gray = cv2.GaussianBlur(gray, (5, 5), 0)

        # Binarization (best for black printed digits)
        _, thresh = cv2.threshold(
            gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
        )

        # Optional: upscale for better OCR accuracy
        thresh = cv2.resize(thresh, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)

        # ---------- BEST TESSERACT CONFIG ----------
        custom_config = r"""
        --oem 3
        --psm 6
        -l eng+hin
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

    return {
        "aadhaar_number": aadhaar_number,
        "auto_detected": bool(aadhaar_number),
        "message": (
            "Aadhaar detected automatically"
            if aadhaar_number
            else "Could not auto-detect Aadhaar. Please enter manually."
        ),
    }


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
