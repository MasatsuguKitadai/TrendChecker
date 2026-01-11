import streamlit as st
import yfinance as yf
import pandas as pd
import json
import os
import base64
import requests
import time
from datetime import datetime
from github import Github

# ==========================================
# 0. 認証機能
# ==========================================
def check_password():
    if "password_correct" not in st.session_state:
        st.session_state.password_correct = False
    
    if st.session_state.password_correct:
        return True

    # プレースホルダー（空のコンテナ）を作成
    login_area = st.empty()

    with login_area.container():
        st.title("🔒 Trend Checker Login")
        password_input = st.text_input("Password", type="password")
        
        if st.button("Login", type="primary"):
            if password_input == st.secrets["PASSWORD"]:
                # 1. 認証フラグを立てる
                st.session_state.password_correct = True
                # 2. ログインUIを即座に消去（これで残像が消える）
                login_area.empty()
                # 3. リロードしてメイン画面へ
                st.rerun()
            else:
                st.error("パスワードが違います")
    return False

# ==========================================
# 1. データ処理・GitHub連携
# ==========================================
def load_data():
    """GitHubから最新のポートフォリオを読み込む"""
    g = Github(st.secrets["GITHUB_TOKEN"])
    repo = g.get_user(st.secrets["GITHUB_USERNAME"]).get_repo(st.secrets["GITHUB_REPO_NAME"])
    contents = repo.get_contents(st.secrets["DATA_FILE_PATH"])
    data = json.loads(base64.b64decode(contents.content).decode("utf-8"))
    return data

def save_data(data):
    """ローカルとGitHubの両方に保存"""
    json_content = json.dumps(data, ensure_ascii=False, indent=4)
    try:
        g = Github(st.secrets["GITHUB_TOKEN"])
        repo = g.get_user(st.secrets["GITHUB_USERNAME"]).get_repo(st.secrets["GITHUB_REPO_NAME"])
        path = st.secrets["DATA_FILE_PATH"]
        try:
            contents = repo.get_contents(path)
            repo.update_file(contents.path, f"Update: {datetime.now()}", json_content, contents.sha)
            st.toast("☁️ クラウドに同期しました", icon="✅")
        except:
            repo.create_file(path, "Create portfolio.json", json_content)
            st.toast("☁️ クラウドに新規作成しました", icon="✅")
    except Exception as e:
        st.error(f"GitHub保存エラー: {e}")
    time.sleep(1)

# ==========================================
# 2. テクニカル分析ロジック
# ==========================================
@st.cache_data(ttl=3600)
def get_stock_info(ticker):
    try:
        return yf.Ticker(ticker).info.get('shortName') or ticker
    except:
        return ticker

