import razorpay
import os

client = razorpay.Client(
    auth=(os.getenv("rzp_live_SAvvEOWMG4hVKT"), os.getenv("7t1yBuHX3NbOufGjqY2VBiY5"))
)
