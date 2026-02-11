import requests
import time
import os
from dotenv import load_dotenv

load_dotenv()


class TokenManager:
    def __init__(self):
        self.api_key = "key_test_eb5f20fd9869467a8dffe81154ff1615"
        self.api_secret = "secret_test_7c8e6321df034a3499b1758a94c7da77"

        self.base_url = "https://api.sandbox.co.in/authenticate"

        self.token = None
        self.expiry = 0  # timestamp

    # 🔥 check token valid or not
    def _is_token_valid(self):
        return self.token and time.time() < self.expiry

    # 🔥 generate new token
    def _generate_token(self):
        print("🔄 Generating new access token...")

        headers = {
            "x-api-key": self.api_key,
            "x-api-secret": self.api_secret,
            "x-api-version": "1.0.0",
            "Content-Type": "application/json",
        }

        response = requests.post(self.base_url, headers=headers)
        data = response.json()

        self.token = data["data"]["access_token"]

        # assume token valid for 1 hour (change if API provides expiry)
        self.expiry = time.time() + 3600

        print("✅ Token generated successfully")

    # 🔥 public method (use everywhere)
    def get_token(self):
        if not self._is_token_valid():
            self._generate_token()

        return self.token


# global instance (singleton style)
token_manager = TokenManager()

