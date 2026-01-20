import streamlit as st
import yfinance as yf
import pandas as pd
import json
import base64
import os
from datetime import datetime
from github import Github

# ロジックファイルをインポート
import logic 

# ==========================================
# 0. 基本設定
# ==========================================
st.set_page_config(page_title="Trend Checker Pro v6.0", layout="wide")

def load_css(file_name):
    """CSSファイルを読み込んで適用する"""
    if os.path.exists(file_name):
        with open(file_name) as f:
            st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)

# ==========================================
# 1. 認証 & GitHub同期
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
        st.write("Mechanical Trading Engine v6.0")
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

def sync_github(data=None, action="load"):
    GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
    REPO_NAME = f"{st.secrets['GITHUB_USERNAME']}/{st.secrets['GITHUB_REPO_NAME']}"
    FILE_PATH = st.secrets["DATA_FILE_PATH"]
    
    try:
        g = Github(GITHUB_TOKEN)
        repo = g.get_repo(REPO_NAME)
    except Exception as e:
        st.error(f"GitHub接続エラー: {e}")
        return {"portfolio": [], "settings": {}}
    
    if action == "load":
        try:
            contents = repo.get_contents(FILE_PATH)
            decoded = base64.b64decode(contents.content).decode("utf-8")
            loaded_data = json.loads(decoded)
            if isinstance(loaded_data, list):
                return {"portfolio": loaded_data, "settings": {"total_capital": 1000000, "risk_per_trade": 2.0}}
            return loaded_data
        except:
            return {"portfolio": [], "settings": {"total_capital": 1000000, "risk_per_trade": 2.0}}
            
    if action == "save":
        json_content = json.dumps(data, ensure_ascii=False, indent=4)
        try:
            contents = repo.get_contents(FILE_PATH)
            repo.update_file(contents.path, f"Sync: {datetime.now()}", json_content, contents.sha)
            st.toast("☁️ クラウド同期完了", icon="✅")
        except:
            repo.create_file(FILE_PATH, "Initial setup", json_content)
            st.toast("☁️ 新規ファイル作成", icon="✅")
    return data

@st.cache_data(ttl=3600)
def fetch_stock_name(ticker):
    try:
        return yf.Ticker(ticker).info.get('shortName') or ticker
    except:
        return ticker

@st.cache_data(ttl=3600)
def get_technical_analysis(ticker):
    try:
        # 長期判定(MA75など)のために期間を2年(2y)に延長
        df = yf.Ticker(ticker).history(period="2y")
        if df.empty: return None
        
        # logic.py で指標計算
        df = logic.add_technical_indicators(df)
        return df
    except: return None

