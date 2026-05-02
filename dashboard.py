import streamlit as st
import json, os
from datetime import date
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

st.set_page_config(page_title="Finance Dashboard", page_icon="💰", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Heebo:wght@300;400;500;600;700;800;900&display=swap');
* { font-family: 'Heebo', sans-serif !important; }
.stApp { background: #060818; direction: rtl; }
section[data-testid="stSidebar"] { background: #0c0f1e; border-left: 1px solid #1a1f35; }
.stTabs [data-baseweb="tab-list"] { background: #0f1323; border-radius: 12px; padding: 4px; }
.stTabs [data-baseweb="tab"] { color: #6b7280; border-radius: 8px; }
.stTabs [aria-selected="true"] { background: #1e2340 !important; color: white !important; }

.kpi-card {
  background: linear-gradient(145deg, #0f1323, #141a2e);
  border: 1px solid #1e2540;
  border-radius: 20px;
  padding: 20px 22px;
  margin-bottom: 12px;
  position: relative;
  overflow: hidden;
  transition: transform 0.2s;
}
.kpi-card::before {
  content: '';
  position: absolute;
  top: 0; left: 0; right: 0;
  height: 3px;
  background: var(--accent);
  border-radius: 20px 20px 0 0;
}
.kpi-icon { font-size: 2rem; margin-bottom: 8px; display: block; }
.kpi-label { font-size: 0.7rem; color: #6b7280; text-transform: uppercase; letter-spacing: 1.5px; margin-bottom: 4px; }
.kpi-value { font-size: 1.9rem; font-weight: 900; color: var(--accent); line-height: 1; margin-bottom: 6px; }
.kpi-desc { font-size: 0.78rem; color: #9ca3af; line-height: 1.4; }
.kpi-sub { font-size: 0.82rem; color: #4b5563; margin-top: 6px; }

.section-title {
  font-size: 1rem; font-weight: 700; color: #e2e8f0;
  margin: 32px 0 16px; padding-right: 14px;
  border-right: 3px solid #6366f1;
  display: flex; align-items: center; gap: 8px;
}
.explain-box {
  background: #0f1528;
  border: 1px solid #1e2540;
  border-radius: 14px;
  padding: 14px 18px;
  margin-bottom: 20px;
  color: #9ca3af;
  font-size: 0.82rem;
  line-height: 1.6;
}
.explain-box strong { color: #c7d2fe; }

.txn-row {
  background: #0f1323;
  border: 1px solid #1a1f35;
  border-radius: 12px;
  padding: 12px 16px;
  margin-bottom: 8px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.tag { padding: 2px 10px; border-radius: 20px; font-size: 0.72rem; font-weight: 700; }
.tag-green { background: #052e16; color: #4ade80; }
.tag-red   { background: #2d0a0a; color: #f87171; }
.tag-yellow{ background: #2d1f00; color: #fbbf24; }
.tag-blue  { background: #0c1a3d; color: #60a5fa; }

div[data-testid="stButton"] button {
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
  color: white; border: none; border-radius: 12px;
  padding: 10px 20px; font-weight: 700; width: 100%;
}
</style>
""", unsafe_allow_html=True)

# ── auth ───────────────────────────────────────────────────
def check_password():
    if st.session_state.get("auth"): return True
    st.markdown("""
    <div style='text-align:center;padding:80px 0 20px'>
      <div style='font-size:4rem'>💰</div>
      <h1 style='color:white;font-size:2.2rem;font-weight:900'>Finance Dashboard</h1>
      <p style='color:#6b7280'>מעקב הוצאות חכם — הכנס סיסמה להמשיך</p>
    </div>""", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        pw = st.text_input("", type="password", placeholder="סיסמה...", label_visibility="collapsed")
        if st.button("כניסה", use_container_width=True):
            if pw == os.environ.get("DASHBOARD_PASSWORD", "finance2024"):
                st.session_state.auth = True; st.rerun()
            else:
                st.error("סיסמה שגויה")
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
    cats = {
        "🏠 דיור": ["משכנת", "שכר דירה", "ועד"],
        "🍔 מזון": ["סופר", "מכולת", "אוכל", "מסעדה", "קפה", "פיצה", "שוורמה", "מזון"],
        "🚗 תחבורה": ["דלק", "חניה", "רכבת", "אוטובוס", "taxi", "uber", "גט", "רכב"],
        "🛡️ ביטוחים": ["ביטוח", "הפניקס", "מגדל", "הראל", "כלל", "מנורה"],
        "📱 תקשורת": ["סלקום", "פרטנר", "hot", "בזק", "yes", "גולן", "אורנג"],
        "🎓 חינוך": ["גן", "צהרון", "חוג", "לימוד", "קורס", "אוניברסיטה"],
        "🛍️ קניות": ["אמזון", "זארה", "h&m", "קניון", "כסף", "shop"],
        "⚡ שירותים": ["חשמל", "מים", "גז", "ארנונה"],
        "🎬 בידור": ["נטפליקס", "netflix", "spotify", "apple", "גוגל", "disney"],
        "🏥 בריאות": ["רופא", "בית חולים", "מרפאה", "תרופ", "קופת חולים", "דנטל"],
    }
    for cat, kws in cats.items():
        if any(k in desc for k in kws):
            return cat
    return "📦 אחר"

def to_df(data):
    rows = []
    for acc in data["accounts"]:
        for t in acc["txns"]:
            amt = t.get("chargedAmount", 0)
            rows.append({
                "date": pd.to_datetime(t.get("date", "")[:10]),
                "amount": abs(amt),
                "raw": amt,
                "description": t.get("description", ""),
                "memo": t.get("memo", ""),
                "type": "הוצאה" if amt < 0 else "הכנסה",
            })
    df = pd.DataFrame(rows)
    df["month"] = df["date"].dt.strftime("%Y-%m")
    df["day"] = df["date"].dt.day
    df["dow"] = df["date"].dt.dayofweek
    df["dow_name"] = df["date"].dt.day_name()
    df["week"] = df["date"].dt.isocalendar().week.astype(int)
    df["category"] = df["description"].apply(categorize)
    return df

data = load_data()
if not data:
    st.warning("אין נתונים עדיין"); st.stop()

df = to_df(data)
expenses = df[df["type"] == "הוצאה"]
income_df = df[df["type"] == "הכנסה"]

# ── sidebar ────────────────────────────────────────────────
with st.sidebar:
    st.markdown("<h2 style='color:white;text-align:center;font-weight:900;font-size:1.4rem'>💰 Finance</h2>", unsafe_allow_html=True)
    st.markdown("<hr style='border-color:#1e2540'>", unsafe_allow_html=True)

    all_months = sorted(expenses["month"].unique(), reverse=True)
    selected_month = st.selectbox("📅 בחר חודש", all_months, index=0)
    budget = st.number_input("🎯 יעד חודשי (₪)", value=BUDGET, step=1000)

    st.markdown("<hr style='border-color:#1e2540'>", unsafe_allow_html=True)
    updated = data.get("scrapedAt", "")[:10]
    st.markdown(f"<p style='color:#4b5563;font-size:0.72rem;text-align:center'>עדכון אחרון: {updated}<br>מתעדכן אוטומטית 08:00</p>", unsafe_allow_html=True)

# ── חישובים ────────────────────────────────────────────────
month_exp = expenses[expenses["month"] == selected_month]
today = date.today()
is_current = selected_month == today.strftime("%Y-%m")
days_in_month = monthrange(int(selected_month[:4]), int(selected_month[5:7]))[1]
days_passed = today.day if is_current else days_in_month
days_left = max(0, days_in_month - days_passed)

total = month_exp["amount"].sum()
daily_avg = total / days_passed if days_passed > 0 else 0
estimated = daily_avg * days_in_month if is_current else total
pct = min((total / budget) * 100, 100)

rec_summary = build_recurring_summary(expenses.to_dict("records"))
pending_fixed = rec_summary["total_pending"] if is_current else 0
estimated_with_fixed = estimated + pending_fixed
remaining = max(0, budget - estimated_with_fixed)

income_this = income_df[income_df["month"] == selected_month]["amount"].sum()
savings_est = income_this - estimated_with_fixed

# ── header ─────────────────────────────────────────────────
month_heb = {
    "01": "ינואר", "02": "פברואר", "03": "מרץ", "04": "אפריל",
    "05": "מאי", "06": "יוני", "07": "יולי", "08": "אוגוסט",
    "09": "ספטמבר", "10": "אוקטובר", "11": "נובמבר", "12": "דצמבר"
}
m_name = month_heb.get(selected_month[5:], "") + " " + selected_month[:4]
status_color = "#4ade80" if estimated_with_fixed <= budget else "#f87171"
status_text = "✅ בתקציב" if estimated_with_fixed <= budget else "⚠️ חריגה צפויה"

st.markdown(f"""
<div style='display:flex;justify-content:space-between;align-items:center;margin-bottom:24px'>
  <div>
    <h1 style='color:white;margin:0;font-weight:900;font-size:2rem'>📊 {m_name}</h1>
    <p style='color:#6b7280;margin:4px 0 0'>מעקב הוצאות אישי</p>
  </div>
  <div style='background:#0f1323;border:1px solid #1e2540;border-radius:14px;padding:10px 20px;text-align:center'>
    <div style='font-size:1.1rem;font-weight:800;color:{status_color}'>{status_text}</div>
    <div style='font-size:0.75rem;color:#6b7280'>{pct:.0f}% מהיעד נוצל</div>
  </div>
</div>
""", unsafe_allow_html=True)

# ── KPIs עם הסברים ─────────────────────────────────────────
st.markdown("<div class='section-title'>📌 מדדים מרכזיים</div>", unsafe_allow_html=True)
st.markdown("""
<div class='explain-box'>
  כל מדד מציג זווית אחרת על ההוצאות שלך.<br>
  <strong>הוצאות עד היום</strong> — מה הוצאת בפועל עד עכשיו.
  <strong>תחזית</strong> — אם תמשיך באותו קצב, כמה תוציא עד סוף החודש (כולל קבועות).
  <strong>נותר</strong> — כמה תוכל להוציא עד סוף החודש בלי לחרוג.
  <strong>ממוצע יומי</strong> — כמה אתה מוציא בממוצע ביום לעומת היעד.
  <strong>חיסכון משוער</strong> — הכנסות פחות כל ההוצאות הצפויות.
</div>
""", unsafe_allow_html=True)

def kpi(col, icon, label, value, desc, accent, sub=""):
    col.markdown(f"""
    <div class='kpi-card' style='--accent:{accent}'>
      <span class='kpi-icon'>{icon}</span>
      <div class='kpi-label'>{label}</div>
      <div class='kpi-value'>₪{value:,.0f}</div>
      <div class='kpi-desc'>{desc}</div>
      {"<div class='kpi-sub'>" + sub + "</div>" if sub else ""}
    </div>""", unsafe_allow_html=True)

c1, c2, c3, c4, c5 = st.columns(5)
kpi(c1, "💳", "הוצאות עד היום", total,
    f"שהוצאת ב-{days_passed} ימים אחרונים", "#6366f1",
    f"{pct:.0f}% מהיעד החודשי")
kpi(c2, "🔮", "תחזית לסוף חודש", estimated_with_fixed,
    "אם תמשיך באותו קצב + קבועות", status_color,
    status_text)
kpi(c3, "🟡", "נותר להוצאה", remaining,
    f"ל-{days_left} ימים שנותרו", "#fbbf24",
    f"₪{remaining/days_left:,.0f}/יום אם תרצה" if days_left > 0 else "")
kpi(c4, "📈", "ממוצע יומי", daily_avg,
    "כמה אתה מוציא ביום בממוצע",
    "#4ade80" if daily_avg <= budget / days_in_month else "#f87171",
    f"יעד: ₪{budget/days_in_month:,.0f}/יום")
kpi(c5, "💰", "חיסכון משוער", max(0, savings_est),
    "הכנסות פחות הוצאות הצפויות",
    "#4ade80" if savings_est > 0 else "#f87171",
    f"הכנסות: ₪{income_this:,.0f}" if income_this > 0 else "לא זוהו הכנסות")

# ── gauge + cumulative ─────────────────────────────────────
st.markdown("<div class='section-title'>📉 ניתוח עומק</div>", unsafe_allow_html=True)

g1, g2 = st.columns([1, 2])

with g1:
    st.markdown("""<div class='explain-box'>
    <strong>מד תקציב</strong> — מראה בצורה ויזואלית כמה מהתקציב החודשי נוצל.
    🟢 פחות מ-70% — מצוין | 🟡 70-90% — שים לב | 🔴 מעל 90% — חריגה קרובה
    </div>""", unsafe_allow_html=True)
    gauge_color = "#4ade80" if pct < 70 else "#fbbf24" if pct < 90 else "#f87171"
    fig_gauge = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=total,
        delta={"reference": budget, "valueformat": ",.0f", "increasing": {"color": "#f87171"}, "decreasing": {"color": "#4ade80"}},
        number={"prefix": "₪", "valueformat": ",.0f", "font": {"color": "white", "size": 26}},
        gauge={
            "axis": {"range": [0, budget * 1.2], "tickcolor": "#374151", "tickfont": {"color": "#6b7280"}},
            "bar": {"color": gauge_color, "thickness": 0.35},
            "bgcolor": "#1a1f35",
            "bordercolor": "#252b45",
            "steps": [
                {"range": [0, budget * 0.7], "color": "#0a2e1a"},
                {"range": [budget * 0.7, budget * 0.9], "color": "#2d1f00"},
                {"range": [budget * 0.9, budget * 1.2], "color": "#2d0a0a"},
            ],
            "threshold": {"line": {"color": "#f87171", "width": 3}, "value": budget},
        }
    ))
    fig_gauge.update_layout(
        paper_bgcolor="#0f1323", font={"color": "white", "family": "Heebo"},
        height=260, margin=dict(t=20, b=10, l=20, r=20)
    )
    st.plotly_chart(fig_gauge, use_container_width=True)

with g2:
    st.markdown("""<div class='explain-box'>
    <strong>הוצאות מצטברות</strong> — קו סגול = החודש הנוכחי. קווים מנוקדים = חודשים קודמים.
    הקו האדום = גבול התקציב. אם הקו הסגול חוצה את האדום — חרגת.
    </div>""", unsafe_allow_html=True)
    past_months = sorted([m for m in expenses["month"].unique() if m < selected_month])[-3:]
    fig_trend = go.Figure()

    for i, m in enumerate(past_months):
        m_exp = expenses[expenses["month"] == m]
        daily = m_exp.groupby("day")["amount"].sum().reset_index()
        daily["cumulative"] = daily["amount"].cumsum()
        fig_trend.add_trace(go.Scatter(
            x=daily["day"], y=daily["cumulative"], mode="lines",
            name=m, line=dict(color=["#2d3561", "#3d4a7a", "#4e5f9a"][i], width=1.5, dash="dot"),
            opacity=0.5,
        ))

    curr_daily = month_exp.groupby("day")["amount"].sum().reset_index()
    curr_daily["cumulative"] = curr_daily["amount"].cumsum()
    fig_trend.add_trace(go.Scatter(
        x=curr_daily["day"], y=curr_daily["cumulative"], mode="lines+markers",
        name=selected_month, line=dict(color="#6366f1", width=3),
        marker=dict(size=5, color="#6366f1"),
        fill="tozeroy", fillcolor="rgba(99,102,241,0.07)"
    ))
    fig_trend.add_hline(y=budget, line_dash="dash", line_color="#f87171",
                        annotation_text=f"יעד ₪{budget:,}", annotation_font_color="#f87171")
    fig_trend.update_layout(
        paper_bgcolor="#0f1323", plot_bgcolor="#0f1323",
        font=dict(color="#9ca3af", family="Heebo"), height=260,
        legend=dict(bgcolor="#141a2e", bordercolor="#252b45", x=0, y=1),
        xaxis=dict(gridcolor="#1a1f35", title="יום בחודש"),
        yaxis=dict(gridcolor="#1a1f35", title="₪ מצטבר"),
        margin=dict(t=10, b=40, l=10, r=20),
        hovermode="x unified",
    )
    st.plotly_chart(fig_trend, use_container_width=True)

# ── גרפים מפורטים ─────────────────────────────────────────
st.markdown("<div class='section-title'>📊 גרפים מפורטים</div>", unsafe_allow_html=True)

tabs = st.tabs(["🥧 קטגוריות", "📅 יומי", "🗓️ לפי יום בשבוע", "🔥 Heatmap", "🏪 עסקים", "📆 חודשי", "💧 Waterfall"])

# Tab 1 - categories
with tabs[0]:
    st.markdown("""<div class='explain-box'>
    <strong>לפי קטגוריה</strong> — הגרף העגול מראה את חלוקת ההוצאות לפי תחום חיים.
    לחץ על קטגוריה בעיגול כדי לבודד אותה. עמודות = אותו מידע בצורה השוואתית.
    </div>""", unsafe_allow_html=True)
    cat_df = month_exp.groupby("category")["amount"].sum().reset_index().sort_values("amount", ascending=False)
    COLORS = px.colors.qualitative.Pastel

    col_pie, col_bar = st.columns(2)
    with col_pie:
        fig_pie = go.Figure(go.Pie(
            labels=cat_df["category"], values=cat_df["amount"],
            hole=0.55, textinfo="label+percent",
            marker=dict(colors=COLORS, line=dict(color="#060818", width=2)),
            pull=[0.05 if i == 0 else 0 for i in range(len(cat_df))],
        ))
        fig_pie.update_layout(
            paper_bgcolor="#0f1323", font=dict(color="white", family="Heebo"),
            showlegend=False, height=340,
            annotations=[dict(text=f"<b>₪{total:,.0f}</b>", x=0.5, y=0.5,
                              font_size=16, font_color="white", showarrow=False)]
        )
        st.plotly_chart(fig_pie, use_container_width=True)

    with col_bar:
        fig_bar = go.Figure(go.Bar(
            y=cat_df["category"], x=cat_df["amount"], orientation="h",
            marker=dict(color=COLORS[:len(cat_df)], line=dict(color="rgba(0,0,0,0)")),
            text=[f"₪{v:,.0f}" for v in cat_df["amount"]],
            textposition="outside", textfont=dict(color="white", size=11),
        ))
        fig_bar.update_layout(
            paper_bgcolor="#0f1323", plot_bgcolor="#0f1323",
            font=dict(color="#9ca3af", family="Heebo"), height=340,
            xaxis=dict(gridcolor="#1a1f35", showticklabels=False),
            yaxis=dict(gridcolor="rgba(0,0,0,0)"),
            margin=dict(l=10, r=80, t=10, b=10),
        )
        st.plotly_chart(fig_bar, use_container_width=True)

# Tab 2 - daily bar
with tabs[1]:
    st.markdown("""<div class='explain-box'>
    <strong>הוצאות לפי יום</strong> — כל עמודה = יום בחודש.
    🟢 מתחת לממוצע | 🟡 קצת מעל | 🔴 יום יקר במיוחד (1.5x+ ממוצע).
    לחץ על עמודה לפרטים.
    </div>""", unsafe_allow_html=True)
    daily = month_exp.groupby("day")["amount"].sum().reset_index()
    avg_d = daily["amount"].mean()
    colors_d = ["#f87171" if v > avg_d * 1.5 else "#fbbf24" if v > avg_d else "#4ade80" for v in daily["amount"]]
    fig_daily = go.Figure(go.Bar(
        x=daily["day"], y=daily["amount"], marker_color=colors_d,
        text=[f"₪{v:,.0f}" for v in daily["amount"]],
        textposition="outside", textfont=dict(color="white", size=9),
        hovertemplate="יום %{x}<br>₪%{y:,.0f}<extra></extra>",
    ))
    fig_daily.add_hline(y=avg_d, line_dash="dash", line_color="#6366f1",
                        annotation_text=f"ממוצע ₪{avg_d:,.0f}", annotation_font_color="#6366f1")
    fig_daily.update_layout(
        paper_bgcolor="#0f1323", plot_bgcolor="#0f1323",
        font=dict(color="#9ca3af", family="Heebo"), height=380,
        xaxis=dict(gridcolor="#1a1f35", title="יום בחודש", dtick=1),
        yaxis=dict(gridcolor="#1a1f35"),
        margin=dict(t=30, b=40),
        bargap=0.3,
    )
    st.plotly_chart(fig_daily, use_container_width=True)

# Tab 3 - day of week
with tabs[2]:
    st.markdown("""<div class='explain-box'>
    <strong>לפי יום בשבוע</strong> — באיזה ימים אתה מוציא הכי הרבה?
    זה עוזר לזהות דפוסים כמו "קניות כל שישי" או "הוצאות גבוהות בסוף שבוע".
    </div>""", unsafe_allow_html=True)
    dow_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    dow_heb = {"Monday": "שני", "Tuesday": "שלישי", "Wednesday": "רביעי",
               "Thursday": "חמישי", "Friday": "שישי", "Saturday": "שבת", "Sunday": "ראשון"}
    dow_df = month_exp.groupby("dow_name")["amount"].mean().reindex(dow_order).reset_index()
    dow_df["heb"] = dow_df["dow_name"].map(dow_heb)
    dow_df["amount"] = dow_df["amount"].fillna(0)
    max_val = dow_df["amount"].max()
    dow_df["color"] = dow_df["amount"].apply(
        lambda v: "#f87171" if v == max_val else "#6366f1" if v > max_val * 0.7 else "#3d4a7a"
    )
    fig_dow = go.Figure(go.Bar(
        x=dow_df["heb"], y=dow_df["amount"], marker_color=dow_df["color"],
        text=[f"₪{v:,.0f}" if v > 0 else "" for v in dow_df["amount"]],
        textposition="outside", textfont=dict(color="white"),
        hovertemplate="%{x}<br>ממוצע ₪%{y:,.0f}<extra></extra>",
    ))
    fig_dow.update_layout(
        paper_bgcolor="#0f1323", plot_bgcolor="#0f1323",
        font=dict(color="#9ca3af", family="Heebo"), height=360,
        xaxis=dict(gridcolor="#1a1f35"),
        yaxis=dict(gridcolor="#1a1f35", title="ממוצע הוצאה יומית ₪"),
        margin=dict(t=30, b=20),
    )
    st.plotly_chart(fig_dow, use_container_width=True)

# Tab 4 - heatmap
with tabs[3]:
    st.markdown("""<div class='explain-box'>
    <strong>Heatmap — מפת חום</strong> — כל תא = יום אחד. צבע כהה יותר = הוצאה גבוהה יותר.
    קל לראות במבט אחד אילו שבועות היו יקרים ואילו חסכוניים.
    </div>""", unsafe_allow_html=True)
    pivot_data = month_exp.copy()
    pivot_data["week_num"] = (pivot_data["day"] - 1) // 7
    pivot_data["dow2"] = pivot_data["date"].dt.dayofweek
    heat = pivot_data.groupby(["week_num", "dow2"])["amount"].sum().reset_index()
    heat_matrix = heat.pivot(index="week_num", columns="dow2", values="amount").fillna(0)
    all_cols = list(range(7))
    for c in all_cols:
        if c not in heat_matrix.columns:
            heat_matrix[c] = 0
    heat_matrix = heat_matrix[sorted(heat_matrix.columns)]
    dow_labels = ["שני", "שלישי", "רביעי", "חמישי", "שישי", "שבת", "ראשון"]
    week_labels = [f"שבוע {i+1}" for i in heat_matrix.index]

    fig_heat = go.Figure(go.Heatmap(
        z=heat_matrix.values,
        x=dow_labels,
        y=week_labels,
        colorscale=[[0, "#0f1323"], [0.3, "#1e2d6b"], [0.6, "#6366f1"], [1, "#f87171"]],
        text=[[f"₪{v:,.0f}" if v > 0 else "" for v in row] for row in heat_matrix.values],
        texttemplate="%{text}",
        textfont=dict(color="white", size=11),
        showscale=True,
        colorbar=dict(tickfont=dict(color="#9ca3af"), bgcolor="#0f1323"),
    ))
    fig_heat.update_layout(
        paper_bgcolor="#0f1323", font=dict(color="#9ca3af", family="Heebo"),
        height=300, margin=dict(t=20, b=20, l=80, r=20),
        xaxis=dict(side="top"),
    )
    st.plotly_chart(fig_heat, use_container_width=True)

# Tab 5 - top merchants
with tabs[4]:
    st.markdown("""<div class='explain-box'>
    <strong>עסקים מובילים</strong> — 15 העסקים שאצלם הוצאת הכי הרבה החודש.
    שימושי לזהות היכן הולך הכסף בפועל, לפי שם העסק.
    </div>""", unsafe_allow_html=True)
    top = month_exp.groupby("description")["amount"].sum().reset_index().sort_values("amount", ascending=False).head(15)
    fig_top = go.Figure(go.Bar(
        y=top["description"], x=top["amount"], orientation="h",
        marker=dict(
            color=top["amount"],
            colorscale=[[0, "#3d4a7a"], [0.5, "#6366f1"], [1, "#f87171"]],
            showscale=False,
        ),
        text=[f"₪{v:,.0f}" for v in top["amount"]],
        textposition="outside", textfont=dict(color="white", size=11),
        hovertemplate="%{y}<br>₪%{x:,.0f}<extra></extra>",
    ))
    fig_top.update_layout(
        paper_bgcolor="#0f1323", plot_bgcolor="#0f1323",
        font=dict(color="#9ca3af", family="Heebo"), height=500,
        xaxis=dict(gridcolor="#1a1f35", showticklabels=False),
        yaxis=dict(gridcolor="rgba(0,0,0,0)", categoryorder="total ascending"),
        margin=dict(l=10, r=80, t=10, b=10),
    )
    st.plotly_chart(fig_top, use_container_width=True)

# Tab 6 - monthly comparison
with tabs[5]:
    st.markdown("""<div class='explain-box'>
    <strong>השוואה חודשית</strong> — השוואה של כל החודשים שיש נתונים עליהם.
    הקו האדום המנוקד = התקציב שהגדרת. החודש הנוכחי מודגש בסגול בהיר.
    </div>""", unsafe_allow_html=True)
    monthly = expenses.groupby("month")["amount"].sum().reset_index()
    monthly["color"] = ["#6366f1" if m == selected_month else "#2d3561" for m in monthly["month"]]
    monthly["avg_daily"] = monthly.apply(
        lambda r: r["amount"] / monthrange(int(r["month"][:4]), int(r["month"][5:7]))[1], axis=1
    )

    col_m1, col_m2 = st.columns(2)
    with col_m1:
        fig_monthly = go.Figure(go.Bar(
            x=monthly["month"], y=monthly["amount"], marker_color=monthly["color"],
            text=[f"₪{v:,.0f}" for v in monthly["amount"]],
            textposition="outside", textfont=dict(color="white", size=10),
        ))
        fig_monthly.add_hline(y=budget, line_dash="dash", line_color="#f87171",
                              annotation_text=f"יעד ₪{budget:,}", annotation_font_color="#f87171")
        fig_monthly.update_layout(
            paper_bgcolor="#0f1323", plot_bgcolor="#0f1323",
            font=dict(color="#9ca3af", family="Heebo"), height=340,
            title=dict(text="סה\"כ הוצאות לפי חודש", font=dict(color="white", size=13)),
            xaxis=dict(gridcolor="#1a1f35"),
            yaxis=dict(gridcolor="#1a1f35"),
            margin=dict(t=40, b=20),
        )
        st.plotly_chart(fig_monthly, use_container_width=True)

    with col_m2:
        fig_avg = go.Figure(go.Scatter(
            x=monthly["month"], y=monthly["avg_daily"],
            mode="lines+markers",
            line=dict(color="#8b5cf6", width=2.5),
            marker=dict(size=8, color="#8b5cf6", symbol="circle"),
            fill="tozeroy", fillcolor="rgba(139,92,246,0.08)",
            hovertemplate="%{x}<br>₪%{y:,.0f}/יום<extra></extra>",
        ))
        fig_avg.add_hline(y=budget / 30, line_dash="dash", line_color="#fbbf24",
                          annotation_text="יעד יומי", annotation_font_color="#fbbf24")
        fig_avg.update_layout(
            paper_bgcolor="#0f1323", plot_bgcolor="#0f1323",
            font=dict(color="#9ca3af", family="Heebo"), height=340,
            title=dict(text="ממוצע הוצאה יומית לפי חודש", font=dict(color="white", size=13)),
            xaxis=dict(gridcolor="#1a1f35"),
            yaxis=dict(gridcolor="#1a1f35", title="₪/יום"),
            margin=dict(t=40, b=20),
        )
        st.plotly_chart(fig_avg, use_container_width=True)

# Tab 7 - waterfall
with tabs[6]:
    st.markdown("""<div class='explain-box'>
    <strong>Waterfall — גרף מפל</strong> — מראה איך התקציב "נשחק" מחודש לחודש לפי קטגוריות.
    כל בלוק אדום = כמה קטגוריה מסוימת "אוכלת" מהתקציב. הבלוק הסגול = מה נותר.
    </div>""", unsafe_allow_html=True)
    cat_wf = month_exp.groupby("category")["amount"].sum().reset_index().sort_values("amount", ascending=False)
    measures = ["relative"] * len(cat_wf) + ["total"]
    x_vals = list(cat_wf["category"]) + ["💼 נותר לתקציב"]
    y_vals = list(-cat_wf["amount"]) + [budget]

    fig_wf = go.Figure(go.Waterfall(
        name="תקציב",
        orientation="v",
        measure=measures,
        x=x_vals,
        y=y_vals,
        base=budget,
        connector=dict(line=dict(color="#1e2540", width=1)),
        decreasing=dict(marker=dict(color="#f87171")),
        increasing=dict(marker=dict(color="#4ade80")),
        totals=dict(marker=dict(color="#6366f1")),
        text=[f"₪{abs(v):,.0f}" for v in y_vals],
        textposition="outside",
        textfont=dict(color="white", size=10),
    ))
    fig_wf.update_layout(
        paper_bgcolor="#0f1323", plot_bgcolor="#0f1323",
        font=dict(color="#9ca3af", family="Heebo"), height=420,
        xaxis=dict(gridcolor="#1a1f35"),
        yaxis=dict(gridcolor="#1a1f35", title="₪"),
        margin=dict(t=20, b=20),
        showlegend=False,
    )
    st.plotly_chart(fig_wf, use_container_width=True)

# ── הוצאות קבועות ─────────────────────────────────────────
st.markdown("<div class='section-title'>📌 הוצאות קבועות</div>", unsafe_allow_html=True)
st.markdown("""<div class='explain-box'>
<strong>הוצאות קבועות</strong> — תשלומים שחוזרים כל חודש: משכנתא, ביטוחים, מנויים, תשלומים בתשלומים.
המערכת מזהה אותם אוטומטית לפי היסטוריית העסקאות שלך.<br>
<strong>צפויות לרדת</strong> = עדיין לא ירדו החודש | <strong>כבר שולם</strong> = ירדו ✅
</div>""", unsafe_allow_html=True)

rc1, rc2, rc3 = st.columns(3)
rc1.metric("סה״כ קבועות חודשיות", f"₪{rec_summary['total_monthly_fixed']:,}", help="סכום כל ההוצאות הקבועות המזוהות")
rc2.metric("כבר נגבו החודש", f"₪{rec_summary['total_charged_so_far']:,}", help="מה כבר ירד מהחשבון")
rc3.metric("עוד צפויות לרדת", f"₪{rec_summary['total_pending']:,}", help="מה עוד צפוי לרדת עד סוף החודש")

tab_r1, tab_r2, tab_r3 = st.tabs(["⏳ צפויות לרדת", "✅ כבר שולם", "📋 הכל"])

def render_rec(items):
    if not items:
        st.markdown("<p style='color:#4b5563;padding:12px'>אין נתונים</p>", unsafe_allow_html=True)
        return
    for r in items:
        badge_cls = "tag-green" if r["charged_this_month"] else "tag-red" if r["expected_day"] < date.today().day else "tag-yellow"
        label = "שולם ✓" if r["charged_this_month"] else "מאוחר" if r["expected_day"] < date.today().day else f"יום {r['expected_day']}"
        tag_type = "📆" if r["is_installment"] else "🔁" if r["months_seen"] >= 3 else "📌"
        st.markdown(f"""
        <div class='txn-row'>
          <div>
            <b style='color:white'>{tag_type} {r['description']}</b>
            <div style='color:#4b5563;font-size:0.78rem'>{r['months_seen']} חודשים | {"תשלומים" if r["is_installment"] else "קבוע"}</div>
          </div>
          <div style='text-align:left'>
            <b style='color:white;font-size:1.1rem'>₪{r['avg_amount']:,}</b>
            <div><span class='tag {badge_cls}'>{label}</span></div>
          </div>
        </div>""", unsafe_allow_html=True)

with tab_r1: render_rec(rec_summary["upcoming"] + rec_summary["overdue"])
with tab_r2: render_rec(rec_summary["charged"])
with tab_r3: render_rec(rec_summary["all_recurring"])

# ── עסקאות ────────────────────────────────────────────────
st.markdown("<div class='section-title'>📋 כל העסקאות</div>", unsafe_allow_html=True)
st.markdown("""<div class='explain-box'>
רשימת כל העסקאות בחודש הנבחר. ניתן לחפש לפי שם עסק.
הנתונים מגיעים ישירות מחשבון הבנק שלך ומתעדכנים כל יום.
</div>""", unsafe_allow_html=True)

search = st.text_input("🔍 חפש עסקה", placeholder="שם עסק...", label_visibility="collapsed")
filtered = month_exp.copy()
if search:
    filtered = filtered[filtered["description"].str.contains(search, case=False, na=False)]

display = filtered[["date", "description", "category", "amount"]].sort_values("date", ascending=False).copy()
display["date"] = display["date"].dt.strftime("%d/%m/%Y")
display["amount"] = display["amount"].apply(lambda x: f"₪{x:,.0f}")
display.columns = ["תאריך", "תיאור", "קטגוריה", "סכום"]
st.dataframe(display, use_container_width=True, hide_index=True, height=380)

# ── AI ────────────────────────────────────────────────────
st.markdown("<div class='section-title'>🤖 ניתוח AI אישי</div>", unsafe_allow_html=True)
st.markdown("""<div class='explain-box'>
<strong>Maya</strong> — הסוכן החכם שלנו, מנתח את ההוצאות שלך ונותן המלצות מותאמות אישית.
הניתוח מסתמך על כל העסקאות של החודש ומשווה לחודשים קודמים.
</div>""", unsafe_allow_html=True)

if st.button("✨ קבל ניתוח וטיפים אישיים מ-Maya"):
    txns_text = "\n".join([
        f"{r['date'].strftime('%d/%m')} | {r['category']} | ₪{r['amount']:.0f} | {r['description']}"
        for _, r in month_exp.iterrows()
    ])
    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    with st.spinner("Maya מנתחת את ההוצאות שלך..."):
        msg = client.messages.create(
            model="claude-sonnet-4-6", max_tokens=900,
            messages=[{"role": "user", "content":
                f"אני מוציא ₪{total:,.0f} מתוך תקציב של ₪{budget:,} ({pct:.0f}%).\n"
                f"נותרו {days_left} ימים בחודש.\n"
                f"הוצאות החודש:\n{txns_text}\n\n"
                f"תן לי 3 תובנות ספציפיות ו-3 המלצות מעשיות בעברית. היה ספציפי עם מספרים."}]
        )
    st.markdown(f"""
    <div style='background:#0f1323;border:1px solid #1e2540;border-radius:16px;padding:24px;color:#e2e8f0;line-height:1.7;white-space:pre-wrap'>
    {msg.content[0].text}
    </div>""", unsafe_allow_html=True)
