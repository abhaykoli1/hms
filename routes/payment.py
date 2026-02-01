from fastapi import APIRouter,HTTPException,  Request, Header
from models import UserJoiningFees, AllPaymentsHistory, User
from utils.razorpay_client import client
from pydantic import BaseModel
import os
import hashlib, hmac, json, os

router = APIRouter(prefix="/payments", tags=["payments"])

class CreateOrderRequest(BaseModel):
    userId: str

@router.post("/create-order")
def create_order(body: CreateOrderRequest):
    user = User.objects.get(id=body.userId)
    joining_fee = UserJoiningFees.objects.first()

    order = client.order.create({
        "amount": joining_fee.amount * 100,
        "currency": "INR",
        "payment_capture": 1
    })

    # 🔥 VERY IMPORTANT: Save order as CREATED
    AllPaymentsHistory(
        user=user,
        amount=joining_fee,
        status="created",
        order_id=order["id"]
    ).save()

    return {
        "order_id": order["id"],
        "amount": order["amount"],
        "currency": "INR",
        "key": os.getenv("RAZORPAY_KEY_ID")
    }

@router.post("/webhook")
async def razorpay_webhook(
    request: Request,
    x_razorpay_signature: str = Header(None)
):
    body = await request.body()
    secret = "jtXp6zgW2QYTqT_"

    expected_signature = hmac.new(
        secret.encode(),
        body,
        hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(expected_signature, x_razorpay_signature):
        raise HTTPException(status_code=400, detail="Invalid signature")

    payload = json.loads(body)
    event = payload["event"]
    payment = payload["payload"]["payment"]["entity"]

    order_id = payment["order_id"]
    payment_id = payment["id"]

    payment_record = AllPaymentsHistory.objects(order_id=order_id).first()

    if not payment_record:
        return {"status": "order_not_found"}

    if event == "payment.captured":
        payment_record.update(
            status="success",
            payment_id=payment_id
        )

    elif event == "payment.failed":
        payment_record.update(
            status="failed",
            payment_id=payment_id
        )

    return {"status": "ok"}