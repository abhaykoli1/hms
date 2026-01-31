import firebase_admin
from firebase_admin import credentials, messaging
import logging
# init once only
if not firebase_admin._apps:
    cred = credentials.Certificate("utils/healthcare-hms-1fdc42c427ae.json")
    firebase_admin.initialize_app(cred)

logger = logging.getLogger("fcm")


def send_bulk_push(tokens, title, body, data=None):
    try:
        if not tokens:
            print("⚠️ No tokens")
            return

        messages = [
            messaging.Message(
                token=token,
                notification=messaging.Notification(
                    title=title,
                    body=body,
                ),
                data=data or {}
            )
            for token in tokens
        ]

        response = messaging.send_all(messages)

        print("✅ Success:", response.success_count)
        print("❌ Failed:", response.failure_count)

        for idx, resp in enumerate(response.responses):
            if resp.success:
                print(f"✔ Sent: {tokens[idx]}")
            else:
                print(f"❌ Failed: {tokens[idx]} | {resp.exception}")

        return response

    except Exception as e:
        print("🔥 FCM bulk push crashed:", e)
        return None
