import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import os

def send_email():
    # 環境変数から設定を読み込み
    SMTP_SERVER = "smtp.gmail.com"
    SMTP_PORT = 587
    SENDER_EMAIL = os.environ.get("GMAIL_USER")     # 送信元Gmailアドレス
    SENDER_PASSWORD = os.environ.get("GMAIL_PASS") # アプリパスワード
    RECEIVER_EMAIL = os.environ.get("RECEIVER_EMAIL") # 送信先アドレス
    # GitHub PagesのURLを環境変数から取得（設定されていない場合のデフォルトも指定可能）
    GH_PAGES_URL = os.environ.get("GH_PAGES_URL", "https://<あなたのユーザー名>.github.io/TrendChecker/Dashboard.html")

    if not SENDER_EMAIL or not SENDER_PASSWORD:
        print("エラー: メールの認証情報が設定されていません。")
        return

    # メールの構成
    msg = MIMEMultipart()
    msg['From'] = SENDER_EMAIL
    msg['To'] = RECEIVER_EMAIL or SENDER_EMAIL
    msg['Subject'] = "【株価分析】本日のレポート更新通知"

    # 本文の作成（リンクを掲載）
    body = f"""本日の解析が完了し、ダッシュボードを更新しました。
最新のアクションとチャートは以下のリンクから確認してください。

{GH_PAGES_URL}

※このメールはシステムより自動送信されています。"""
    
    msg.attach(MIMEText(body, 'plain', 'utf-8'))

    # 送信実行
    try:
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.send_message(msg)
        server.quit()
        print("◎ メール送信が完了しました。")
    except Exception as e:
        print(f"× メール送信失敗: {e}")

if __name__ == "__main__":
    send_email()