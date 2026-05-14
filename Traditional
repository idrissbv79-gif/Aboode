import httpx
import asyncio
import json
import os
from flask import Flask
from deep_translator import GoogleTranslator
from threading import Thread

# --- إعدادات خادم الويب (Render Web Service) ---
app = Flask(__name__)

@app.route('/')
def home():
    return "SwiftTranslate Pro is Running with Async Power! 🚀"

def run_web_server():
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, use_reloader=False)

# --- إعدادات البوت الأساسية ---
PAGE_ACCESS_TOKEN = 'EAAMJBZBOZCnhsBRT50G56dfJOtCoCsONXnds8d1dp6JcyFhb7Dp7ljOgPjfmsLDqZC6IFHjOyiDuyxvkMxpOzWcPYpLzq8vJOt2ZBquqcEPTGggmsnYwnEqHkotjTJlrh8pk19cbAVaj5ZAhIYWBdwjk0UI5b9ICOoAs7CD2zfezlPsZB7alH1ez9YMDXX6ZBaGjXrU3QZDZD'
PAGE_ID = '61589538039390' 
VERSION = 'v19.0'
BOT_NAME = "SwiftTranslate Pro"

LANGUAGES_MAP = {
    "1": {"name": "الإنجليزية", "code": "en", "flag": "🇺🇸"},
    "2": {"name": "الفرنسية", "code": "fr", "flag": "🇫🇷"},
    "3": {"name": "الألمانية", "code": "de", "flag": "🇩🇪"},
    "4": {"name": "الإسبانية", "code": "es", "flag": "🇪🇸"},
    "5": {"name": "التركية", "code": "tr", "flag": "🇹🇷"},
    "6": {"name": "الإيطالية", "code": "it", "flag": "🇮🇹"},
    "7": {"name": "الروسية", "code": "ru", "flag": "🇷🇺"},
    "8": {"name": "الصينية", "code": "zh-CN", "flag": "🇨🇳"},
    "9": {"name": "اليابانية", "code": "ja", "flag": "🇯🇵"},
    "10": {"name": "الكورية", "code": "ko", "flag": "🇰🇷"},
    "11": {"name": "البرتغالية", "code": "pt", "flag": "🇵🇹"},
    "12": {"name": "الهندية", "code": "hi", "flag": "🇮🇳"},
    "13": {"name": "الإندونيسية", "code": "id", "flag": "🇮🇩"},
    "14": {"name": "الهولندية", "code": "nl", "flag": "🇳🇱"},
    "15": {"name": "السويدية", "code": "sv", "flag": "🇸🇪"},
    "16": {"name": "البولندية", "code": "pl", "flag": "🇵🇱"},
    "17": {"name": "اليونانية", "code": "el", "flag": "🇬🇷"},
    "18": {"name": "التايلاندية", "code": "th", "flag": "🇹🇭"},
    "19": {"name": "الفيتنامية", "code": "vi", "flag": "🇻🇳"},
    "20": {"name": "العربية", "code": "ar", "flag": "🇩🇿"},
    "21": {"name": "النرويجية", "code": "no", "flag": "🇳🇴"},
    "22": {"name": "الدنماركية", "code": "da", "flag": "🇩🇰"},
    "23": {"name": "الفنلندية", "code": "fi", "flag": "🇫🇮"},
    "24": {"name": "المجرية", "code": "hu", "flag": "🇭🇺"},
    "25": {"name": "التشيكية", "code": "cs", "flag": "🇨🇿"},
    "26": {"name": "العبرية", "code": "he", "flag": "🇮🇱"},
    "27": {"name": "الرومانية", "code": "ro", "flag": "🇷🇴"},
    "28": {"name": "الفارسية", "code": "fa", "flag": "🇮🇷"},
    "29": {"name": "الأوكرانية", "code": "uk", "flag": "🇺🇦"},
    "30": {"name": "الأردية", "code": "ur", "flag": "🇵🇰"}
}

