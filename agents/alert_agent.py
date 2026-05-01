import os
import json
import requests
from datetime import date, datetime, timedelta
from collections import defaultdict
from .base_agent import BaseAgent
from .whatsapp_sender import send_whatsapp
from dotenv import load_dotenv

load_dotenv()

BUDGET = 32000

class AlertAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Tal",
            role="סוכן התראות פיננסיות",
            system_prompt="""אתה Tal, סוכן התראות פיננסי חכם.
תפקידך: לזהות אירועים חריגים ולשלוח התראות קצרות וברורות בעברית.
- הודעות קצרות — עד 8 שורות
- ישיר ולעניין
- תמיד כלול פעולה מומלצת"""
        )
        self.token = os.environ.get("TELEGRAM_BOT_TOKEN")
        self.chat_id = os.environ.get("TELEGRAM_CHAT_ID")

    def send(self, text: str):
        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        requests.post(url, json={"chat_id": self.chat_id, "text": text, "parse_mode": "HTML"})
        send_whatsapp(text)

    # ── 1. התראת הוצאה גדולה ──────────────────────────────

    def check_large_transactions(self, transactions: list, threshold: int = 500):
        """שולח התראה על כל הוצאה מעל הסף שהתרחשה בשעה האחרונה"""
        one_hour_ago = datetime.now() - timedelta(hours=24)
        today = date.today().strftime("%Y-%m-%d")

        new_large = [
            t for t in transactions
            if t['amount'] >= threshold and t['date'] == today
        ]

        for txn in new_large:
            msg = f"""⚡ <b>הוצאה גדולה זוהתה</b>
━━━━━━━━━━━━━━
💸 <b>₪{txn['amount']:,.0f}</b>
📝 {txn['description']}
📅 {txn['date']}
━━━━━━━━━━━━━━
בדוק שזו הוצאה מוכרת."""
            self.send(msg)

        return len(new_large)

    # ── 2. התראת תקציב ────────────────────────────────────

    def check_budget(self, transactions: list):
        """שולח התראה כשמגיעים ל-70%, 85%, 95% מהתקציב"""
        current_month = date.today().strftime("%Y-%m")
        total = sum(t['amount'] for t in transactions if t['date'][:7] == current_month)
        pct = (total / BUDGET) * 100

        thresholds = {70: "🟡", 85: "🟠", 95: "🔴"}
        state_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".budget_alerts_sent.json")

        try:
            with open(state_file) as f:
                sent = json.load(f)
        except:
            sent = {}

        month_key = date.today().strftime("%Y-%m")
        sent_this_month = sent.get(month_key, [])
        sent_alert = False

        for threshold, emoji in sorted(thresholds.items(), reverse=True):
            if pct >= threshold and threshold not in sent_this_month:
                days_left = 30 - date.today().day
                remaining = max(0, BUDGET - total)
                msg = f"""{emoji} <b>התראת תקציב — {pct:.0f}%</b>
━━━━━━━━━━━━━━
💸 הוצאת: ₪{total:,.0f} מתוך ₪{BUDGET:,}
✅ נותר: ₪{remaining:,.0f}
📅 {days_left} ימים לסוף חודש
━━━━━━━━━━━━━━
💡 מומלץ: ₪{remaining/days_left:,.0f} ליום מקסימום"""
                self.send(msg)
                sent_this_month.append(threshold)
                sent_alert = True
                break

        if sent_alert:
            sent[month_key] = sent_this_month
            with open(state_file, "w") as f:
                json.dump(sent, f)

        return pct

    # ── 3. סיכום שבועי ────────────────────────────────────

    def weekly_summary(self, transactions: list):
        """סיכום שבועי — נשלח ביום ראשון"""
        today = date.today()
        week_ago = (today - timedelta(days=7)).strftime("%Y-%m-%d")
        today_str = today.strftime("%Y-%m-%d")
        prev_week_start = (today - timedelta(days=14)).strftime("%Y-%m-%d")
        prev_week_end = (today - timedelta(days=7)).strftime("%Y-%m-%d")

        this_week = [t for t in transactions if week_ago <= t['date'] <= today_str]
        prev_week = [t for t in transactions if prev_week_start <= t['date'] < prev_week_end]

        this_total = sum(t['amount'] for t in this_week)
        prev_total = sum(t['amount'] for t in prev_week)
        diff = this_total - prev_total
        diff_pct = (diff / prev_total * 100) if prev_total > 0 else 0

        # קטגוריה עם ההוצאה הגבוהה ביותר השבוע
        top = sorted(this_week, key=lambda x: x['amount'], reverse=True)[:3]
        top_lines = "\n".join([f"  • {t['description']} — ₪{t['amount']:,.0f}" for t in top])

        trend = "📈 גבוה יותר" if diff > 0 else "📉 נמוך יותר"
        trend_color = "⚠️" if diff > 0 else "✅"

        ai_tip = self.think(f"""בהתבסס על הוצאות השבוע, תן טיפ קצר אחד לחיסכון (שורה אחת):
{chr(10).join([f"{t['date']} | ₪{t['amount']:.0f} | {t['description']}" for t in this_week])}

פורמט: 💡 טיפ קצר""", max_tokens=100)

        msg = f"""📅 <b>סיכום שבועי</b>
━━━━━━━━━━━━━━
💸 הוצאות השבוע: <b>₪{this_total:,.0f}</b>
{trend_color} לעומת שבוע קודם: {trend} ב-{abs(diff_pct):.0f}% (₪{abs(diff):,.0f})

🏆 ההוצאות הגדולות:
{top_lines}
━━━━━━━━━━━━━━
{ai_tip}"""
        self.send(msg)

    # ── 6. זיהוי קטגוריה חריגה ───────────────────────────

    def check_category_anomaly(self, transactions: list):
        """התראה אם קטגוריה גבוהה ב-40%+ מהממוצע"""
        current_month = date.today().strftime("%Y-%m")
        past_months = sorted(set(
            t['date'][:7] for t in transactions
            if t['date'][:7] < current_month
        ))[-3:]

        this_month_txns = [t for t in transactions if t['date'][:7] == current_month]

        if not past_months or not this_month_txns:
            return

        # קיבוץ לפי תיאור (קטגוריה פשוטה)
        def group_by_desc(txns):
            groups = defaultdict(float)
            for t in txns:
                groups[t['description']] += t['amount']
            return groups

        current_groups = group_by_desc(this_month_txns)

        past_groups = defaultdict(list)
        for m in past_months:
            month_txns = [t for t in transactions if t['date'][:7] == m]
            for desc, total in group_by_desc(month_txns).items():
                past_groups[desc].append(total)

        anomalies = []
        for desc, current_total in current_groups.items():
            if desc not in past_groups:
                continue
            avg = sum(past_groups[desc]) / len(past_groups[desc])
            if avg > 200 and current_total > avg * 1.4:
                anomalies.append({
                    "desc": desc,
                    "current": current_total,
                    "avg": avg,
                    "pct": ((current_total - avg) / avg) * 100
                })

        if not anomalies:
            return

        anomalies.sort(key=lambda x: x['pct'], reverse=True)
        lines = "\n".join([
            f"  • {a['desc']}: ₪{a['current']:,.0f} (ממוצע ₪{a['avg']:,.0f}, +{a['pct']:.0f}%)"
            for a in anomalies[:3]
        ])

        msg = f"""⚠️ <b>הוצאות חריגות זוהו</b>
━━━━━━━━━━━━━━
הוצאות אלו גבוהות ב-40%+ מהרגיל:

{lines}
━━━━━━━━━━━━━━
💡 כדאי לבדוק אם ניתן לקצץ."""
        self.send(msg)

    # ── 7. טיפ חיסכון שבועי ──────────────────────────────

    def weekly_savings_tip(self, transactions: list):
        """טיפ חיסכון ספציפי אחד בשבוע"""
        current_month = date.today().strftime("%Y-%m")
        recent = [t for t in transactions if t['date'][:7] >= current_month]

        txns_text = "\n".join([
            f"{t['date']} | ₪{t['amount']:.0f} | {t['description']}"
            for t in recent
        ])

        tip = self.think(f"""נתח את ההוצאות ותן המלצה ספציפית אחת לחיסכון שאפשר לבצע השבוע.
היה קונקרטי — ציין את ההוצאה הספציפית, כמה לחסוך ואיך.

הוצאות:
{txns_text}

פורמט:
💡 **[כותרת]**
מה לעשות: [פעולה ספציפית]
חיסכון משוער: ₪X בחודש""", max_tokens=200)

        msg = f"""💡 <b>טיפ החיסכון של השבוע</b>
━━━━━━━━━━━━━━
{tip}
━━━━━━━━━━━━━━
<i>נשלח ע"י Tal — סוכן ההתראות שלך</i>"""
        self.send(msg)
