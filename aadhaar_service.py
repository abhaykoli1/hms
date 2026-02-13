import requests
import os
from token_manager import token_manager


BASE_URL = "https://api.sandbox.co.in"


class AadhaarService:

    def __init__(self):
        self.api_key = "key_live_596d1cc1a8ec4cf4972d2a3847649041"
        self.api_secret = "secret_live_fdab340fc4704fd2bb18295563b158cc"

    def _headers(self):
        token = token_manager.get_token()

        return {
            "Authorization": token,
            "x-api-key": self.api_key,
            "Content-Type": "application/json"
        }

    # 🔥 STEP 1 → Generate OTP
    def generate_otp(self, aadhaar_number, reason="Verification"):

        url = f"{BASE_URL}/kyc/aadhaar/okyc/otp"

        payload = {
            "entity": "in.co.sandbox.kyc.aadhaar.okyc.otp.request",
            "aadhaar_number": aadhaar_number,
            "consent": "Y",
            "reason": reason
        }

        res = requests.post(url, headers=self._headers(), json=payload)

        return res.json()

    # 🔥 STEP 2 → Verify OTP
    def verify_otp(self, reference_id, otp):

        url = f"{BASE_URL}/kyc/aadhaar/okyc/otp/verify"

        payload = {
            "entity": "in.co.sandbox.kyc.aadhaar.okyc.request",
            "reference_id": reference_id,
            "otp": otp
        }

        res = requests.post(url, headers=self._headers(), json=payload)

        return res.json()
