import streamlit as st
import pandas as pd
from google.ads.googleads.client import GoogleAdsClient
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import DateRange, Dimension, Metric, RunReportRequest
import datetime
import random
import os
import plotly.graph_objects as go

st.set_page_config(page_title="広告ダッシュボード", layout="wide", initial_sidebar_state="collapsed")

# --- サイバーパンク風 カスタムCSS ---
st.markdown("""
<style>
.block-container { padding-top: 1.5rem; padding-bottom: 1.5rem; }
.stApp { background-image: radial-gradient(circle at 50% 50%, #0a192f 0%, #020c1b 100%); }
[data-testid="stMetric"] { background-color: rgba(2, 12, 27, 0.7); border-radius: 8px; padding: 10px 15px; box-shadow: 0 0 10px rgba(0, 243, 255, 0.15), inset 0 0 10px rgba(0, 243, 255, 0.05); border: 1px solid rgba(0, 243, 255, 0.5); backdrop-filter: blur(5px); margin-bottom: 0px; }
[data-testid="stMetricLabel"] { font-size: 0.85rem; font-weight: bold; color: #64ffda !important; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: -5px; }
[data-testid="stMetricValue"] { font-size: 1.7rem; font-weight: 800; color: #ffffff !important; text-shadow: 0 0 10px rgba(0, 243, 255, 0.6); }
[data-testid="stMetricDelta"] { font-size: 0.9rem !important; }
h1, h3, h4 { color: #64ffda !important; font-family: 'Arial', sans-serif; text-shadow: 0 0 8px rgba(100, 255, 218, 0.3); letter-spacing: 1px; }
h1 { margin-bottom: 0 !important; padding-bottom: 0 !important; font-size: 2.0rem; }
h3 { font-size: 1.25rem; margin-top: 0px; margin-bottom: 15px; }
hr { border-color: rgba(0, 243, 255, 0.2); box-shadow: 0 0 5px rgba(0, 243, 255, 0.4); margin-top: 1rem; margin-bottom: 1rem; }
thead tr th { background-color: #0a192f !important; color: #00f3ff !important; }
.report-box { background-color: rgba(2, 12, 27, 0.5); border: 1px solid rgba(0, 243, 255, 0.3); padding: 25px; border-radius: 8px; color: #ffffff; line-height: 1.8; font-size: 1.05rem; }
.date-info { color: #00f3ff; text-shadow: 0 0 5px rgba(0, 243, 255, 0.5); font-size: 0.9rem; margin-top: -10px; margin-bottom: 15px; }
</style>
""", unsafe_allow_html=True)

today = datetime.date.today()
days_since_sunday = (today.weekday() + 1) % 7
this_week_start = today - datetime.timedelta(days=days_since_sunday)
last_week_start = this_week_start - datetime.timedelta(days=7)
last_week_end = this_week_start - datetime.timedelta(days=1)

presets = {
    "今日": (today, today),
    "昨日": (today - datetime.timedelta(days=1), today - datetime.timedelta(days=1)),
    "今週": (this_week_start, today),
    "先週": (last_week_start, last_week_end),
    "今月": (today.replace(day=1), today),
    "先月": ((today.replace(day=1) - datetime.timedelta(days=1)).replace(day=1), today.replace(day=1) - datetime.timedelta(days=1)),
    "カスタム指定": None
}

h_left, h_mid1, h_mid2, h_right = st.columns([1.8, 1, 0.6, 1])
with h_left:
    st.markdown("<div style='height: 15px;'></div>", unsafe_allow_html=True)
    st.title("🌌 Y2ENERGY COMMAND CENTER")
with h_mid1:
    selected_preset_a = st.selectbox("▶ 対象期間", list(presets.keys()), index=4)
    if selected_preset_a == "カスタム指定":
        date_range_a = st.date_input("カレンダー (対象)", value=(today - datetime.timedelta(days=30), today), max_value=today)
        start_date_a = date_range_a[0]
        end_date_a = date_range_a[1] if len(date_range_a) == 2 else date_range_a[0]
    else:
        start_date_a, end_date_a = presets[selected_preset_a]
        st.markdown(f"<div class='date-info'>{start_date_a.strftime('%Y-%m-%d')} 〜 {end_date_a.strftime('%Y-%m-%d')}</div>", unsafe_allow_html=True)

with h_mid2:
    st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
    compare_mode = st.toggle("VS 比較モード")

