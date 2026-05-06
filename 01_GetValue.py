import yfinance as yf
import pandas as pd
import os

# --- 設定 ---
# 解析対象の銘柄リスト
TICKERS = ["1605.T", "464A.T", "186A.T", "6629.T", "9412.T", "5724.T", "5857.T", "7014.T"]
INTERVAL = "1d"

def download_stock_data(tickers):
    """
    yfinanceを使用して株価データをダウンロードし、
    直近10ヶ月分の始値・高値・安値・終値をCSVとして保存する。
    """
    # 保存用フォルダの作成
    os.makedirs("data", exist_ok=True)
    
    print(f"--- データ収集開始 (直近10ヶ月分 / 始値・高値・安値・終値) ---")
    
    for ticker in tickers:
        try:
            # print(f"取得中: {ticker}...")
            # 余裕を持って1年分（1y）の履歴データを取得[cite: 3]
            stock = yf.Ticker(ticker)
            df = stock.history(period="1y", interval=INTERVAL)
            
            if df.empty:
                print(f"× {ticker}: データが見つかりません。")
                continue
            
            # 【新規追加】直近8ヶ月分のみに絞り込む
            latest_date = df.index.max() # データ内の最新日付を取得
            start_date = latest_date - pd.DateOffset(months=10) # 10ヶ月前の日付を算出
            df = df[df.index >= start_date] # 8ヶ月前以降のデータのみ抽出
            
            # 必要な4本値（Open, High, Low, Close）に絞り込む
            df_selected = df[['Open', 'High', 'Low', 'Close']]
            
            # CSV形式で保存
            file_path = f"data/{ticker}.csv"
            df_selected.to_csv(file_path)
            print(f"◎ {ticker}: 保存完了 (データ件数: {len(df_selected)}日分) -> {file_path}")
            
        except Exception as e:
            print(f"! {ticker} 取得エラー: {e}")

if __name__ == "__main__":
    download_stock_data(TICKERS)