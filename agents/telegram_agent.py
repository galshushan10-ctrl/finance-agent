import os
import requests
from .base_agent import BaseAgent
from .whatsapp_sender import send_whatsapp
from datetime import date

class TelegramAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Noa",
            role="שגרירת דוחות יומיים",
            system_prompt="""את Noa, אחראית על שליחת דוחות פיננסיים יומיים בטלגרם.
תפקידך: לקחת נתוני ניתוח ולהפוך אותם להודעת טלגרם קצרה, ברורה ומעוצבת.
עקרונות:
- הודעה קצרה — עד 20 שורות
- תמיד בעברית
- השתמשי באימוג'ים לבהירות
- הדגישי את הדבר הכי חשוב שצריך לדעת היום
- סיימי תמיד עם פעולה אחת שאפשר לעשות עכשיו"""
        )
        self.token = os.environ.get("TELEGRAM_BOT_TOKEN")
        self.chat_id = os.environ.get("TELEGRAM_CHAT_ID")
        self.dashboard_url = os.environ.get("DASHBOARD_URL", "")

    def format_message(self, analysis: dict) -> str:
        today = date.today().strftime("%d/%m/%Y")
        total = analysis["total_this_month"]
        estimated = analysis["estimated_total"]
        budget = analysis["budget"]
        remaining = max(0, budget - total)
        pct = (total / budget * 100) if budget > 0 else 0
        days_left = 30 - date.today().day
        status = "✅ בתקציב" if estimated <= budget else "⚠️ צפויה חריגה"
        progress = "█" * int(pct / 10) + "░" * (10 - int(pct / 10))

        summary = self.think(f"""קח את הניתוח הזה ותמצה רק את 2 ההמלצות הכי חשובות בשורה אחת כל אחת:
{analysis['report']}

פורמט: • המלצה קצרה (חיסכון: ₪X)""", max_tokens=200)

        # הוצאות קבועות צפויות שעוד לא ירדו
        pending = analysis.get("pending_recurring", [])
        pending_total = analysis.get("pending_total", 0)

        pending_lines = ""
        if pending:
            pending_lines = "\n\n📌 <b>הוצאות קבועות צפויות החודש:</b>\n"
            for r in pending[:6]:
                pending_lines += f"  • {r['description']} — ₪{r['avg_amount']:,.0f} (בסביבות יום {r['expected_day']})\n"
            pending_lines += f"  <b>סה\"כ צפוי: ₪{pending_total:,.0f}</b>"

        return f"""📊 <b>דוח בוקר — {today}</b>
━━━━━━━━━━━━━━━━━━━
💸 הוצאות עד היום: <b>₪{total:,.0f}</b>
🎯 יעד: ₪{budget:,} | נותר: <b>₪{remaining:,.0f}</b>
📅 {days_left} ימים | תחזית (כולל קבועות): ₪{estimated:,.0f} — {status}

{progress} {pct:.0f}%
{pending_lines}

💡 <b>לפעול היום:</b>
{summary}"""

    def send(self, analysis: dict):
        message = self.format_message(analysis)
        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": message,
            "parse_mode": "HTML",
        }
        if self.dashboard_url:
            payload["reply_markup"] = {
                "inline_keyboard": [[{
                    "text": "🖥️ פתח דשבורד מלא",
                    "url": self.dashboard_url
                }]]
            }
        response = requests.post(url, json=payload)
        send_whatsapp(message)
        return response.json().get("ok", False)

    def send_raw(self, text: str):
        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        payload = {"chat_id": self.chat_id, "text": text, "parse_mode": "HTML"}
        response = requests.post(url, json=payload)
        send_whatsapp(text)
        return response.json().get("ok", False)
