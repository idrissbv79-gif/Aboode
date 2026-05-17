import httpx
import asyncio
import json
import os
import threading
from flask import Flask
from deep_translator import GoogleTranslator
from langdetect import detect

# ─── إعداد خادم الويب ───────────────────────────────────────────────────────
app = Flask(__name__)

@app.route('/')
def home():
    return "SwiftTranslate Pro v2 is Running! ✅"

def run_web_server():
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)

# ─── إعدادات البوت ──────────────────────────────────────────────────────────
PAGE_ACCESS_TOKEN = 'EAAMJBZBOZCnhsBRT50G56dfJOtCoCsONXnds8d1dp6JcyFhb7Dp7ljOgPjfmsLDqZC6IFHjOyiDuyxvkMxpOzWcPYpLzq8vJOt2ZBquqcEPTGggmsnYwnEqHkotjTJlrh8pk19cbAVaj5ZAhIYWBdwjk0UI5b9ICOoAs7CD2zfezlPsZB7alH1ez9YMDXX6ZBaGjXrU3QZDZD'
PAGE_ID    = '61589538039390'
VERSION    = 'v19.0'
BOT_NAME   = "SwiftTranslate Pro"
ADMIN_PASS = "idriss78"       # كلمة مرور لوحة التحكم
ADMIN_ID   = '61589585954378' # معرف المسؤول الثابت

LANGUAGES_MAP = {
    "1":  {"name": "الإنجليزية",   "code": "en",    "flag": "🇺🇸"},
    "2":  {"name": "الفرنسية",     "code": "fr",    "flag": "🇫🇷"},
    "3":  {"name": "الألمانية",    "code": "de",    "flag": "🇩🇪"},
    "4":  {"name": "الإسبانية",   "code": "es",    "flag": "🇪🇸"},
    "5":  {"name": "التركية",      "code": "tr",    "flag": "🇹🇷"},
    "6":  {"name": "الإيطالية",   "code": "it",    "flag": "🇮🇹"},
    "7":  {"name": "الروسية",      "code": "ru",    "flag": "🇷🇺"},
    "8":  {"name": "الصينية",      "code": "zh-CN", "flag": "🇨🇳"},
    "9":  {"name": "اليابانية",   "code": "ja",    "flag": "🇯🇵"},
    "10": {"name": "الكورية",      "code": "ko",    "flag": "🇰🇷"},
    "11": {"name": "البرتغالية",  "code": "pt",    "flag": "🇵🇹"},
    "12": {"name": "الهندية",      "code": "hi",    "flag": "🇮🇳"},
    "13": {"name": "الإندونيسية", "code": "id",    "flag": "🇮🇩"},
    "14": {"name": "الهولندية",   "code": "nl",    "flag": "🇳🇱"},
    "15": {"name": "السويدية",    "code": "sv",    "flag": "🇸🇪"},
    "16": {"name": "البولندية",   "code": "pl",    "flag": "🇵🇱"},
    "17": {"name": "اليونانية",   "code": "el",    "flag": "🇬🇷"},
    "18": {"name": "التايلاندية", "code": "th",    "flag": "🇹🇭"},
    "19": {"name": "الفيتنامية",  "code": "vi",    "flag": "🇻🇳"},
    "20": {"name": "العربية",      "code": "ar",    "flag": "🇩🇿"},
    "21": {"name": "النرويجية",   "code": "no",    "flag": "🇳🇴"},
    "22": {"name": "الدنماركية",  "code": "da",    "flag": "🇩🇰"},
    "23": {"name": "الفنلندية",   "code": "fi",    "flag": "🇫🇮"},
    "24": {"name": "المجرية",      "code": "hu",    "flag": "🇭🇺"},
    "25": {"name": "التشيكية",    "code": "cs",    "flag": "🇨🇿"},
    "26": {"name": "العبرية",      "code": "he",    "flag": "🇮🇱"},
    "27": {"name": "الرومانية",   "code": "ro",    "flag": "🇷🇴"},
    "28": {"name": "الفارسية",    "code": "fa",    "flag": "🇮🇷"},
    "29": {"name": "الأوكرانية",  "code": "uk",    "flag": "🇺🇦"},
    "30": {"name": "الأردية",      "code": "ur",    "flag": "🇵🇰"},
}

