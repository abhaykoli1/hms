import cv2
from fastapi.responses import JSONResponse
import pytesseract
import re
import numpy as np
from fastapi import APIRouter,UploadFile, File,Depends, HTTPException, Request,status
from aadhaar_service import AadhaarService as aadhaar

from core.dependencies import get_current_user
from models import NurseProfile
router = APIRouter(prefix="/adhar")

def extract_aadhaar_from_image(image_bytes):
    # bytes → numpy array
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    # preprocessing
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (5, 5), 0)

    thresh = cv2.adaptiveThreshold(
        gray, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY, 11, 2
    )

    # OCR
    text = pytesseract.image_to_string(thresh)

    # regex for 12 digit
    pattern = r"\d{4}\s?\d{4}\s?\d{4}"
    match = re.search(pattern, text)

    if match:
        return match.group().replace(" ", "")
    return None


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

@router.post("/generate-otp")
def generate(aadhaar_number: str):
    return aadhaar.generate_otp(aadhaar_number)


from fastapi import HTTPException

@router.post("/verify-otp")
def verify(reference_id: str, otp: str, user = Depends(get_current_user)):
    try:
        nurse = NurseProfile.objects.get(user=user)
        result = aadhaar.verify_otp(reference_id, otp)

        # Agar API hi fail ho gayi
        if not result or "data" not in result:
            raise HTTPException(status_code=500, detail="Invalid response from Aadhaar service")

        data = result.get("data", {})

        # ========== ONLY VALID CASE (AS YOU SAID) ==========
        if data.get("status") == "VALID":
           
            nurse.aadhaar_verified =True
            nurse.aadharData = {
                    "reference_id": data.get("reference_id"),
                    "name": data.get("name"),
                    "date_of_birth": data.get("date_of_birth"),
                    "gender": data.get("gender"),
                    "full_address": data.get("full_address"),
                    "care_of": data.get("care_of"),
                    "photo": data.get("photo"),  # base64 image
                }
            nurse.save()
            return {
                "success": True,
                "message": "Aadhaar Verified Successfully",
                "data": {
                    "reference_id": data.get("reference_id"),
                    "name": data.get("name"),
                    "date_of_birth": data.get("date_of_birth"),
                    "gender": data.get("gender"),
                    "full_address": data.get("full_address"),
                    "care_of": data.get("care_of"),
                    "photo": data.get("photo"),  # base64 image
                },
            }

        # ========== ERROR CASE HANDLING ==========
        msg = data.get("message", "Verification failed")

        # Map friendly error messages
        error_map = {
            "Invalid OTP": ("INVALID_OTP", "OTP is incorrect"),
            "OTP Expired": ("OTP_EXPIRED", "OTP has expired, please resend"),
            "Request under process, please try after 30 seconds": (
                "IN_PROGRESS",
                "Please wait 30 seconds and try again",
            ),
            "Invalid Reference Id": ("INVALID_REF_ID", "Session expired, please resend OTP"),
        }

        code, message = error_map.get(msg, ("FAILED", msg))

        return {
            "success": False,
            "error_code": code,
            "message": message,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
