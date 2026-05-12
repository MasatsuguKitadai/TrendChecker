import yfinance as yf
import pandas as pd
import os

# --- 設定 ---
TICKERS_FILE = "tickers.txt"
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
            # '#' で分割して最初の要素（銘柄コード部分）だけを取得し、空白を除去
            ticker = line.split('#')[0].strip()
            
            # 抽出した結果が空でなければ（銘柄コードがあれば）追加
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
    print(f"--- データ収集開始 (対象: {len(tickers)}銘柄) ---")
    
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
    # Python を使用したツール開発の効率を高めるため、設定を外部化
    target_tickers = load_tickers(TICKERS_FILE)
    download_stock_data(target_tickers)