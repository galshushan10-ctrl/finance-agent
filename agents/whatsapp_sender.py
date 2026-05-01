import os
import requests
from dotenv import load_dotenv

load_dotenv()

def send_whatsapp(text: str):
    instance = os.environ.get("GREENAPI_INSTANCE_ID", "").strip()
    token = os.environ.get("GREENAPI_TOKEN", "").strip()
    phone = os.environ.get("WHATSAPP_PHONE", "").strip()

    if not all([instance, token, phone]):
        return False

    # WhatsApp לא תומך ב-HTML — נמחק תגיות
    import re
    clean = re.sub(r'<[^>]+>', '', text)
    clean = clean.replace('&quot;', '"').replace('&amp;', '&')

    url = f"https://api.green-api.com/waInstance{instance}/sendMessage/{token}"
    payload = {"chatId": f"{phone}@c.us", "message": clean}
    r = requests.post(url, json=payload)
    return r.status_code == 200
