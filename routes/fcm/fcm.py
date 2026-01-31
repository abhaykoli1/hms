import firebase_admin
from firebase_admin import credentials, messaging

# init once only
if not firebase_admin._apps:
    cred = credentials.Certificate("utils/healthcare-hms-1fdc42c427ae.json")
    firebase_admin.initialize_app(cred)


def send_push(token: str, title: str, body: str, data: dict | None = None):
    try:
        message = messaging.Message(
            token=token,
            notification=messaging.Notification(
                title=title,
                body=body,
            ),
            data=data or {}
        )

        response = messaging.send(message)
        print("✅ FCM sent:", response)
        return response

    except Exception as e:
        print("❌ FCM error:", e)
        return None
