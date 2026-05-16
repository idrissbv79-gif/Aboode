import requests
import time
import json
import os
import threading
from flask import Flask
from deep_translator import GoogleTranslator

# --- إعدادات خادم الويب (Render Web Service) ---
app = Flask(__name__)

@app.route('/')
def home():
    return "SwiftTranslate Pro is Running!"

def run_web_server():
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)

# --- إعدادات البوت الأساسية ---
PAGE_ACCESS_TOKEN = 'EAAMJBZBOZCnhsBRT50G56dfJOtCoCsONXnds8d1dp6JcyFhb7Dp7ljOgPjfmsLDqZC6IFHjOyiDuyxvkMxpOzWcPYpLzq8vJOt2ZBquqcEPTGggmsnYwnEqHkotjTJlrh8pk19cbAVaj5ZAhIYWBdwjk0UI5b9ICOoAs7CD2zfezlPsZB7alH1ez9YMDXX6ZBaGjXrU3QZDZD'
PAGE_ID = '61589538039390' 
VERSION = 'v19.0'
BOT_NAME = "SwiftTranslate Pro"

# معرف حساب الآدمن الخاص بك
ADMIN_ID = '61589585954378'

# اختصارات اللغات متوافقة 100% مع GoogleTranslator بدقة عالية
LANGUAGES_MAP = {
    "1": {"name": "الإنجليزية", "code": "en", "flag": "🇺🇸"},
    "2": {"name": "الفرنسية", "code": "fr", "flag": "🇫🇷"},
    "3": {"name": "الألمانية", "code": "de", "flag": "🇩🇪"},
    "4": {"name": "الإسبانية", "code": "es", "flag": "🇪🇸"},
    "5": {"name": "التركية", "code": "tr", "flag": "🇹🇷"},
    "6": {"name": "الإيطالية", "code": "it", "flag": "🇮🇹"},
    "7": {"name": "الروسية", "code": "ru", "flag": "🇷🇺"},
    "8": {"name": "الصينية", "code": "zh-cn", "flag": "🇨🇳"},
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
    "28": {"name": "الفارسية", "code": "fa", "flag": "🇮ران"},
    "29": {"name": "الأوكرانية", "code": "uk", "flag": "🇺🇦"},
    "30": {"name": "الأردية", "code": "ur", "flag": "🇵🇰"}
}

