from agents import ScraperAgent, AnalystAgent, TelegramAgent
from agents.recurring_summary import build_recurring_summary, format_recurring_telegram

def run():
    print("\n🤖 מערכת סוכנים פיננסיים")
    print("=" * 40)

    lior = ScraperAgent()
    maya = AnalystAgent()
    noa = TelegramAgent()

    print(f"✅ {lior}")
    print(f"✅ {maya}")
    print(f"✅ {noa}")
    print("=" * 40)

    print(f"\n[{lior.name}] שולף נתונים מלאומי...")
    transactions = lior.load()
    print(f"[{lior.name}] נטענו {len(transactions)} עסקאות")

    # סיכום הוצאות קבועות
    recurring_summary = build_recurring_summary(transactions)
    print(f"\n[Maya] זוהו {len(recurring_summary['all_recurring'])} הוצאות קבועות")
    print(f"       סה\"כ קבועות חודשיות: ₪{recurring_summary['total_monthly_fixed']:,}")
    print(f"       עוד צפויות לרדת: ₪{recurring_summary['total_pending']:,}")

    print(f"\n[{maya.name}] מנתחת הוצאות...")
    analysis = maya.analyze(transactions, budget=32000)
    analysis["recurring_summary"] = recurring_summary
    print(f"[{maya.name}] ניתוח הושלם — תחזית: ₪{analysis['estimated_total']:,.0f}")

    # שליחת 2 הודעות לטלגרם: דוח יומי + סיכום קבועות
    print(f"\n[{noa.name}] שולחת דוח יומי...")
    success = noa.send(analysis)
    if success:
        print(f"[{noa.name}] ✅ דוח יומי נשלח!")

    print(f"\n[{noa.name}] שולחת סיכום הוצאות קבועות...")
    recurring_msg = format_recurring_telegram(recurring_summary)
    success2 = noa.send_raw(recurring_msg)
    if success2:
        print(f"[{noa.name}] ✅ סיכום קבועות נשלח!")

    print("\n" + "=" * 40)
    print("📋 דוח מלא:")
    print(analysis["report"])

if __name__ == "__main__":
    run()
