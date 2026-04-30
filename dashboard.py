import streamlit as st
import json
import os
import subprocess
import sys
from datetime import datetime, date
from dotenv import load_dotenv
import anthropic
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd

load_dotenv()

st.set_page_config(
    page_title="מעקב הוצאות - גל",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    body { direction: rtl; }
    .stApp { direction: rtl; }
    .metric-card {
        background: #1e1e2e;
        border-radius: 12px;
        padding: 20px;
        text-align: center;
        border: 1px solid #333;
    }
    .status-good { color: #00ff88; }
    .status-warn { color: #ffaa00; }
    .status-bad { color: #ff4444; }
</style>
""", unsafe_allow_html=True)

# ── פונקציות ──────────────────────────────────────────────

def load_transactions():
    path = "/Users/galshushan/finance-agent/transactions.json"
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def load_report():
    path = "/Users/galshushan/finance-agent/report.txt"
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def parse_transactions(data):
    rows = []
    for account in data["accounts"]:
        for txn in account["txns"]:
            amount = txn.get("chargedAmount", 0)
            rows.append({
                "תאריך": txn.get("date", "")[:10],
                "סכום": abs(amount),
                "תיאור": txn.get("description", ""),
                "סוג": "הוצאה" if amount < 0 else "הכנסה",
                "חודש": txn.get("date", "")[:7],
            })
    return pd.DataFrame(rows)

def get_ai_analysis(txns_text):
    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    today = date.today().strftime("%d/%m/%Y")
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        messages=[{
            "role": "user",
            "content": f"""אתה סוכן פיננסי אישי חכם. נתח את הנתונים הבאים ותן דוח מלא בעברית.
היום: {today}

עסקאות:
{txns_text}

תן דוח שכולל:
1. **סיכום חודש נוכחי** - כמה הוצאתי עד היום
2. **קטגוריות** - סווג הוצאות (מזון, תחבורה, בידור, שירותים, קניות, אחר) עם סכום לכל קטגוריה בפורמט: קטגוריה: ₪סכום
3. **הוצאות קבועות** - הוצאות שחוזרות כל חודש
4. **תחזית לסוף החודש** - כמה צפוי להוציא סה"כ
5. **3 המלצות לקיצוץ** עם חיסכון משוער
6. **ציון פיננסי 1-10** עם הסבר"""
        }]
    )
    return message.content[0].text

def run_scraper():
    result = subprocess.run(
        ["node", "/Users/galshushan/finance-agent/scrape.mjs"],
        capture_output=True, text=True,
        cwd="/Users/galshushan/finance-agent"
    )
    return result.returncode == 0, result.stdout, result.stderr

# ── סיידבר ────────────────────────────────────────────────

with st.sidebar:
    st.title("💰 מעקב הוצאות")
    st.markdown("---")

    st.markdown("### ⚙️ פעולות")

    if st.button("🔄 משוך נתונים מלאומי", use_container_width=True, type="primary"):
        with st.spinner("מתחבר ללאומי..."):
            success, out, err = run_scraper()
        if success:
            st.success("✅ נתונים עודכנו!")
            st.rerun()
        else:
            st.error(f"❌ שגיאה: {err[:200]}")

    if st.button("🤖 נתח עם AI", use_container_width=True):
        data = load_transactions()
        if not data:
            st.error("משוך נתונים קודם")
        else:
            df = parse_transactions(data)
            expenses = df[df["סוג"] == "הוצאה"]
            txns_text = "\n".join([
                f"{r['תאריך']} | ₪{r['סכום']:.0f} | {r['תיאור']}"
                for _, r in expenses.iterrows()
            ])
            with st.spinner("מנתח..."):
                report = get_ai_analysis(txns_text)
            with open("/Users/galshushan/finance-agent/report.txt", "w", encoding="utf-8") as f:
                f.write(f"דוח פיננסי - {date.today().strftime('%d/%m/%Y')}\n{'='*50}\n{report}")
            st.success("✅ ניתוח הושלם!")
            st.rerun()

    st.markdown("---")
    st.markdown("### 🎯 יעד חודשי")
    budget = st.number_input("₪", value=8000, step=500, label_visibility="collapsed")

    data = load_transactions()
    if data:
        scraped_at = data.get("scrapedAt", "")[:10]
        st.markdown(f"**עדכון אחרון:** {scraped_at}")

# ── תוכן ראשי ─────────────────────────────────────────────

st.title("📊 דשבורד פיננסי")

data = load_transactions()

if not data:
    st.info("לחץ על 'משוך נתונים מלאומי' כדי להתחיל")
    st.stop()

df = parse_transactions(data)
expenses = df[df["סוג"] == "הוצאה"]
current_month = date.today().strftime("%Y-%m")
this_month = expenses[expenses["חודש"] == current_month]

total_this_month = this_month["סכום"].sum()
remaining = max(0, budget - total_this_month)
pct = (total_this_month / budget * 100) if budget > 0 else 0

days_in_month = 31
today_day = date.today().day
days_left = days_in_month - today_day
daily_avg = total_this_month / today_day if today_day > 0 else 0
estimated_total = daily_avg * days_in_month
over_budget = estimated_total > budget

# ── כרטיסי מדדים ──────────────────────────────────────────

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("הוצאות החודש", f"₪{total_this_month:,.0f}", f"{pct:.0f}% מהיעד")

with col2:
    delta_color = "normal" if remaining > 1000 else "inverse"
    st.metric("נותר להוציא", f"₪{remaining:,.0f}", f"{days_left} ימים נותרו")

with col3:
    color = "🔴" if over_budget else "🟢"
    st.metric("תחזית לסוף חודש", f"₪{estimated_total:,.0f}", f"{color} {'חריגה' if over_budget else 'בתקציב'}")

with col4:
    st.metric("ממוצע יומי", f"₪{daily_avg:,.0f}", f"יעד: ₪{budget/30:,.0f}/יום")

# ── פס התקדמות ────────────────────────────────────────────

st.markdown("### התקדמות תקציב חודשי")
progress_color = "#00ff88" if pct < 75 else "#ffaa00" if pct < 95 else "#ff4444"
st.progress(min(pct / 100, 1.0))
st.markdown(f"<p style='color:{progress_color}; text-align:center'>₪{total_this_month:,.0f} מתוך ₪{budget:,.0f} ({pct:.1f}%)</p>", unsafe_allow_html=True)

st.markdown("---")

# ── גרפים ─────────────────────────────────────────────────

col_left, col_right = st.columns(2)

with col_left:
    st.markdown("### הוצאות לפי חודש")
    monthly = expenses.groupby("חודש")["סכום"].sum().reset_index()
    monthly.columns = ["חודש", "סכום"]
    fig = px.bar(monthly, x="חודש", y="סכום", color="סכום",
                 color_continuous_scale="Blues",
                 labels={"סכום": "₪", "חודש": "חודש"})
    fig.update_layout(showlegend=False, height=300)
    st.plotly_chart(fig, use_container_width=True)

with col_right:
    st.markdown("### עסקאות גדולות החודש")
    top = this_month.nlargest(8, "סכום")[["תאריך", "תיאור", "סכום"]]
    if not top.empty:
        fig2 = px.bar(top, x="סכום", y="תיאור", orientation="h",
                      labels={"סכום": "₪", "תיאור": ""},
                      color="סכום", color_continuous_scale="Reds")
        fig2.update_layout(showlegend=False, height=300)
        st.plotly_chart(fig2, use_container_width=True)

# ── טבלת עסקאות ───────────────────────────────────────────

st.markdown("### 📋 עסקאות החודש")
if not this_month.empty:
    display = this_month[["תאריך", "תיאור", "סכום"]].sort_values("תאריך", ascending=False)
    display["סכום"] = display["סכום"].apply(lambda x: f"₪{x:,.0f}")
    st.dataframe(display, use_container_width=True, hide_index=True)
else:
    st.info("אין עסקאות לחודש הנוכחי")

# ── דוח AI ────────────────────────────────────────────────

st.markdown("---")
st.markdown("### 🤖 ניתוח AI")
report = load_report()
if report:
    st.markdown(report)
else:
    st.info("לחץ על 'נתח עם AI' בסיידבר לקבלת המלצות")
