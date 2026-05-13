import yfinance as yf
import pandas as pd
import os
import sys

# --- 設定 ---
# コマンドライン引数があれば第1引数をリストファイルとし、なければデフォルトを使用
TICKERS_FILE = sys.argv[1] if len(sys.argv) > 1 else "tickers.txt"
INTERVAL = "1d"

def load_tickers(file_path):
    """
    外部テキストファイルから銘柄リストを読み込む。
    '#' 以降のコメントおよび空行を除外する。
    """
    if not os.path.exists(file_path):
        print(f"× エラー: {file_path} が見つかりません。")
        return []
    
    tickers = []
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            ticker = line.split('#')[0].strip()
            if ticker:
                tickers.append(ticker)
    return tickers

def download_stock_data(tickers):
    """
    yfinanceを使用して株価データをダウンロードし、CSVとして保存する。
    """
    if not tickers:
        print("実行対象の銘柄がありません。")
        return

    os.makedirs("data", exist_ok=True)
    print(f"--- データ収集開始 (対象: {len(tickers)}銘柄 / 読み込みファイル: {TICKERS_FILE}) ---")
    
    for ticker in tickers:
        try:
            stock = yf.Ticker(ticker)
            df = stock.history(period="1y", interval=INTERVAL)
            
            if df.empty:
                print(f"× {ticker}: データが見つかりません。")
                continue
            
            # 直近10ヶ月分に絞り込み
            latest_date = df.index.max()
            start_date = latest_date - pd.DateOffset(months=10)
            df = df[df.index >= start_date]
            
            # CSV保存
            file_path = f"data/{ticker}.csv"
            df[['Open', 'High', 'Low', 'Close']].to_csv(file_path)
            print(f"◎ {ticker}: 保存完了")
            
        except Exception as e:
            print(f"! {ticker} 取得エラー: {e}")

if __name__ == "__main__":
    target_tickers = load_tickers(TICKERS_FILE)
    download_stock_data(target_tickers)