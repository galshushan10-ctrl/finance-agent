import json
import os
import requests
from datetime import datetime, date
from dotenv import load_dotenv
import anthropic

load_dotenv()

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
DASHBOARD_URL = os.environ.get("DASHBOARD_URL", "")

def send_telegram(text, button_url=None):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
    }
    if button_url:
        payload["reply_markup"] = {
            "inline_keyboard": [[{
                "text": "🖥️ פתח דשבורד מלא",
                "url": button_url
            }]]
        }
    response = requests.post(url, json=payload)
    print("תגובה מטלגרם:", response.json())

def load_transactions():
    with open("transactions.json", "r", encoding="utf-8") as f:
        return json.load(f)

def build_report(data, budget=8000):
    all_txns = []
    for account in data["accounts"]:
        for txn in account["txns"]:
            all_txns.append(txn)

    current_month = date.today().strftime("%Y-%m")
    this_month_txns = [
        t for t in all_txns
        if t.get("date", "")[:7] == current_month and t.get("chargedAmount", 0) < 0
    ]

    total_spent = sum(abs(t["chargedAmount"]) for t in this_month_txns)
    remaining = max(0, budget - total_spent)
    today_day = date.today().day
    days_in_month = 30
    days_left = days_in_month - today_day
    daily_avg = total_spent / today_day if today_day > 0 else 0
    estimated = daily_avg * days_in_month
    pct = (total_spent / budget * 100) if budget > 0 else 0

    status = "✅ בתקציב" if estimated <= budget else "⚠️ צפויה חריגה"
    progress_bar = "█" * int(pct / 10) + "░" * (10 - int(pct / 10))

    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    txns_text = "\n".join([
        f"{t['date'][:10]} | ₪{abs(t['chargedAmount']):.0f} | {t['description']}"
        for t in this_month_txns[-20:]
    ])

    ai = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=500,
        messages=[{
            "role": "user",
            "content": f"""בהתבסס על העסקאות האלו, תן 2 המלצות קצרות לחיסכון (שורה אחת כל אחת):
{txns_text}

פורמט: • המלצה (חיסכון משוער: ₪X)"""
        }]
    ).content[0].text

    today_str = date.today().strftime("%d/%m/%Y")

    message = f"""📊 <b>דוח בוקר — {today_str}</b>
━━━━━━━━━━━━━━━━━━━
💸 הוצאתי החודש: <b>₪{total_spent:,.0f}</b>
🎯 יעד חודשי: ₪{budget:,}
✅ נותר: <b>₪{remaining:,.0f}</b> ({days_left} ימים)
📈 תחזית לסוף חודש: ₪{estimated:,.0f} — {status}

{progress_bar} {pct:.0f}%

💡 <b>המלצות:</b>
{ai}"""

    return message

def main():
    print("🔄 מכין דוח טלגרם...")
    data = load_transactions()
    msg = build_report(data)
    send_telegram(msg, button_url=DASHBOARD_URL if DASHBOARD_URL else None)
    print("✅ הדוח נשלח לטלגרם!")

if __name__ == "__main__":
    main()
