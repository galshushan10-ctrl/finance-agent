import argparse
import json
import os
from dotenv import load_dotenv
from agents.scraper_agent import ScraperAgent
from agents.alert_agent import AlertAgent

load_dotenv()

parser = argparse.ArgumentParser()
parser.add_argument("--check", nargs="+", default=[])
args = parser.parse_args()

lior = ScraperAgent()
tal  = AlertAgent()

print("📂 טוען נתונים...")
transactions = lior.load()
print(f"✅ נטענו {len(transactions)} עסקאות")

for check in args.check:
    if check == "large_transactions":
        print("[Tal] בודק הוצאות גדולות...")
        count = tal.check_large_transactions(transactions, threshold=500)
        print(f"      נמצאו {count} הוצאות גדולות היום")

    elif check == "budget":
        print("[Tal] בודק תקציב...")
        pct = tal.check_budget(transactions)
        print(f"      תקציב: {pct:.1f}%")

    elif check == "anomaly":
        print("[Tal] בודק חריגות קטגוריה...")
        tal.check_category_anomaly(transactions)
        print("      בדיקה הושלמה")

    elif check == "weekly_summary":
        print("[Tal] שולח סיכום שבועי...")
        tal.weekly_summary(transactions)
        print("      ✅ נשלח")

    elif check == "savings_tip":
        print("[Tal] שולח טיפ חיסכון...")
        tal.weekly_savings_tip(transactions)
        print("      ✅ נשלח")

print("\n✅ סיום")