# ==========================================
# 2. メインアプリケーション
# ==========================================
def main():
    if not check_password(): return
    load_css("style.css")
    
    if 'data' not in st.session_state:
        st.session_state.data = sync_github(action="load")
    
    data = st.session_state.data
    settings = data.get("settings", {"total_capital": 1000000, "risk_per_trade": 2.0})

    st.title("📈 Trend Checker Pro v6.0")

    # --- サイドバー ---
    with st.sidebar:
        st.header("⚙️ 戦略モード設定")
        # モード切替UIの追加
        strategy_mode_jp = st.radio(
            "運用スタイル", 
            ["短期", "長期"],
            help="短期：設定した％で機械的に売買\n長期：利益が乗るほど逆指値を緩くし、MA75も参照"
        )
        # ロジックに渡す用の文字列変換
        strategy_mode = "short" if "Short" in strategy_mode_jp else "long"

        st.divider()
        st.header("💰 資金管理設定")
        new_capital = st.number_input("総投資資金 (円)", value=int(settings.get("total_capital", 1000000)), step=100000)
        new_risk = st.slider("1トレード許容リスク (%)", 0.5, 5.0, float(settings.get("risk_per_trade", 2.0)))
        
        if st.button("資金設定を保存", use_container_width=True):
            st.session_state.data["settings"] = {"total_capital": new_capital, "risk_per_trade": new_risk}
            sync_github(st.session_state.data, action="save")
            st.rerun()
            
        st.divider()
        st.header("🔧 パラメータ微調整")
        st.caption("※短期モードおよび長期モードの初期段階で使用")
        default_stop_pct = st.slider("損切り基準 (%)", 1, 15, 5) / 100
        default_trail_pct = st.slider("利確トレール (%)", 1, 20, 10) / 100
        
        st.divider()
        st.header("➕ 銘柄追加")
        with st.form("add_stock_form", clear_on_submit=True):
            t_code = st.text_input("銘柄コード (例: 202A.T)")
            t_status = st.selectbox("カテゴリ", ["保有株 (Exit監視)", "監視株 (Entry判定)"])
            t_price = st.number_input("取得/目安単価", min_value=0.0)
            t_shares = st.number_input("株数", min_value=0, step=100, value=100)
            if st.form_submit_button("銘柄を追加"):
                if t_code:
                    name = fetch_stock_name(t_code)
                    st.session_state.data["portfolio"].append({
                        "id": str(datetime.now().timestamp()),
                        "ticker": t_code, "name": name, "price": t_price,
                        "shares": t_shares, 
                        "status": "holding" if "保有" in t_status else "watching",
                        "custom_stop": None, "custom_trail": None
                    })
                    sync_github(st.session_state.data, action="save")
                    st.rerun()

        st.divider()
        st.header("📂 データインポート")
        uploaded_file = st.file_uploader("JSONファイルをアップロード", type=["json"])
        if uploaded_file is not None:
            try:
                import_data = json.load(uploaded_file)
                if isinstance(import_data, list):
                    st.session_state.data["portfolio"] = import_data
                elif isinstance(import_data, dict) and "portfolio" in import_data:
                    st.session_state.data["portfolio"] = import_data["portfolio"]
                    if "settings" in import_data:
                        st.session_state.data["settings"] = import_data["settings"]
                sync_github(st.session_state.data, action="save")
                st.rerun()
            except Exception as e:
                st.error(f"読み込みエラー: {e}")

    # --- データエディタ ---
    with st.expander("🛠️ ポートフォリオ一括管理 (JSON編集)", expanded=False):
        df_editor = pd.DataFrame(st.session_state.data["portfolio"])
        for col in ['shares', 'custom_stop', 'custom_trail']:
            if col not in df_editor.columns: df_editor[col] = None
        edited_df = st.data_editor(df_editor, num_rows="dynamic", use_container_width=True)
        if st.button("変更をクラウド保存", use_container_width=True):
            st.session_state.data["portfolio"] = edited_df.to_dict(orient="records")
            sync_github(st.session_state.data, action="save")
            st.rerun()

    # --- メインタブ ---
    tab1, tab2 = st.tabs(["🚀 保有銘柄 (Exit)", "🔍 監視銘柄 (Entry)"])

    # --- タブ1: 保有銘柄 ---
    with tab1:
        current_holdings = [s for s in st.session_state.data["portfolio"] if s.get("status") == "holding"]
        total_market_value = 0
        
        if not current_holdings:
            st.info("保有銘柄がありません。")
        else:
            st.markdown(f"### 📋 逆指値注文")
            st.caption("証券アプリで以下の逆指値（成行売）を設定してください。")
            
          # 3列グリッドで表示
            cols = st.columns(len(current_holdings) if len(current_holdings) < 3 else 3)
            
            for idx, s in enumerate(current_holdings):
                df = get_technical_analysis(s['ticker'])
                if df is None: continue
                
                # logic.py の新しい関数引数に対応 (ma75も取得)
                curr, high, rsi, ma75 = logic.get_latest_metrics(df, s['price'], s['id'])
                
                p_stop = s.get('custom_stop')
                p_trail = s.get('custom_trail')
                applied_stop = (p_stop / 100) if (pd.notnull(p_stop) and p_stop > 0) else default_stop_pct
                applied_trail = (p_trail / 100) if (pd.notnull(p_trail) and p_trail > 0) else default_trail_pct
                
                # --- ロジック呼び出し ---
                strategy = logic.calculate_exit_strategy(
                    s['price'], curr, high, ma75, applied_stop, applied_trail, mode=strategy_mode
                )
                
                card_class = "bg-emergency" if strategy['is_emergency'] else ("bg-safe" if strategy['profit_pct'] > 5 else "bg-normal")
                label_class = "card-label-red" if strategy['is_emergency'] else "card-label-green"

                # 損益額の計算
                unrealized_pl = (curr - s['price']) * s.get('shares', 0)
                pl_color = "#2ecc71" if unrealized_pl < 0 else "#ff4b4b" # プラスなら緑、マイナスなら赤（提示コード準拠）
                
                with cols[idx % 3]:
                    st.markdown(f"""
                    <div class="guide-card {card_class}">
                        <div class="card-header">
                            <span class="card-ticker">{s['ticker']}</span>
                            <span class="{label_class}">{strategy['label']}</span>
                        </div>
                        <div class="card-name">{s.get('name', s['ticker'])}</div>
                        <div class="card-price-area">
                            {strategy['order_price']:,.0f} <span class="card-price-unit">円以下で売</span>
                        </div>
                        <div class="card-footer">
                            <div>建値：{s['price']:,.0f}</div>
                            <div>現在：{curr:,.0f}</div>
                            <div style="color:{pl_color}; font-weight:bold;">
                                損益: {unrealized_pl:+,.0f} 円 ({strategy['profit_pct']:+.1f}%)
                            </div>
                            <div>期間高値：{high:,.0f} 円</div>
                            <div>保有株数：{s.get('shares', 0)} 株</div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # 削除ボタンを追加
                    if  st.button("削除", key=f"del_{s['id']}", use_container_width=True,type="primary"):
                        st.session_state.data["portfolio"] = [x for x in st.session_state.data["portfolio"] if x['id'] != s['id']]
                        sync_github(st.session_state.data, action="save")
                        st.rerun()
            
                total_market_value += (curr * s.get('shares', 0))

    # --- タブ2: 監視銘柄 ---
    with tab2:
        current_watchings = [s for s in st.session_state.data["portfolio"] if s.get("status") == "watching"]
        # 現金余力の計算（全保有株の現在評価額を引いたもの）
        current_holdings_value = sum([
            logic.get_latest_metrics(get_technical_analysis(h['ticker']), h['price'], h['id'])[0] * h.get('shares', 0)
            for h in st.session_state.data["portfolio"] if h.get("status") == "holding" and get_technical_analysis(h['ticker']) is not None
        ])
        cash_pos = settings.get("total_capital", 1000000) - current_holdings_value
        
        st.markdown(f"### 🏦 買付余力: {cash_pos:,.0f}円")
        st.caption("スコア50点以上で買い")
        
        if not current_watchings:
            st.info("監視中の銘柄はありません。サイドバーから追加してください。")
        else:
            # 3列グリッド
            cols = st.columns(len(current_watchings) if len(current_watchings) < 3 else 3)

            for idx, s in enumerate(current_watchings):
                df = get_technical_analysis(s['ticker'])
                if df is None: continue
                
                # Entry用データ取得
                curr = df['Close'].iloc[-1]
                rsi = df['RSI'].iloc[-1]
                vol_curr = df['Volume'].iloc[-1]
                vol_ma5 = df['VolMA5'].iloc[-1]
                vol_ratio = vol_curr / vol_ma5 if vol_ma5 > 0 else 0
                
                # ロジック判定
                score, reasons = logic.analyze_entry_strategy(df)
                
                # 資金管理からの推奨株数算出
                rec_shares = logic.calculate_position_size(
                    settings.get("total_capital", 1000000), 
                    settings.get("risk_per_trade", 2.0), 
                    curr, 
                    default_stop_pct
                )
                
                # デザイン判定
                is_buy_signal = score >= 50
                card_class = "bg-safe" if is_buy_signal else "bg-normal" # 買い時は緑、それ以外は通常
                label_text = f"🚀 買い時：{score}点" if is_buy_signal else f"💤 監視中：{score}点"
                label_class = "card-label-green" if is_buy_signal else "card-label-gray" # card-label-grayはCSSになければ白文字になります
                
                # 加点理由のテキスト化
                reason_text = ", ".join(reasons) if reasons else "特になし"

                with cols[idx % 3]:
                    st.markdown(f"""
                    <div class="guide-card {card_class}">
                        <div class="card-header">
                            <span class="card-ticker">{s['ticker']}</span>
                            <span class="{label_class}">{label_text}</span>
                        </div>
                        <div class="card-name">{s.get('name', s['ticker'])}</div>
                        <div class="card-price-area">
                            {curr:,.0f} <span class="card-price-unit">円</span>
                        </div>
                        <div class="card-footer">
                            <div>RSI：{rsi:.1f}</div>
                            <div>出来高倍率：{vol_ratio:.1f}倍</div>
                            <div style="font-size: 0.7rem; color: #aaa; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
                                要因：{reason_text}
                            </div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

                    if st.button("保有へ", key=f"mov_{s['id']}", use_container_width=True, type="primary"):
                        for p in st.session_state.data["portfolio"]:
                            if p['id'] == s['id']:
                                p['status'] = 'holding'
                                p['price'] = curr
                                p['shares'] = rec_shares
                        sync_github(st.session_state.data, action="save")
                        st.rerun()


if __name__ == "__main__":
    main()