with h_right:
    if compare_mode:
        selected_preset_b = st.selectbox("▶ 比較期間", list(presets.keys()), index=5)
        if selected_preset_b == "カスタム指定":
            date_range_b = st.date_input("カレンダー (比較)", value=(last_week_start, last_week_end), max_value=today)
            start_date_b = date_range_b[0]
            end_date_b = date_range_b[1] if len(date_range_b) == 2 else date_range_b[0]
        else:
            start_date_b, end_date_b = presets[selected_preset_b]
            st.markdown(f"<div class='date-info'>{start_date_b.strftime('%Y-%m-%d')} 〜 {end_date_b.strftime('%Y-%m-%d')}</div>", unsafe_allow_html=True)
    else:
        start_date_b = end_date_b = today # ダミー

st.markdown("---")

YAML_PATH = "google-ads.yaml"
ADS_CUSTOMER_ID = "8153094421"
GA4_PROPERTY_ID = "552749882"
GA4_KEY_PATH = "teak-amphora-506601-t5-806531f345b4.json"
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = GA4_KEY_PATH

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_real_data(start_str, end_str):
    ads_df_summary = pd.DataFrame()
    ads_df_keywords = pd.DataFrame()
    ads_error = None
    
    try:
        client = GoogleAdsClient.load_from_storage(YAML_PATH)
        ga_service = client.get_service("GoogleAdsService")
        query_summary = f'''
            SELECT segments.date, metrics.clicks, metrics.impressions, metrics.cost_micros, metrics.conversions
            FROM customer 
            WHERE segments.date >= '{start_str}' AND segments.date <= '{end_str}'
            ORDER BY segments.date ASC
        '''
        res_summary = ga_service.search_stream(customer_id=ADS_CUSTOMER_ID, query=query_summary)
        s_data = []
        for batch in res_summary:
            for row in batch.results:
                s_data.append({
                    "日付": row.segments.date, 
                    "クリック数": row.metrics.clicks,
                    "表示回数": row.metrics.impressions,
                    "費用": row.metrics.cost_micros / 1000000.0, 
                    "コンバージョン": row.metrics.conversions
                })
        ads_df_summary = pd.DataFrame(s_data)
        if not ads_df_summary.empty:
            ads_df_summary["CTR"] = (ads_df_summary["クリック数"] / ads_df_summary["表示回数"] * 100).fillna(0)
        
        query_kw = f'''
            SELECT ad_group_criterion.keyword.text, metrics.clicks, metrics.impressions, metrics.cost_micros, metrics.conversions
            FROM keyword_view
            WHERE segments.date >= '{start_str}' AND segments.date <= '{end_str}'
        '''
        res_kw = ga_service.search_stream(customer_id=ADS_CUSTOMER_ID, query=query_kw)
        k_data = []
        for batch in res_kw:
            for row in batch.results:
                k_data.append({
                    "キーワード": row.ad_group_criterion.keyword.text,
                    "クリック数": row.metrics.clicks,
                    "表示回数": row.metrics.impressions,
                    "費用": row.metrics.cost_micros / 1000000.0,
                    "コンバージョン": row.metrics.conversions
                })
        ads_df_keywords = pd.DataFrame(k_data)
    except Exception as e:
        ads_error = str(e)
        
    ga4_df = pd.DataFrame()
    ga4_error = None
    try:
        ga4_client = BetaAnalyticsDataClient()
        request = RunReportRequest(
            property=f"properties/{GA4_PROPERTY_ID}",
            dimensions=[Dimension(name="sessionSourceMedium")],
            metrics=[Metric(name="sessions"), Metric(name="engagementRate")],
            date_ranges=[DateRange(start_date=start_str, end_date=end_str)],
        )
        response = ga4_client.run_report(request)
        g_data = []
        for row in response.rows:
            g_data.append({
                "流入元": row.dimension_values[0].value,
                "セッション数": int(row.metric_values[0].value),
                "エンゲージメント率": float(row.metric_values[1].value) * 100
            })
        ga4_df = pd.DataFrame(g_data)
    except Exception as e:
        ga4_error = str(e)
        
    return ads_df_summary, ads_df_keywords, ads_error, ga4_df, ga4_error