class FacebookPollingBot:
    def __init__(self):
        self.db_file = "bot_database.json"
        self.load_data()
        self.last_processed_message_id = None

    def load_data(self):
        if os.path.exists(self.db_file):
            try:
                with open(self.db_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.user_data = data.get('user_data', {})
                    self.admin_state = data.get('admin_state', {})
            except: 
                self.reset_memory()
        else:
            self.reset_memory()

    def reset_memory(self):
        self.user_data = {}
        self.admin_state = {'bot_active': True, 'waiting_for_broadcast': False}

    def save_data(self):
        try:
            with open(self.db_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'user_data': self.user_data, 
                    'admin_state': self.admin_state
                }, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"❌ Error saving database: {e}")

    def get_user_name(self, user_id):
        url = f"https://graph.facebook.com/{VERSION}/{user_id}?fields=first_name&access_token={PAGE_ACCESS_TOKEN}"
        try:
            response = requests.get(url).json()
            return response.get('first_name', 'صديقي')
        except: return "صديقي"

    def split_text(self, text, max_length=1900):
        """تقسيم النصوص الطويلة جداً إلى أجزاء لا تتعدى الـ 1900 حرف بشكل ذكي دون قطع الكلمات"""
        if len(text) <= max_length:
            return [text]
        
        chunks = []
        while text:
            if len(text) <= max_length:
                chunks.append(text)
                break
            
            # البحث عن أنسب مكان للقطع (مسافة أو سطر جديد) قبل الحد الأقصى
            split_at = text.rfind('\n', 0, max_length)
            if split_at == -1:
                split_at = text.rfind(' ', 0, max_length)
            if split_at == -1:
                split_at = max_length
                
            chunks.append(text[:split_at].strip())
            text = text[split_at:].strip()
        return chunks

    def send_message(self, recipient_id, text):
        """إرسال الرسائل مع دعم التقسيم التلقائي للنصوص الطويلة لحمايتها من سياسة فيسبوك"""
        url = f"https://graph.facebook.com/{VERSION}/me/messages?access_token={PAGE_ACCESS_TOKEN}"
        
        # تقسيم النص إذا تجاوز الحد المسموح
        text_chunks = self.split_text(text, max_length=1900)
        
        success = True
        for chunk in text_chunks:
            if not chunk:
                continue
            payload = {"recipient": {"id": recipient_id}, "message": {"text": chunk}}
            try: 
                res = requests.post(url, json=payload)
                if res.status_code != 200:
                    print(f"❌ Facebook API Error: {res.text}")
                    success = False
                time.sleep(0.5) # تأخير بسيط لمنع تداخل الرسائل المرسلة متتالية
            except Exception as e: 
                print(f"❌ Error sending message chunk: {e}")
                success = False
        return success

    def show_welcome_msg(self, user_id):
        user_name = self.get_user_name(user_id)
        msg = (f"👋 مرحباً بك {user_name} في {BOT_NAME}!\n\n"
               f"🚀 أسرع بوت ترجمة للنصوص القصيرة والطويلة على فيسبوك.\n"
               f"لإظهار قائمة اللغات والتحكم في الإعدادات، أرسل كلمة (قائمة) أو الرقم (0).\n"
               f"أو ابدأ بإرسال أي نص لترجمته فوراً.")
        self.send_message(user_id, msg)

    def show_menu(self, user_id):
        current_lang = self.user_data.get(user_id, {}).get('lang_name', 'العربية')
        menu = f"⚙️ **إعدادات الترجمة الحالية:** {current_lang}\n"
        menu += "---------------------------\n"
        
        for k in range(1, 31):
            key = str(k)
            v = LANGUAGES_MAP[key]
            num = key.zfill(2)
            menu += f"{num}. {v['flag']} {v['name']}\n"

        menu += "\n🔄 أرسل رقم اللغة للاختيار، أو النص للترجمة."
        self.send_message(user_id, menu)

    def show_admin_panel(self):
        status_emoji = "✅ نشط" if self.admin_state.get('bot_active', True) else "🛑 متوقف مؤقتاً"
        panel = (f"🛠️ **[ لوحة تحكم المشرف المتقدمة ]**\n"
                 f"----------------------------------\n"
                 f"🤖 حالة البوت الحالية: {status_emoji}\n\n"
                 f"📢 أرسل [ M ] -> لتفعيل بث الإذاعة الجماعية\n"
                 f"📊 أرسل [ B ] -> لعرض الإحصائيات الحالية\n"
                 f"🛑 أرسل [ OFF ] -> لإيقاف البوت مؤقتاً عن الخدمة\n"
                 f"🟢 أرسل [ ON ] -> لإعادة تشغيل البوت للجمهور\n"
                 f"⚠️ أرسل [ RESET ] -> لمسح كل البيانات وتصفير النظام")
        self.send_message(ADMIN_ID, panel)

    def get_latest_messages(self):
        url = f"https://graph.facebook.com/{VERSION}/me/conversations?fields=messages{{message,from,id}}&access_token={PAGE_ACCESS_TOKEN}"
        try:
            response = requests.get(url).json()
            if 'data' in response and response['data']:
                for convo in response['data']:
                    if 'messages' in convo and convo['messages']['data']:
                        latest_msg = convo['messages']['data'][0]
                        if str(latest_msg['from']['id']) != PAGE_ID:
                            return latest_msg
        except Exception as e:
            print(f"❌ Error fetching messages: {e}")
        return None

    def safe_translate(self, text, target_language):
        """دالة ترجمة احترافية تقوم بتقسيم النصوص الطويلة جداً لترجمتها بدقة عالية 100% دون أخطاء"""
        translator = GoogleTranslator(source='auto', target=target_language)
        
        # نقسم النص المدخل إلى أجزاء صغيرة (حوالي 1500 حرف) لضمان دقة محرك جوجل للترجمة
        input_chunks = self.split_text(text, max_length=1500)
        translated_chunks = []
        
        for chunk in input_chunks:
            if not chunk.strip():
                continue
            translated_part = translator.translate(chunk)
            if translated_part:
                translated_chunks.append(translated_part)
            else:
                return None
                
        return "\n".join(translated_chunks)

    def process_logic(self):
        print(f"--- {BOT_NAME} IS ONLINE ✅ ---")
        while True:
            latest_msg = self.get_latest_messages()
            if latest_msg:
                msg_id = latest_msg['id']
                user_id = str(latest_msg['from']['id'])
                text = latest_msg.get('message', '').strip()

                if msg_id == self.last_processed_message_id:
                    time.sleep(1.5)
                    continue

                self.last_processed_message_id = msg_id
                
                if user_id not in self.user_data:
                    self.user_data[user_id] = {'lang_code': 'ar', 'lang_name': 'العربية', 'count': 0}
                    self.show_welcome_msg(user_id)
                    self.save_data()
                    continue

                # --- [ 1. تحكم الآدمن الصارم وسيناريوهات الأوامر ] ---
                if user_id == ADMIN_ID:
                    if self.admin_state.get('waiting_for_broadcast', False):
                        self.admin_state['waiting_for_broadcast'] = False
                        self.save_data()
                        
                        self.send_message(ADMIN_ID, "⏳ جاري بدء الإرسال الإذاعي للمشتركين.. يرجى الانتظار.")
                        
                        formatted_broadcast_msg = (f"📢 **رسالة من المطور | Message from Developer** ✨\n"
                                                    f"----------------------------------------\n\n"
                                                    f"{text}\n\n"
                                                    f"----------------------------------------\n"
                                                    f"🤖 شكراً لاستخدامك {BOT_NAME}!")
                        
                        success_count = 0
                        fail_count = 0
                        total_users = len(self.user_data)
                        
                        for u_id in list(self.user_data.keys()):
                            if u_id == PAGE_ID or u_id == ADMIN_ID:
                                continue
                            
                            is_sent = self.send_message(u_id, formatted_broadcast_msg)
                            if is_sent:
                                success_count += 1
                            else:
                                fail_count += 1
                            time.sleep(0.3) 
                        
                        report = (f"📋 **[ تقرير انتهاء البث الجماعي ]**\n"
                                  f"----------------------------------\n"
                                  f"✅ نجاح الإرسال: {success_count} مستخدم\n"
                                  f"❌ فشل الإرسال: {fail_count} مستخدم\n"
                                  f"👥 قاعدة البيانات: {total_users} إجمالي المسجلين")
                        self.send_message(ADMIN_ID, report)
                        continue

                    elif text == "0" or text == "قائمة" or text.lower() == "menu":
                        self.show_admin_panel()
                        continue

                    elif text.upper() == "M":
                        self.admin_state['waiting_for_broadcast'] = True
                        self.save_data()
                        self.send_message(ADMIN_ID, "📢 **[ وضع الإذاعة نشط ]**\n\nأرسل الآن نص الرسالة لبثها فوراً.")
                        continue

                    elif text.upper() == "B":
                        total_users = len(self.user_data)
                        total_translations = sum(u.get('count', 0) for u in self.user_data.values())
                        stats_msg = (f"📊 **[ إحصائيات الأداء والنظام ]**\n"
                                     f"----------------------------------\n"
                                     f"👥 إجمالي المشتركين: {total_users} مستخدم\n"
                                     f"🔤 إجمالي الترجمات: {total_translations} عملية ناجحة")
                        self.send_message(ADMIN_ID, stats_msg)
                        continue

                    elif text.upper() == "OFF":
                        self.admin_state['bot_active'] = False
                        self.save_data()
                        self.send_message(ADMIN_ID, "🛑 تم إيقاف استقبال طلبات الترجمة بنجاح. البوت الآن في وضع الصيانة.")
                        continue

                    elif text.upper() == "ON":
                        self.admin_state['bot_active'] = True
                        self.save_data()
                        self.send_message(ADMIN_ID, "🟢 تم إعادة تشغيل البوت بنجاح. يستقبل طلبات المستخدمين الآن بشكل طبيعي.")
                        continue

                    elif text.upper() == "RESET":
                        self.reset_memory()
                        self.save_data()
                        self.send_message(ADMIN_ID, "⚠️ تم مسح قاعدة البيانات بالكامل وإعادة تعيين إعدادات المصنع بنجاح!")
                        continue

                # --- [ 2. التحقق من وضع الصيانة للمستخدِمين العاديين ] ---
                if not self.admin_state.get('bot_active', True) and user_id != ADMIN_ID:
                    self.send_message(user_id, "🛠️ البوت في صيانة مؤقتة لتحديث وتطوير الميزات الإضافية، سنعود للعمل قريباً جداً! شكراً لصبرك. 🙏")
                    time.sleep(1.5)
                    continue

                # --- [ 3. منطق المستخدمين العاديين + ترجمة نصوص الآدمن العادية ] ---
                if (text == "0" or text == "قائمة" or text.lower() == "menu") and user_id != ADMIN_ID:
                    self.show_menu(user_id)
                
                elif text in LANGUAGES_MAP or (text.isdigit() and str(int(text)) in LANGUAGES_MAP):
                    clean_text = str(int(text))
                    selected = LANGUAGES_MAP[clean_text]
                    self.user_data[user_id]['lang_code'] = selected['code']
                    self.user_data[user_id]['lang_name'] = selected['name']
                    self.save_data()
                    self.send_message(user_id, f"✅ تم حفظ لغتك المفضلة: {selected['flag']} {selected['name']}")
                
                else:
                    # آلية الترجمة المطورة وفائقة الدقة للنصوص الطويلة والقصيرة
                    try:
                        user_settings = self.user_data[user_id]
                        target_language = user_settings['lang_code']
                        
                        # استدعاء دالة الترجمة الآمنة للنصوص الطويلة جداً
                        translated = self.safe_translate(text, target_language)
                        
                        if translated:
                            self.user_data[user_id]['count'] += 1
                            self.save_data()
                            
                            reply = f"✨ ({user_settings['lang_name']}):\n\n{translated}"
                            self.send_message(user_id, reply)
                        else:
                            self.send_message(user_id, "⚠️ تعذر ترجمة هذا النص، يرجى التحقق من صياغته وإعادة المحاولة.")
                            
                    except Exception as e:
                        print(f"❌ Translation Error: {e}")
                        self.send_message(user_id, "⚠️ عذراً، واجهنا مشكلة مؤقتة في معالجة الترجمة، يرجى المحاولة مرة أخرى.")

            time.sleep(2)

if __name__ == "__main__":
    threading.Thread(target=run_web_server, daemon=True).start()
    bot = FacebookPollingBot()
    bot.process_logic()