# رسم قائمة اللغات (يُستدعى مرة واحدة)
_LANG_MENU_BODY = ""
for _k in range(1, 31):
    _v = LANGUAGES_MAP[str(_k)]
    _LANG_MENU_BODY += f" [{str(_k).zfill(2)}] {_v['flag']} {_v['name']}\n"

# ─── كلاس البوت الرئيسي ─────────────────────────────────────────────────────
class SwiftTranslateBot:

    DB_FILE = "bot_database.json"

    def __init__(self):
        self.processed_messages: dict = {}
        self.client = httpx.AsyncClient(
            timeout=20.0,
            limits=httpx.Limits(max_connections=200, max_keepalive_connections=50)
        )
        self.load_data()

    # ── قاعدة البيانات ───────────────────────────────────────────────────────
    def load_data(self):
        if os.path.exists(self.DB_FILE):
            try:
                with open(self.DB_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self.users: dict  = data.get('users', {})
                self.admins: dict = data.get('admins', {})  # {uid: state}
                return
            except Exception:
                pass
        self.users:  dict = {}
        self.admins: dict = {}

    def save_data(self):
        try:
            with open(self.DB_FILE, 'w', encoding='utf-8') as f:
                json.dump({'users': self.users, 'admins': self.admins},
                          f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"❌ DB save error: {e}")

    def get_admin(self, uid: str) -> dict:
        if uid not in self.admins:
            self.admins[uid] = {
                'in_panel': False,
                'waiting_broadcast': False,
                'waiting_target_lang': False,
            }
        return self.admins[uid]

    # ── مساعدات الشبكة ───────────────────────────────────────────────────────
    async def get_user_name(self, uid: str) -> str:
        url = (f"https://graph.facebook.com/{VERSION}/{uid}"
               f"?fields=first_name&access_token={PAGE_ACCESS_TOKEN}")
        try:
            r = await self.client.get(url)
            return r.json().get('first_name', 'صديقي')
        except Exception:
            return "صديقي"

    def _split(self, text: str, max_len: int = 1900) -> list:
        if len(text) <= max_len:
            return [text]
        chunks, rest = [], text
        while rest:
            if len(rest) <= max_len:
                chunks.append(rest); break
            cut = rest.rfind('\n', 0, max_len)
            if cut == -1: cut = rest.rfind(' ', 0, max_len)
            if cut == -1: cut = max_len
            chunks.append(rest[:cut].strip())
            rest = rest[cut:].strip()
        return chunks

    async def send(self, uid: str, text: str) -> bool:
        url = (f"https://graph.facebook.com/{VERSION}"
               f"/me/messages?access_token={PAGE_ACCESS_TOKEN}")
        ok = True
        for chunk in self._split(text):
            if not chunk: continue
            try:
                r = await self.client.post(
                    url, json={"recipient": {"id": uid}, "message": {"text": chunk}})
                if r.status_code != 200:
                    print(f"❌ API {uid}: {r.text}"); ok = False
            except Exception as e:
                print(f"❌ send {uid}: {e}"); ok = False
            await asyncio.sleep(0.15)
        return ok

    # ── الترجمة ──────────────────────────────────────────────────────────────
    async def detect_lang(self, text: str) -> str:
        """يكتشف لغة النص تلقائياً."""
        def _detect():
            try:
                return detect(text)
            except Exception:
                return "auto"
        return await asyncio.to_thread(_detect)

    async def translate(self, text: str, source: str, target: str) -> str | None:
        """يترجم النص مع دعم الأجزاء الكبيرة وإعادة المحاولة."""
        def _do():
            tr = GoogleTranslator(source=source, target=target)
            parts = self._split(text, max_len=4500)
            result = []
            for p in parts:
                if not p.strip(): continue
                out = tr.translate(p)
                if not out: return None
                result.append(out)
            return "\n".join(result)
        for attempt in range(3):
            try:
                out = await asyncio.to_thread(_do)
                if out: return out
            except Exception as e:
                if attempt == 2: print(f"❌ translate error: {e}")
                await asyncio.sleep(0.5)
        return None

    # ── الرسائل الجاهزة ──────────────────────────────────────────────────────
    async def send_welcome(self, uid: str):
        name = await self.get_user_name(uid)
        await self.send(uid,
            f"👋 أهلاً بك {name} في {BOT_NAME} v2!\n\n"
            "🌐 أرسل أي نص وسيُترجم فوراً للغتك المختارة.\n"
            "🔍 يتعرف البوت تلقائياً على لغة النص ويترجمها.\n"
            "🔄 يدعم الترجمة العكسية والترجمة بين أي لغتين.\n\n"
            "📋 الأوامر المتاحة:\n"
            "  • [0] أو (قائمة) — اختيار لغة الترجمة\n"
            "  • [عكس]         — عكس اتجاه الترجمة\n"
            "  • [لغتي]        — معرفة إعداداتك الحالية\n"
            "  • [مساعدة]      — عرض هذه الرسالة\n\n"
            "⚡ ابدأ الآن بإرسال أي نص!")

    async def send_menu(self, uid: str):
        u = self.users[uid]
        src_name = u.get('src_lang_name', 'تلقائي')
        dst_name = u.get('lang_name', 'العربية')
        header = (f"⚙️ إعدادات الترجمة\n"
                  f"{'─'*34}\n"
                  f"📤 من : {src_name}\n"
                  f"📥 إلى: {dst_name}\n"
                  f"{'─'*34}\n\n"
                  f"{_LANG_MENU_BODY}\n"
                  "💡 أرسل رقم اللغة لتغيير لغة الوجهة.\n"
                  "💡 أرسل [من:رقم] لتغيير لغة المصدر، مثال: من:1\n"
                  "💡 أرسل [عكس] لعكس اتجاه الترجمة.")
        await self.send(uid, header)

    async def send_my_settings(self, uid: str):
        u = self.users[uid]
        src = u.get('src_lang_name', 'تلقائي (كشف تلقائي)')
        dst = u.get('lang_name', 'العربية')
        count = u.get('count', 0)
        await self.send(uid,
            f"📊 إعداداتك الحالية\n{'─'*28}\n"
            f"📤 لغة المصدر : {src}\n"
            f"📥 لغة الهدف  : {dst}\n"
            f"🔤 عدد ترجماتك: {count} عملية")

    # ── لوحة الإدارة ─────────────────────────────────────────────────────────
    async def send_admin_panel(self, uid: str):
        await self.send(uid,
            f"🛠️ لوحة تحكم {BOT_NAME}\n{'═'*32}\n\n"
            "1️⃣  إذاعة رسالة لجميع المستخدمين\n"
            "2️⃣  إحصائيات المستخدمين والترجمات\n"
            "3️⃣  قائمة أكثر 5 لغات استخداماً\n"
            "4️⃣  إعادة تشغيل الإحصائيات (تصفير العدادات)\n"
            "0️⃣  خروج من لوحة التحكم\n\n"
            "👉 أرسل رقم الخيار فقط.")

    async def handle_admin_panel(self, uid: str, text: str):
        st = self.get_admin(uid)

        # انتظار نص الإذاعة
        if st.get('waiting_broadcast'):
            if text == "0":
                st['waiting_broadcast'] = False
                self.save_data()
                await self.send(uid, "❌ تم إلغاء الإذاعة.")
                return
            st['waiting_broadcast'] = False
            self.save_data()
            broadcast_text = (f"📢 رسالة من إدارة {BOT_NAME}\n{'─'*30}\n\n"
                              f"{text}\n\n{'─'*30}\n🤖 {BOT_NAME}")
            await self.send(uid, "⏳ جاري الإرسال الجماعي...")
            ok_c, fail_c = 0, 0
            for u_id in list(self.users.keys()):
                if u_id == str(PAGE_ID): continue
                if await self.send(str(u_id), broadcast_text): ok_c += 1
                else: fail_c += 1
                await asyncio.sleep(0.3)
            await self.send(uid,
                f"✅ انتهت الإذاعة\n{'─'*24}\n"
                f"نجاح : {ok_c}\nفشل  : {fail_c}\nإجمالي: {len(self.users)}")
            return

        # اختيارات اللوحة
        if text == "1":
            st['waiting_broadcast'] = True
            self.save_data()
            await self.send(uid, "📝 أرسل الآن نص الإذاعة، أو [0] للإلغاء.")
        elif text == "2":
            total = len(self.users)
            total_tr = sum(u.get('count', 0) for u in self.users.values())
            await self.send(uid,
                f"📊 الإحصائيات\n{'─'*24}\n"
                f"👥 المستخدمون: {total}\n"
                f"🔤 إجمالي الترجمات: {total_tr}")
        elif text == "3":
            lang_counts: dict = {}
            for u in self.users.values():
                ln = u.get('lang_name', 'غير محدد')
                lang_counts[ln] = lang_counts.get(ln, 0) + u.get('count', 0)
            top5 = sorted(lang_counts.items(), key=lambda x: x[1], reverse=True)[:5]
            msg = "🏆 أكثر 5 لغات استخداماً\n" + "─"*24 + "\n"
            for i, (ln, cnt) in enumerate(top5, 1):
                msg += f"{i}. {ln}: {cnt} ترجمة\n"
            await self.send(uid, msg)
        elif text == "4":
            for u in self.users.values():
                u['count'] = 0
            self.save_data()
            await self.send(uid, "🔄 تم تصفير جميع العدادات بنجاح.")
        elif text == "0":
            st['in_panel'] = False
            self.save_data()
            await self.send(uid, "🚪 تم الخروج من لوحة التحكم. أنت الآن في وضع الترجمة.")
        else:
            await self.send_admin_panel(uid)

    # ── معالجة الرسائل ───────────────────────────────────────────────────────
    async def handle_message(self, msg: dict):
        uid    = str(msg['from']['id'])
        msg_id = msg['id']
        text   = msg.get('message', '').strip()
        upper  = text.upper()

        if self.processed_messages.get(uid) == msg_id: return
        self.processed_messages[uid] = msg_id
        if uid == str(PAGE_ID): return

        # تسجيل مستخدم جديد
        is_new = uid not in self.users
        if is_new:
            self.users[uid] = {
                'lang_code': 'ar', 'lang_name': 'العربية',
                'src_lang_code': 'auto', 'src_lang_name': 'تلقائي',
                'count': 0
            }
            self.save_data()
            await self.send_welcome(uid)
            return

        u = self.users[uid]

        # ─── فحص كلمة سر لوحة الإدارة (لأي مستخدم) ─────────────────────
        if text == ADMIN_PASS:
            st = self.get_admin(uid)
            st['in_panel'] = True
            self.save_data()
            await self.send_admin_panel(uid)
            return

        # ─── لوحة الإدارة ────────────────────────────────────────────────
        st = self.get_admin(uid)
        if st.get('in_panel') or st.get('waiting_broadcast'):
            await self.handle_admin_panel(uid, text)
            return

        # ─── أوامر المستخدم ───────────────────────────────────────────────
        if text in ("0", "قائمة") or upper == "MENU":
            await self.send_menu(uid)
            return

        if text in ("مساعدة", "help", "HELP"):
            await self.send_welcome(uid)
            return

        if text in ("لغتي", "اعداداتي"):
            await self.send_my_settings(uid)
            return

        # عكس اتجاه الترجمة
        if text in ("عكس", "REVERSE", "FLIP"):
            old_src_code = u.get('src_lang_code', 'auto')
            old_src_name = u.get('src_lang_name', 'تلقائي')
            old_dst_code = u.get('lang_code', 'ar')
            old_dst_name = u.get('lang_name', 'العربية')
            u['lang_code']      = old_src_code if old_src_code != 'auto' else 'ar'
            u['lang_name']      = old_src_name if old_src_name != 'تلقائي' else 'العربية'
            u['src_lang_code']  = old_dst_code
            u['src_lang_name']  = old_dst_name
            self.save_data()
            await self.send(uid,
                f"🔄 تم عكس الترجمة\n"
                f"📤 من: {u['src_lang_name']}\n"
                f"📥 إلى: {u['lang_name']}")
            return

        # تغيير لغة المصدر: من:رقم
        if text.startswith("من:") or text.startswith("من :"):
            num = text.split(":", 1)[1].strip()
            clean = str(int(num)) if num.isdigit() else num
            if clean in LANGUAGES_MAP:
                sel = LANGUAGES_MAP[clean]
                u['src_lang_code'] = sel['code']
                u['src_lang_name'] = sel['name']
                self.save_data()
                await self.send(uid, f"✅ لغة المصدر: {sel['flag']} {sel['name']}")
            elif num == "0":
                u['src_lang_code'] = 'auto'
                u['src_lang_name'] = 'تلقائي'
                self.save_data()
                await self.send(uid, "✅ لغة المصدر: تلقائي (كشف تلقائي)")
            else:
                await self.send(uid, "⚠️ رقم اللغة غير صحيح. أرسل [قائمة] لعرض الأرقام.")
            return

        # اختيار لغة الهدف بالرقم
        if text.isdigit():
            clean = str(int(text))
            if clean in LANGUAGES_MAP:
                sel = LANGUAGES_MAP[clean]
                u['lang_code'] = sel['code']
                u['lang_name'] = sel['name']
                self.save_data()
                await self.send(uid,
                    f"✅ لغة الترجمة: {sel['flag']} {sel['name']}\n"
                    "📝 أرسل أي نص الآن للترجمة.")
            else:
                await self.send(uid, "⚠️ الرقم خارج النطاق (1-30). أرسل [قائمة].")
            return

        # ─── الترجمة الرئيسية ─────────────────────────────────────────────
        if len(text) < 2:
            await self.send(uid, "⚠️ النص قصير جداً. أرسل جملة أو أكثر.")
            return

        src_code = u.get('src_lang_code', 'auto')
        dst_code = u.get('lang_code', 'ar')
        dst_name = u.get('lang_name', 'العربية')

        # كشف اللغة تلقائياً
        if src_code == 'auto':
            detected = await self.detect_lang(text)
        else:
            detected = src_code

        # تجنب ترجمة النص لنفس لغته
        if detected == dst_code:
            await self.send(uid,
                f"ℹ️ النص بالفعل بلغة الهدف ({dst_name}).\n"
                "غيّر اللغة أو استخدم [عكس].")
            return

        result = await self.translate(text, detected, dst_code)
        if result:
            u['count'] = u.get('count', 0) + 1
            self.save_data()
            src_label = detected.upper() if src_code == 'auto' else u.get('src_lang_name', '')
            await self.send(uid,
                f"✨ [{src_label} → {dst_name}]\n\n{result}")
        else:
            await self.send(uid,
                "⚠️ تعذرت الترجمة. تأكد من النص أو جرب لغة مختلفة.")

    # ── حلقة الاستطلاع ──────────────────────────────────────────────────────
    async def fetch_latest(self) -> dict | None:
        url = (f"https://graph.facebook.com/{VERSION}/me/conversations"
               f"?fields=messages{{message,from,id}}"
               f"&access_token={PAGE_ACCESS_TOKEN}")
        try:
            r = await self.client.get(url)
            data = r.json()
            for convo in data.get('data', []):
                msgs = convo.get('messages', {}).get('data', [])
                if msgs:
                    m = msgs[0]
                    if str(m['from']['id']) != str(PAGE_ID):
                        return m
        except Exception as e:
            print(f"❌ fetch error: {e}")
        return None

    async def run(self):
        print(f"{'═'*42}")
        print(f"  {BOT_NAME} v2  |  ONLINE ✅")
        print(f"{'═'*42}")
        while True:
            msg = await self.fetch_latest()
            if msg:
                asyncio.create_task(self.handle_message(msg))
            await asyncio.sleep(0.5)

# ─── نقطة الدخول ────────────────────────────────────────────────────────────
def start_bot():
    asyncio.run(SwiftTranslateBot().run())

if __name__ == "__main__":
    threading.Thread(target=run_web_server, daemon=True).start()
    start_bot()
