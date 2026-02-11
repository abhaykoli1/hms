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


router = APIRouter(prefix="/adhar", tags=["adhar"])


# ============================================================
# 🔥 ROBUST AADHAAR OCR (FINAL VERSION)


import os
import re
import requests

def ocr_space_file(filename: str, overlay=False, api_key=None, language="eng"):
    """
    OCR.space API request with local file.
    """

    if not api_key:
        api_key = "K84530418188957"

    payload = {
        "isOverlayRequired": overlay,
        "apikey": api_key,
        "language": language,
    }

    with open(filename, "rb") as f:
        r = requests.post(
            "https://api.ocr.space/parse/image",
            files={"file": f},
            data=payload,
            timeout=30,
        )

    return r.json()


def extract_aadhaar_from_ocr_result(ocr_result: dict) -> str | None:
    """
    Extract 12-digit Aadhaar from OCR result
    """
    try:
        if "ParsedResults" not in ocr_result or not ocr_result["ParsedResults"]:
            print("OCR API ERROR:", ocr_result)
            return None

        text = ocr_result["ParsedResults"][0].get("ParsedText", "")
        print("OCR TEXT:", text)

        digits = re.sub(r"[^0-9]", "", text)
        match = re.search(r"\d{12}", digits)

        return match.group() if match else None

    except Exception as e:
        print("OCR PARSE ERROR:", str(e))
        return None


# ============================================================
# 🔹 EXTRACT AADHAAR API
# ============================================================
UPLOAD_TMP_DIR = "/tmp"

@router.post("/extract-aadhaar")
async def extract_aadhaar(file: UploadFile = File(...)):
    # 1️⃣ Save uploaded file temporarily
    file_path = os.path.join(UPLOAD_TMP_DIR, file.filename)

    with open(file_path, "wb") as f:
        f.write(await file.read())

    print("Saved file to:", file_path)

    # 2️⃣ Call OCR.Space
    ocr_result = ocr_space_file(
        filename=file_path,
        language="eng",
        api_key=os.getenv("OCR_API_KEY", "helloworld"),
    )

    # 3️⃣ Extract Aadhaar
    aadhaar_number = extract_aadhaar_from_ocr_result(ocr_result)

    # 4️⃣ Clean up temp file (optional)
    try:
        os.remove(file_path)
    except:
        pass

    if aadhaar_number:
        return {
            "aadhaar_number": aadhaar_number,
            "method": "ocr_space",
        }

    return JSONResponse(
        status_code=404,
        content={"message": "Aadhaar number not found"},
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
