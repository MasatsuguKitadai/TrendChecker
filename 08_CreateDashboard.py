import os
import pandas as pd
import json

# --- 設定 ---
LONG_CHART_DIR, SHORT_CHART_DIR = "visualized_charts", "visualized_charts_short"
LONG_RESULT_DIR, SHORT_RESULT_DIR = "simulation_results", "simulation_results_short"
ACTION_FILE = "simulation_results/todays_actions.csv"
OUTPUT_FILE = "Dashboard.html"

def generate_dashboard():
    # アクションデータの読み込み
    df_actions = pd.read_csv(ACTION_FILE) if os.path.exists(ACTION_FILE) else pd.DataFrame()
    actions_json = df_actions.to_dict(orient='records')
    
    # 銘柄名と株価のマッピングを作成（シミュレーションタブ用）
    name_map = {}
    price_map = {}
    if not df_actions.empty:
        # SUMMARY行を除外してマッピングを作成
        df_valid = df_actions[df_actions['Ticker'] != 'SUMMARY']
        name_map = dict(zip(df_valid['Ticker'], df_valid['Name']))
        price_map = dict(zip(df_valid['Ticker'], df_valid['Close']))

    def get_sum(p): 
        return {r['Ticker']: r['Total_Profit'] for _, r in pd.read_csv(p).iterrows()} if os.path.exists(p) else {}
    
    l_sum, s_sum = get_sum(f"{LONG_RESULT_DIR}/overall_summary.csv"), get_sum(f"{SHORT_RESULT_DIR}/overall_summary.csv")

    html_content = f"""
    <!DOCTYPE html>
    <html lang="ja">
    <head>
        <meta charset="UTF-8"><title>Stock Advisor Dashboard</title>
        <style>
            :root {{ --primary: #007bff; --bg: #ffffff; --sidebar-bg: #f8f9fa; --text: #212529; --border: #dee2e6; --up-color: #28a745; --down-color: #dc3545; }}
            body {{ font-family: 'Segoe UI', Roboto, sans-serif; margin: 0; background: var(--bg); color: var(--text); overflow: hidden; }}
            .nav-bar {{ display: flex; background: #fff; border-bottom: 1px solid var(--border); box-shadow: 0 2px 4px rgba(0,0,0,0.05); }}
            .nav-item {{ padding: 16px 24px; cursor: pointer; color: #6c757d; border-bottom: 3px solid transparent; font-weight: 500; }}
            .nav-item.active {{ color: var(--primary); border-bottom-color: var(--primary); background: #f0f7ff; }}
            .content-page {{ display: none; height: calc(100vh - 55px); overflow: auto; }}
            .content-page.active {{ display: flex; }}
            
            .container {{ width: 70%; padding: 30px; box-sizing: border-box; margin: 0 auto; }}
            table {{ width: 100%; border-collapse: collapse; background: #fff; border-radius: 8px; overflow: hidden; box-shadow: 0 0 20px rgba(0,0,0,0.05); }}
            th, td {{ padding: 15px; border-bottom: 1px solid var(--border); text-align: left; }}
            th {{ background: #f1f3f5; font-weight: 600; color: #495057; }}
            
            .row-summary {{ background-color: #e7f3ff; font-weight: bold; }}
            .row-summary td {{ border-bottom: 2px solid var(--primary); }}
            
            .gap-up {{ color: var(--up-color); font-weight: bold; }} 
            .gap-down {{ color: var(--down-color); font-weight: bold; }} 

            .action-badge {{ padding: 4px 8px; border-radius: 4px; font-size: 0.85em; font-weight: bold; background: #e9ecef; }}
            .new-signal {{ background: #fff3cd; color: #856404; border: 1px solid #ffeeba; }}
            /* 【追加】保持日用の緑色バッジスタイル */
            .hold-signal {{ background: #d4edda; color: #155724; border: 1px solid #c3e6cb; }}

            #sidebar {{ width: 380px; background: var(--sidebar-bg); border-right: 1px solid var(--border); display: flex; flex-direction: column; }}
            #chart-area {{ flex: 1; background: #fff; }}
            .list-item {{ padding: 15px; border-bottom: 1px solid var(--border); cursor: pointer; transition: 0.2s; }}
            .list-item:hover {{ background: #e9ecef; }}
            .sub-tab {{ display: flex; border-bottom: 1px solid var(--border); }}
            .sub-tab div {{ flex: 1; padding: 12px; text-align: center; cursor: pointer; color: #6c757d; }}
            .sub-tab div.active {{ color: var(--primary); font-weight: bold; background: #fff; }}
            
            .ticker-sub {{ font-size: 0.85em; color: #6c757d; margin-left: 5px; font-weight: normal; }}
        </style>
    </head>
    <body>
        <div class="nav-bar">
            <div id="nav-1" class="nav-item active" onclick="showPage(1)">本日の株価</div>
            <div id="nav-2" class="nav-item" onclick="showPage(2)">シミュレーション</div>
        </div>

        <div id="page-1" class="content-page active">
            <div class="container">
                <h2 style="margin-top:0;">⚡ 明日のアクション</h2>
                <table>
                    <thead><tr><th>Ticker</th><th>銘柄名</th><th>終値</th><th>前日との差（損益率）</th><th>アクション</th></tr></thead>
                    <tbody id="action-body"></tbody>
                </table>
            </div>
        </div>

        <div id="page-2" class="content-page">
            <div id="sidebar">
                <div class="sub-tab">
                    <div id="sub-l" class="active" onclick="setMode('long')">ロング</div>
                    <div id="sub-s" onclick="setMode('short')">ショート</div>
                </div>
                <div id="ticker-list" style="overflow-y:auto; flex:1;"></div>
            </div>
            <div id="chart-area"><iframe id="frame" style="width:100%; height:100%; border:none;"></iframe></div>
        </div>

        <script>
            const data = {json.dumps(actions_json)};
            const nameMap = {json.dumps(name_map)};
            const priceMap = {json.dumps(price_map)};
            const lSum = {json.dumps(l_sum)}, sSum = {json.dumps(s_sum)};
            let currentMode = 'long';

            function showPage(n) {{
                document.querySelectorAll('.nav-item, .content-page').forEach(el => el.classList.remove('active'));
                document.getElementById('nav-'+n).classList.add('active');
                document.getElementById('page-'+n).classList.add('active');
            }}

            function renderStatus() {{
                const aBody = document.getElementById('action-body');
                
                aBody.innerHTML = '';

                data.forEach(r => {{
                    const isSummary = r.Ticker === 'SUMMARY';
                    const rowClass = isSummary ? 'row-summary' : '';
                    const gapClass = r.GapRaw > 0 ? 'gap-up' : (r.GapRaw < 0 ? 'gap-down' : '');
                    
                    // 【修正】保持日の文言が含まれている場合は緑色のバッジを適用
                    let badgeClass = 'action-badge';
                    if (!isSummary) {{
                        if (r.Type.startsWith('NEW')) {{
                            badgeClass += ' new-signal';
                        }} else if (r.Action && (r.Action.includes('スキップ') || r.Action.includes('逆指値'))) {{
                            badgeClass += ' hold-signal';
                        }}
                    }}
                    
                    aBody.innerHTML += `<tr class="${{rowClass}}">
                        <td><b>${{r.Ticker}}</b></td>
                        <td>${{r.Name}}</td>
                        <td style="font-size:1.1em; font-weight:600;">${{r.Close.toLocaleString()}}円</td>
                        <td class="${{gapClass}}">${{r.GapText}}</td>
                        <td><span class="${{badgeClass}}">${{r.Action}}</span></td>
                    </tr>`;
                }});
            }}

            function setMode(m) {{
                currentMode = m;
                document.getElementById('sub-l').className = m==='long'?'active':'';
                document.getElementById('sub-s').className = m==='short'?'active':'';
                renderList();
            }}

            function renderList() {{
                const list = document.getElementById('ticker-list');
                list.innerHTML = '';
                const sum = currentMode === 'long' ? lSum : sSum;
                const dir = currentMode === 'long' ? '{LONG_CHART_DIR}' : '{SHORT_CHART_DIR}';
                const prefix = currentMode === 'long' ? 'chart_' : 'chart_short_';

                Object.keys(sum).forEach(t => {{
                    const mName = nameMap[t] || '';
                    const currentPrice = priceMap[t] || 0;
                    const profit = sum[t];
                    
                    // 指標の計算：(累積損益 ÷ 現在の株価 × 100)
                    let ratioStr = "";
                    if (currentPrice > 0) {{
                        const ratio = (profit / currentPrice) * 100;
                        ratioStr = `（${{ratio.toFixed(1)}}%）`;
                    }}

                    const div = document.createElement('div');
                    div.className = 'list-item';
                    div.innerHTML = `<b>${{t}}</b><span class="ticker-sub">${{mName}}</span><br>
                                     <small style="color:#6c757d;">累計損益：${{profit.toLocaleString()}}円${{ratioStr}}</small>`;
                    div.onclick = () => document.getElementById('frame').src = dir + '/' + prefix + t + '.html';
                    list.appendChild(div);
                }});
            }}

            renderStatus(); setMode('long');
        </script>
    </body>
    </html>
    """
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"◎ Dashboard.html 更新完了")

if __name__ == "__main__":
    generate_dashboard()