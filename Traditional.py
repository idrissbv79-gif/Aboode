import g4f
import time
import re
import requests
from flask import Flask, request

app = Flask(__name__)

# إعدادات إنستغرام
# USER_ID: 8352764359
INSTA_TOKEN = 'EAAUl1OesGpoBR3HkSfyp7gRADTGOQ2mZC5eBatqtgC6a7kv234v0T8qlo3GuQskq6XNxzyZBrZCNIRJYxZBkN3dHt15SQ34mwwf5lJvHNFqCgGLbKCXgo4FU4abV0wG8ZAaqdqphehF5liLbZCSOgnVTuZCjAk3dvXoAMTRmJcot2cxZAzTVb3aPPYMeC67wZCF8cx8QRZAxPwGBdJzL7OsQkh38nLgF67tpsOjUou6mBM5A9xLxwvwpaC0XwwftyRXsZCDHj37H9vGjAfSijGlmyuBhERY'
WEBHOOK_SECRET = 'idriss990'

# وظيفة التحقق من التوكن
def verify_token():
    url = f"https://graph.facebook.com/v20.0/me?fields=id,username&access_token={INSTA_TOKEN}"
    response = requests.get(url)
    if response.status_code == 200:
        print("✅ التوكن يعمل بنجاح:", response.json().get('username'))
        return True
    else:
        print("❌ التوكن غير صالح أو انتهت صلاحيته:", response.json())
        return False

# تخزين المحادثات
chat_history = {}
MAX_MESSAGES = 15
EXPIRATION_TIME = 2 * 60 * 60 

def clean_response(text):
    url_pattern = r'(https?://\S+|www\.\S+)'
    cleaned_text = re.sub(url_pattern, '', text)
    return cleaned_text.strip()

def send_insta_message(recipient_id, text):
    text = clean_response(text)
    if not text:
        return
    url = f"https://graph.facebook.com/v20.0/me/messages"
    params = {"access_token": INSTA_TOKEN}
    payload = {
        "recipient": {"id": recipient_id},
        "message": {"text": text}
    }
    requests.post(url, params=params, json=payload)

@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    if request.method == 'GET':
        if request.args.get('hub.verify_token') == WEBHOOK_SECRET:
            return request.args.get('hub.challenge')
        return "Invalid token"

    data = request.json
    if 'entry' in data:
        for entry in data['entry']:
            for messaging_event in entry.get('messaging', []):
                sender_id = messaging_event['sender']['id']
                message_text = messaging_event['message'].get('text', '')
                handle_insta_message(sender_id, message_text)
    return "OK", 200

def handle_insta_message(chat_id, text):
    current_time = time.time()
    if chat_id not in chat_history:
        chat_history[chat_id] = {"messages": [], "last_activity": current_time}
    
    if current_time - chat_history[chat_id]["last_activity"] > EXPIRATION_TIME:
        chat_history[chat_id]["messages"] = []
    
    chat_history[chat_id]["last_activity"] = current_time
    chat_history[chat_id]["messages"].append({"role": "user", "content": text})
    
    if len(chat_history[chat_id]["messages"]) > MAX_MESSAGES:
        chat_history[chat_id]["messages"] = chat_history[chat_id]["messages"][-MAX_MESSAGES:]

    system_instruction = "أنت مساعد ذكي. التزم بالاختصار الشديد في إجاباتك، قدم المعلومة المباشرة فقط بدون مقدمات. ممنوع نهائياً إرسال أي روابط URL." if "ابحث" in text else "أنت مساعد ذكي ومتحدث لبق. أجب على المستخدم بشكل طبيعي، وافٍ، وودي كأي مساعد ذكاء اصطناعي."
    
    messages_to_send = [{"role": "system", "content": system_instruction}] + chat_history[chat_id]["messages"]
    
    try:
        response = g4f.ChatCompletion.create(model="gpt-4o", messages=messages_to_send, stream=False)
        if response:
            chat_history[chat_id]["messages"].append({"role": "assistant", "content": response})
            send_insta_message(chat_id, response)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    # بدء التحقق قبل تشغيل السيرفر
    if verify_token():
        app.run(port=5000)
    else:
        print("توقف البرنامج بسبب فشل التحقق من التوكن.")
