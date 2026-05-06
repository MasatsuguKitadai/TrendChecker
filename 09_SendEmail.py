import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import os

def send_email():
    # 環境変数から設定を読み込み
    SMTP_SERVER = "smtp.gmail.com"
    SMTP_PORT = 587
    SENDER_EMAIL = os.environ.get("GMAIL_USER")     # 送信元Gmailアドレス
    SENDER_PASSWORD = os.environ.get("GMAIL_PASS") # アプリパスワード
    RECEIVER_EMAIL = os.environ.get("RECEIVER_EMAIL") # 送信先アドレス

    if not SENDER_EMAIL or not SENDER_PASSWORD:
        print("エラー: メールの認証情報が設定されていません。")
        return

    # メールの構成
    msg = MIMEMultipart()
    msg['From'] = SENDER_EMAIL
    msg['To'] = RECEIVER_EMAIL or SENDER_EMAIL
    msg['Subject'] = "【株価分析】本日のレポートとアクション"

    body = "本日の解析が完了しました。詳細は添付の Dashboard.html または GitHub Pages を確認してください。"
    msg.attach(MIMEText(body, 'plain', 'utf-8'))

    # Dashboard.html を添付
    filename = "Dashboard.html"
    if os.path.exists(filename):
        with open(filename, "rb") as attachment:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(attachment.read())
            encoders.encode_base64(part)
            part.add_header("Content-Disposition", f"attachment; filename= {filename}")
            msg.attach(part)
    else:
        print(f"警告: {filename} が見つかりません。")

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