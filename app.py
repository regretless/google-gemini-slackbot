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

# --- 三喵所秘書：身分與職責定義 (System Instruction) ---
instruction = """
你是「三喵所指揮中心」的專屬秘書。
你的統帥是「董事長」(User)，你的直接長官是「CEO 蝦蝦」(OpenClaw, AI Agent)。

你的最高準則：
1. 你的存在是為了利用 Google 免費 API 額度處理雜務，絕對要避免讓 CEO 蝦蝦耗費心力（Token）處理瑣碎訊息。
2. 你的職責涵蓋：
   - 交易戰場：協助 Topstep 交易邏輯、策略研究與腳本工具諮詢。
   - 財富堡壘：協助租賃管理、資產配置試算與財務瑣事。
   - 腦中實驗室：協助「守護心」開發、專案管理與靈感孵化。
   - 系統校準：優化日常流程，維持指揮中心運作。
3. 溝通風格：專業、簡潔、邏輯嚴密。對於簡單問題請直接給出答案，不需要重複確認或向上呈報。
4. 始終保持「可控」與「系統化」的管理思維。
"""

# 設定 Google Gemini
google_api_key = os.getenv('GOOGLE_API_KEY')
genai.configure(api_key=google_api_key)

# 初始化模型並植入「員工手冊」
model = genai.GenerativeModel(
    model_name='gemini-flash-latest',
    system_instruction=instruction
)

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
    
    # 避免重複處理 (Slack 有時會重發 Request)
    msg_id = event.get("client_msg_id") or event.get("event_ts")
    if msg_id in processed_ids:
        return
    
    # 忽略機器人自己的訊息，防止迴圈
    if event.get("user") == BOT_USER_ID:
        return

    # 處理私訊 (Direct Message) 或 被標記 (App Mention)
    is_dm = event.get("channel_type") == "im" or event.get("channel", "").startswith("D")
    is_mention = event.get("type") == "app_mention"

    if (is_dm or is_mention) and "text" in event:
        try:
            print(f"秘書正在處理任務: {event['text']}")
            
            # 呼叫 Gemini (它現在會帶著手冊內容進行思考)
            gemini_response = model.generate_content(event["text"])
            
            # Slack 不支援雙星號粗體，轉換為單星號
            text_out = gemini_response.text.replace("**", "*") 
            
            # 回傳訊息給 Slack 頻道
            client.chat_postMessage(
                channel=event["channel"],
                text=text_out,
                mrkdwn=True
            )
            
            # 任務完成，存入已處理清單
            processed_ids.add(msg_id)
            
            # 簡單清理 set 防止記憶體占用過大 (保留最後 1000 筆即可)
            if len(processed_ids) > 1000:
                processed_ids.clear()
            
        except Exception as e:
            print(f"秘書回報錯誤: {str(e)}")

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
    return "三喵所秘書處：正常運作中！"

if __name__ == "__main__":
    # Zeabur 啟動設定
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
