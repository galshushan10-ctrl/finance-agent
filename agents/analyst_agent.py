from .base_agent import BaseAgent
from datetime import date
from collections import defaultdict

class AnalystAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Maya",
            role="אנליסטית פיננסית אישית",
            system_prompt="""את Maya, אנליסטית פיננסית אישית חכמה וישירה.
תפקידך: לנתח הוצאות, לזהות דפוסים, ולתת המלצות מעשיות לחיסכון.
עקרונות:
- תמיד כתבי בעברית
- היי ישירה וספציפית — מספרים, לא מילים ריקות
- זהי הוצאות קבועות לעומת משתנות
- תני המלצות שאפשר לבצע מחר בבוקר
- אל תשפטי, רק תנתחי ותמליצי"""
        )

    def detect_recurring(self, transactions: list) -> list:
        """זיהוי הוצאות קבועות לפי דפוס חזרה בחודשים קודמים"""
        current_month = date.today().strftime("%Y-%m")

        # קיבוץ לפי תיאור ובחינת חודשים
        by_description = defaultdict(list)
        for t in transactions:
            key = t['description'].strip()
            month = t['date'][:7]
            by_description[key].append({
                "month": month,
                "amount": t['amount'],
                "day": int(t['date'][8:10]),
                "date": t['date'],
            })

        recurring = []
        for desc, entries in by_description.items():
            months = list(set(e['month'] for e in entries))
            past_months = [m for m in months if m < current_month]

            # הוצאה קבועה = מופיעה ב-2+ חודשים קודמים
            if len(past_months) >= 2:
                avg_amount = sum(e['amount'] for e in entries if e['month'] != current_month) / len([e for e in entries if e['month'] != current_month])
                avg_day = sum(e['day'] for e in entries if e['month'] != current_month) / len([e for e in entries if e['month'] != current_month])
                charged_this_month = any(e['month'] == current_month for e in entries)

                recurring.append({
                    "description": desc,
                    "avg_amount": avg_amount,
                    "expected_day": round(avg_day),
                    "charged_this_month": charged_this_month,
                    "months_seen": len(past_months),
                })

        return sorted(recurring, key=lambda x: x['expected_day'])

    def analyze(self, transactions: list, budget: int = 32000) -> dict:
        today = date.today().strftime("%d/%m/%Y")
        today_day = date.today().day
        current_month = date.today().strftime("%Y-%m")

        txns_text = "\n".join([
            f"{t['date']} | ₪{t['amount']:.0f} | {t['description']}"
            for t in transactions
        ])

        this_month_txns = [t for t in transactions if t['date'][:7] == current_month]
        total_this_month = sum(t['amount'] for t in this_month_txns)
        daily_avg = total_this_month / today_day if today_day > 0 else 0

        # זיהוי הוצאות קבועות
        recurring = self.detect_recurring(transactions)

        # חישוב הוצאות קבועות שעוד לא ירדו החודש
        pending_recurring = [r for r in recurring if not r['charged_this_month']]
        pending_total = sum(r['avg_amount'] for r in pending_recurring)

        # תחזית מדויקת: הוצאות עד היום + ממוצע יומי לימים הנותרים + הוצאות קבועות צפויות
        days_left = 30 - today_day
        variable_estimate = daily_avg * days_left
        estimated = total_this_month + variable_estimate + pending_total

        report = self.think(f"""היום: {today}
יעד חודשי: ₪{budget:,}
הוצאות עד היום: ₪{total_this_month:,.0f}
תחזית לסוף חודש (כולל הוצאות קבועות צפויות): ₪{estimated:,.0f}

כל העסקאות:
{txns_text}

נתח ותן:
1. סיווג לקטגוריות עם סכומים
2. הוצאות קבועות שזוהו עם הסכום הממוצע
3. 3 המלצות לקיצוץ עם סכום חיסכון משוער
4. ציון פיננסי 1-10""", max_tokens=3000)

        return {
            "agent": str(self),
            "total_this_month": total_this_month,
            "estimated_total": estimated,
            "budget": budget,
            "report": report,
            "recurring": recurring,
            "pending_recurring": pending_recurring,
            "pending_total": pending_total,
        }
