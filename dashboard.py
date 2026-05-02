import streamlit as st
import json, os
from datetime import date, timedelta
from dotenv import load_dotenv
import anthropic
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
from agents.recurring_summary import build_recurring_summary
from calendar import monthrange

load_dotenv()
BUDGET = 32000

st.set_page_config(page_title="Finance Dashboard", page_icon="💰", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Heebo:wght@300;400;500;600;700;800&display=swap');
* { font-family: 'Heebo', sans-serif !important; }
.stApp { background: #0a0d1a; direction: rtl; }
section[data-testid="stSidebar"] { background: #0f1323; border-right: 1px solid #1e2235; }
.metric-card { background: linear-gradient(145deg, #141728, #1a1f35); border: 1px solid #252b45; border-radius: 20px; padding: 24px; margin-bottom: 16px; }
.metric-value { font-size: 2rem; font-weight: 800; margin: 6px 0; }
.metric-label { font-size: 0.8rem; color: #6b7280; text-transform: uppercase; letter-spacing: 1px; }
.metric-sub { font-size: 0.85rem; color: #9ca3af; margin-top: 4px; }
.section-header { font-size: 1.1rem; font-weight: 700; color: #e2e8f0; margin: 28px 0 16px; padding-right: 12px; border-right: 3px solid #6366f1; }
.tag-green { background: #052e16; color: #4ade80; padding: 2px 10px; border-radius: 20px; font-size: 0.75rem; font-weight: 600; }
.tag-red { background: #2d0a0a; color: #f87171; padding: 2px 10px; border-radius: 20px; font-size: 0.75rem; font-weight: 600; }
.tag-yellow { background: #2d1f00; color: #fbbf24; padding: 2px 10px; border-radius: 20px; font-size: 0.75rem; font-weight: 600; }
.txn-row { background: #141728; border: 1px solid #1e2235; border-radius: 12px; padding: 12px 16px; margin-bottom: 8px; display: flex; justify-content: space-between; align-items: center; }
div[data-testid="stButton"] button { background: linear-gradient(135deg, #6366f1, #8b5cf6); color: white; border: none; border-radius: 12px; padding: 10px 20px; font-weight: 600; width: 100%; transition: all 0.2s; }
div[data-testid="stMetric"] { background: #141728; border: 1px solid #1e2235; border-radius: 16px; padding: 16px; }
</style>
""", unsafe_allow_html=True)

# ── auth ───────────────────────────────────────────────────
def check_password():
    if st.session_state.get("auth"): return True
    st.markdown("<div style='text-align:center;padding:80px 0 20px'><h1 style='color:white;font-size:2.5rem'>💰 Finance</h1><p style='color:#6b7280'>הכנס סיסמה להמשיך</p></div>", unsafe_allow_html=True)
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

def to_df(data):
    rows = []
    for acc in data["accounts"]:
        for t in acc["txns"]:
            amt = t.get("chargedAmount", 0)
            rows.append({
                "date": pd.to_datetime(t.get("date","")[:10]),
                "amount": abs(amt),
                "raw": amt,
                "description": t.get("description",""),
                "memo": t.get("memo",""),
                "type": "הוצאה" if amt < 0 else "הכנסה",
            })
    df = pd.DataFrame(rows)
    df["month"] = df["date"].dt.strftime("%Y-%m")
    df["day"] = df["date"].dt.day
    df["week"] = df["date"].dt.isocalendar().week.astype(int)
    df["dow"] = df["date"].dt.dayofweek
    return df

data = load_data()
if not data:
    st.warning("אין נתונים עדיין"); st.stop()

df = to_df(data)
expenses = df[df["type"] == "הוצאה"]
income_df = df[df["type"] == "הכנסה"]

# ── sidebar ────────────────────────────────────────────────
with st.sidebar:
    st.markdown("<h2 style='color:white;text-align:center;margin-bottom:24px'>💰 Finance</h2>", unsafe_allow_html=True)

    all_months = sorted(expenses["month"].unique(), reverse=True)
    selected_month = st.selectbox("📅 חודש", all_months, index=0)

    st.markdown("---")
    budget = st.number_input("🎯 יעד חודשי (₪)", value=BUDGET, step=1000)
    st.markdown("---")

    updated = data.get("scrapedAt","")[:10]
    st.markdown(f"<p style='color:#6b7280;font-size:0.75rem;text-align:center'>עדכון אחרון: {updated}</p>", unsafe_allow_html=True)
    st.markdown("<p style='color:#6b7280;font-size:0.75rem;text-align:center'>מתעדכן אוטומטית 08:00</p>", unsafe_allow_html=True)

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
remaining = max(0, budget - estimated)

rec_summary = build_recurring_summary(expenses.to_dict("records"))
pending_fixed = rec_summary["total_pending"] if is_current else 0
estimated_with_fixed = estimated + pending_fixed

income_this = income_df[income_df["month"] == selected_month]["amount"].sum()
savings_est = income_this - estimated_with_fixed

# ── KPIs ───────────────────────────────────────────────────
st.markdown(f"<h1 style='color:white;margin-bottom:4px'>📊 {selected_month}</h1>", unsafe_allow_html=True)

c1,c2,c3,c4,c5 = st.columns(5)
def kpi(col, label, value, sub, color="#6366f1", tag=None):
    tag_html = f"<span class='tag-{'green' if color=='#4ade80' else 'red' if color=='#f87171' else 'yellow'}'>{tag}</span>" if tag else ""
    col.markdown(f"""<div class='metric-card'>
    <div class='metric-label'>{label}</div>
    <div class='metric-value' style='color:{color}'>₪{value:,.0f}</div>
    <div class='metric-sub'>{sub} {tag_html}</div></div>""", unsafe_allow_html=True)

kpi(c1, "הוצאות עד היום", total, f"{pct:.0f}% מהיעד", "#6366f1")
kpi(c2, "תחזית לסוף חודש", estimated_with_fixed, "כולל קבועות צפויות",
    "#4ade80" if estimated_with_fixed <= budget else "#f87171",
    "✅ בתקציב" if estimated_with_fixed <= budget else "⚠️ חריגה")
kpi(c3, "נותר להוצאה", remaining, f"{days_left} ימים נותרו", "#fbbf24")
kpi(c4, "ממוצע יומי", daily_avg, f"יעד: ₪{budget/days_in_month:,.0f}/יום",
    "#4ade80" if daily_avg <= budget/days_in_month else "#f87171")
kpi(c5, "חיסכון משוער", max(0,savings_est), f"הכנסות: ₪{income_this:,.0f}",
    "#4ade80" if savings_est > 0 else "#f87171")

# ── gauge + trend ──────────────────────────────────────────
g1, g2 = st.columns([1, 2])

with g1:
    st.markdown("<div class='section-header'>מד תקציב</div>", unsafe_allow_html=True)
    gauge_color = "#4ade80" if pct < 70 else "#fbbf24" if pct < 90 else "#f87171"
    fig_gauge = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=total,
        delta={"reference": budget, "valueformat": ",.0f"},
        number={"prefix": "₪", "valueformat": ",.0f", "font": {"color": "white", "size": 28}},
        gauge={
            "axis": {"range": [0, budget * 1.2], "tickcolor": "#374151"},
            "bar": {"color": gauge_color, "thickness": 0.3},
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
        paper_bgcolor="#141728", font={"color": "white"},
        height=280, margin=dict(t=20, b=20, l=20, r=20)
    )
    st.plotly_chart(fig_gauge, use_container_width=True)

with g2:
    st.markdown("<div class='section-header'>הוצאות יומיות — השוואה לחודשים קודמים</div>", unsafe_allow_html=True)
    past_months = sorted([m for m in expenses["month"].unique() if m < selected_month])[-3:]
    fig_trend = go.Figure()

    colors_past = ["#2d3561", "#3d4a7a", "#4e5f9a"]
    for i, m in enumerate(past_months):
        m_exp = expenses[expenses["month"] == m]
        daily = m_exp.groupby("day")["amount"].sum().reset_index()
        daily["cumulative"] = daily["amount"].cumsum()
        fig_trend.add_trace(go.Scatter(
            x=daily["day"], y=daily["cumulative"], mode="lines",
            name=m, line=dict(color=colors_past[i % 3], width=1.5, dash="dot"),
            opacity=0.6
        ))

    curr_daily = month_exp.groupby("day")["amount"].sum().reset_index()
    curr_daily["cumulative"] = curr_daily["amount"].cumsum()
    fig_trend.add_trace(go.Scatter(
        x=curr_daily["day"], y=curr_daily["cumulative"], mode="lines+markers",
        name=selected_month, line=dict(color="#6366f1", width=3),
        marker=dict(size=6, color="#6366f1")
    ))
    fig_trend.add_hline(y=budget, line_dash="dash", line_color="#f87171",
                        annotation_text=f"יעד ₪{budget:,}", annotation_font_color="#f87171")
    fig_trend.update_layout(
        paper_bgcolor="#141728", plot_bgcolor="#141728",
        font=dict(color="#9ca3af"), height=280,
        legend=dict(bgcolor="#1a1f35", bordercolor="#252b45"),
        xaxis=dict(gridcolor="#1e2235", title="יום בחודש"),
        yaxis=dict(gridcolor="#1e2235", title="₪ מצטבר"),
        margin=dict(t=10, b=40)
    )
    st.plotly_chart(fig_trend, use_container_width=True)

# ── categories + merchants ─────────────────────────────────
st.markdown("<div class='section-header'>פירוט הוצאות</div>", unsafe_allow_html=True)
t1, t2, t3, t4 = st.tabs(["🥧 לפי קטגוריה", "🏪 עסקים מובילים", "📅 לפי יום", "📆 השוואה חודשית"])

with t1:
    rec_descs = set(r["description"] for r in rec_summary["all_recurring"])
    cat_map = {
        "משכנתא / שכירות": ["משכנת", "שכר דירה"],
        "מזון ומסעדות": ["סופר", "מכולת", "שוק", "אוכל", "מסעדה", "קפה", "ויזה", "max", "מקס"],
        "תחבורה": ["דלק", "רכב", "חניה", "רכבת", "אוטובוס", "taxi", "תחבורה"],
        "ביטוחים": ["ביטוח", "הפניקס", "מגדל", "הראל", "כלל"],
        "תקשורת": ["סלקום", "פרטנר", "hot", "בזק", "yes"],
        "חינוך": ["גן", "צהרון", "חוג", "לימוד"],
        "קניות": ["אמזון", "זארה", "h&m", "קניון"],
        "שירותים": ["חשמל", "מים", "גז", "ארנונה"],
    }
    cats = {}
    for _, row in month_exp.iterrows():
        desc = row["description"].lower()
        found = False
        for cat, keywords in cat_map.items():
            if any(k.lower() in desc for k in keywords):
                cats[cat] = cats.get(cat, 0) + row["amount"]
                found = True
                break
        if not found:
            cats["אחר"] = cats.get("אחר", 0) + row["amount"]

    if cats:
        cat_df = pd.DataFrame(list(cats.items()), columns=["קטגוריה", "סכום"]).sort_values("סכום", ascending=False)
        col_pie, col_bar = st.columns(2)
        with col_pie:
            fig_pie = go.Figure(go.Pie(
                labels=cat_df["קטגוריה"], values=cat_df["סכום"],
                hole=0.6, textinfo="label+percent",
                marker=dict(colors=px.colors.qualitative.Plotly),
            ))
            fig_pie.update_layout(
                paper_bgcolor="#141728", font=dict(color="white"),
                showlegend=False, height=320,
                annotations=[dict(text=f"₪{total:,.0f}", x=0.5, y=0.5,
                                  font_size=18, font_color="white", showarrow=False)]
            )
            st.plotly_chart(fig_pie, use_container_width=True)
        with col_bar:
            fig_bar = go.Figure(go.Bar(
                y=cat_df["קטגוריה"], x=cat_df["סכום"], orientation="h",
                marker=dict(color=cat_df["סכום"], colorscale="Viridis"),
                text=[f"₪{v:,.0f}" for v in cat_df["סכום"]],
                textposition="outside", textfont=dict(color="white")
            ))
            fig_bar.update_layout(
                paper_bgcolor="#141728", plot_bgcolor="#141728",
                font=dict(color="#9ca3af"), height=320,
                xaxis=dict(gridcolor="#1e2235"),
                yaxis=dict(gridcolor="#1e2235"),
                margin=dict(l=10, r=60)
            )
            st.plotly_chart(fig_bar, use_container_width=True)

with t2:
    top = month_exp.groupby("description")["amount"].sum().reset_index()
    top = top.sort_values("amount", ascending=False).head(15)
    fig_top = go.Figure(go.Bar(
        y=top["description"], x=top["amount"], orientation="h",
        marker=dict(color=top["amount"], colorscale="Reds"),
        text=[f"₪{v:,.0f}" for v in top["amount"]],
        textposition="outside", textfont=dict(color="white")
    ))
    fig_top.update_layout(
        paper_bgcolor="#141728", plot_bgcolor="#141728",
        font=dict(color="#9ca3af"), height=480,
        xaxis=dict(gridcolor="#1e2235"),
        yaxis=dict(gridcolor="#1e2235", categoryorder="total ascending"),
        margin=dict(l=10, r=80)
    )
    st.plotly_chart(fig_top, use_container_width=True)

with t3:
    daily = month_exp.groupby("day")["amount"].sum().reset_index()
    avg_day = daily["amount"].mean()
    colors = ["#f87171" if v > avg_day * 1.5 else "#fbbf24" if v > avg_day else "#4ade80" for v in daily["amount"]]
    fig_daily = go.Figure(go.Bar(
        x=daily["day"], y=daily["amount"],
        marker_color=colors,
        text=[f"₪{v:,.0f}" for v in daily["amount"]],
        textposition="outside", textfont=dict(color="white", size=10)
    ))
    fig_daily.add_hline(y=avg_day, line_dash="dash", line_color="#6366f1",
                        annotation_text=f"ממוצע ₪{avg_day:,.0f}", annotation_font_color="#6366f1")
    fig_daily.update_layout(
        paper_bgcolor="#141728", plot_bgcolor="#141728",
        font=dict(color="#9ca3af"), height=360,
        xaxis=dict(gridcolor="#1e2235", title="יום בחודש", dtick=1),
        yaxis=dict(gridcolor="#1e2235"),
    )
    st.plotly_chart(fig_daily, use_container_width=True)

with t4:
    monthly = expenses.groupby("month")["amount"].sum().reset_index()
    monthly["color"] = ["#6366f1" if m == selected_month else "#3d4a7a" for m in monthly["month"]]
    fig_monthly = go.Figure(go.Bar(
        x=monthly["month"], y=monthly["amount"],
        marker_color=monthly["color"],
        text=[f"₪{v:,.0f}" for v in monthly["amount"]],
        textposition="outside", textfont=dict(color="white")
    ))
    fig_monthly.add_hline(y=budget, line_dash="dash", line_color="#f87171",
                          annotation_text=f"יעד ₪{budget:,}", annotation_font_color="#f87171")
    fig_monthly.update_layout(
        paper_bgcolor="#141728", plot_bgcolor="#141728",
        font=dict(color="#9ca3af"), height=360,
        xaxis=dict(gridcolor="#1e2235"),
        yaxis=dict(gridcolor="#1e2235"),
    )
    st.plotly_chart(fig_monthly, use_container_width=True)

# ── הוצאות קבועות ─────────────────────────────────────────
st.markdown("<div class='section-header'>📌 הוצאות קבועות</div>", unsafe_allow_html=True)

rc1, rc2, rc3 = st.columns(3)
rc1.metric("סה״כ קבועות חודשיות", f"₪{rec_summary['total_monthly_fixed']:,}")
rc2.metric("כבר נגבו", f"₪{rec_summary['total_charged_so_far']:,}")
rc3.metric("עוד צפויות לרדת", f"₪{rec_summary['total_pending']:,}")

tab_r1, tab_r2, tab_r3 = st.tabs(["⏳ צפויות", "✅ שולם", "📋 הכל"])

def render_rec(items):
    if not items:
        st.markdown("<p style='color:#6b7280'>אין נתונים</p>", unsafe_allow_html=True); return
    for r in items:
        badge = "tag-green" if r["charged_this_month"] else "tag-red" if r["expected_day"] < date.today().day else "tag-yellow"
        label = "שולם ✓" if r["charged_this_month"] else "מאוחר" if r["expected_day"] < date.today().day else f"יום {r['expected_day']}"
        st.markdown(f"""<div class='txn-row'>
            <div><b style='color:white'>{r['description']}</b>
            <div style='color:#6b7280;font-size:0.8rem'>{r['months_seen']} חודשים</div></div>
            <div style='text-align:left'>
            <b style='color:white;font-size:1.1rem'>₪{r['avg_amount']:,}</b>
            <div><span class='{badge}'>{label}</span></div></div>
        </div>""", unsafe_allow_html=True)

with tab_r1: render_rec(rec_summary["upcoming"] + rec_summary["overdue"])
with tab_r2: render_rec(rec_summary["charged"])
with tab_r3: render_rec(rec_summary["all_recurring"])

# ── עסקאות ────────────────────────────────────────────────
st.markdown("<div class='section-header'>📋 עסקאות</div>", unsafe_allow_html=True)

search = st.text_input("🔍 חיפוש", placeholder="חפש עסקה...", label_visibility="collapsed")
filtered = month_exp.copy()
if search:
    filtered = filtered[filtered["description"].str.contains(search, case=False, na=False)]

display = filtered[["date","description","amount"]].sort_values("date", ascending=False).copy()
display["date"] = display["date"].dt.strftime("%d/%m/%Y")
display["amount"] = display["amount"].apply(lambda x: f"₪{x:,.0f}")
display.columns = ["תאריך", "תיאור", "סכום"]
st.dataframe(display, use_container_width=True, hide_index=True, height=400)

# ── AI ────────────────────────────────────────────────────
st.markdown("<div class='section-header'>🤖 ניתוח AI</div>", unsafe_allow_html=True)
if st.button("✨ קבל ניתוח וטיפים אישיים"):
    txns = "\n".join([f"{r['date'].strftime('%d/%m')} | ₪{r['amount']:.0f} | {r['description']}" for _,r in month_exp.iterrows()])
    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    with st.spinner("Maya מנתחת..."):
        msg = client.messages.create(model="claude-sonnet-4-6", max_tokens=800,
            messages=[{"role":"user","content":f"נתח הוצאות ותן 3 המלצות ספציפיות בעברית:\n{txns}"}])
    st.markdown(f"<div style='background:#141728;border:1px solid #1e2235;border-radius:16px;padding:24px;color:#e2e8f0'>{msg.content[0].text}</div>", unsafe_allow_html=True)
