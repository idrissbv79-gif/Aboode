import httpx, asyncio, json, os, threading
from flask import Flask
from deep_translator import GoogleTranslator
from langdetect import detect

# ─── Flask (keep-alive) ──────────────────────────────────────────────────────
app = Flask(__name__)

@app.route('/')
def home():
    return "SwiftTranslate Pro v2 is Running! ✅"

def run_web_server():
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, use_reloader=False)

# ─── إعدادات ─────────────────────────────────────────────────────────────────
PAGE_ACCESS_TOKEN = 'EAAMJBZBOZCnhsBRT50G56dfJOtCoCsONXnds8d1dp6JcyFhb7Dp7ljOgPjfmsLDqZC6IFHjOyiDuyxvkMxpOzWcPYpLzq8vJOt2ZBquqcEPTGggmsnYwnEqHkotjTJlrh8pk19cbAVaj5ZAhIYWBdwjk0UI5b9ICOoAs7CD2zfezlPsZB7alH1ez9YMDXX6ZBaGjXrU3QZDZD'
PAGE_ID    = '61589538039390'
VERSION    = 'v19.0'
BOT_NAME   = "SwiftTranslate Pro"
ADMIN_PASS = "idriss78"
DB_FILE    = "bot_database.json"

LANG = {
    "1":("الإنجليزية","en","🇺🇸"),   "2":("الفرنسية","fr","🇫🇷"),
    "3":("الألمانية","de","🇩🇪"),    "4":("الإسبانية","es","🇪🇸"),
    "5":("التركية","tr","🇹🇷"),      "6":("الإيطالية","it","🇮🇹"),
    "7":("الروسية","ru","🇷🇺"),      "8":("الصينية","zh-CN","🇨🇳"),
    "9":("اليابانية","ja","🇯🇵"),    "10":("الكورية","ko","🇰🇷"),
    "11":("البرتغالية","pt","🇵🇹"),  "12":("الهندية","hi","🇮🇳"),
    "13":("الإندونيسية","id","🇮🇩"), "14":("الهولندية","nl","🇳🇱"),
    "15":("السويدية","sv","🇸🇪"),    "16":("البولندية","pl","🇵🇱"),
    "17":("اليونانية","el","🇬🇷"),   "18":("التايلاندية","th","🇹🇭"),
    "19":("الفيتنامية","vi","🇻🇳"),  "20":("العربية","ar","🇩🇿"),
    "21":("النرويجية","no","🇳🇴"),   "22":("الدنماركية","da","🇩🇰"),
    "23":("الفنلندية","fi","🇫🇮"),   "24":("المجرية","hu","🇭🇺"),
    "25":("التشيكية","cs","🇨🇿"),    "26":("العبرية","he","🇮🇱"),
    "27":("الرومانية","ro","🇷🇴"),   "28":("الفارسية","fa","🇮🇷"),
    "29":("الأوكرانية","uk","🇺🇦"),  "30":("الأردية","ur","🇵🇰"),
}

LANG_MENU_BODY = "".join(
    f" [{k.zfill(2)}] {LANG[k][2]} {LANG[k][0]}\n" for k in [str(i) for i in range(1, 31)]
)

NEW_USER = lambda: {
    'lang_code': 'ar', 'lang_name': 'العربية',
    'src_lang_code': 'auto', 'src_lang_name': 'تلقائي', 'count': 0
}

# ─── قاعدة البيانات ───────────────────────────────────────────────────────────
def load_db():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, 'r', encoding='utf-8') as f:
                d = json.load(f)
            return d.get('users', {}), d.get('admins', {})
        except Exception:
            pass
    return {}, {}

def save_db(users, admins):
    try:
        with open(DB_FILE, 'w', encoding='utf-8') as f:
            json.dump({'users': users, 'admins': admins}, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"❌ DB: {e}")

