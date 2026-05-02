from collections import defaultdict
from datetime import date

# מילות מפתח להוצאות קבועות ידועות
KNOWN_RECURRING_KEYWORDS = [
    # דיור
    "משכנתא", "שכר דירה", "ועד בית", "ועד",
    # חשמל ומים
    "חברת חשמל", "חשמל", "מפעל המים", "מים", "ישרגז", "גז",
    # תקשורת
    "סלקום", "פרטנר", "HOT", "הוט", "בזק", "YES", "יס", "012", "cellcom",
    "019", "רנדום", "גולן", "אורנג",
    # ביטוחים
    "ביטוח", "הפניקס", "מגדל", "הראל", "כלל", "מנורה", "מיטב", "הכשרה",
    # חינוך
    "גן", "צהרון", "חוג", "בית ספר", "אוניברסיטה", "מכללה", "שכר לימוד",
    # פנסיה וחסכון
    "פנסיה", "קרן השתלמות", "גמל", "חסכון",
    # רכב
    "ביטוח רכב", "טסט", "רישוי",
    # מנויים
    "נטפליקס", "netflix", "spotify", "ספוטיפיי", "apple", "אפל",
    "google", "גוגל", "amazon", "אמזון",
    # הוראת קבע
    "הוראת קבע",
]

def is_known_recurring(description: str, memo: str = "") -> bool:
    text = (description + " " + memo).lower()
    for keyword in KNOWN_RECURRING_KEYWORDS:
        if keyword.lower() in text:
            return True
    return False

def has_installments(memo: str) -> bool:
    """זיהוי תשלומים מהבנק"""
    keywords = ["תשלום", "תשלומים", "פריסה", "תשלום מתוך", "/"]
    memo_lower = memo.lower()
    for k in keywords:
        if k in memo_lower:
            return True
    return False

def build_recurring_summary(transactions: list) -> dict:
    current_month = date.today().strftime("%Y-%m")
    today_day = date.today().day

    by_desc = defaultdict(list)
    for t in transactions:
        date_str = str(t['date'])[:10]
        by_desc[t['description'].strip()].append({
            "month": date_str[:7],
            "day": int(date_str[8:10]),
            "amount": t['amount'],
            "date": date_str,
            "memo": t.get('memo', ''),
        })

    recurring = []
    seen_descs = set()

    for desc, entries in by_desc.items():
        if desc in seen_descs:
            continue

        past = [e for e in entries if e['month'] < current_month]
        months_seen = list(set(e['month'] for e in past))
        memo = entries[0].get('memo', '')

        # קריטריונים לקביעת הוצאה קבועה:
        is_recurring = (
            len(months_seen) >= 2 or                        # מופיע 2+ חודשים
            (len(months_seen) >= 1 and is_known_recurring(desc, memo)) or  # מופיע פעם + מילת מפתח
            is_known_recurring(desc, memo) or               # מילת מפתח ידועה
            has_installments(memo)                          # תשלומים
        )

        if not is_recurring:
            continue

        if past:
            avg_amount = sum(e['amount'] for e in past) / len(past)
            avg_day = sum(e['day'] for e in past) / len(past)
        else:
            # הוצאה ידועה שעוד לא הופיעה בהיסטוריה
            this_month_entries = [e for e in entries if e['month'] == current_month]
            avg_amount = this_month_entries[0]['amount'] if this_month_entries else 0
            avg_day = this_month_entries[0]['day'] if this_month_entries else 15

        charged_this_month = any(e['month'] == current_month for e in entries)
        this_month_amount = sum(e['amount'] for e in entries if e['month'] == current_month)

        recurring.append({
            "description": desc,
            "avg_amount": round(avg_amount),
            "expected_day": round(avg_day) if past else (round(this_month_amount) and 15),
            "charged_this_month": charged_this_month,
            "this_month_amount": round(this_month_amount),
            "months_seen": len(months_seen),
            "is_installment": has_installments(memo),
            "is_known": is_known_recurring(desc, memo),
        })
        seen_descs.add(desc)

    recurring.sort(key=lambda x: x['expected_day'])

    charged  = [r for r in recurring if r['charged_this_month']]
    pending  = [r for r in recurring if not r['charged_this_month']]
    upcoming = [r for r in pending if r['expected_day'] >= today_day]
    overdue  = [r for r in pending if r['expected_day'] < today_day]

    total_monthly_fixed   = sum(r['avg_amount'] for r in recurring)
    total_charged         = sum(r['this_month_amount'] for r in charged)
    total_pending         = sum(r['avg_amount'] for r in pending)

    return {
        "all_recurring":        recurring,
        "charged":              charged,
        "upcoming":             upcoming,
        "overdue":              overdue,
        "total_monthly_fixed":  total_monthly_fixed,
        "total_charged_so_far": total_charged,
        "total_pending":        total_pending,
    }

def format_recurring_telegram(summary: dict) -> str:
    lines = [
        "📋 <b>הוצאות קבועות — סיכום חודשי</b>",
        "━━━━━━━━━━━━━━━━━━━",
        f"💳 סה\"כ קבועות חודשיות: <b>₪{summary['total_monthly_fixed']:,}</b>",
        f"✅ כבר נגבו: ₪{summary['total_charged_so_far']:,}",
        f"⏳ עוד צפויות לרדת: <b>₪{summary['total_pending']:,}</b>",
        "",
    ]

    if summary['upcoming']:
        lines.append("🔜 <b>צפויות לרדת:</b>")
        for r in summary['upcoming']:
            tag = " 📆" if r['is_installment'] else ""
            lines.append(f"  • {r['description']}{tag} — ₪{r['avg_amount']:,} (בסביבות יום {r['expected_day']})")

    if summary['overdue']:
        lines += ["", "⚠️ <b>מאוחרות — עדיין לא ירדו:</b>"]
        for r in summary['overdue']:
            lines.append(f"  • {r['description']} — ₪{r['avg_amount']:,}")

    if summary['charged']:
        lines += ["", "✅ <b>כבר נגבו החודש:</b>"]
        for r in summary['charged']:
            lines.append(f"  • {r['description']} — ₪{r['this_month_amount']:,}")

    return "\n".join(lines)