def generate_mock_ads_data(start_str, end_str):
    delta = (datetime.datetime.strptime(end_str, "%Y-%m-%d").date() - datetime.datetime.strptime(start_str, "%Y-%m-%d").date()).days
    if delta < 0: delta = 0
    dates = [(datetime.datetime.strptime(start_str, "%Y-%m-%d").date() + datetime.timedelta(days=x)).strftime("%Y-%m-%d") for x in range(delta + 1)]
    
    summary_data = []
    for d in dates:
        imps = random.randint(10, 100)
        clicks = int(imps * random.uniform(0.01, 0.08))
        cost = clicks * random.randint(150, 400)
        conv = 1 if random.random() > 0.95 else 0
        ctr = (clicks / imps * 100) if imps > 0 else 0
        summary_data.append({"日付": d, "表示回数": imps, "クリック数": clicks, "費用": cost, "コンバージョン": conv, "CTR": ctr})
    
    kw_data = []
    for kw in ["太陽光 費用", "蓄電池 補助金", "太陽光パネル 見積もり", "ソーラーパネル デメリット", "Y2ENERGY 評判", "神奈川 太陽光", "蓄電池 おすすめ"]:
        k_imps = random.randint(10, 500)
        k_clicks = int(k_imps * random.uniform(0.01, 0.1))
        k_cost = k_clicks * random.randint(150, 500)
        k_conv = 1 if random.random() > 0.9 else 0
        if k_clicks > 0:
            kw_data.append({"キーワード": kw, "表示回数": k_imps, "クリック数": k_clicks, "費用": k_cost, "コンバージョン": k_conv})
    
    return pd.DataFrame(summary_data), pd.DataFrame(kw_data)

with st.spinner('対象期間のデータを取得しています...'):
    start_str_a = start_date_a.strftime("%Y-%m-%d")
    end_str_a = end_date_a.strftime("%Y-%m-%d")
    df_summary_a, df_keywords_a, ads_error_a, df_ga4_a, ga4_error_a = fetch_real_data(start_str_a, end_str_a)
    
if compare_mode:
    with st.spinner('比較期間のデータを取得しています...'):
        start_str_b = start_date_b.strftime("%Y-%m-%d")
        end_str_b = end_date_b.strftime("%Y-%m-%d")
        df_summary_b, df_keywords_b, ads_error_b, df_ga4_b, ga4_error_b = fetch_real_data(start_str_b, end_str_b)
else:
    df_summary_b = pd.DataFrame()

if ads_error_a or df_summary_a.empty:
    if ads_error_a:
        st.error(f"⚠️ Google広告 APIエラー: (詳細: {ads_error_a})")
    df_summary_a, df_keywords_a = generate_mock_ads_data(start_str_a, end_str_a)
    if compare_mode:
        df_summary_b, df_keywords_b = generate_mock_ads_data(start_str_b, end_str_b)

def calc_metrics(df):
    if df.empty: return 0, 0, 0, 0, 0, 0, 0
    clk = df["クリック数"].sum()
    imp = df["表示回数"].sum()
    cst = df["費用"].sum()
    cnv = df["コンバージョン"].sum()
    ctr = (clk / imp * 100) if imp > 0 else 0
    cpa = (cst / cnv) if cnv > 0 else 0
    cvr = (cnv / clk * 100) if clk > 0 else 0
    return clk, imp, cst, cnv, ctr, cpa, cvr

clk_a, imp_a, cst_a, cnv_a, ctr_a, cpa_a, cvr_a = calc_metrics(df_summary_a)
clk_b, imp_b, cst_b, cnv_b, ctr_b, cpa_b, cvr_b = calc_metrics(df_summary_b)

def get_delta(val_a, val_b, is_currency=False, is_percent=False):
    if not compare_mode or df_summary_b.empty: return None
    diff = val_a - val_b
    sign = "+" if diff > 0 else ""
    if is_currency: return f"{sign}{diff:,.0f}円"
    if is_percent: return f"{sign}{diff:.2f}%"
    return f"{sign}{diff:,.0f}"

col_main_left, col_main_right = st.columns([1, 1])

