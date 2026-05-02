#!/bin/bash
cd /Users/galshushan/finance-agent

# שליפת נתונים מלאומי (רק מהמק — בנק ישראלי חוסם IPs זרים)
node scrape.mjs

# דחיפה לגיטהאב — GitHub Actions יופעל אוטומטית ויישלח הדוח
git add transactions.json
git diff --staged --quiet || git commit -m "update transactions $(date +%Y-%m-%d)"
git push
