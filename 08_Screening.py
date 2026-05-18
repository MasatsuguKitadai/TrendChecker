import pandas as pd
import os
import yfinance as yf

# --- 設定 ---
SUMMARY_FILE = "simulation_results/overall_summary.csv"
OUTPUT_TXT = "screened_tickers.txt"

# --- スクリーニング条件 ---
MIN_TRADE_COUNT = 3    # 最低取引回数（ノイズを除去するため）
TOP_N = 30             # 抽出する上位銘柄の数

def get_company_name(ticker):
    """yfinanceを使用して銘柄名を取得する"""
    try:
        t_code = ticker if ".T" in ticker else f"{ticker}.T"
        info = yf.Ticker(t_code).info
        return info.get('shortName') or info.get('longName') or ticker
    except:
        return ticker

def run_screening():
    if not os.path.exists(SUMMARY_FILE):
        print(f"× エラー: {SUMMARY_FILE} が見つかりません。先にシミュレーションを実行してください。")
        return

    print("--- スクリーニング処理開始（銘柄名取得中...） ---")
    
    # 1. サマリー結果の読み込み
    df = pd.read_csv(SUMMARY_FILE)
    total_tickers = len(df)
    
    # 2. ノイズの除去（取引回数が少なすぎるものを除外）
    df_filtered = df[df['Trade_Count'] >= MIN_TRADE_COUNT].copy()
    
    # 3. 収益率（Profit_Rate_Pct）で降順（高い順）にソート
    df_sorted = df_filtered.sort_values(by="Profit_Rate_Pct", ascending=False)
    
    # 上位N件を取得
    if TOP_N is not None:
        df_sorted = df_sorted.head(TOP_N)

    if df_sorted.empty:
        print("条件を満たす銘柄が見つかりませんでした。")
        return

    # 4. 銘柄名のマッピングを追加
    print(" 銘柄名を取得しています...")
    df_sorted['Name'] = df_sorted['Ticker'].astype(str).apply(get_company_name)

    # 5. テキストファイルへの書き出し
    with open(OUTPUT_TXT, "w", encoding="utf-8") as f:
        f.write("# スクリーニング抽出銘柄\n")
        f.write(f"# 条件: 最低取引回数 {MIN_TRADE_COUNT}回以上, 上位 {len(df_sorted)}件\n\n")
        
        for index, row in df_sorted.iterrows():
            ticker = row['Ticker']
            name = row['Name']
            rate = row['Profit_Rate_Pct']
            count = row['Trade_Count']
            
            # 銘柄名の後に収益率などのパフォーマンスデータを整理して出力
            f.write(f"{ticker} \t# {name} | 収益率: {rate:+.2f}% (取引回数: {count}回)\n")

    # コンソールにも上位結果をサマリー表示
    print(f"\n【スクリーニング完了】 対象 {total_tickers}銘柄 -> 抽出 {len(df_sorted)}銘柄")
    print(f"結果を {OUTPUT_TXT} に保存しました。\n")
    
    print("--- 収益率上位トップ10 ---")
    display_df = df_sorted.head(10)[['Ticker', 'Name', 'Profit_Rate_Pct', 'Trade_Count']]
    display_df.rename(columns={'Ticker': 'コード', 'Name': '銘柄名', 'Profit_Rate_Pct': '収益率(%)', 'Trade_Count': '取引回数'}, inplace=True)
    print(display_df.to_string(index=False))

if __name__ == "__main__":
    run_screening()