with col_main_left:
    st.markdown("### 📊 Google広告 パフォーマンス")
    
    m1, m2, m3 = st.columns(3)
    m1.metric("総費用", f"¥{int(cst_a):,}", get_delta(cst_a, cst_b, is_currency=True), delta_color="inverse")
    m2.metric("クリック数", f"{int(clk_a):,} 回", get_delta(clk_a, clk_b))
    m3.metric("クリック率 (CTR)", f"{ctr_a:.2f} %", get_delta(ctr_a, ctr_b, is_percent=True))
    
    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    
    m4, m5, m6 = st.columns(3)
    m4.metric("コンバージョン", f"{int(cnv_a)} 件", get_delta(cnv_a, cnv_b))
    m5.metric("コンバージョン率(CVR)", f"{cvr_a:.2f} %", get_delta(cvr_a, cvr_b, is_percent=True))
    cpa_display = f"¥{int(cpa_a):,}" if cpa_a > 0 else "¥-"
    m6.metric("獲得単価 (CPA)", cpa_display, get_delta(cpa_a, cpa_b, is_currency=True) if cpa_a > 0 and cpa_b > 0 else None, delta_color="inverse")

    st.markdown("<div style='height:25px'></div>", unsafe_allow_html=True)
    
    st.markdown("### 📈 パフォーマンス推移 <span style='font-size:0.95rem; color:#888; font-weight:normal;'>(※右上の凡例をクリックで表示切替)</span>", unsafe_allow_html=True)
    fig = go.Figure()
    
    if compare_mode and not df_summary_b.empty:
        df_summary_a['Day'] = [f"{i+1}日目" for i in range(len(df_summary_a))]
        df_summary_b['Day'] = [f"{i+1}日目" for i in range(len(df_summary_b))]
        
        # 比較データ (グレー系)
        fig.add_trace(go.Bar(x=df_summary_b['Day'], y=df_summary_b["費用"], name="費用 (比較)", marker_color="rgba(100, 150, 200, 0.2)", yaxis="y1"))
        fig.add_trace(go.Scatter(x=df_summary_b['Day'], y=df_summary_b["クリック数"], name="クリック数 (比較)", mode="lines", line=dict(color="rgba(180, 180, 180, 0.5)", width=2, dash='dot'), yaxis="y2"))
        fig.add_trace(go.Scatter(x=df_summary_b['Day'], y=df_summary_b["コンバージョン"], name="CV (比較)", mode="lines", line=dict(color="rgba(200, 200, 100, 0.5)", width=2, dash='dot'), yaxis="y2", visible="legendonly"))
        fig.add_trace(go.Scatter(x=df_summary_b['Day'], y=df_summary_b["CTR"], name="CTR (比較)", mode="lines", line=dict(color="rgba(200, 100, 200, 0.5)", width=2, dash='dot'), yaxis="y2", visible="legendonly"))
        
        # 対象データ (ネオンカラー)
        fig.add_trace(go.Bar(x=df_summary_a['Day'], y=df_summary_a["費用"], name="費用 (対象)", marker_color="rgba(0, 243, 255, 0.6)", marker_line_color="#00f3ff", marker_line_width=1.5, yaxis="y1"))
        fig.add_trace(go.Scatter(x=df_summary_a['Day'], y=df_summary_a["クリック数"], name="クリック数 (対象)", mode="lines+markers", line=dict(color="#ff007f", width=3), marker=dict(color="#ff007f", size=7, line=dict(color="#ffffff", width=1)), yaxis="y2"))
        fig.add_trace(go.Scatter(x=df_summary_a['Day'], y=df_summary_a["コンバージョン"], name="CV (対象)", mode="lines+markers", line=dict(color="#ffcf00", width=3), marker=dict(size=7), yaxis="y2", visible="legendonly"))
        fig.add_trace(go.Scatter(x=df_summary_a['Day'], y=df_summary_a["CTR"], name="CTR (対象)", mode="lines+markers", line=dict(color="#b500ff", width=3), marker=dict(size=7), yaxis="y2", visible="legendonly"))
    else:
        fig.add_trace(go.Bar(x=df_summary_a["日付"], y=df_summary_a["費用"], name="費用 (¥)", marker_color="rgba(0, 243, 255, 0.4)", marker_line_color="#00f3ff", marker_line_width=1.5, yaxis="y1"))
        fig.add_trace(go.Scatter(x=df_summary_a["日付"], y=df_summary_a["クリック数"], name="クリック数", mode="lines+markers", line=dict(color="#ff007f", width=3), marker=dict(color="#ff007f", size=8, line=dict(color="#ffffff", width=1)), yaxis="y2"))
        fig.add_trace(go.Scatter(x=df_summary_a["日付"], y=df_summary_a["コンバージョン"], name="コンバージョン", mode="lines+markers", line=dict(color="#ffcf00", width=3), marker=dict(color="#ffcf00", size=8), yaxis="y2", visible="legendonly"))
        fig.add_trace(go.Scatter(x=df_summary_a["日付"], y=df_summary_a["CTR"], name="CTR (%)", mode="lines+markers", line=dict(color="#b500ff", width=3), marker=dict(color="#b500ff", size=8), yaxis="y2", visible="legendonly"))

    fig.update_layout(
        template="plotly_dark",
        xaxis=dict(tickangle=0, type='category', showgrid=False, color="#64ffda"),
        yaxis=dict(title="費用 (¥)", side="left", showgrid=True, gridcolor='rgba(0, 243, 255, 0.1)', color="#64ffda"),
        yaxis2=dict(title="クリック数・CV・CTR", side="right", overlaying="y", showgrid=False, color="#ff007f"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(color="#ffffff", size=11)),
        margin=dict(l=0, r=0, t=10, b=0),
        height=320,
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        barmode='group'
    )
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)

    st.markdown("### 🌐 Webサイト アクセス解析")
    if ga4_error_a:
        st.error(f"⚠️ GA4 APIエラー: {ga4_error_a}")
    elif not df_ga4_a.empty:
        if compare_mode and not df_ga4_b.empty:
            m_ga4 = pd.merge(df_ga4_a, df_ga4_b, on="流入元", how="left", suffixes=("", " (比較)"))
            m_ga4.fillna(0, inplace=True)
            m_ga4["セッション(増減)"] = m_ga4["セッション数"] - m_ga4["セッション数 (比較)"]
            show_ga4 = m_ga4[["流入元", "セッション数", "セッション(増減)", "エンゲージメント率"]]
            st.dataframe(show_ga4, use_container_width=True, hide_index=True, column_config={"エンゲージメント率": st.column_config.NumberColumn(format="%.1f %%")}, height=250)
        else:
            st.dataframe(df_ga4_a, use_container_width=True, hide_index=True, column_config={"エンゲージメント率": st.column_config.NumberColumn(format="%.1f %%")}, height=250)
    else:
        st.info("指定された期間のGA4データはありません。")

