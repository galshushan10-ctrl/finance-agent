#!/bin/bash

cd /Users/galshushan/finance-agent

# שליפת נתונים מלאומי
node scrape.mjs

# דחיפה לגיטהאב
git add transactions.json
git diff --staged --quiet || git commit -m "update transactions $(date +%Y-%m-%d)"
git push

# שליחת דוח וטלגרם ווואטסאפ
python3 orchestrator.py
