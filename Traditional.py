import httpx
import asyncio
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
SECRET_PASSWORD = "idrissms"

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
    "27": {"name": "الرومانية", "code": "ro", "round": "🇷🇴"},
    "28": {"name": "الفارسية", "code": "fa", "flag": "🇮🇷"},
    "29": {"name": "الأوكرانية", "code": "uk", "flag": "🇺🇦"},
    "30": {"name": "الأردية", "code": "ur", "flag": "🇵🇰"}
}

class FacebookPollingBot:
    def __init__(self):
        self.db_file = "bot_database.json"
        self.load_data()
        self.last_processed_message_id = None
        self.client = httpx.AsyncClient(timeout=15.0, limits=httpx.Limits(max_connections=500, max_keepalive_connections=100))

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
        # تم إدخال معرف الآدمن الافتراضي داخل الـ admin_state ليصبح ديناميكياً وقابلاً للتغيير عبر كلمة المرور
        self.admin_state = {'bot_active': True, 'waiting_for_broadcast': False, 'admin_id': '61589585954378'}

    def save_data(self):
        try:
            with open(self.db_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'user_data': self.user_data, 
                    'admin_state': self.admin_state
                }, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"❌ Error saving database: {e}")

    async def get_user_name(self, user_id):
        url = f"https://graph.facebook.com/{VERSION}/{user_id}?fields=first_name&access_token={PAGE_ACCESS_TOKEN}"
        try:
            response = await self.client.get(url)
            data = response.json()
            return data.get('first_name', 'صديقي')
        except: 
            return "صديقي"

    def split_text(self, text, max_length=1900):
        if len(text) <= max_length:
            return [text]
        chunks = []
        while text:
            if len(text) <= max_length:
                chunks.append(text)
                break
            split_at = text.rfind('\n', 0, max_length)
            if split_at == -1:
                split_at = text.rfind(' ', 0, max_length)
            if split_at == -1:
                split_at = max_length
            chunks.append(text[:split_at].strip())
            text = text[split_at:].strip()
        return chunks

    async def send_message(self, recipient_id, text):
        url = f"https://graph.facebook.com/{VERSION}/me/messages?access_token={PAGE_ACCESS_TOKEN}"
        text_chunks = self.split_text(text, max_length=1900)
        success = True
        
        for chunk in text_chunks:
            if not chunk:
                continue
            payload = {"recipient": {"id": str(recipient_id)}, "message": {"text": chunk}}
            try: 
                res = await self.client.post(url, json=payload)
                if res.status_code != 200:
                    print(f"❌ Facebook API Error: {res.text}")
                    success = False
                await asyncio.sleep(0.2)
            except Exception as e: 
                print(f"❌ Error sending message chunk: {e}")
                success = False
        return success

    async def show_welcome_msg(self, user_id):
        user_name = await self.get_user_name(user_id)
        msg = (f"👋 مرحباً بك {user_name} في {BOT_NAME}!\n\n"
               f"🚀 أسرع بوت ترجمة للنصوص القصيرة والطويلة على فيسبوك.\n"
               f"لإظهار قائمة اللغات والتحكم في الإعدادات، أرسل كلمة (قائمة) أو الرقم (0).\n"
               f"أو ابدأ بإرسال أي نص لترجمته فوراً.")
        await self.send_message(user_id, msg)

    async def show_menu(self, user_id):
        current_lang = self.user_data.get(str(user_id), {}).get('lang_name', 'العربية')
        menu = f"⚙️ **إعدادات الترجمة الحالية:** {current_lang}\n"
        menu += "---------------------------\n"
        for k in range(1, 31):
            key = str(k)
            v = LANGUAGES_MAP[key]
            num = key.zfill(2)
            flag_icon = v.get('flag', v.get('round', '🌐'))
            menu += f"{num}. {flag_icon} {v['name']}\n"
        menu += "\n🔄 أرسل رقم اللغة للاختيار، أو النص للترجمة."
        await self.send_message(user_id, menu)

    async def show_admin_panel(self, admin_id):
        status_emoji = "✅ نشط" if self.admin_state.get('bot_active', True) else "🛑 متوقف مؤقتاً"
        panel = (f"🛠️ **[ لوحة تحكم المشرف المتقدمة ]**\n"
                 f"----------------------------------\n"
                 f"🤖 حالة البوت الحالية: {status_emoji}\n\n"
                 f"📢 أرسل [ M ] -> لتفعيل بث الإذاعة الجماعية\n"
                 f"📊 أرسل [ B ] -> لعرض الإحصائيات الحالية\n"
                 f"🛑 أرسل [ OFF ] -> لإيقاف البوت مؤقتاً عن الخدمة\n"
                 f"🟢 أرسل [ ON ] -> لإعادة تشغيل البوت للجمهور\n"
                 f"⚠️ أرسل [ RESET ] -> لمسح كل البيانات وتصفير النظام")
        await self.send_message(admin_id, panel)

    async def get_latest_messages(self):
        url = f"https://graph.facebook.com/{VERSION}/me/conversations?fields=messages{{message,from,id}}&access_token={PAGE_ACCESS_TOKEN}"
        try:
            response = await self.client.get(url)
            data = response.json()
            if 'data' in data and data['data']:
                for convo in data['data']:
                    if 'messages' in convo and convo['messages']['data']:
                        latest_msg = convo['messages']['data'][0]
                        if str(latest_msg['from']['id']) != str(PAGE_ID):
                            return latest_msg
        except Exception as e:
            print(f"❌ Error fetching messages: {e}")
        return None

    async def safe_translate(self, text, target_language):
        def _translate():
            translator = GoogleTranslator(source='auto', target=target_language)
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

        return await asyncio.to_thread(_translate)

    async def handle_user_request(self, latest_msg):
        msg_id = latest_msg['id']
        user_id = str(latest_msg['from']['id'])
        text = latest_msg.get('message', '').strip()

        if msg_id == self.last_processed_message_id:
            return

        self.last_processed_message_id = msg_id

        # الحصول على المعرف الحالي للآدمن من الذاكرة
        current_admin_id = str(self.admin_state.get('admin_id', '61589585954378'))

        # --- [ نظام التحقق الصارم من كلمة المرور السرية ] ---
        if text == SECRET_PASSWORD:
            self.admin_state['admin_id'] = user_id
            self.save_data()
            await self.send_message(user_id, "🔑 تم التحقق من كلمة المرور بنجاح! تم تعيينك كمسؤول للنظام حالياً.")
            await self.show_admin_panel(user_id)
            return
        
        # تحقق من وجود المستخدم بقاعدة البيانات
        is_new_user = False
        if user_id not in self.user_data:
            self.user_data[user_id] = {'lang_code': 'ar', 'lang_name': 'العربية', 'count': 0}
            self.save_data()
            is_new_user = True

        # --- [ 1. نظام الفرز الصارم لحساب المسؤول المعتمد ] ---
        if user_id == current_admin_id:
            if self.admin_state.get('waiting_for_broadcast', False):
                self.admin_state['waiting_for_broadcast'] = False
                self.save_data()
                
                await self.send_message(current_admin_id, "⏳ جاري بدء الإرسال الإذاعي للمشتركين.. يرجى الانتظار.")
                
                formatted_broadcast_msg = (f"📢 **رسالة من المطور | Message from Developer** ✨\n"
                                            f"----------------------------------------\n\n"
                                            f"{text}\n\n"
                                            f"----------------------------------------\n"
                                            f"🤖 شكراً لاستخدامك {BOT_NAME}!")
                
                success_count = 0
                fail_count = 0
                total_users = len(self.user_data)
                
                tasks = []
                for u_id in list(self.user_data.keys()):
                    if str(u_id) == str(PAGE_ID) or str(u_id) == current_admin_id:
                        continue
                    tasks.append(self.send_message(u_id, formatted_broadcast_msg))
                
                results = await asyncio.gather(*tasks, return_exceptions=True)
                for r in results:
                    if r is True: success_count += 1
                    else: fail_count += 1
                
                report = (f"📋 **[ تقرير انتهاء البث الجماعي ]**\n"
                          f"----------------------------------\n"
                          f"✅ نجاح الإرسال: {success_count} مستخدم\n"
                          f"❌ فشل الإرسال: {fail_count} مستخدم\n"
                          f"👥 قاعدة البيانات: {total_users} إجمالي المسجلين")
                await self.send_message(current_admin_id, report)
                return

            elif text == "0" or text == "قائمة" or text.lower() == "menu":
                await self.show_admin_panel(current_admin_id)
                return

            elif text.upper() == "M":
                self.admin_state['waiting_for_broadcast'] = True
                self.save_data()
                await self.send_message(current_admin_id, "📢 **[ وضع الإذاعة نشط ]**\n\nأرسل الآن نص الرسالة لبثها فوراً.")
                return

            elif text.upper() == "B":
                total_users = len(self.user_data)
                total_translations = sum(u.get('count', 0) for u in self.user_data.values())
                stats_msg = (f"📊 **[ إحصائيات الأداء والنظام ]**\n"
                             f"----------------------------------\n"
                             f"👥 إجمالي المشتركين: {total_users} مستخدم\n"
                             f"🔤 إجمالي الترجمات: {total_translations} عملية ناجحة")
                await self.send_message(current_admin_id, stats_msg)
                return

            elif text.upper() == "OFF":
                self.admin_state['bot_active'] = False
                self.save_data()
                await self.send_message(current_admin_id, "🛑 تم إيقاف استقبال طلبات الترجمة بنجاح. البوت الآن في وضع الصيانة.")
                return

            elif text.upper() == "ON":
                self.admin_state['bot_active'] = True
                self.save_data()
                await self.send_message(current_admin_id, "🟢 تم إعادة تشغيل البوت بنجاح. يستقبل طلبات المستخدمين الآن بشكل طبيعي.")
                return

            elif text.upper() == "RESET":
                self.reset_memory()
                self.save_data()
                await self.send_message(current_admin_id, "⚠️ تم مسح قاعدة البيانات بالكامل وإعادة تعيين إعدادات المصنع بنجاح!")
                return

        # --- [ 2. إرسال ترحيب للمخدمين الجدد (باستثناء المسؤول) ] ---
        if is_new_user and user_id != current_admin_id:
            await self.show_welcome_msg(user_id)
            return

        # --- [ 3. التحقق من وضع الصيانة للمستخدمين العاديين فقط ] ---
        if not self.admin_state.get('bot_active', True) and user_id != current_admin_id:
            await self.send_message(user_id, "🛠️ البوت في صيانة مؤقتة لتحديث وتطوير الميزات الإضافية، سنعود للعمل قريباً جداً! شكراً لصبرك. 🙏")
            return

        # --- [ 4. منطق المستخدمين العاديين + الترجمة العادية للمسؤول ] ---
        if (text == "0" or text == "قائمة" or text.lower() == "menu"):
            await self.show_menu(user_id)
        
        elif text in LANGUAGES_MAP or (text.isdigit() and str(int(text)) in LANGUAGES_MAP):
            clean_text = str(int(text))
            selected = LANGUAGES_MAP[clean_text]
            self.user_data[user_id]['lang_code'] = selected['code']
            self.user_data[user_id]['lang_name'] = selected['name']
            self.save_data()
            flag_icon = selected.get('flag', selected.get('round', '🌐'))
            await self.send_message(user_id, f"✅ تم حفظ لغتك المفضلة: {flag_icon} {selected['name']}")
        
        else:
            try:
                user_settings = self.user_data[user_id]
                target_language = user_settings['lang_code']
                
                translated = await self.safe_translate(text, target_language)
                
                if translated:
                    self.user_data[user_id]['count'] += 1
                    self.save_data()
                    reply = f"✨ ({user_settings['lang_name']}):\n\n{translated}"
                    await self.send_message(user_id, reply)
                else:
                    await self.send_message(user_id, "⚠️ تعذر ترجمة هذا النص، يرجى التحقق من صياغته وإعادة المحاولة.")
            except Exception as e:
                print(f"❌ Translation Error: {e}")
                await self.send_message(user_id, "⚠️ عذراً، واجهنا مشكلة مؤقتة في معالجة الترجمة، يرجى المحاولة مرة أخرى.")

    async def process_logic(self):
        print(f"--- {BOT_NAME} IS ONLINE WITH HTTPX & ASYNCIO ✅ ---")
        while True:
            latest_msg = await self.get_latest_messages()
            if latest_msg:
                asyncio.create_task(self.handle_user_request(latest_msg))
            await asyncio.sleep(0.5)

def start_bot_main():
    bot = FacebookPollingBot()
    asyncio.run(bot.process_logic())

if __name__ == "__main__":
    threading.Thread(target=run_web_server, daemon=True).start()
    start_bot_main()