with col_main_right:
    st.markdown("### 🔍 キーワード別 パフォーマンス")
    if not df_keywords_a.empty:
        df_keywords_a["CPA"] = df_keywords_a.apply(lambda r: (r["費用"] / r["コンバージョン"]) if r["コンバージョン"] > 0 else 0, axis=1)
        
        if compare_mode and not df_keywords_b.empty:
            df_keywords_b["CPA"] = df_keywords_b.apply(lambda r: (r["費用"] / r["コンバージョン"]) if r["コンバージョン"] > 0 else 0, axis=1)
            m_kw = pd.merge(df_keywords_a, df_keywords_b, on="キーワード", how="left", suffixes=("", " (比較)"))
            m_kw.fillna(0, inplace=True)
            m_kw["費用(増減)"] = m_kw["費用"] - m_kw["費用 (比較)"]
            m_kw["CPA(増減)"] = m_kw["CPA"] - m_kw["CPA (比較)"]
            
            show_kw = m_kw[["キーワード", "費用", "費用(増減)", "CPA", "CPA(増減)"]].sort_values("費用", ascending=False)
            st.dataframe(
                show_kw, 
                use_container_width=True,
                column_config={
                    "費用": st.column_config.NumberColumn("費用", format="¥%d"),
                    "費用(増減)": st.column_config.NumberColumn("費用(増減)", format="¥%d"),
                    "CPA": st.column_config.NumberColumn("CPA", format="¥%d"),
                    "CPA(増減)": st.column_config.NumberColumn("CPA(増減)", format="¥%d"),
                },
                hide_index=True,
                height=940
            )
        else:
            df_keywords_a = df_keywords_a.sort_values("費用", ascending=False)
            st.dataframe(
                df_keywords_a, 
                use_container_width=True,
                column_config={
                    "費用": st.column_config.NumberColumn("費用", format="¥%d"),
                    "CPA": st.column_config.NumberColumn("CPA", format="¥%d"),
                },
                hide_index=True,
                height=940
            )

st.markdown("---")

st.markdown("### 📝 今週の運用レポート")
report_path = "weekly_analysis.md"
if os.path.exists(report_path):
    with open(report_path, "r", encoding="utf-8") as f:
        report_content = f.read()
    
    report_content = report_content.replace("【今週（日〜金）の運用サマリー】", "").strip()
    report_content = report_content.replace("\n", "<br>")
    
    date_header = f"<strong style='color:#00f3ff; font-size:1.15rem;'>【{start_date_a.strftime('%m月%d日')} 〜 {end_date_a.strftime('%m月%d日')}】</strong><br><br>"
    st.markdown(f"<div class='report-box'>{date_header}{report_content}</div>", unsafe_allow_html=True)
else:
    st.markdown("<div class='report-box'>今週のレポートはまだ作成されていません。（※毎週土曜朝6時に更新されます）</div>", unsafe_allow_html=True)
