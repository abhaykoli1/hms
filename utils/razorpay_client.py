import razorpay
import os

client = razorpay.Client(
    auth=(os.getenv("rzp_live_SAtcVq3nE15AyV"), os.getenv("crf7HFjHmjl7FUgrKY304qGt"))
)