class FacebookPollingBot:
    def __init__(self):
        self.db_file = "bot_database.json"
        self.user_data = self.load_data()
        self.last_processed_message_id = None
        self.client = httpx.AsyncClient(timeout=20.0)

    def load_data(self):
        if os.path.exists(self.db_file):
            try:
                with open(self.db_file, 'r', encoding='utf-8') as f:
                    return json.load(f).get('user_data', {})
            except: return {}
        return {}

    def save_data(self):
        with open(self.db_file, 'w', encoding='utf-8') as f:
            json.dump({'user_data': self.user_data}, f, ensure_ascii=False, indent=4)

    # --- التعديل: وظيفة حذف البيانات كل ساعتين ---
    async def auto_clear_database(self):
        """تقوم بمسح جميع بيانات المستخدمين من الذاكرة والملف كل ساعتين"""
        while True:
            await asyncio.sleep(7200)  # الانتظار لمدة ساعتين (2 * 60 * 60)
            self.user_data = {}  # تفريغ البيانات في الذاكرة
            self.save_data()     # تحديث الملف ليصبح فارغاً
            print(f"🧹 [CLEANUP] تم حذف جميع بيانات المستخدمين بنجاح.")

    async def get_user_name(self, user_id):
        url = f"https://graph.facebook.com/{VERSION}/{user_id}?fields=first_name&access_token={PAGE_ACCESS_TOKEN}"
        try:
            response = await self.client.get(url)
            data = response.json()
            return data.get('first_name', 'صديقي')
        except: return "صديقي"

    async def send_message(self, recipient_id, text):
        url = f"https://graph.facebook.com/{VERSION}/me/messages?access_token={PAGE_ACCESS_TOKEN}"
        payload = {"recipient": {"id": recipient_id}, "message": {"text": text}}
        try:
            await self.client.post(url, json=payload)
        except Exception as e:
            print(f"❌ Error sending message: {e}")

    async def show_welcome_msg(self, user_id):
        user_name = await self.get_user_name(user_id)
        msg = (f"👋 مرحباً بك {user_name} في {BOT_NAME}!\n\n"
               f"🚀 أسرع بوت ترجمة على فيسبوك.\n"
               f"لإظهار قائمة اللغات وتغيير الإعدادات، أرسل الرقم (0).\n"
               f"أو ابدأ بإرسال أي نص لترجمته فوراً.")
        await self.send_message(user_id, msg)

    async def show_menu(self, user_id):
        current_lang = self.user_data.get(user_id, {}).get('lang_name', 'العربية')
        menu = f"⚙️ **إعدادات الترجمة الحالية:** {current_lang}\n"
        menu += "---------------------------\n"
        for k in range(1, 31):
            key = str(k)
            v = LANGUAGES_MAP[key]
            num = key.zfill(2)
            menu += f"{num}. {v['flag']} {v['name']}\n"
        menu += "\n🔄 أرسل رقم اللغة للاختيار، أو النص للترجمة."
        await self.send_message(user_id, menu)

    async def get_latest_messages(self):
        url = f"https://graph.facebook.com/{VERSION}/me/conversations?fields=messages{{message,from,id}}&access_token={PAGE_ACCESS_TOKEN}"
        try:
            response = await self.client.get(url)
            data = response.json()
            if 'data' in data and data['data']:
                latest_convo = data['data'][0]
                if 'messages' in latest_convo:
                    return latest_convo['messages']['data'][0]
        except: return None

    async def process_logic(self):
        print(f"--- {BOT_NAME} IS ONLINE ON RENDER ✅ ---")
        
        # --- تشغيل مهمة التنظيف التلقائي في الخلفية ---
        asyncio.create_task(self.auto_clear_database())
        
        while True:
            latest_msg = await self.get_latest_messages()
            if latest_msg:
                msg_id = latest_msg['id']
                user_id = str(latest_msg['from']['id'])
                text = latest_msg.get('message', '').strip()

                if user_id == PAGE_ID or msg_id == self.last_processed_message_id:
                    await asyncio.sleep(1)
                    continue

                self.last_processed_message_id = msg_id
                asyncio.create_task(self.handle_user_request(user_id, text))

            await asyncio.sleep(1)

    async def handle_user_request(self, user_id, text):
        if user_id not in self.user_data:
            self.user_data[user_id] = {'lang_code': 'ar', 'lang_name': 'العربية', 'count': 0}
            await self.show_welcome_msg(user_id)
            self.save_data()
            return

        if text == "0" or text.lower() == "menu":
            await self.show_menu(user_id)
        
        elif text in LANGUAGES_MAP or (text.isdigit() and str(int(text)) in LANGUAGES_MAP):
            clean_text = str(int(text))
            selected = LANGUAGES_MAP[clean_text]
            self.user_data[user_id].update({'lang_code': selected['code'], 'lang_name': selected['name']})
            self.save_data()
            await self.send_message(user_id, f"✅ تم الحفظ: {selected['flag']} {selected['name']}")
        
        else:
            try:
                loop = asyncio.get_event_loop()
                user_settings = self.user_data[user_id]
                translated = await loop.run_in_executor(None, 
                    lambda: GoogleTranslator(source='auto', target=user_settings['lang_code']).translate(text))
                
                self.user_data[user_id]['count'] += 1
                self.save_data()
                reply = f"✨ ({user_settings['lang_name']}):\n\n{translated}"
                await self.send_message(user_id, reply)
            except:
                await self.send_message(user_id, "⚠️ خطأ في الترجمة، حاول لاحقاً.")

if __name__ == "__main__":
    server_thread = Thread(target=run_web_server, daemon=True)
    server_thread.start()
    
    bot = FacebookPollingBot()
    try:
        asyncio.run(bot.process_logic())
    except KeyboardInterrupt:
        print("Stopping Bot...")
