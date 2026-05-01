import streamlit as st
import json
import os
import subprocess
from datetime import datetime, date
from dotenv import load_dotenv
import anthropic
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from agents.recurring_summary import build_recurring_summary

load_dotenv()

st.set_page_config(
    page_title="מעקב פיננסי — גל",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Heebo:wght@300;400;600;700&display=swap');

* { font-family: 'Heebo', sans-serif !important; direction: rtl; }
.stApp { background: #0f1117; }

.card {
    background: linear-gradient(135deg, #1a1d2e 0%, #16192a 100%);
    border: 1px solid #2a2d3e;
    border-radius: 16px;
    padding: 24px;
    margin-bottom: 12px;
    text-align: right;
}
.card-green { border-left: 4px solid #00d084; }
.card-red   { border-left: 4px solid #ff4d4d; }
.card-blue  { border-left: 4px solid #4d9fff; }
.card-yellow{ border-left: 4px solid #ffd700; }

.big-number { font-size: 2.2rem; font-weight: 700; color: #fff; margin: 4px 0; }
.label      { font-size: 0.85rem; color: #888; margin-bottom: 4px; }
.sub        { font-size: 0.9rem; color: #aaa; }

.progress-bar-bg {
    background: #1e2130;
    border-radius: 999px;
    height: 12px;
    width: 100%;
    margin: 8px 0;
}
.progress-bar-fill {
    height: 12px;
    border-radius: 999px;
    transition: width 0.5s ease;
}

.section-title {
    font-size: 1.2rem;
    font-weight: 700;
    color: #fff;
    margin: 28px 0 12px 0;
    padding-bottom: 8px;
    border-bottom: 1px solid #2a2d3e;
}

.recurring-item {
    background: #1a1d2e;
    border-radius: 12px;
    padding: 14px 18px;
    margin-bottom: 8px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    border: 1px solid #2a2d3e;
}
.badge-green { background: #0d3d2a; color: #00d084; padding: 3px 10px; border-radius: 999px; font-size: 0.75rem; }
.badge-orange{ background: #3d2a0d; color: #ffaa00; padding: 3px 10px; border-radius: 999px; font-size: 0.75rem; }
.badge-red   { background: #3d0d0d; color: #ff4d4d; padding: 3px 10px; border-radius: 999px; font-size: 0.75rem; }

div[data-testid="stButton"] button {
    background: linear-gradient(135deg, #4d9fff, #7c6fff);
    color: white; border: none; border-radius: 12px;
    padding: 10px 24px; font-weight: 600; width: 100%;
}
</style>
""", unsafe_allow_html=True)

# ── helpers ────────────────────────────────────────────────

BUDGET = 32000

def load_data():
    path = "/Users/galshushan/finance-agent/transactions.json"
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)

def parse(data):
    rows = []
    for acc in data["accounts"]:
        for t in acc["txns"]:
            amt = t.get("chargedAmount", 0)
            rows.append({
                "date": t.get("date","")[:10],
                "month": t.get("date","")[:7],
                "amount": abs(amt),
                "raw": amt,
                "description": t.get("description",""),
                "type": "הוצאה" if amt < 0 else "הכנסה",
            })
    return pd.DataFrame(rows)

def progress_html(pct, color):
    fill = min(pct, 100)
    return f"""
    <div class="progress-bar-bg">
      <div class="progress-bar-fill" style="width:{fill}%; background:{color};"></div>
    </div>"""

def run_scraper():
    r = subprocess.run(["node","scrape.mjs"], capture_output=True, text=True,
                       cwd="/Users/galshushan/finance-agent")
    return r.returncode == 0

def get_ai_tips(txns_text):
    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    msg = client.messages.create(
        model="claude-sonnet-4-6", max_tokens=600,
        messages=[{"role":"user","content":f"""בהתבסס על ההוצאות, תן 3 המלצות ספציפיות לחיסכון בעברית.
פורמט לכל המלצה:
**כותרת קצרה** — הסבר + חיסכון משוער: ₪X

הוצאות:
{txns_text}"""}])
    return msg.content[0].text

# ── load ───────────────────────────────────────────────────

data = load_data()

# ── header ─────────────────────────────────────────────────

col_title, col_btn = st.columns([4, 1])
with col_title:
    st.markdown("<h1 style='color:white;margin:0'>💰 מעקב פיננסי</h1>", unsafe_allow_html=True)
    if data:
        updated = data.get("scrapedAt","")[:10]
        st.markdown(f"<p class='sub'>עדכון אחרון: {updated}</p>", unsafe_allow_html=True)
with col_btn:
    if st.button("🔄 עדכן נתונים"):
        with st.spinner("מתחבר ללאומי..."):
            ok = run_scraper()
        if ok:
            st.success("✅ עודכן!")
            st.rerun()
        else:
            st.error("❌ שגיאה")

if not data:
    st.info("לחץ 'עדכן נתונים' כדי להתחיל")
    st.stop()

df = parse(data)
expenses = df[df["type"] == "הוצאה"]
income_df = df[df["type"] == "הכנסה"]
current_month = date.today().strftime("%Y-%m")
this_month = expenses[expenses["month"] == current_month]

total = this_month["amount"].sum()
today_day = date.today().day
days_left = 30 - today_day
daily_avg = total / today_day if today_day > 0 else 0
income_this_month = income_df[income_df["month"] == current_month]["amount"].sum()

rec_summary = build_recurring_summary(expenses.to_dict("records"))
pending_fixed = rec_summary["total_pending"]
estimated = total + (daily_avg * days_left) + pending_fixed
remaining = max(0, BUDGET - estimated)
pct = min((total / BUDGET) * 100, 100)

# ── כרטיסי מדדים ──────────────────────────────────────────

c1, c2, c3, c4 = st.columns(4)

with c1:
    color = "#00d084" if total < BUDGET * 0.6 else "#ffaa00" if total < BUDGET * 0.85 else "#ff4d4d"
    st.markdown(f"""<div class="card card-blue">
    <div class="label">הוצאות עד היום</div>
    <div class="big-number" style="color:{color}">₪{total:,.0f}</div>
    <div class="sub">מתוך יעד ₪{BUDGET:,}</div>
    {progress_html(pct, color)}
    <div class="sub">{pct:.0f}% מהתקציב</div>
    </div>""", unsafe_allow_html=True)

with c2:
    est_color = "#00d084" if estimated <= BUDGET else "#ff4d4d"
    st.markdown(f"""<div class="card card-yellow">
    <div class="label">תחזית לסוף חודש</div>
    <div class="big-number" style="color:{est_color}">₪{estimated:,.0f}</div>
    <div class="sub">{'✅ בתקציב' if estimated <= BUDGET else '⚠️ צפויה חריגה'}</div>
    {progress_html((estimated/BUDGET)*100, est_color)}
    <div class="sub">{(estimated/BUDGET)*100:.0f}% מהתקציב</div>
    </div>""", unsafe_allow_html=True)

with c3:
    st.markdown(f"""<div class="card card-green">
    <div class="label">נותר להוצאה</div>
    <div class="big-number" style="color:#00d084">₪{remaining:,.0f}</div>
    <div class="sub">{days_left} ימים נותרו</div>
    <div class="sub">מומלץ: ₪{remaining/days_left:,.0f}/יום</div>
    </div>""", unsafe_allow_html=True)

with c4:
    st.markdown(f"""<div class="card card-red">
    <div class="label">הוצאות קבועות צפויות</div>
    <div class="big-number" style="color:#ffaa00">₪{pending_fixed:,.0f}</div>
    <div class="sub">עוד לא ירדו החודש</div>
    <div class="sub">{len(rec_summary['upcoming'])} תשלומים ממתינים</div>
    </div>""", unsafe_allow_html=True)

# ── הוצאות קבועות (סגנון Riseup) ─────────────────────────

st.markdown("<div class='section-title'>📌 הוצאות קבועות חודשיות</div>", unsafe_allow_html=True)

tab1, tab2, tab3 = st.tabs(["⏳ עוד לא ירדו", "✅ כבר נגבו", "📋 הכל"])

def render_recurring(items, show_status=True):
    if not items:
        st.markdown("<p class='sub'>אין נתונים</p>", unsafe_allow_html=True)
        return
    for r in items:
        if r['charged_this_month']:
            badge = "<span class='badge-green'>שולם ✓</span>"
        elif r['expected_day'] < date.today().day:
            badge = "<span class='badge-red'>מאוחר ⚠️</span>"
        else:
            badge = f"<span class='badge-orange'>יום {r['expected_day']}</span>"

        st.markdown(f"""
        <div class="recurring-item">
            <div>
                <div style="color:white;font-weight:600">{r['description']}</div>
                <div class="sub">ממוצע: ₪{r['avg_amount']:,} | מופיע {r['months_seen']} חודשים</div>
            </div>
            <div style="text-align:left">
                <div style="color:white;font-weight:700;font-size:1.1rem">₪{r['avg_amount']:,}</div>
                {badge}
            </div>
        </div>""", unsafe_allow_html=True)

with tab1:
    all_pending = rec_summary['upcoming'] + rec_summary['overdue']
    render_recurring(all_pending)
    if all_pending:
        st.markdown(f"<div class='card'><div class='label'>סה\"כ צפוי לרדת</div><div class='big-number'>₪{pending_fixed:,.0f}</div></div>", unsafe_allow_html=True)

with tab2:
    render_recurring(rec_summary['charged'])
    if rec_summary['charged']:
        st.markdown(f"<div class='card'><div class='label'>סה\"כ נגבה</div><div class='big-number'>₪{rec_summary['total_charged_so_far']:,.0f}</div></div>", unsafe_allow_html=True)

with tab3:
    render_recurring(rec_summary['all_recurring'])
    st.markdown(f"<div class='card'><div class='label'>סה\"כ קבועות חודשיות</div><div class='big-number'>₪{rec_summary['total_monthly_fixed']:,.0f}</div></div>", unsafe_allow_html=True)

# ── גרפים ─────────────────────────────────────────────────

st.markdown("<div class='section-title'>📊 ניתוח הוצאות</div>", unsafe_allow_html=True)

# ── השוואה לחודשים קודמים ─────────────────────────────────

recurring_descs = set(r['description'] for r in rec_summary['all_recurring'])
variable_expenses = expenses[~expenses["description"].isin(recurring_descs)]

today_day = date.today().day
months_list = sorted(variable_expenses["month"].unique())
past_months = [m for m in months_list if m < current_month][-6:]

# חישוב הוצאות עד יום X בכל חודש
comparison_rows = []
for m in past_months:
    month_txns = variable_expenses[variable_expenses["month"] == m]
    up_to_today = month_txns[month_txns["date"].str[8:].astype(int) <= today_day]["amount"].sum()
    full_month = month_txns["amount"].sum()
    comparison_rows.append({"חודש": m, "עד יום היום": up_to_today, "סה\"כ חודש": full_month})

current_var = variable_expenses[variable_expenses["month"] == current_month]
current_up_to_today = current_var["amount"].sum()
avg_up_to_today = sum(r["עד יום היום"] for r in comparison_rows) / len(comparison_rows) if comparison_rows else 0
diff_pct = ((current_up_to_today - avg_up_to_today) / avg_up_to_today * 100) if avg_up_to_today > 0 else 0
is_better = diff_pct < 0

st.markdown(f"""
<div class="card {'card-green' if is_better else 'card-red'}" style="margin-bottom:20px">
  <div style="display:flex;justify-content:space-between;align-items:center">
    <div>
      <div class="label">הוצאות משתנות עד יום {today_day} — השוואה ל-6 חודשים</div>
      <div class="big-number">₪{current_up_to_today:,.0f}</div>
      <div class="sub">ממוצע 6 חודשים עד יום זה: ₪{avg_up_to_today:,.0f}</div>
    </div>
    <div style="text-align:center;padding:16px 24px;background:{'#0d3d2a' if is_better else '#3d0d0d'};border-radius:12px">
      <div style="font-size:2rem">{'📉' if is_better else '📈'}</div>
      <div style="color:{'#00d084' if is_better else '#ff4d4d'};font-size:1.4rem;font-weight:700">{abs(diff_pct):.1f}%</div>
      <div style="color:{'#00d084' if is_better else '#ff4d4d'};font-size:0.85rem">{'פחות מהרגיל ✅' if is_better else 'יותר מהרגיל ⚠️'}</div>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

# גרף השוואה לפי חודש
if comparison_rows:
    comp_df = pd.DataFrame(comparison_rows)
    fig_comp = go.Figure()
    fig_comp.add_trace(go.Bar(
        name="עד יום " + str(today_day) + " (חודשים קודמים)",
        x=comp_df["חודש"], y=comp_df["עד יום היום"],
        marker_color="#4d9fff", opacity=0.7
    ))
    fig_comp.add_trace(go.Bar(
        name="סה\"כ חודש שלם",
        x=comp_df["חודש"], y=comp_df["סה\"כ חודש"],
        marker_color="#2a3a5e", opacity=0.5
    ))
    fig_comp.add_hline(y=avg_up_to_today, line_dash="dash", line_color="#888",
                       annotation_text=f"ממוצע עד יום {today_day}: ₪{avg_up_to_today:,.0f}")
    fig_comp.add_trace(go.Scatter(
        x=[current_month], y=[current_up_to_today],
        mode="markers+text", name="החודש הנוכחי",
        marker=dict(color="#00d084" if is_better else "#ff4d4d", size=16, symbol="star"),
        text=[f"₪{current_up_to_today:,.0f}"], textposition="top center",
        textfont=dict(color="#00d084" if is_better else "#ff4d4d", size=13)
    ))
    fig_comp.update_layout(
        title=f"השוואת הוצאות משתנות עד יום {today_day} בחודש",
        paper_bgcolor="#0f1117", plot_bgcolor="#0f1117",
        font=dict(color="white"), height=360, barmode="overlay",
        legend=dict(bgcolor="#1a1d2e", bordercolor="#2a2d3e"),
        xaxis=dict(gridcolor="#2a2d3e"), yaxis=dict(gridcolor="#2a2d3e")
    )
    st.plotly_chart(fig_comp, use_container_width=True)

g1, g2 = st.columns(2)

with g1:
    monthly = expenses.groupby("month")["amount"].sum().reset_index()
    fig = go.Figure(go.Bar(
        x=monthly["month"], y=monthly["amount"],
        marker=dict(color=monthly["amount"],
                    colorscale=[[0,"#4d9fff"],[0.5,"#7c6fff"],[1,"#ff4d4d"]]),
        text=[f"₪{v:,.0f}" for v in monthly["amount"]],
        textposition="outside"
    ))
    fig.add_hline(y=BUDGET, line_dash="dash", line_color="#ff4d4d",
                  annotation_text=f"יעד ₪{BUDGET:,}", annotation_position="top right")
    fig.update_layout(
        title="הוצאות לפי חודש", paper_bgcolor="#0f1117", plot_bgcolor="#0f1117",
        font=dict(color="white"), height=320, showlegend=False,
        xaxis=dict(gridcolor="#2a2d3e"), yaxis=dict(gridcolor="#2a2d3e")
    )
    st.plotly_chart(fig, use_container_width=True)

with g2:
    top10 = this_month.nlargest(10, "amount")[["description","amount"]]
    fig2 = go.Figure(go.Bar(
        x=top10["amount"], y=top10["description"], orientation="h",
        marker=dict(color=top10["amount"], colorscale="Reds"),
        text=[f"₪{v:,.0f}" for v in top10["amount"]],
        textposition="outside"
    ))
    fig2.update_layout(
        title="10 הוצאות גדולות החודש", paper_bgcolor="#0f1117", plot_bgcolor="#0f1117",
        font=dict(color="white"), height=320,
        xaxis=dict(gridcolor="#2a2d3e"), yaxis=dict(gridcolor="#2a2d3e")
    )
    st.plotly_chart(fig2, use_container_width=True)

# ── המלצות AI ─────────────────────────────────────────────

st.markdown("<div class='section-title'>🤖 המלצות לחיסכון</div>", unsafe_allow_html=True)

if st.button("✨ קבל המלצות AI"):
    txns_text = "\n".join([f"{r['date']} | ₪{r['amount']:.0f} | {r['description']}"
                           for _, r in this_month.iterrows()])
    with st.spinner("Maya מנתחת..."):
        tips = get_ai_tips(txns_text)
    st.markdown(f"<div class='card'>{tips}</div>", unsafe_allow_html=True)

# ── טבלת עסקאות ───────────────────────────────────────────

st.markdown("<div class='section-title'>📋 כל עסקאות החודש</div>", unsafe_allow_html=True)
display = this_month[["date","description","amount"]].sort_values("date", ascending=False).copy()
display.columns = ["תאריך","תיאור","סכום"]
display["סכום"] = display["סכום"].apply(lambda x: f"₪{x:,.0f}")
st.dataframe(display, use_container_width=True, hide_index=True)
