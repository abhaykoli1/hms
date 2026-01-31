import firebase_admin
from firebase_admin import credentials, messaging
import logging
# init once only
if not firebase_admin._apps:
    cred = credentials.Certificate("utils/healthcare-hms-1fdc42c427ae.json")
    firebase_admin.initialize_app(cred)

logger = logging.getLogger("fcm")


def send_bulk_push(tokens: list[str], title: str, body: str, data: dict | None = None):

    try:
        if not tokens:
            logger.warning("⚠️ No tokens provided for push notification")
            return

        logger.info(f"🚀 Sending push to {len(tokens)} users")

        message = messaging.MulticastMessage(
            tokens=tokens,
            notification=messaging.Notification(
                title=title,
                body=body,
            ),
            data=data or {}
        )

        response = messaging.send_multicast(message)

        # ✅ summary logs
        logger.info(f"✅ Success count: {response.success_count}")
        logger.info(f"❌ Failure count: {response.failure_count}")

        # 🔥 per token result
        for idx, resp in enumerate(response.responses):
            if resp.success:
                logger.info(f"✔ Token success: {tokens[idx]}")
            else:
                logger.error(
                    f"❌ Token failed: {tokens[idx]} | Error: {resp.exception}"
                )

        return response

    except Exception as e:
        logger.exception(f"🔥 FCM bulk push crashed: {str(e)}")
        return None