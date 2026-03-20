from flask import Flask, request, jsonify
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
import os
from dotenv import load_dotenv
import google.generativeai as genai
from threading import Thread

# 用於防止重複處理訊息
processed_ids = set()

# 載入環境變數 (本地測試用)
load_dotenv()

# 設定 Google Gemini
google_api_key = os.getenv('GOOGLE_API_KEY')
genai.configure(api_key=google_api_key)
model = genai.GenerativeModel('gemini-1.5-flash') # 修正了引號錯誤

# 初始化 Slack Web Client
slack_token = os.getenv('SLACK_BOT_TOKEN')
client = WebClient(token=slack_token)

# 機器人的 User ID
BOT_USER_ID = os.getenv('BOT_USER_ID')

app = Flask(__name__)

def handle_event_async(data):
    thread = Thread(target=handle_event, args=(data,), daemon=True)
    thread.start()

def handle_event(data):
    event = data["event"]
    
    # 避免重複處理
    msg_id = event.get("client_msg_id") or event.get("event_ts")
    if msg_id in processed_ids:
        return
    
    # 忽略機器人自己的訊息
    if event.get("user") == BOT_USER_ID:
        return

    # 處理私訊 (Direct Message) 或 被標記 (App Mention)
    is_dm = event.get("channel_type") == "im" or event.get("channel", "").startswith("D")
    is_mention = event.get("type") == "app_mention"

    if (is_dm or is_mention) and "text" in event:
        try:
            print(f"處理訊息中: {event['text']}")
            
            # 呼叫 Gemini
            gemini_response = model.generate_content(event["text"])
            text_out = gemini_response.text.replace("**", "*") # Slack 不支援雙星號粗體
            
            # 回傳訊息給 Slack
            client.chat_postMessage(
                channel=event["channel"],
                text=text_out,
                mrkdwn=True
            )
            processed_ids.add(msg_id)
            
        except Exception as e:
            print(f"錯誤: {str(e)}")

@app.route("/slack/events", methods=["POST"])
def slack_events():
    data = request.json
    
    # 處理 Slack 的挑戰驗證 (Challenge)
    if "challenge" in data:
        return jsonify({"challenge": data["challenge"]})
    
    # 處理實際事件
    if "event" in data:
        handle_event_async(data)
    
    return "", 200

# 測試用首頁
@app.route("/", methods=["GET"])
def index():
    return "Gemini Slack Bot is Running!"

if __name__ == "__main__":
    # 修正後的啟動設定
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
