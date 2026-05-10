import requests
import os

def send_line_notification():
    # 環境変数から設定を読み込み
    LINE_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
    USER_ID = os.environ.get("LINE_USER_ID")
    
    # GitHub PagesのURL
    GH_PAGES_URL = os.environ.get("GH_PAGES_URL", "https://<USER>.github.io/TrendChecker/Dashboard.html")

    if not LINE_TOKEN or not USER_ID:
        print("エラー: LINEの認証情報が設定されていません。")
        return

    # メッセージの構成
    message_text = f"""【株価分析】レポート更新
本日分の解析が完了しました。

ダッシュボードはこちら:
{GH_PAGES_URL}"""

    url = "https://api.line.me/v2/bot/message/push"
    # ★ 修正箇所：波括弧を1つにする
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LINE_TOKEN}"
    }
    # ★ 修正箇所：波括弧を1つにする
    payload = {
        "to": USER_ID,
        "messages": [
            {
                "type": "text",
                "text": message_text
            }
        ]
    }

    # 送信実行
    try:
        response = requests.post(url, headers=headers, json=payload)
        if response.status_code == 200:
            print("◎ LINE通知が完了しました。")
        else:
            print(f"× LINE通知失敗: {response.status_code} {response.text}")
    except Exception as e:
        print(f"× 通信エラー: {e}")

if __name__ == "__main__":
    send_line_notification()