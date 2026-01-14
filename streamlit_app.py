import streamlit as st
import yfinance as yf
import pandas as pd
import json
import base64
import requests
import time
import os
from datetime import datetime
from github import Github

# ==========================================
# 0. 初期設定 & CSS読み込み
# ==========================================
st.set_page_config(page_title="Trend Checker Pro v4.7", layout="wide")

def load_local_css(file_name):
    if os.path.exists(file_name):
        with open(file_name) as f:
            st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)

# ==========================================
# 1. 認証機能
# ==========================================
def check_password():
    if "password_correct" not in st.session_state:
        st.session_state.password_correct = False
    if st.session_state.password_correct:
        return True

    login_area = st.empty()
    with login_area.container():
        st.markdown('<div class="login-container">', unsafe_allow_html=True)
        st.title("🔒 Trend Checker Pro")
        st.write("Mechanical Trading Engine")
        password_input = st.text_input("Password", type="password")
        if st.button("Login", type="primary", use_container_width=True):
            if password_input == st.secrets["PASSWORD"]:
                st.session_state.password_correct = True
                login_area.empty()
                st.rerun()
            else:
                st.error("パスワードが正しくありません")
        st.markdown('</div>', unsafe_allow_html=True)
    return False

# ==========================================
# 2. GitHubデータ同期
# ==========================================
def sync_github(portfolio_data=None, action="load"):
    GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
    REPO_NAME = st.secrets["GITHUB_USERNAME"] + "/" + st.secrets["GITHUB_REPO_NAME"]
    FILE_PATH = st.secrets["DATA_FILE_PATH"]
    
    g = Github(GITHUB_TOKEN)
    repo = g.get_repo(REPO_NAME)
    
    if action == "load":
        try:
            contents = repo.get_contents(FILE_PATH)
            return json.loads(base64.b64decode(contents.content).decode("utf-8"))
        except:
            return []
            
    if action == "save":
        json_content = json.dumps(portfolio_data, ensure_ascii=False, indent=4)
        try:
            contents = repo.get_contents(FILE_PATH)
            repo.update_file(contents.path, f"Sync: {datetime.now()}", json_content, contents.sha)
            st.toast("☁️ Sync Completed", icon="✅")
        except:
            repo.create_file(FILE_PATH, "Initial setup", json_content)
            st.toast("☁️ Created New Cloud File", icon="✅")
    return portfolio_data

# ==========================================
# 3. 分析エンジン
# ==========================================
@st.cache_data(ttl=3600)
def fetch_stock_name(ticker):
    try:
        return yf.Ticker(ticker).info.get('shortName') or ticker
    except:
        return ticker

def get_technical_analysis(ticker):
    df = yf.Ticker(ticker).history(period="60d")
    if df.empty: return None
    df['MA5'] = df['Close'].rolling(window=5).mean()
    df['MA25'] = df['Close'].rolling(window=25).mean()
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    df['RSI'] = 100 - (100 / (1 + (gain / (loss + 1e-10))))
    return df

