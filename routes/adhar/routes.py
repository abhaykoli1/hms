import cv2
from fastapi.responses import JSONResponse
import pytesseract
import re
import numpy as np
from fastapi import APIRouter,UploadFile, File
from aadhaar_service import AadhaarService as aadhaar
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


@router.post("/verify-otp")
def verify(reference_id: str, otp: str):
    return aadhaar.verify_otp(reference_id, otp)