# ─── البوت ───────────────────────────────────────────────────────────────────
class Bot:
    S_PANEL = "panel"
    S_BROADCAST = "broadcast"
    S_TRANSLATE = "translate"

    def __init__(self):
        self.users, self.admins = load_db()
        self.seen: dict = {}
        self.client = httpx.AsyncClient(
            timeout=30.0,
            limits=httpx.Limits(max_connections=100, max_keepalive_connections=20)
        )

    def save(self): save_db(self.users, self.admins)

    # ── حالة الأدمن ──────────────────────────────────────────────────────────
    def is_admin(self, uid):
        return uid in self.admins and bool(self.admins[uid].get('state'))

    def get_state(self, uid):
        return self.admins.get(uid, {}).get('state', '')

    def set_state(self, uid, state):
        self.admins.setdefault(uid, {})['state'] = state
        self.save()

    def clear_admin(self, uid):
        if uid in self.admins:
            self.admins[uid]['state'] = ''
        self.save()

    # ── إرسال ────────────────────────────────────────────────────────────────
    def _chunks(self, text, n=1900):
        if len(text) <= n:
            return [text]
        out, rest = [], text
        while rest:
            if len(rest) <= n:
                out.append(rest)
                break
            i = rest.rfind('\n', 0, n) or rest.rfind(' ', 0, n) or n
            out.append(rest[:i].strip())
            rest = rest[i:].strip()
        return out

    async def send(self, uid, text):
        url = f"https://graph.facebook.com/{VERSION}/me/messages?access_token={PAGE_ACCESS_TOKEN}"
        for chunk in self._chunks(text):
            if not chunk:
                continue
            try:
                r = await self.client.post(
                    url, json={"recipient": {"id": uid}, "message": {"text": chunk}}
                )
                if r.status_code != 200:
                    print(f"❌ send {uid}: {r.text}")
            except Exception as e:
                print(f"❌ send: {e}")
            await asyncio.sleep(0.15)

    async def get_name(self, uid):
        try:
            r = await self.client.get(
                f"https://graph.facebook.com/{VERSION}/{uid}"
                f"?fields=first_name&access_token={PAGE_ACCESS_TOKEN}"
            )
            return r.json().get('first_name', 'صديقي')
        except Exception:
            return "صديقي"

    # ── ترجمة ────────────────────────────────────────────────────────────────
    async def detect_lang(self, text):
        def _d():
            try:
                return detect(text)
            except Exception:
                return "auto"
        return await asyncio.to_thread(_d)

    async def translate(self, text, src, dst):
        def _do():
            tr = GoogleTranslator(source=src, target=dst)
            parts = [text[i:i+4500] for i in range(0, len(text), 4500)]
            result = [tr.translate(p) for p in parts if p.strip()]
            return "\n".join(r for r in result if r) or None
        for i in range(3):
            try:
                r = await asyncio.to_thread(_do)
                if r:
                    return r
            except Exception as e:
                if i == 2:
                    print(f"❌ translate: {e}")
                await asyncio.sleep(0.5)
        return None

    # ══════════════════════════════════════════════════════════════════════════
    # مسار الأدمن
    # ══════════════════════════════════════════════════════════════════════════
    async def send_panel(self, uid):
        total = len(self.users)
        total_tr = sum(u.get('count', 0) for u in self.users.values())
        await self.send(uid,
            f"🛠️ لوحة تحكم {BOT_NAME}\n{'═'*30}\n"
            f"👥 المستخدمون: {total}  |  🔤 ترجمات: {total_tr}\n{'─'*30}\n"
            "1️⃣  إذاعة رسالة\n2️⃣  إحصائيات\n3️⃣  أكثر 5 لغات\n4️⃣  تصفير العدادات\n"
            f"{'─'*30}\n🔟  وضع الترجمة الشخصي\n0️⃣  إغلاق اللوحة\n\n👉 أرسل رقم الخيار."
        )

    async def admin_panel(self, uid, text):
        if text == "0":
            self.clear_admin(uid)
            await self.send(uid, "🔒 تم إغلاق لوحة التحكم.\nأنت الآن في وضع المستخدم العادي.")
            return
        if text == "10":
            self.set_state(uid, self.S_TRANSLATE)
            await self.send(uid, "✅ وضع الترجمة الشخصي.\nأرسل أي نص للترجمة.\nأرسل [panel] للعودة.")
            return
        if text == "1":
            self.set_state(uid, self.S_BROADCAST)
            await self.send(uid, "📝 أرسل نص الإذاعة.\nأرسل [0] للإلغاء.")
            return
        if text == "2":
            new_ = sum(1 for u in self.users.values() if u.get('is_new'))
            total_tr = sum(u.get('count', 0) for u in self.users.values())
            await self.send(uid,
                f"📊 إحصائيات\n{'─'*24}\n"
                f"👥 المستخدمون : {len(self.users)}\n"
                f"🔤 الترجمات   : {total_tr}\n"
                f"🆕 جدد        : {new_}"
            )
        elif text == "3":
            counts = {}
            for u in self.users.values():
                ln = u.get('lang_name', 'غير محدد')
                counts[ln] = counts.get(ln, 0) + u.get('count', 0)
            top = sorted(counts.items(), key=lambda x: x[1], reverse=True)[:5]
            msg = f"🏆 أكثر 5 لغات\n{'─'*24}\n"
            for i, (ln, cnt) in enumerate(top, 1):
                msg += f"{i}. {ln}: {cnt}\n"
            await self.send(uid, msg)
        elif text == "4":
            for u in self.users.values():
                u['count'] = 0
            self.save()
            await self.send(uid, "🔄 تم تصفير عدادات الترجمة.")
        else:
            await self.send(uid, "⚠️ خيار غير معروف.")
        await self.send_panel(uid)

    async def admin_broadcast(self, uid, text):
        if text == "0":
            self.set_state(uid, self.S_PANEL)
            await self.send(uid, "❌ تم إلغاء الإذاعة.")
            await self.send_panel(uid)
            return
        self.set_state(uid, self.S_PANEL)
        msg = f"📢 رسالة من {BOT_NAME}\n{'─'*24}\n\n{text}\n\n{'─'*24}\n🤖 {BOT_NAME}"
        await self.send(uid, "⏳ جاري الإرسال...")
        ok = fail = 0
        for u_id in list(self.users):
            if str(u_id) == PAGE_ID:
                continue
            try:
                await self.send(str(u_id), msg)
                ok += 1
            except Exception:
                fail += 1
            await asyncio.sleep(0.3)
        await self.send(uid, f"✅ انتهت الإذاعة\n✔️ نجاح: {ok} | ❌ فشل: {fail}")
        await self.send_panel(uid)

    async def route_admin(self, uid, text):
        state = self.get_state(uid)
        if state == self.S_PANEL:
            await self.admin_panel(uid, text)
        elif state == self.S_BROADCAST:
            await self.admin_broadcast(uid, text)
        elif state == self.S_TRANSLATE:
            if text.lower() == "panel":
                self.set_state(uid, self.S_PANEL)
                await self.send_panel(uid)
            else:
                await self.user_logic(uid, text)
        else:
            self.set_state(uid, self.S_PANEL)
            await self.send_panel(uid)

    # ══════════════════════════════════════════════════════════════════════════
    # مسار المستخدم
    # ══════════════════════════════════════════════════════════════════════════
    async def send_welcome(self, uid):
        name = await self.get_name(uid)
        await self.send(uid,
            f"👋 أهلاً {name} في {BOT_NAME}!\n\n"
            "📋 الأوامر:\n"
            "  • [قائمة] أو [0]  — قائمة اللغات\n"
            "  • [من:رقم]        — تغيير لغة المصدر\n"
            "  • [عكس]           — عكس اتجاه الترجمة\n"
            "  • [لغتي]          — إعداداتك الحالية\n"
            "  • [مساعدة]        — هذه الرسالة\n\n"
            "⚡ أرسل أي نص وسيُترجم فوراً!"
        )

    async def user_logic(self, uid, text):
        u = self.users.setdefault(uid, NEW_USER())
        t = text.upper()

        if text in ("0", "قائمة") or t == "MENU":
            await self.send(uid,
                f"⚙️ إعدادات الترجمة\n{'─'*28}\n"
                f"📤 من : {u.get('src_lang_name','تلقائي')}\n"
                f"📥 إلى: {u.get('lang_name','العربية')}\n{'─'*28}\n\n"
                f"{LANG_MENU_BODY}\n"
                "💡 أرسل رقم اللغة (1-30) لتعيين لغة الهدف.\n"
                "💡 أرسل [من:رقم] لتغيير لغة المصدر."
            )
            return

        if text in ("مساعدة", "help") or t == "HELP":
            await self.send_welcome(uid)
            return

        if text in ("لغتي", "اعداداتي"):
            await self.send(uid,
                f"📊 إعداداتك\n{'─'*22}\n"
                f"📤 من : {u.get('src_lang_name','تلقائي')}\n"
                f"📥 إلى: {u.get('lang_name','العربية')}\n"
                f"🔤 ترجماتك: {u.get('count',0)}"
            )
            return

        if text in ("عكس", "reverse") or t == "REVERSE":
            sc, sn = u.get('src_lang_code', 'auto'), u.get('src_lang_name', 'تلقائي')
            dc, dn = u.get('lang_code', 'ar'),        u.get('lang_name', 'العربية')
            u['lang_code']     = sc if sc != 'auto' else 'ar'
            u['lang_name']     = sn if sn != 'تلقائي' else 'العربية'
            u['src_lang_code'] = dc
            u['src_lang_name'] = dn
            self.save()
            await self.send(uid,
                f"🔄 تم عكس الاتجاه\n"
                f"📤 من : {u['src_lang_name']}\n📥 إلى: {u['lang_name']}"
            )
            return

        if text.startswith("من:") or text.startswith("من :"):
            num = text.split(":", 1)[1].strip()
            clean = str(int(num)) if num.isdigit() else num
            if clean == "0":
                u['src_lang_code'] = 'auto'
                u['src_lang_name'] = 'تلقائي'
                self.save()
                await self.send(uid, "✅ لغة المصدر: تلقائي 🔍")
                return
            if clean in LANG:
                u['src_lang_code'] = LANG[clean][1]
                u['src_lang_name'] = LANG[clean][0]
                self.save()
                await self.send(uid, f"✅ لغة المصدر: {LANG[clean][2]} {LANG[clean][0]}")
                return
            await self.send(uid, "⚠️ رقم غير صحيح (1-30).")
            return

        if text.isdigit():
            clean = str(int(text))
            if clean in LANG:
                u['lang_code'] = LANG[clean][1]
                u['lang_name'] = LANG[clean][0]
                self.save()
                await self.send(uid, f"✅ لغة الهدف: {LANG[clean][2]} {LANG[clean][0]}")
                return
            await self.send(uid, "⚠️ الرقم خارج النطاق (1-30).")
            return

        # ── ترجمة النص ────────────────────────────────────────────────────────
        if len(text) < 2:
            await self.send(uid, "⚠️ النص قصير جداً.")
            return
        src = u.get('src_lang_code', 'auto')
        dst = u.get('lang_code', 'ar')
        detected = await self.detect_lang(text) if src == 'auto' else src
        if detected == dst:
            await self.send(uid, f"ℹ️ النص بالفعل بلغة الهدف ({u['lang_name']}).")
            return
        result = await self.translate(text, detected, dst)
        if result:
            u['count'] = u.get('count', 0) + 1
            self.save()
            label = detected.upper() if src == 'auto' else u.get('src_lang_name', src)
            await self.send(uid, f"✨ [{label} → {u['lang_name']}]\n\n{result}")
        else:
            await self.send(uid, "⚠️ تعذرت الترجمة. حاول مجدداً.")

    # ══════════════════════════════════════════════════════════════════════════
    # المعالج الرئيسي
    # ══════════════════════════════════════════════════════════════════════════
    async def handle(self, msg: dict):
        uid    = str(msg.get('from', {}).get('id', ''))
        msg_id = msg.get('id', '')
        text   = msg.get('message', '').strip()

        if not uid or not text:
            return
        if self.seen.get(uid) == msg_id:
            return
        self.seen[uid] = msg_id
        if uid == PAGE_ID:
            return

        # مستخدم جديد
        if uid not in self.users:
            self.users[uid] = {**NEW_USER(), 'is_new': True}
            self.save()
            await self.send_welcome(uid)
            return

        # كلمة مرور الأدمن (أولوية قصوى)
        if text == ADMIN_PASS:
            self.set_state(uid, self.S_PANEL)
            await self.send_panel(uid)
            return

        # توجيه حسب النوع
        if self.is_admin(uid):
            await self.route_admin(uid, text)
        else:
            await self.user_logic(uid, text)

    # ══════════════════════════════════════════════════════════════════════════
    # Long Polling — جلب الرسائل بدون Webhook
    # ══════════════════════════════════════════════════════════════════════════
    async def fetch_messages(self):
        """جلب آخر رسالة من كل محادثة عبر Graph API."""
        url = (
            f"https://graph.facebook.com/{VERSION}/{PAGE_ID}/conversations"
            f"?fields=id,messages.limit(1){{message,from,id,created_time}}"
            f"&access_token={PAGE_ACCESS_TOKEN}"
        )
        try:
            r = await self.client.get(url)
            if r.status_code != 200:
                print(f"❌ fetch: {r.status_code} {r.text}")
                return
            data = r.json().get('data', [])
            tasks = []
            for conv in data:
                for msg in conv.get('messages', {}).get('data', []):
                    tasks.append(self.handle(msg))
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
        except Exception as e:
            print(f"❌ fetch_messages: {e}")

    async def polling_loop(self):
        """حلقة Long Polling — تعمل بشكل مستمر كل 3 ثوانٍ."""
        print(f"🚀 {BOT_NAME} — Long Polling started...")
        while True:
            try:
                await self.fetch_messages()
            except Exception as e:
                print(f"❌ polling_loop: {e}")
            await asyncio.sleep(3)

    async def run(self):
        await self.polling_loop()

# ─── نقطة الدخول ─────────────────────────────────────────────────────────────
if __name__ == '__main__':
    threading.Thread(target=run_web_server, daemon=True).start()
    bot = Bot()
    asyncio.run(bot.run())
