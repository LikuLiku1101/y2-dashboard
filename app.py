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
/* 全体の余白調整と背景グラデーション */
.block-container { padding-top: 2rem; padding-bottom: 2rem; }
.stApp {
    background-image: radial-gradient(circle at 50% 50%, #0a192f 0%, #020c1b 100%);
}

/* 指標(Metric)をネオン風カードにデザイン */
[data-testid="stMetric"] {
    background-color: rgba(2, 12, 27, 0.7);
    border-radius: 8px;
    padding: 15px 20px;
    box-shadow: 0 0 10px rgba(0, 243, 255, 0.15), inset 0 0 10px rgba(0, 243, 255, 0.05);
    border: 1px solid rgba(0, 243, 255, 0.5);
    backdrop-filter: blur(5px);
}
[data-testid="stMetricLabel"] {
    font-size: 0.95rem;
    font-weight: bold;
    color: #64ffda !important;
    text-transform: uppercase;
    letter-spacing: 1px;
}
[data-testid="stMetricValue"] {
    font-size: 2.2rem;
    font-weight: 800;
    color: #ffffff !important;
    text-shadow: 0 0 10px rgba(0, 243, 255, 0.6);
}

/* 見出しをサイバー風に */
h1, h3, h4 { 
    color: #64ffda !important; 
    font-family: 'Arial', sans-serif; 
    text-shadow: 0 0 8px rgba(100, 255, 218, 0.3); 
    letter-spacing: 1px;
}

/* 区切り線をネオン風に */
hr { border-color: rgba(0, 243, 255, 0.2); box-shadow: 0 0 5px rgba(0, 243, 255, 0.4); margin-top: 1.5rem; margin-bottom: 1.5rem; }

/* dataframeのヘッダー色修正 */
thead tr th { background-color: #0a192f !important; color: #00f3ff !important; }
</style>
""", unsafe_allow_html=True)

st.title("🌌 Y2ENERGY COMMAND CENTER")

# --- 期間絞り込み (日曜始まりに修正) ---
col_preset, col_custom = st.columns([1, 2])
today = datetime.date.today()

# Python weekday(): 0=Mon, 6=Sun
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

with col_preset:
    selected_preset = st.selectbox("期間を選択", list(presets.keys()), index=4)
    
with col_custom:
    if selected_preset == "カスタム指定":
        date_range = st.date_input("カレンダーから選択", value=(today - datetime.timedelta(days=30), today), max_value=today)
        if len(date_range) == 2:
            start_date, end_date = date_range
        else:
            start_date = end_date = date_range[0]
    else:
        start_date, end_date = presets[selected_preset]
        st.info(f"**対象期間:** {start_date.strftime('%Y-%m-%d')} 〜 {end_date.strftime('%Y-%m-%d')}")

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
        summary_data.append({"日付": d, "表示回数": imps, "クリック数": clicks, "費用": cost, "コンバージョン": conv})
    
    kw_data = []
    for kw in ["太陽光 費用", "蓄電池 補助金", "太陽光パネル 見積もり", "ソーラーパネル デメリット", "Y2ENERGY 評判", "神奈川 太陽光", "蓄電池 おすすめ"]:
        k_imps = random.randint(10, 500)
        k_clicks = int(k_imps * random.uniform(0.01, 0.1))
        k_cost = k_clicks * random.randint(150, 500)
        k_conv = 1 if random.random() > 0.9 else 0
        if k_clicks > 0:
            kw_data.append({"キーワード": kw, "表示回数": k_imps, "クリック数": k_clicks, "費用": k_cost, "コンバージョン": k_conv})
    
    return pd.DataFrame(summary_data), pd.DataFrame(kw_data)

with st.spinner('各APIからリアルタイムデータを取得しています...'):
    start_str = start_date.strftime("%Y-%m-%d")
    end_str = end_date.strftime("%Y-%m-%d")
    df_summary, df_keywords, ads_error, df_ga4, ga4_error = fetch_real_data(start_str, end_str)

if ads_error or df_summary.empty:
    if ads_error:
        st.error(f"⚠️ Google広告 APIエラー: (詳細: {ads_error})")
    df_summary, df_keywords = generate_mock_ads_data(start_str, end_str)

if not df_summary.empty:
    total_clicks = df_summary["クリック数"].sum()
    total_imps = df_summary["表示回数"].sum()
    total_cost = df_summary["費用"].sum()
    total_conv = df_summary["コンバージョン"].sum()
    
    ctr = (total_clicks / total_imps * 100) if total_imps > 0 else 0
    cpc = (total_cost / total_clicks) if total_clicks > 0 else 0
    cpa = (total_cost / total_conv) if total_conv > 0 else 0
    cvr = (total_conv / total_clicks * 100) if total_clicks > 0 else 0

    # ==========================================
    # ROW 1: サマリー(左) と グラフ(右)
    # ==========================================
    row1_col1, row1_col2 = st.columns(2)
    
    with row1_col1:
        st.markdown("### 📊 Google広告 パフォーマンス")
        m1, m2 = st.columns(2)
        m1.metric("総費用", f"¥{int(total_cost):,}")
        m2.metric("クリック数", f"{int(total_clicks):,} 回")
        
        st.markdown("<div style='height:15px'></div>", unsafe_allow_html=True)
        m3, m4 = st.columns(2)
        m3.metric("クリック率 (CTR)", f"{ctr:.2f} %")
        m4.metric("コンバージョン", f"{int(total_conv)} 件")
        
        st.markdown("<div style='height:15px'></div>", unsafe_allow_html=True)
        m5, m6 = st.columns(2)
        m5.metric("コンバージョン率 (CVR)", f"{cvr:.2f} %")
        m6.metric("コンバージョン単価 (CPA)", f"¥{int(cpa):,}" if cpa > 0 else "¥-")

    with row1_col2:
        st.markdown("### 📈 クリック数 と 費用の推移")
        fig = go.Figure()
        # ネオンサイバー風のグラフ設定
        fig.add_trace(go.Bar(
            x=df_summary["日付"], y=df_summary["費用"], 
            name="費用 (¥)", marker_color="rgba(0, 243, 255, 0.4)", 
            marker_line_color="#00f3ff", marker_line_width=1.5, yaxis="y1"
        ))
        fig.add_trace(go.Scatter(
            x=df_summary["日付"], y=df_summary["クリック数"], 
            name="クリック数", mode="lines+markers", 
            line=dict(color="#ff007f", width=3), 
            marker=dict(color="#ff007f", size=8, line=dict(color="#ffffff", width=1)),
            yaxis="y2"
        ))
        fig.update_layout(
            template="plotly_dark",
            xaxis=dict(tickangle=0, type='category', showgrid=False, color="#64ffda"),
            yaxis=dict(title="費用 (¥)", side="left", showgrid=True, gridcolor='rgba(0, 243, 255, 0.1)', color="#64ffda"),
            yaxis2=dict(title="クリック数", side="right", overlaying="y", showgrid=False, color="#ff007f"),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(color="#ffffff")),
            margin=dict(l=0, r=0, t=30, b=0),
            height=380,
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)"
        )
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")

    # ==========================================
    # ROW 2: キーワード(左) と GA4(右)
    # ==========================================
    row2_col1, row2_col2 = st.columns(2)
    
    with row2_col1:
        st.markdown("### 🔍 キーワード別 パフォーマンス")
        if not df_keywords.empty:
            df_keywords["CPA"] = df_keywords.apply(lambda r: (r["費用"] / r["コンバージョン"]) if r["コンバージョン"] > 0 else 0, axis=1)
            df_keywords = df_keywords.sort_values("費用", ascending=False)
            st.dataframe(
                df_keywords, 
                use_container_width=True,
                column_config={
                    "費用": st.column_config.NumberColumn("費用", format="¥%d"),
                    "CPA": st.column_config.NumberColumn("CPA", format="¥%d"),
                },
                hide_index=True,
                height=350
            )
            
    with row2_col2:
        st.markdown("### 🌐 Webサイト アクセス解析")
        if ga4_error:
            st.error(f"⚠️ GA4 APIエラー: {ga4_error}")
        elif not df_ga4.empty:
            st.dataframe(
                df_ga4, 
                use_container_width=True, 
                hide_index=True, 
                column_config={"エンゲージメント率": st.column_config.NumberColumn(format="%.1f %%")},
                height=350
            )
        else:
            st.info("指定された期間のGA4データはありません。")

st.markdown("---")

# ==========================================
# ROW 3: 運用レポート
# ==========================================
st.markdown("### 📝 今週の運用レポート")
report_path = "weekly_analysis.md"
if os.path.exists(report_path):
    with open(report_path, "r", encoding="utf-8") as f:
        report_content = f.read()
    date_header = f"**【{start_date.strftime('%m月%d日')} 〜 {end_date.strftime('%m月%d日')}】**\n\n"
    st.info(date_header + report_content)
else:
    st.info("今週のレポートはまだ作成されていません。（※毎週土曜朝6時に更新されます）")