# ==========================================
# 4. メインアプリケーション
# ==========================================
def main():
    if not check_password(): return
    load_local_css("style.css")
    
    if 'portfolio' not in st.session_state:
        st.session_state.portfolio = sync_github(action="load")

    st.title("📈 Trend Checker Pro")

    with st.sidebar:
        st.header("⚙️ 銘柄管理")
        with st.form("add_stock_form", clear_on_submit=True):
            t_code = st.text_input("銘柄コード (例: 5724.T)")
            t_status = st.selectbox("カテゴリ", ["保有株 (Exit監視)", "監視株 (Entry判定)"])
            t_price = st.number_input("取得/目安単価", min_value=0.0)
            t_shares = st.number_input("持ち株数", min_value=0, step=1, value=100)
            if st.form_submit_button("保存"):
                if t_code:
                    name = fetch_stock_name(t_code)
                    st.session_state.portfolio.append({
                        "id": str(datetime.now().timestamp()),
                        "ticker": t_code, 
                        "name": name, 
                        "price": t_price,
                        "shares": t_shares,
                        "status": "holding" if "保有" in t_status else "watching"
                    })
                    sync_github(st.session_state.portfolio, action="save")
                    st.rerun()

        st.divider()
        st.header("⚖️ ルール")
        stop_pct = st.sidebar.slider("損切り (%)", 1, 10, 5) / 100
        trail_pct = st.sidebar.slider("利確トレール (%)", 1, 20, 10) / 100

    # データ管理エディタ
    with st.expander("🛠️ データ管理（編集・復元）", expanded=False):
        df_editor = pd.DataFrame(st.session_state.portfolio)
        # 以前のデータにsharesがない場合のデフォルト値補完
        if not df_editor.empty and 'shares' not in df_editor.columns:
            df_editor['shares'] = 0
            
        edited_df = st.data_editor(
            df_editor, 
            num_rows="dynamic", 
            use_container_width=True,
            column_config={
                "status": st.column_config.SelectboxColumn("Status", options=["holding", "watching"]),
                "price": st.column_config.NumberColumn("Price", format="%.1f"),
                "shares": st.column_config.NumberColumn("Shares", min_value=0, step=1)
            }
        )
        if st.button("クラウド保存"):
            st.session_state.portfolio = edited_df.to_dict(orient="records")
            sync_github(st.session_state.portfolio, action="save")
            st.rerun()

    tab1, tab2 = st.tabs(["🚀 保有銘柄 (Exit)", "🔍 監視銘柄 (Entry)"])

    # タブ1: 保有銘柄
    with tab1:
        holdings = [s for s in st.session_state.portfolio if s.get("status") == "holding"]
        for s in holdings:
            df = get_technical_analysis(s['ticker'])
            if df is None: continue
            
            curr, high, rsi = df['Close'].iloc[-1], df['High'].max(), df['RSI'].iloc[-1]
            shares = s.get('shares', 0)
            
            # 各種計算
            profit_pct = ((curr - s['price']) / s['price']) * 100
            profit_amt = (curr - s['price']) * shares
            market_val = curr * shares
            
            stop_v, trail_v = s['price'] * (1 - stop_pct), high * (1 - trail_pct)
            
            with st.expander(f"【 {s['ticker']} 】{s['name']} / 時価：{market_val:,.0f}円", expanded=True):
                # カラム数を5に拡張
                c1, c2, c3, c4, c5 = st.columns(5)
                c1.metric(" 取得単価", f"{s['price']:,.1f}")
                c2.metric(" 現在価格", f"{curr:,.1f}", delta=f"{curr-s['price']:+.1f}")
                c3.metric(" 持ち株数", f"{shares:,.0f} 株")
                c4.metric(" 5日最高値", f"{high:,.1f}")
                
                # 判定エリア (c5)
                if curr <= stop_v:
                    c5.markdown(f'<div class="status-box status-error">🚨 損切り!! {profit_amt:+,.0f}円 {stop_v:,.0f}円)</div>', unsafe_allow_html=True)
                elif curr <= trail_v and curr > s['price']:
                    c5.markdown(f'<div class="status-box status-warning">💰 利確!! {profit_amt:+,.0f}円 {profit_pct:+.1f}%</div>', unsafe_allow_html=True)
                else:
                    c5.markdown(f'<div class="status-box status-success">✅ ホールド {profit_amt:+,.0f}円 {profit_pct:+.1f}%</div>', unsafe_allow_html=True)
                
                if rsi >= 80:
                    st.markdown(f'<div class="overheat-box">🔥 超過熱 (RSI：{rsi:.1f}) / 追撃買い厳禁</div>', unsafe_allow_html=True)
                
                if st.button(f"削除", key=f"del_{s['id']}"):
                    st.session_state.portfolio = [x for x in st.session_state.portfolio if x['id'] != s['id']]
                    sync_github(st.session_state.portfolio, action="save")
                    st.rerun()

    # タブ2: 監視銘柄
    with tab2:
        watchings = [s for s in st.session_state.portfolio if s.get("status") == "watching"]
        for s in watchings:
            df = get_technical_analysis(s['ticker'])
            if df is None: continue
            rsi, curr = df['RSI'].iloc[-1], df['Close'].iloc[-1]
            ma5, ma25 = df['MA5'].iloc[-1], df['MA25'].iloc[-1]
            
            score = 0
            if rsi < 35: score += 50 
            elif ma5 > ma25 and df['MA5'].iloc[-2] <= df['MA25'].iloc[-2]: score += 50
            
            with st.expander(f"【 {s['ticker']} 】{s['name']} / スコア： {score}", expanded=True):
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("価格", f"{curr:,.1f}")
                c2.metric("RSI", f"{rsi:.1f}")
                c3.metric("MA 5/25", f"{ma5:,.0f}/{ma25:,.0f}")
                
                if score >= 50:
                    c4.markdown('<div class="status-box status-success">🚀 買い時!!</div>', unsafe_allow_html=True)
                else:
                    c4.markdown('<div class="status-box status-info">💤 監視継続</div>', unsafe_allow_html=True)
                
                if st.button(f"保有へ移行", key=f"mov_{s['id']}"):
                    for p in st.session_state.portfolio:
                        if p['id'] == s['id']:
                            p['status'], p['price'] = 'holding', curr
                    sync_github(st.session_state.portfolio, action="save")
                    st.rerun()

if __name__ == "__main__":
    main()