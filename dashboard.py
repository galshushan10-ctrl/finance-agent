import streamlit as st
import json, os, re
from datetime import date, timedelta
from dotenv import load_dotenv
import anthropic
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np
from agents.recurring_summary import build_recurring_summary
from calendar import monthrange

load_dotenv()
BUDGET = 32000

# תקציבים לפי קטגוריה
CATEGORY_BUDGETS = {
    "🍔 מזון": 4000,
    "🚗 תחבורה": 2000,
    "🛍️ קניות": 2000,
    "🎬 בידור": 800,
    "🏥 בריאות": 500,
    "📱 תקשורת": 400,
    "⚡ שירותים": 600,
    "🎓 חינוך": 1000,
}

st.set_page_config(page_title="Finance", page_icon="💰", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Heebo:wght@300;400;500;600;700;800;900&display=swap');
* { font-family: 'Heebo', sans-serif !important; }
.stApp { background: #060818; direction: rtl; }
section[data-testid="stSidebar"] { background: #0b0e1f; border-left: 1px solid #151c35; }
.stTabs [data-baseweb="tab-list"] { background: #0e1228; border-radius: 12px; padding: 4px; gap: 4px; }
.stTabs [data-baseweb="tab"] { color: #6b7280; border-radius: 8px; padding: 6px 16px; }
.stTabs [aria-selected="true"] { background: #1a2040 !important; color: white !important; font-weight: 700 !important; }

.kpi-card { background: linear-gradient(145deg, #0e1228, #131828); border: 1px solid #1a2240;
  border-radius: 18px; padding: 18px 20px; position: relative; overflow: hidden; }
.kpi-card::before { content:''; position:absolute; top:0; left:0; right:0; height:3px;
  background:var(--accent); border-radius:18px 18px 0 0; }
.kpi-icon { font-size:1.8rem; margin-bottom:6px; display:block; }
.kpi-label { font-size:0.65rem; color:#6b7280; text-transform:uppercase; letter-spacing:1.5px; }
.kpi-value { font-size:1.8rem; font-weight:900; color:var(--accent); line-height:1.1; margin:3px 0; }
.kpi-desc { font-size:0.75rem; color:#9ca3af; }
.kpi-sub { font-size:0.72rem; color:#4b5563; margin-top:4px; }

.alert-card { border-radius:12px; padding:12px 16px; margin-bottom:8px; display:flex; align-items:flex-start; gap:12px; }
.alert-error   { background:#1a0505; border:1px solid #7f1d1d; }
.alert-warning { background:#1a1005; border:1px solid #78350f; }
.alert-info    { background:#050f1a; border:1px solid #1e3a5f; }
.alert-success { background:#051a08; border:1px solid #14532d; }
.alert-icon { font-size:1.2rem; flex-shrink:0; }
.alert-text { color:#e2e8f0; font-size:0.85rem; font-weight:600; }
.alert-detail { color:#6b7280; font-size:0.78rem; margin-top:2px; }

.section-title { font-size:0.95rem; font-weight:800; color:#e2e8f0; margin:28px 0 12px;
  padding-right:12px; border-right:3px solid #6366f1; }
.explain-box { background:#0a0e20; border:1px solid #151c35; border-radius:12px;
  padding:10px 16px; margin-bottom:14px; color:#6b7280; font-size:0.78rem; line-height:1.5; }
.explain-box strong { color:#a5b4fc; }

.cat-budget-row { background:#0e1228; border:1px solid #151c35; border-radius:12px;
  padding:12px 16px; margin-bottom:8px; }
.txn-row { background:#0e1228; border:1px solid #151c35; border-radius:10px;
  padding:10px 16px; margin-bottom:6px; display:flex; justify-content:space-between; align-items:center; }

div[data-testid="stButton"] button { background:linear-gradient(135deg,#6366f1,#8b5cf6);
  color:white; border:none; border-radius:10px; padding:10px 20px; font-weight:700; width:100%; }
div[data-testid="metric-container"] { background:#0e1228; border:1px solid #151c35; border-radius:14px; padding:14px; }
</style>
""", unsafe_allow_html=True)

# ── auth ───────────────────────────────────────────────────
def check_password():
    if st.session_state.get("auth"): return True
    st.markdown("<div style='text-align:center;padding:80px 0 20px'><div style='font-size:3.5rem'>💰</div><h1 style='color:white;font-weight:900'>Finance Dashboard</h1><p style='color:#6b7280'>מעקב הוצאות חכם</p></div>", unsafe_allow_html=True)
    c1,c2,c3 = st.columns([1,2,1])
    with c2:
        pw = st.text_input("", type="password", placeholder="סיסמה...", label_visibility="collapsed")
        if st.button("כניסה", use_container_width=True):
            if pw == os.environ.get("DASHBOARD_PASSWORD","finance2024"):
                st.session_state.auth = True; st.rerun()
            else: st.error("סיסמה שגויה")
    return False

if not check_password(): st.stop()

# ── data ───────────────────────────────────────────────────
@st.cache_data(ttl=300)
def load_data():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "transactions.json")
    if not os.path.exists(path): return None
    with open(path, encoding="utf-8") as f: return json.load(f)

def categorize(desc):
    desc = desc.lower()
    mapping = {
        "🏠 דיור": ["משכנת","שכר דירה","ועד","שכירות"],
        "🍔 מזון": ["סופר","מכולת","אוכל","מסעדה","קפה","פיצה","שוורמה","מזון","מינימרקט","פלאפל","בורגר"],
        "🚗 תחבורה": ["דלק","חניה","רכבת","אוטובוס","taxi","uber","גט","רכב","תחנת דלק"],
        "🛡️ ביטוחים": ["ביטוח","הפניקס","מגדל","הראל","כלל","מנורה"],
        "📱 תקשורת": ["סלקום","פרטנר","hot","בזק","yes","גולן","אורנג","012"],
        "🎓 חינוך": ["גן","צהרון","חוג","לימוד","קורס","אוניברסיטה","מכללה"],
        "🛍️ קניות": ["אמזון","זארה","h&m","קניון","shop","חנות","ביגוד"],
        "⚡ שירותים": ["חשמל","מים","גז","ארנונה","עירייה"],
        "🎬 בידור": ["נטפליקס","netflix","spotify","apple","גוגל","disney","סרט","תיאטרון"],
        "🏥 בריאות": ["רופא","בית חולים","מרפאה","תרופ","קופת חולים","דנטל","אופטיקה"],
    }
    for cat, kws in mapping.items():
        if any(k in desc for k in kws): return cat
    return "📦 אחר"

def parse_installment(memo):
    if not memo: return None
    m = re.search(r'(\d+)\s*[מ/]\s*(\d+)', str(memo))
    if m:
        cur, total = int(m.group(1)), int(m.group(2))
        return {"current": cur, "total": total, "remaining": total - cur}
    return None

def to_df(data):
    rows = []
    for acc in data["accounts"]:
        for t in acc["txns"]:
            amt = t.get("chargedAmount", 0)
            rows.append({
                "date": pd.to_datetime(t.get("date","")[:10]),
                "amount": abs(amt), "raw": amt,
                "description": t.get("description",""),
                "memo": t.get("memo",""),
                "type": "הוצאה" if amt < 0 else "הכנסה",
            })
    df = pd.DataFrame(rows)
    df["month"] = df["date"].dt.strftime("%Y-%m")
    df["day"]   = df["date"].dt.day
    df["dow"]   = df["date"].dt.dayofweek
    df["dow_name"] = df["date"].dt.day_name()
    df["week"]  = df["date"].dt.isocalendar().week.astype(int)
    df["category"] = df["description"].apply(categorize)
    df["installment"] = df["memo"].apply(parse_installment)
    return df

data = load_data()
if not data: st.warning("אין נתונים עדיין"); st.stop()

df = to_df(data)
expenses   = df[df["type"] == "הוצאה"]
income_df  = df[df["type"] == "הכנסה"]
all_months = sorted(expenses["month"].unique(), reverse=True)

# ── sidebar ────────────────────────────────────────────────
with st.sidebar:
    st.markdown("<h2 style='color:white;text-align:center;font-weight:900'>💰 Finance</h2>", unsafe_allow_html=True)
    st.markdown("<hr style='border-color:#151c35;margin:8px 0'>", unsafe_allow_html=True)

    selected_month = st.selectbox("📅 חודש", all_months, index=0)
    budget = st.slider("🎯 תקציב חודשי ₪", 15000, 60000, BUDGET, 1000)

    st.markdown("<hr style='border-color:#151c35;margin:8px 0'>", unsafe_allow_html=True)
    updated = data.get("scrapedAt","")[:10]
    st.markdown(f"<p style='color:#374151;font-size:0.7rem;text-align:center'>עדכון אחרון: {updated}<br>מתעדכן אוטומטית 08:00</p>", unsafe_allow_html=True)

# ── חישובים ────────────────────────────────────────────────
month_exp   = expenses[expenses["month"] == selected_month]
today       = date.today()
is_current  = selected_month == today.strftime("%Y-%m")
days_in_month = monthrange(int(selected_month[:4]), int(selected_month[5:7]))[1]
days_passed = today.day if is_current else days_in_month
days_left   = max(0, days_in_month - days_passed)

total       = month_exp["amount"].sum()
daily_avg   = total / days_passed if days_passed > 0 else 0
estimated   = daily_avg * days_in_month if is_current else total
pct         = min((total / budget) * 100, 100) if budget else 0

rec_summary = build_recurring_summary(expenses.to_dict("records"))
pending_fixed   = rec_summary["total_pending"] if is_current else 0
estimated_total = estimated + pending_fixed
remaining   = max(0, budget - estimated_total)

income_this = income_df[income_df["month"] == selected_month]["amount"].sum()
savings_est = income_this - estimated_total
savings_rate = (savings_est / income_this * 100) if income_this > 0 else 0

# velocity — עד כמה אתה מהיר ביחס לציפייה
expected_by_now = (budget / days_in_month) * days_passed if days_passed > 0 else budget
velocity = total / expected_by_now if expected_by_now > 0 else 1.0

# ממוצע 3 חודשים קודמים לכל קטגוריה
past3 = sorted([m for m in all_months if m < selected_month])[-3:]
cat_avg_3m = {}
if past3:
    for m in past3:
        m_data = expenses[expenses["month"] == m]
        for cat, grp in m_data.groupby("category"):
            cat_avg_3m[cat] = cat_avg_3m.get(cat, 0) + grp["amount"].sum()
    for cat in cat_avg_3m:
        cat_avg_3m[cat] /= len(past3)

# ── header ─────────────────────────────────────────────────
month_heb = {"01":"ינואר","02":"פברואר","03":"מרץ","04":"אפריל","05":"מאי","06":"יוני",
             "07":"יולי","08":"אוגוסט","09":"ספטמבר","10":"אוקטובר","11":"נובמבר","12":"דצמבר"}
m_name = month_heb.get(selected_month[5:],"") + " " + selected_month[:4]
vel_text = f"⚡ קצב גבוה {velocity:.0%}" if velocity > 1.15 else f"🐢 קצב אטי" if velocity < 0.8 else "✅ קצב תקין"
vel_color = "#f87171" if velocity > 1.15 else "#fbbf24" if velocity < 0.8 else "#4ade80"

st.markdown(f"""
<div style='display:flex;justify-content:space-between;align-items:center;margin-bottom:20px'>
  <div>
    <h1 style='color:white;margin:0;font-weight:900;font-size:1.9rem'>📊 {m_name}</h1>
    <p style='color:#6b7280;margin:2px 0 0;font-size:0.8rem'>יום {days_passed} מתוך {days_in_month} ({days_passed*100//days_in_month}% מהחודש) | <span style='color:{vel_color};font-weight:700'>{vel_text}</span></p>
  </div>
  <div style='text-align:center;background:#0e1228;border:1px solid #1a2240;border-radius:14px;padding:10px 18px'>
    <div style='font-size:1rem;font-weight:800;color:{"#4ade80" if estimated_total<=budget else "#f87171"}'>{"✅ בתקציב" if estimated_total<=budget else "⚠️ חריגה צפויה"}</div>
    <div style='font-size:0.72rem;color:#6b7280'>{pct:.0f}% נוצל</div>
  </div>
</div>
""", unsafe_allow_html=True)

# ── SMART ALERTS (תמיד מוצגים) ─────────────────────────────
def generate_alerts():
    alerts = []
    if velocity > 1.2:
        overage = estimated_total - budget
        alerts.append(("error","🔴",f"קצב הוצאה גבוה ב-{(velocity-1)*100:.0f}% מהרגיל",f"תחזית חריגה של ₪{overage:,.0f} בסוף החודש"))
    if savings_rate < 0 and income_this > 0:
        alerts.append(("error","💸",f"גירעון חזוי: ₪{abs(savings_est):,.0f}",f"ההוצאות הצפויות עולות על ההכנסות"))
    for cat, avg in cat_avg_3m.items():
        curr = month_exp[month_exp["category"]==cat]["amount"].sum()
        if avg > 200 and curr > avg * 1.4:
            alerts.append(("warning","📈",f"{cat}: +{(curr/avg-1)*100:.0f}% מהממוצע",f"₪{curr:,.0f} לעומת ממוצע ₪{avg:,.0f}"))
    median_txn = month_exp["amount"].median() if len(month_exp) > 5 else 0
    if median_txn > 0:
        for _, t in month_exp[month_exp["amount"] > max(median_txn*6, 2000)].head(2).iterrows():
            alerts.append(("info","🚩",f"עסקה גדולה: {t['description'][:30]} — ₪{t['amount']:,.0f}","לחץ על עסקאות לפרטים"))
    if rec_summary.get("overdue"):
        names = ", ".join(r["description"] for r in rec_summary["overdue"][:2])
        alerts.append(("warning","⏰",f"תשלום קבוע עדיין לא ירד: {names}","בדוק יתרה בחשבון"))
    if savings_rate >= 15 and income_this > 0:
        alerts.append(("success","🎯",f"חיסכון מצוין: {savings_rate:.0f}% מההכנסה",f"₪{savings_est:,.0f} חיסכון צפוי החודש"))
    return alerts

alerts = generate_alerts()
if alerts:
    st.markdown("<div class='section-title'>🔔 התראות והתראות</div>", unsafe_allow_html=True)
    a_cols = st.columns(min(len(alerts), 3))
    for i, (level, icon, text, detail) in enumerate(alerts[:3]):
        a_cols[i % 3].markdown(f"""
        <div class='alert-card alert-{level}'>
          <span class='alert-icon'>{icon}</span>
          <div><div class='alert-text'>{text}</div><div class='alert-detail'>{detail}</div></div>
        </div>""", unsafe_allow_html=True)
    if len(alerts) > 3:
        with st.expander(f"+ {len(alerts)-3} התראות נוספות"):
            for level, icon, text, detail in alerts[3:]:
                st.markdown(f"<div class='alert-card alert-{level}'><span class='alert-icon'>{icon}</span><div><div class='alert-text'>{text}</div><div class='alert-detail'>{detail}</div></div></div>", unsafe_allow_html=True)

# ── KPIs ───────────────────────────────────────────────────
st.markdown("<div class='section-title'>📌 מדדים מרכזיים</div>", unsafe_allow_html=True)

def kpi(col, icon, label, value, desc, accent, sub="", is_pct=False):
    val_str = f"{value:.0f}%" if is_pct else f"₪{value:,.0f}"
    col.markdown(f"""<div class='kpi-card' style='--accent:{accent}'>
      <span class='kpi-icon'>{icon}</span>
      <div class='kpi-label'>{label}</div>
      <div class='kpi-value'>{val_str}</div>
      <div class='kpi-desc'>{desc}</div>
      {"<div class='kpi-sub'>"+sub+"</div>" if sub else ""}
    </div>""", unsafe_allow_html=True)

c1,c2,c3,c4,c5,c6 = st.columns(6)
kpi(c1,"💳","הוצאות עד היום",total,f"ב-{days_passed} ימים | {pct:.0f}% מיעד","#6366f1",f"יומי: ₪{daily_avg:,.0f}")
kpi(c2,"🔮","תחזית לסוף חודש",estimated_total,"כולל קבועות צפויות","#4ade80" if estimated_total<=budget else "#f87171","✅ בתקציב" if estimated_total<=budget else f"⚠️ חריג ₪{estimated_total-budget:,.0f}")
kpi(c3,"🟡","נותר להוצאה",remaining,f"ל-{days_left} ימים שנותרו","#fbbf24",f"₪{remaining/days_left:,.0f}/יום" if days_left>0 else "")
kpi(c4,"📈","ממוצע יומי",daily_avg,"לעומת יעד יומי","#4ade80" if daily_avg<=budget/days_in_month else "#f87171",f"יעד: ₪{budget/days_in_month:,.0f}/יום")
kpi(c5,"💰","חיסכון משוער",max(0,savings_est),f"הכנסות: ₪{income_this:,.0f}","#4ade80" if savings_est>=0 else "#f87171",f"שיעור: {savings_rate:.0f}%")
kpi(c6,"📊","שיעור חיסכון",savings_rate,"מהכנסה החודשית","#4ade80" if savings_rate>=15 else "#fbbf24" if savings_rate>=5 else "#f87171","מומלץ: 15%+",is_pct=True)

# ── SANKEY + CUMULATIVE ────────────────────────────────────
st.markdown("<div class='section-title'>💡 תמונת כסף מלאה</div>", unsafe_allow_html=True)
sk1, sk2 = st.columns([1, 1])

with sk1:
    st.markdown("<div class='explain-box'><strong>Sankey — זרימת כסף:</strong> מימין הכנסות, משמאל הוצאות לפי קטגוריה + חיסכון. רוחב הקו = סכום. מראה בדיוק לאיפה הולך כל שקל.</div>", unsafe_allow_html=True)
    cat_sums = month_exp.groupby("category")["amount"].sum().sort_values(ascending=False)
    top_cats = cat_sums.head(6)
    other = cat_sums.iloc[6:].sum()

    labels = ["הכנסות"] + list(top_cats.index) + (["📦 קטגוריות אחרות"] if other > 0 else []) + (["💰 חיסכון"] if savings_est > 0 else [])
    sources, targets, values, link_colors = [], [], [], []
    colors_nodes = ["#4ade80"] + ["#f87171"]*len(top_cats) + (["#6b7280"] if other > 0 else []) + (["#6366f1"] if savings_est > 0 else [])

    for i, (cat, val) in enumerate(top_cats.items()):
        sources.append(0); targets.append(i+1); values.append(val); link_colors.append("rgba(248,113,113,0.3)")
    if other > 0:
        sources.append(0); targets.append(len(top_cats)+1); values.append(other); link_colors.append("rgba(107,114,128,0.3)")
    if savings_est > 0:
        sources.append(0); targets.append(len(labels)-1); values.append(savings_est); link_colors.append("rgba(99,102,241,0.4)")

    if income_this > 0 and values:
        fig_sankey = go.Figure(go.Sankey(
            node=dict(label=labels, color=colors_nodes, pad=15, thickness=20,
                      line=dict(color="#060818", width=0.5)),
            link=dict(source=sources, target=targets, value=values, color=link_colors)
        ))
        fig_sankey.update_layout(paper_bgcolor="#0e1228", font=dict(color="white", family="Heebo", size=11),
                                  height=340, margin=dict(t=10,b=10,l=10,r=10))
        st.plotly_chart(fig_sankey, use_container_width=True)
    else:
        st.info("נדרשות הכנסות זוהו כדי להציג Sankey")

with sk2:
    st.markdown("<div class='explain-box'><strong>מצטבר vs תקציב:</strong> קו סגול = החודש הנוכחי. קווים מנוקדים = חודשים קודמים. הקו האדום = תקציב. אם הסגול חוצה את האדום — חרגת.</div>", unsafe_allow_html=True)
    fig_trend = go.Figure()
    past_months_list = sorted([m for m in expenses["month"].unique() if m < selected_month])[-3:]
    colors_p = ["#1e2d6b","#2d4080","#3d5299"]
    for i, m in enumerate(past_months_list):
        m_exp = expenses[expenses["month"]==m]
        di = m_exp.groupby("day")["amount"].sum()
        full = pd.DataFrame({"day": range(1, days_in_month+1)}).merge(
            di.reset_index(), on="day", how="left").fillna(0)
        full["cum"] = full["amount"].cumsum()
        fig_trend.add_trace(go.Scatter(x=full["day"], y=full["cum"], mode="lines", name=m,
            line=dict(color=colors_p[i], width=1.5, dash="dot"), opacity=0.5))
    di_curr = month_exp.groupby("day")["amount"].sum()
    full_curr = pd.DataFrame({"day": range(1, days_passed+1)}).merge(
        di_curr.reset_index(), on="day", how="left").fillna(0)
    full_curr["cum"] = full_curr["amount"].cumsum()
    fig_trend.add_trace(go.Scatter(x=full_curr["day"], y=full_curr["cum"], mode="lines+markers",
        name=selected_month, line=dict(color="#6366f1", width=3),
        marker=dict(size=4), fill="tozeroy", fillcolor="rgba(99,102,241,0.06)"))
    fig_trend.add_hline(y=budget, line_dash="dash", line_color="#f87171",
                        annotation_text=f"יעד ₪{budget:,}", annotation_font_color="#f87171")
    fig_trend.update_layout(paper_bgcolor="#0e1228", plot_bgcolor="#0e1228",
        font=dict(color="#9ca3af", family="Heebo"), height=340,
        legend=dict(bgcolor="#131828", bordercolor="#1a2240", x=0, y=1),
        xaxis=dict(gridcolor="#151c35", title="יום"), yaxis=dict(gridcolor="#151c35"),
        margin=dict(t=10,b=30,l=10,r=20), hovermode="x unified")
    st.plotly_chart(fig_trend, use_container_width=True)

# ── CATEGORY BUDGETS ────────────────────────────────────────
st.markdown("<div class='section-title'>🎯 תקציב לפי קטגוריה</div>", unsafe_allow_html=True)
st.markdown("<div class='explain-box'><strong>מעקב תקציב לפי קטגוריה</strong> — כל שורה מראה כמה הוצאת ביחס ליעד שהגדרת. 🟢 בתקציב | 🟡 מתקרב | 🔴 חרג. הממוצע 3 חודשים = הבנצ'מארק שלך.</div></div>", unsafe_allow_html=True)

bc1, bc2 = st.columns(2)
cat_items = list(CATEGORY_BUDGETS.items())
for i, (cat, cat_budget) in enumerate(cat_items):
    col = bc1 if i % 2 == 0 else bc2
    spent = month_exp[month_exp["category"]==cat]["amount"].sum()
    pct_cat = min(spent / cat_budget, 1.0) if cat_budget > 0 else 0
    avg3 = cat_avg_3m.get(cat, 0)
    color = "#4ade80" if pct_cat < 0.8 else "#fbbf24" if pct_cat < 1.0 else "#f87171"
    diff_avg = ((spent - avg3) / avg3 * 100) if avg3 > 0 else 0
    diff_str = (f"+{diff_avg:.0f}% מממוצע" if diff_avg > 5 else f"{diff_avg:.0f}% מממוצע" if diff_avg < -5 else "≈ ממוצע")

    col.markdown(f"""<div class='cat-budget-row'>
      <div style='display:flex;justify-content:space-between;margin-bottom:6px'>
        <b style='color:white;font-size:0.9rem'>{cat}</b>
        <span style='font-size:0.8rem;color:{color};font-weight:700'>₪{spent:,.0f} / ₪{cat_budget:,}</span>
      </div>
      <div style='background:#151c35;border-radius:6px;height:8px;overflow:hidden'>
        <div style='background:{color};width:{pct_cat*100:.0f}%;height:100%;border-radius:6px;transition:width 0.5s'></div>
      </div>
      <div style='color:#4b5563;font-size:0.7rem;margin-top:4px'>{diff_str} | {pct_cat*100:.0f}% מהיעד</div>
    </div>""", unsafe_allow_html=True)

# ── גרפים ─────────────────────────────────────────────────
st.markdown("<div class='section-title'>📊 ניתוח גרפי</div>", unsafe_allow_html=True)
tabs = st.tabs(["🥧 קטגוריות","📅 יומי","🗓️ יום בשבוע","🔥 Heatmap","🏪 עסקים","📆 חודשי & הכנסות","💧 Waterfall"])

with tabs[0]:
    st.markdown("<div class='explain-box'><strong>קטגוריות:</strong> העיגול = חלוקה יחסית. העמודות = השוואה ישירה. לחץ על קטגוריה בעיגול לבידוד.</div>", unsafe_allow_html=True)
    cat_df = month_exp.groupby("category")["amount"].sum().reset_index().sort_values("amount",ascending=False)
    COLORS = px.colors.qualitative.Pastel
    p1, p2 = st.columns(2)
    with p1:
        fig_pie = go.Figure(go.Pie(labels=cat_df["category"], values=cat_df["amount"], hole=0.55,
            textinfo="label+percent", marker=dict(colors=COLORS, line=dict(color="#060818",width=2)),
            pull=[0.05 if i==0 else 0 for i in range(len(cat_df))]))
        fig_pie.update_layout(paper_bgcolor="#0e1228", font=dict(color="white",family="Heebo"),
            showlegend=False, height=320,
            annotations=[dict(text=f"<b>₪{total:,.0f}</b>",x=0.5,y=0.5,font_size=15,font_color="white",showarrow=False)])
        st.plotly_chart(fig_pie, use_container_width=True)
    with p2:
        fig_bar = go.Figure(go.Bar(y=cat_df["category"], x=cat_df["amount"], orientation="h",
            marker=dict(color=COLORS[:len(cat_df)]),
            text=[f"₪{v:,.0f}" for v in cat_df["amount"]], textposition="outside", textfont=dict(color="white",size=10)))
        if cat_avg_3m:
            avg_vals = [cat_avg_3m.get(c,0) for c in cat_df["category"]]
            fig_bar.add_trace(go.Scatter(y=cat_df["category"], x=avg_vals, mode="markers",
                name="ממוצע 3 חודשים", marker=dict(symbol="line-ew-open", size=12, color="#6366f1", line=dict(width=2))))
        fig_bar.update_layout(paper_bgcolor="#0e1228", plot_bgcolor="#0e1228",
            font=dict(color="#9ca3af",family="Heebo"), height=320,
            xaxis=dict(gridcolor="#151c35",showticklabels=False), yaxis=dict(gridcolor="rgba(0,0,0,0)"),
            margin=dict(l=10,r=80,t=10,b=10), showlegend=True,
            legend=dict(bgcolor="#131828", bordercolor="#1a2240"))
        st.plotly_chart(fig_bar, use_container_width=True)

with tabs[1]:
    st.markdown("<div class='explain-box'><strong>הוצאות יומיות:</strong> 🟢 מתחת לממוצע | 🟡 מעל ממוצע | 🔴 יום יקר (1.5x+). לחץ על עמודה לסינון עסקאות.</div>", unsafe_allow_html=True)
    daily = pd.DataFrame({"day":range(1,days_passed+1)}).merge(
        month_exp.groupby("day")["amount"].sum().reset_index(), on="day", how="left").fillna(0)
    avg_d = daily["amount"].mean()
    colors_d = ["#f87171" if v>avg_d*1.5 else "#fbbf24" if v>avg_d else "#4ade80" for v in daily["amount"]]
    fig_daily = go.Figure(go.Bar(x=daily["day"], y=daily["amount"], marker_color=colors_d,
        text=[f"₪{v:,.0f}" if v>0 else "" for v in daily["amount"]],
        textposition="outside", textfont=dict(color="white",size=9),
        hovertemplate="יום %{x}<br>₪%{y:,.0f}<extra></extra>"))
    fig_daily.add_hline(y=avg_d, line_dash="dash", line_color="#6366f1",
        annotation_text=f"ממוצע ₪{avg_d:,.0f}", annotation_font_color="#6366f1")
    fig_daily.add_hline(y=budget/days_in_month, line_dash="dash", line_color="#fbbf24",
        annotation_text=f"יעד ₪{budget/days_in_month:,.0f}/יום", annotation_font_color="#fbbf24")
    fig_daily.update_layout(paper_bgcolor="#0e1228", plot_bgcolor="#0e1228",
        font=dict(color="#9ca3af",family="Heebo"), height=380,
        xaxis=dict(gridcolor="#151c35",title="יום",dtick=1), yaxis=dict(gridcolor="#151c35"),
        margin=dict(t=30,b=40), bargap=0.25)
    st.plotly_chart(fig_daily, use_container_width=True)

with tabs[2]:
    st.markdown("<div class='explain-box'><strong>לפי יום בשבוע:</strong> באיזה ימים אתה מוציא הכי הרבה? מזהה דפוסים כמו 'קניות כל שישי'.</div>", unsafe_allow_html=True)
    dow_order = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
    dow_heb = {"Monday":"שני","Tuesday":"שלישי","Wednesday":"רביעי","Thursday":"חמישי","Friday":"שישי","Saturday":"שבת","Sunday":"ראשון"}
    dow_df = month_exp.groupby("dow_name")["amount"].mean().reindex(dow_order).reset_index()
    dow_df["heb"] = dow_df["dow_name"].map(dow_heb)
    dow_df["amount"] = dow_df["amount"].fillna(0)
    max_val = dow_df["amount"].max()
    fig_dow = go.Figure(go.Bar(x=dow_df["heb"], y=dow_df["amount"],
        marker_color=["#f87171" if v==max_val else "#6366f1" if v>max_val*0.7 else "#2d3a6b" for v in dow_df["amount"]],
        text=[f"₪{v:,.0f}" if v>0 else "" for v in dow_df["amount"]],
        textposition="outside", textfont=dict(color="white"),
        hovertemplate="%{x}<br>ממוצע ₪%{y:,.0f}<extra></extra>"))
    fig_dow.update_layout(paper_bgcolor="#0e1228", plot_bgcolor="#0e1228",
        font=dict(color="#9ca3af",family="Heebo"), height=360,
        yaxis=dict(gridcolor="#151c35",title="ממוצע הוצאה ₪"),
        margin=dict(t=30,b=20))
    st.plotly_chart(fig_dow, use_container_width=True)

with tabs[3]:
    st.markdown("<div class='explain-box'><strong>Heatmap — מפת חום:</strong> כל תא = יום אחד. צבע כהה = הוצאה גבוהה. רואים במבט אחד אילו שבועות היו יקרים.</div>", unsafe_allow_html=True)
    heat_data = month_exp.copy()
    heat_data["iso_week"] = heat_data["date"].dt.isocalendar().week.astype(int)
    heat_data["dow2"] = heat_data["date"].dt.dayofweek
    heat = heat_data.groupby(["iso_week","dow2"])["amount"].sum().reset_index()
    weeks = sorted(heat["iso_week"].unique())
    week_map = {w: i for i, w in enumerate(weeks)}
    heat["row"] = heat["iso_week"].map(week_map)
    heat_matrix = heat.pivot(index="row", columns="dow2", values="amount").reindex(
        index=range(len(weeks)), columns=range(7)).fillna(0)
    fig_heat = go.Figure(go.Heatmap(z=heat_matrix.values,
        x=["שני","שלישי","רביעי","חמישי","שישי","שבת","ראשון"],
        y=[f"שבוע {i+1}" for i in range(len(weeks))],
        colorscale=[[0,"#0e1228"],[0.3,"#1e2d6b"],[0.6,"#6366f1"],[1,"#f87171"]],
        text=[[f"₪{v:,.0f}" if v>0 else "" for v in row] for row in heat_matrix.values],
        texttemplate="%{text}", textfont=dict(color="white",size=11),
        showscale=True, colorbar=dict(tickfont=dict(color="#9ca3af"))))
    fig_heat.update_layout(paper_bgcolor="#0e1228", font=dict(color="#9ca3af",family="Heebo"),
        height=280, margin=dict(t=10,b=20,l=70,r=20), xaxis=dict(side="top"))
    st.plotly_chart(fig_heat, use_container_width=True)

with tabs[4]:
    st.markdown("<div class='explain-box'><strong>עסקים מובילים:</strong> 15 העסקים שאצלם הוצאת הכי הרבה החודש. מזהה לאן הולך הכסף בפועל.</div>", unsafe_allow_html=True)
    top = month_exp.groupby("description")["amount"].sum().reset_index().sort_values("amount",ascending=False).head(15)
    fig_top = go.Figure(go.Bar(y=top["description"], x=top["amount"], orientation="h",
        marker=dict(color=top["amount"], colorscale=[[0,"#2d3a6b"],[0.5,"#6366f1"],[1,"#f87171"]], showscale=False),
        text=[f"₪{v:,.0f}" for v in top["amount"]], textposition="outside", textfont=dict(color="white",size=10),
        hovertemplate="%{y}<br>₪%{x:,.0f}<extra></extra>"))
    fig_top.update_layout(paper_bgcolor="#0e1228", plot_bgcolor="#0e1228",
        font=dict(color="#9ca3af",family="Heebo"), height=500,
        xaxis=dict(gridcolor="#151c35",showticklabels=False),
        yaxis=dict(gridcolor="rgba(0,0,0,0)",categoryorder="total ascending"),
        margin=dict(l=10,r=80,t=10,b=10))
    st.plotly_chart(fig_top, use_container_width=True)

with tabs[5]:
    st.markdown("<div class='explain-box'><strong>השוואה חודשית + הכנסות:</strong> עמודות ירוקות = הכנסות, אדומות = הוצאות. הקו הכחול = חיסכון נטו. האם אתה חוסך כל חודש?</div>", unsafe_allow_html=True)
    monthly_summary = []
    for m in sorted(expenses["month"].unique()):
        inc = income_df[income_df["month"]==m]["amount"].sum()
        exp = expenses[expenses["month"]==m]["amount"].sum()
        monthly_summary.append({"month":m,"income":inc,"expenses":exp,"net":inc-exp})
    ms_df = pd.DataFrame(monthly_summary)

    fig_monthly = go.Figure()
    fig_monthly.add_trace(go.Bar(name="הכנסות",x=ms_df["month"],y=ms_df["income"],
        marker_color=["#4ade80" if m==selected_month else "#1a4d2e" for m in ms_df["month"]],
        text=[f"₪{v:,.0f}" if v>0 else "" for v in ms_df["income"]],
        textposition="outside", textfont=dict(color="white",size=9)))
    fig_monthly.add_trace(go.Bar(name="הוצאות",x=ms_df["month"],y=ms_df["expenses"],
        marker_color=["#f87171" if m==selected_month else "#4d1a1a" for m in ms_df["month"]],
        text=[f"₪{v:,.0f}" for v in ms_df["expenses"]],
        textposition="outside", textfont=dict(color="white",size=9)))
    fig_monthly.add_trace(go.Scatter(name="חיסכון נטו",x=ms_df["month"],y=ms_df["net"],
        mode="lines+markers", line=dict(color="#6366f1",width=2.5),
        marker=dict(size=7, color=["#4ade80" if v>=0 else "#f87171" for v in ms_df["net"]])))
    fig_monthly.add_hline(y=budget, line_dash="dash", line_color="#fbbf24",
        annotation_text=f"יעד", annotation_font_color="#fbbf24")
    fig_monthly.update_layout(paper_bgcolor="#0e1228", plot_bgcolor="#0e1228",
        font=dict(color="#9ca3af",family="Heebo"), height=400, barmode="group",
        legend=dict(bgcolor="#131828",bordercolor="#1a2240",x=0,y=1),
        xaxis=dict(gridcolor="#151c35"), yaxis=dict(gridcolor="#151c35"),
        margin=dict(t=30,b=20))
    st.plotly_chart(fig_monthly, use_container_width=True)

    # Savings Rate trend
    if len(ms_df[ms_df["income"]>0]) >= 2:
        sr_df = ms_df[ms_df["income"]>0].copy()
        sr_df["savings_rate"] = (sr_df["net"] / sr_df["income"] * 100)
        fig_sr = go.Figure(go.Scatter(x=sr_df["month"], y=sr_df["savings_rate"],
            mode="lines+markers", fill="tozeroy",
            fillcolor="rgba(99,102,241,0.1)", line=dict(color="#6366f1",width=2.5),
            marker=dict(size=8, color=["#4ade80" if v>=15 else "#fbbf24" if v>=0 else "#f87171" for v in sr_df["savings_rate"]]),
            hovertemplate="%{x}<br>%{y:.1f}%<extra></extra>"))
        fig_sr.add_hline(y=15, line_dash="dash", line_color="#4ade80",
            annotation_text="יעד 15%", annotation_font_color="#4ade80")
        fig_sr.add_hline(y=0, line_color="#f87171", line_width=1)
        fig_sr.update_layout(paper_bgcolor="#0e1228", plot_bgcolor="#0e1228",
            font=dict(color="#9ca3af",family="Heebo"), height=240,
            title=dict(text="שיעור חיסכון לאורך זמן",font=dict(color="white",size=13)),
            yaxis=dict(gridcolor="#151c35",title="%",ticksuffix="%"),
            xaxis=dict(gridcolor="#151c35"), margin=dict(t=40,b=20))
        st.plotly_chart(fig_sr, use_container_width=True)

with tabs[6]:
    st.markdown("<div class='explain-box'><strong>Waterfall:</strong> מתחיל מהכנסות (ירוק), כל קטגוריה מורידה (אדום), מה שנותר = חיסכון (סגול).</div>", unsafe_allow_html=True)
    cat_wf = month_exp.groupby("category")["amount"].sum().reset_index().sort_values("amount",ascending=False)
    base_income = income_this if income_this > 0 else estimated_total
    measures = ["absolute"] + ["relative"]*len(cat_wf) + ["total"]
    x_vals = ["💵 הכנסות"] + list(cat_wf["category"]) + ["💰 חיסכון/גירעון"]
    y_vals = [base_income] + list(-cat_wf["amount"]) + [0]
    fig_wf = go.Figure(go.Waterfall(orientation="v", measure=measures,
        x=x_vals, y=y_vals,
        connector=dict(line=dict(color="#151c35",width=1)),
        decreasing=dict(marker=dict(color="#f87171",line=dict(color="rgba(0,0,0,0)"))),
        increasing=dict(marker=dict(color="#4ade80",line=dict(color="rgba(0,0,0,0)"))),
        totals=dict(marker=dict(color="#6366f1",line=dict(color="rgba(0,0,0,0)"))),
        text=[f"₪{abs(v):,.0f}" for v in y_vals], textposition="outside",
        textfont=dict(color="white",size=10)))
    fig_wf.update_layout(paper_bgcolor="#0e1228", plot_bgcolor="#0e1228",
        font=dict(color="#9ca3af",family="Heebo"), height=420,
        xaxis=dict(gridcolor="#151c35"), yaxis=dict(gridcolor="#151c35",title="₪"),
        margin=dict(t=20,b=20), showlegend=False)
    st.plotly_chart(fig_wf, use_container_width=True)

# ── הוצאות קבועות ─────────────────────────────────────────
st.markdown("<div class='section-title'>📌 הוצאות קבועות ותשלומים</div>", unsafe_allow_html=True)
st.markdown("<div class='explain-box'><strong>קבועות</strong> = מזוהות אוטומטית לפי היסטוריה וכלי מפתח. <strong>📆 תשלומים</strong> = עסקאות בפריסה עם מעקב תשלום נוכחי / סה\"כ.</div>", unsafe_allow_html=True)

rc1,rc2,rc3 = st.columns(3)
rc1.metric("סה״כ קבועות חודשיות",f"₪{rec_summary['total_monthly_fixed']:,}",help="הוצאות שחוזרות כל חודש")
rc2.metric("כבר נגבו",f"₪{rec_summary['total_charged_so_far']:,}")
rc3.metric("עוד צפויות לרדת",f"₪{rec_summary['total_pending']:,}")

# timeline של הוצאות קבועות בחודש
all_rec = rec_summary["all_recurring"]
if all_rec:
    timeline_sorted = sorted(all_rec, key=lambda r: r["expected_day"])
    fig_tl = go.Figure()
    for r in timeline_sorted:
        color = "#4ade80" if r["charged_this_month"] else "#fbbf24" if r["expected_day"] >= today.day else "#f87171"
        fig_tl.add_trace(go.Scatter(
            x=[r["expected_day"]], y=[r["description"][:20]],
            mode="markers+text", text=[f"₪{r['avg_amount']:,}"],
            textposition="middle right", textfont=dict(color="white",size=10),
            marker=dict(size=14, color=color, symbol="circle"),
            hovertemplate=f"{r['description']}<br>₪{r['avg_amount']:,}<br>יום {r['expected_day']}<extra></extra>",
            showlegend=False))
    if is_current:
        fig_tl.add_vline(x=today.day, line_dash="dash", line_color="#6366f1",
                         annotation_text="היום", annotation_font_color="#6366f1")
    fig_tl.update_layout(paper_bgcolor="#0e1228", plot_bgcolor="#0e1228",
        font=dict(color="#9ca3af",family="Heebo"), height=max(200, len(all_rec)*30),
        xaxis=dict(gridcolor="#151c35", range=[0,32], title="יום בחודש"),
        yaxis=dict(gridcolor="rgba(0,0,0,0)"), margin=dict(l=10,r=100,t=10,b=30))
    st.plotly_chart(fig_tl, use_container_width=True)

tab_r1,tab_r2,tab_r3 = st.tabs(["⏳ צפויות","✅ שולם","📋 הכל"])
def render_rec(items):
    if not items:
        st.markdown("<p style='color:#374151;padding:12px'>אין נתונים</p>", unsafe_allow_html=True); return
    for r in items:
        badge = "color:#4ade80" if r["charged_this_month"] else "color:#f87171" if r["expected_day"]<today.day else "color:#fbbf24"
        label = "שולם ✓" if r["charged_this_month"] else "מאוחר" if r["expected_day"]<today.day else f"יום {r['expected_day']}"
        tag = "📆" if r["is_installment"] else "🔁" if r["months_seen"]>=3 else "📌"
        st.markdown(f"""<div class='txn-row'>
          <div><b style='color:white'>{tag} {r['description']}</b>
          <div style='color:#374151;font-size:0.75rem'>{r['months_seen']} חודשים | {"תשלומים" if r["is_installment"] else "קבוע"}</div></div>
          <div style='text-align:left'><b style='color:white'>₪{r['avg_amount']:,}</b>
          <div style='font-size:0.75rem;{badge};font-weight:700'>{label}</div></div>
        </div>""", unsafe_allow_html=True)

with tab_r1: render_rec(rec_summary["upcoming"]+rec_summary["overdue"])
with tab_r2: render_rec(rec_summary["charged"])
with tab_r3: render_rec(rec_summary["all_recurring"])

# ── עסקאות ────────────────────────────────────────────────
st.markdown("<div class='section-title'>📋 עסקאות</div>", unsafe_allow_html=True)
col_s, col_cat, col_exp = st.columns([3,2,1])
search = col_s.text_input("🔍","",placeholder="חפש עסקה...",label_visibility="collapsed")
cat_filter = col_cat.selectbox("קטגוריה",["הכל"]+sorted(month_exp["category"].unique().tolist()),label_visibility="collapsed")
col_exp.download_button("📥 CSV", data=month_exp[["date","description","category","amount"]].to_csv(index=False).encode("utf-8-sig"),
    file_name=f"expenses_{selected_month}.csv", mime="text/csv")

filtered = month_exp.copy()
if search: filtered = filtered[filtered["description"].str.contains(search,case=False,na=False)]
if cat_filter != "הכל": filtered = filtered[filtered["category"]==cat_filter]

display = filtered[["date","description","category","amount"]].sort_values("date",ascending=False).copy()
display["date"] = display["date"].dt.strftime("%d/%m/%Y")
display["amount"] = display["amount"].apply(lambda x: f"₪{x:,.0f}")
display.columns = ["תאריך","תיאור","קטגוריה","סכום"]
st.dataframe(display, use_container_width=True, hide_index=True, height=360)

# ── AI ────────────────────────────────────────────────────
st.markdown("<div class='section-title'>🤖 ניתוח AI — Maya</div>", unsafe_allow_html=True)

@st.cache_data(ttl=3600, show_spinner=False)
def get_ai_insight(month, total_spent, budget_val, pct_used, days_left_val, top_cats_str, velocity_val):
    try:
        client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY",""))
        msg = client.messages.create(model="claude-sonnet-4-6", max_tokens=150,
            messages=[{"role":"user","content":
                f"בדיוק 2-3 משפטים בעברית: בחודש {month} הוצאתי ₪{total_spent:,.0f} מתוך ₪{budget_val:,} ({pct_used:.0f}%). נותרו {days_left_val} ימים. קטגוריות עיקריות: {top_cats_str}. קצב הוצאה: {velocity_val:.0%} מהיעד. תן תובנה אחת חדה ומלצה אחת ספציפית."}])
        return msg.content[0].text
    except: return None

top_cats_str = ", ".join([f"{r['category']} ₪{r['amount']:,.0f}" for _,r in
    month_exp.groupby("category")["amount"].sum().reset_index().sort_values("amount",ascending=False).head(3).iterrows()])

auto_insight = get_ai_insight(selected_month, total, budget, pct, days_left, top_cats_str, velocity)
if auto_insight:
    st.markdown(f"<div style='background:#0a0e1f;border:1px solid #1a2240;border-left:3px solid #6366f1;border-radius:12px;padding:14px 18px;color:#c7d2fe;font-size:0.88rem;line-height:1.6'>🤖 <b>Maya:</b> {auto_insight}</div>", unsafe_allow_html=True)

if st.button("✨ ניתוח מעמיק + 3 המלצות"):
    txns_text = "\n".join([f"{r['date'].strftime('%d/%m')} | {r['category']} | ₪{r['amount']:.0f} | {r['description']}"
        for _,r in month_exp.iterrows()])
    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY",""))
    with st.spinner("Maya מנתחת..."):
        msg = client.messages.create(model="claude-sonnet-4-6", max_tokens=900,
            messages=[{"role":"user","content":
                f"אני מוציא ₪{total:,.0f} מתוך ₪{budget:,} ({pct:.0f}%). שיעור חיסכון: {savings_rate:.0f}%. נותרו {days_left} ימים.\n"
                f"הוצאות:\n{txns_text}\n\nתן 3 תובנות + 3 המלצות מעשיות עם מספרים. בעברית."}])
    st.markdown(f"<div style='background:#0e1228;border:1px solid #1a2240;border-radius:14px;padding:20px;color:#e2e8f0;line-height:1.7;white-space:pre-wrap'>{msg.content[0].text}</div>", unsafe_allow_html=True)