def get_tech_data(ticker):
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
# 3. メインアプリ
# ==========================================
def main():
    if not check_password():
        return

    st.set_page_config(page_title="Trend Checker Pro", layout="wide")
    
    # CSS読み込み
    if os.path.exists("style.css"):
        with open("style.css") as f:
            st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)

    st.title("📈 Trend Checker Pro")
    
    # データロード
    if 'portfolio' not in st.session_state:
        st.session_state.portfolio = load_data()

    # --- サイドバー：銘柄管理 ---
    with st.sidebar:
        st.header("⚙️ 銘柄登録")
        with st.form("entry_form", clear_on_submit=True):
            new_ticker = st.text_input("銘柄コード (例: 0000.T)")
            new_status = st.selectbox("カテゴリ", ["保有 (Exit監視)", "監視 (Entry判定)"])
            new_price = st.number_input("取得/目安単価", min_value=0.0)
            
            if st.form_submit_button("ポートフォリオに追加"):
                if new_ticker:
                    name = get_stock_info(new_ticker)
                    new_entry = {
                        "id": str(datetime.now().timestamp()),
                        "ticker": new_ticker,
                        "name": name,
                        "price": new_price,
                        "status": "holding" if "保有" in new_status else "watching"
                    }
                    st.session_state.portfolio.append(new_entry)
                    save_data(st.session_state.portfolio)
                    st.rerun()

        st.divider()
        stop_pct = st.slider("損切りライン (%)", 1, 10, 5) / 100
        trail_pct = st.slider("利確トレール (%)", 1, 20, 10) / 100

    # --- データ管理エディタ ---
    with st.expander("🛠️ データ管理（直接編集・復元）", expanded=False):
        st.markdown("### ポートフォリオ編集")
        df_editor = pd.DataFrame(st.session_state.portfolio)
        edited_df = st.data_editor(
            df_editor,
            num_rows="dynamic",
            column_config={
                "ticker": st.column_config.TextColumn("銘柄コード", required=True),
                "status": st.column_config.SelectboxColumn("ステータス", options=["holding", "watching"]),
                "price": st.column_config.NumberColumn("単価", format="%.1f")
            }
        )

        col_save, col_backup = st.columns([1, 1])
        with col_save:
            if st.button("変更を保存", use_container_width=True):
                updated_data = json.loads(edited_df.to_json(orient="records"))
                save_data(updated_data)
                st.success("保存しました。")
                st.rerun()
        
        # --- バックアップダウンロード機能 ---
        with col_backup:
            # ダウンロードボタン
            st.download_button(
                label="JSON形式でバックアップ",
                data=json.dumps(st.session_state.portfolio, ensure_ascii=False, indent=4),
                file_name=f"portfolio_backup_{datetime.now().strftime('%Y%m%d')}.json",
                mime="application/json",
                use_container_width=True,
            )

        st.markdown("### データの復元")
        up_file = st.file_uploader("バックアップファイル(.json)を選択してください", type="json")
        if up_file is not None:
            # ファイルが選択された時だけ「復元実行」ボタンを表示
            if st.button("このデータで復元（上書き）を実行する", type="primary", use_container_width=True):
                try:
                    st.session_state.portfolio = json.load(up_file)
                    save_data(st.session_state.portfolio) # GitHubへ同期
                    st.success("データの復元に成功しました！")
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    st.error(f"復元エラー: {e}")

    # --- メインコンテンツ：監視パネル ---
    tab1, tab2 = st.tabs(["🔍 監視銘柄 (Entry判定)","🚀 保有銘柄 (Exit監視)"])

    # タブ1: 監視（豆蔵、テクノホライズンなど）
    with tab1:
        watchings = [s for s in st.session_state.portfolio if s.get("status") == "watching"]
        for s in watchings:
            df = get_tech_data(s['ticker'])
            if df is None: continue
            rsi, curr = df['RSI'].iloc[-1], df['Close'].iloc[-1]
            ma5, ma25 = df['MA5'].iloc[-1], df['MA25'].iloc[-1]
            
            score = 0
            if rsi < 35: score += 50 
            elif ma5 > ma25 and df['MA5'].iloc[-2] <= df['MA25'].iloc[-2]: score += 50
            
            with st.expander(f"【{s['ticker']}】{s['name']}", expanded=True):
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("現在価格", f"{curr:,.1f}")
                c2.metric("RSI(14)", f"{rsi:.1f}")
                c3.metric("短期/長期MA", f"{ma5:,.0f}/{ma25:,.0f}")
                if score >= 50: c4.success("🚀 買い時!!")
                else: c4.info("💤 待機中")

    # タブ2: 保有（アサカ理研、QPS研究所など）
    with tab2:
        holdings = [s for s in st.session_state.portfolio if s.get("status") == "holding"]
        for s in holdings:
            df = get_tech_data(s['ticker'])
            if df is None: continue
            curr = df['Close'].iloc[-1]
            high = df['High'].max()
            profit_pct = ((curr - s['price']) / s['price']) * 100
            
            with st.expander(f"【{s['ticker']}】{s['name']} | 損益：{profit_pct:+.2f}%", expanded=True):
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("取得単価", f"{s['price']:,.1f}")
                c2.metric("現在価格", f"{curr:,.1f}", delta=f"{curr-s['price']:+.1f}")
                c3.metric("5日最高値", f"{high:,.1f}")
                
                # 判定
                stop_v, trail_v = s['price']*(1-stop_pct), high*(1-trail_pct)
                if curr <= stop_v: c4.error(f"🚨 損切り\n({stop_v:,.0f}円)")
                elif curr <= trail_v and curr > s['price']: c4.warning(f"💰 利確!!\n({trail_v:,.0f}円)")
                else: c4.success("✅ ホールド")



if __name__ == "__main__":
    main()