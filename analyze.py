import json
import os
from datetime import datetime, date
from dotenv import load_dotenv
import anthropic

load_dotenv()

client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

with open("transactions.json", "r", encoding="utf-8") as f:
    data = json.load(f)

all_txns = []
for account in data["accounts"]:
    for txn in account["txns"]:
        all_txns.append({
            "date": txn.get("date", "")[:10],
            "amount": abs(txn.get("chargedAmount", 0)),
            "description": txn.get("description", ""),
            "type": "הוצאה" if txn.get("chargedAmount", 0) < 0 else "הכנסה",
        })

all_txns.sort(key=lambda x: x["date"])

txns_text = "\n".join([
    f"{t['date']} | {t['type']} | ₪{t['amount']:.0f} | {t['description']}"
    for t in all_txns
])

today = date.today().strftime("%d/%m/%Y")
current_month = date.today().strftime("%m/%Y")

print("🔄 שולח לניתוח Claude...")

message = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=4096,
    messages=[
        {
            "role": "user",
            "content": f"""אתה סוכן פיננסי אישי חכם. נתח את הנתונים הבאים ותן דוח מלא בעברית.

היום: {today}
החודש הנוכחי: {current_month}

עסקאות:
{txns_text}

תן דוח מפורט שכולל:

1. **סיכום חודש נוכחי** - כמה הוצאתי עד היום
2. **קטגוריות** - סווג את ההוצאות (מזון, תחבורה, בידור, שירותים, קניות, אחר) וכמה בכל קטגוריה
3. **הוצאות קבועות** - זהה הוצאות שחוזרות כל חודש (שכר דירה, ביטוח, מנויים וכו') והערך אם הן צפויות לחזור החודש
4. **תחזית לסוף החודש** - בהתבסס על הדפוס, כמה אני צפוי להוציא סה"כ החודש
5. **איפה לקצץ** - 3 המלצות ספציפיות עם חיסכון משוער לכל אחת
6. **ציון פיננסי** - תן לי ציון 1-10 על ניהול ההוצאות עם הסבר קצר

פורמט את הדוח בצורה ברורה עם כותרות ואימוג'ים."""
        }
    ]
)

report = message.content[0].text

print("\n" + "="*50)
print(report)
print("="*50)

with open("report.txt", "w", encoding="utf-8") as f:
    f.write(f"דוח פיננסי - {today}\n")
    f.write("="*50 + "\n")
    f.write(report)

print("\n✅ הדוח נשמר ב-report.txt")
