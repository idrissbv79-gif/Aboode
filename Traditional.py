import httpx, asyncio, json, os, threading
from flask import Flask
from deep_translator import GoogleTranslator
from langdetect import detect

app = Flask(__name__)

@app.route('/')
def home(): return "SwiftTranslate Pro v2 is Running! ✅"

def run_web_server():
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))

PAGE_ACCESS_TOKEN = 'EAAMJBZBOZCnhsBRT50G56dfJOtCoCsONXnds8d1dp6JcyFhb7Dp7ljOgPjfmsLDqZC6IFHjOyiDuyxvkMxpOzWcPYpLzq8vJOt2ZBquqcEPTGggmsnYwnEqHkotjTJlrh8pk19cbAVaj5ZAhIYWBdwjk0UI5b9ICOoAs7CD2zfezlPsZB7alH1ez9YMDXX6ZBaGjXrU3QZDZD'
PAGE_ID    = '61589538039390'
VERSION    = 'v19.0'
BOT_NAME   = "SwiftTranslate Pro"
ADMIN_PASS = "idriss78"

LANGUAGES_MAP = {
    "1":{"name":"الإنجليزية","code":"en","flag":"🇺🇸"},   "2":{"name":"الفرنسية","code":"fr","flag":"🇫🇷"},
    "3":{"name":"الألمانية","code":"de","flag":"🇩🇪"},    "4":{"name":"الإسبانية","code":"es","flag":"🇪🇸"},
    "5":{"name":"التركية","code":"tr","flag":"🇹🇷"},      "6":{"name":"الإيطالية","code":"it","flag":"🇮🇹"},
    "7":{"name":"الروسية","code":"ru","flag":"🇷🇺"},      "8":{"name":"الصينية","code":"zh-CN","flag":"🇨🇳"},
    "9":{"name":"اليابانية","code":"ja","flag":"🇯🇵"},   "10":{"name":"الكورية","code":"ko","flag":"🇰🇷"},
    "11":{"name":"البرتغالية","code":"pt","flag":"🇵🇹"}, "12":{"name":"الهندية","code":"hi","flag":"🇮🇳"},
    "13":{"name":"الإندونيسية","code":"id","flag":"🇮🇩"},"14":{"name":"الهولندية","code":"nl","flag":"🇳🇱"},
    "15":{"name":"السويدية","code":"sv","flag":"🇸🇪"},   "16":{"name":"البولندية","code":"pl","flag":"🇵🇱"},
    "17":{"name":"اليونانية","code":"el","flag":"🇬🇷"},  "18":{"name":"التايلاندية","code":"th","flag":"🇹🇭"},
    "19":{"name":"الفيتنامية","code":"vi","flag":"🇻🇳"}, "20":{"name":"العربية","code":"ar","flag":"🇩🇿"},
    "21":{"name":"النرويجية","code":"no","flag":"🇳🇴"},  "22":{"name":"الدنماركية","code":"da","flag":"🇩🇰"},
    "23":{"name":"الفنلندية","code":"fi","flag":"🇫🇮"},  "24":{"name":"المجرية","code":"hu","flag":"🇭🇺"},
    "25":{"name":"التشيكية","code":"cs","flag":"🇨🇿"},   "26":{"name":"العبرية","code":"he","flag":"🇮🇱"},
    "27":{"name":"الرومانية","code":"ro","flag":"🇷🇴"},  "28":{"name":"الفارسية","code":"fa","flag":"🇮🇷"},
    "29":{"name":"الأوكرانية","code":"uk","flag":"🇺🇦"}, "30":{"name":"الأردية","code":"ur","flag":"🇵🇰"},
}

_LANG_MENU_BODY = "".join(
    f" [{str(k).zfill(2)}] {LANGUAGES_MAP[str(k)]['flag']} {LANGUAGES_MAP[str(k)]['name']}\n"
    for k in range(1, 31)
)

class SwiftTranslateBot:
    DB_FILE = "bot_database.json"
    S_PANEL = "panel"; S_BROADCAST = "broadcast"; S_TRANSLATE = "translate"

    def __init__(self):
        self.seen: dict = {}
        self.client = httpx.AsyncClient(timeout=20.0,
            limits=httpx.Limits(max_connections=200, max_keepalive_connections=50))
        self.load_data()

    # ── DB ────────────────────────────────────────────────────────────────────
    def load_data(self):
        if os.path.exists(self.DB_FILE):
            try:
                with open(self.DB_FILE, 'r', encoding='utf-8') as f: d = json.load(f)
                self.users = d.get('users', {}); self.admins = d.get('admins', {}); return
            except Exception: pass
        self.users = {}; self.admins = {}

    def save_data(self):
        try:
            with open(self.DB_FILE, 'w', encoding='utf-8') as f:
                json.dump({'users': self.users, 'admins': self.admins}, f, ensure_ascii=False, indent=2)
        except Exception as e: print(f"❌ DB: {e}")

    def is_admin(self, uid): return uid in self.admins and bool(self.admins[uid].get('state'))
    def admin_state(self, uid): return self.admins.get(uid, {}).get('state', '')
    def set_admin_state(self, uid, state):
        self.admins.setdefault(uid, {})['state'] = state; self.save_data()
    def exit_admin(self, uid):
        if uid in self.admins: self.admins[uid]['state'] = ''
        self.save_data()

    # ── شبكة ──────────────────────────────────────────────────────────────────
    async def get_name(self, uid):
        try:
            r = await self.client.get(f"https://graph.facebook.com/{VERSION}/{uid}"
                                      f"?fields=first_name&access_token={PAGE_ACCESS_TOKEN}")
            return r.json().get('first_name', 'صديقي')
        except Exception: return "صديقي"

    def _split(self, text, max_len=1900):
        if len(text) <= max_len: return [text]
        chunks, rest = [], text
        while rest:
            if len(rest) <= max_len: chunks.append(rest); break
            cut = rest.rfind('\n', 0, max_len)
            if cut == -1: cut = rest.rfind(' ', 0, max_len)
            if cut == -1: cut = max_len
            chunks.append(rest[:cut].strip()); rest = rest[cut:].strip()
        return chunks

    async def send(self, uid, text):
        url = f"https://graph.facebook.com/{VERSION}/me/messages?access_token={PAGE_ACCESS_TOKEN}"
        ok = True
        for chunk in self._split(text):
            if not chunk: continue
            try:
                r = await self.client.post(url, json={"recipient":{"id":uid},"message":{"text":chunk}})
                if r.status_code != 200: print(f"❌ API {uid}: {r.text}"); ok = False
            except Exception as e: print(f"❌ send: {e}"); ok = False
            await asyncio.sleep(0.15)
        return ok

    # ── ترجمة ─────────────────────────────────────────────────────────────────
    async def detect_lang(self, text):
        def _d():
            try: return detect(text)
            except: return "auto"
        return await asyncio.to_thread(_d)

    async def translate(self, text, src, dst):
        def _do():
            tr = GoogleTranslator(source=src, target=dst)
            out = [r for p in self._split(text, 4500) if p.strip() and (r := tr.translate(p))]
            return "\n".join(out) if out else None
        for attempt in range(3):
            try:
                result = await asyncio.to_thread(_do)
                if result: return result
            except Exception as e:
                if attempt == 2: print(f"❌ translate: {e}")
                await asyncio.sleep(0.5)
        return None

    # ══════════════════════════════════════════════════════════════════════════
    # مسار الأدمن — منفصل تماماً
    # ══════════════════════════════════════════════════════════════════════════
    async def send_admin_panel(self, uid):
        total = len(self.users); total_tr = sum(u.get('count',0) for u in self.users.values())
        await self.send(uid,
            f"🛠️ لوحة تحكم {BOT_NAME}\n{'═'*32}\n"
            f"👥 المستخدمون: {total}  |  🔤 ترجمات: {total_tr}\n{'─'*32}\n"
            "1️⃣  إذاعة رسالة\n2️⃣  إحصائيات تفصيلية\n"
            "3️⃣  أكثر 5 لغات\n4️⃣  تصفير العدادات\n"
            f"{'─'*32}\n🔟  وضع الترجمة الشخصي\n0️⃣  إغلاق لوحة التحكم\n\n👉 أرسل رقم الخيار.")

    async def _admin_panel(self, uid, text):
        # الأرقام هنا = أوامر اللوحة فقط — لا تُرسل للترجمة أو LANGUAGES_MAP أبداً
        if text == "0":
            self.exit_admin(uid)
            await self.send(uid, "🔒 تم إغلاق لوحة التحكم.\nأنت الآن في وضع المستخدم العادي.")
        elif text == "10":
            self.set_admin_state(uid, self.S_TRANSLATE)
            await self.send(uid, "✅ دخلت وضع الترجمة الشخصي.\nأرسل [panel] للعودة للوحة التحكم.")
        elif text == "1":
            self.set_admin_state(uid, self.S_BROADCAST)
            await self.send(uid, "📝 أرسل نص الإذاعة الآن.\nأرسل [0] للإلغاء.")
        elif text == "2":
            total = len(self.users); total_tr = sum(u.get('count',0) for u in self.users.values())
            new_ = sum(1 for u in self.users.values() if u.get('is_new'))
            await self.send(uid, f"📊 إحصائيات\n{'─'*24}\n👥 مستخدمون: {total}\n🔤 ترجمات: {total_tr}\n🆕 جدد: {new_}")
        elif text == "3":
            counts = {}
            for u in self.users.values(): ln = u.get('lang_name','?'); counts[ln] = counts.get(ln,0)+u.get('count',0)
            top5 = sorted(counts.items(), key=lambda x: x[1], reverse=True)[:5]
            await self.send(uid, f"🏆 أكثر 5 لغات\n{'─'*24}\n" + "".join(f"{i}. {ln}: {c}\n" for i,(ln,c) in enumerate(top5,1)))
        elif text == "4":
            for u in self.users.values(): u['count'] = 0
            self.save_data(); await self.send(uid, "🔄 تم تصفير جميع العدادات.")
        else:
            await self.send(uid, "⚠️ خيار غير معروف."); await self.send_admin_panel(uid)

    async def _admin_broadcast(self, uid, text):
        if text == "0":
            self.set_admin_state(uid, self.S_PANEL)
            await self.send(uid, "❌ تم إلغاء الإذاعة."); await self.send_admin_panel(uid); return
        self.set_admin_state(uid, self.S_PANEL)
        broadcast = f"📢 رسالة من إدارة {BOT_NAME}\n{'─'*28}\n\n{text}\n\n{'─'*28}\n🤖 {BOT_NAME}"
        await self.send(uid, "⏳ جاري الإرسال الجماعي...")
        ok_c = fail_c = 0
        for u_id in list(self.users.keys()):
            if str(u_id) == str(PAGE_ID): continue
            if await self.send(str(u_id), broadcast): ok_c += 1
            else: fail_c += 1
            await asyncio.sleep(0.3)
        await self.send(uid, f"✅ انتهت الإذاعة\n✔️ نجاح: {ok_c} | ❌ فشل: {fail_c}")
        await self.send_admin_panel(uid)

    async def _admin_translate(self, uid, text):
        # [panel] = العودة، أي نص آخر = ترجمة كالمستخدم العادي
        if text.lower() == "panel":
            self.set_admin_state(uid, self.S_PANEL); await self.send_admin_panel(uid)
        else:
            await self._user_logic(uid, text)

    async def route_admin(self, uid, text):
        state = self.admin_state(uid)
        if   state == self.S_PANEL:     await self._admin_panel(uid, text)
        elif state == self.S_BROADCAST: await self._admin_broadcast(uid, text)
        elif state == self.S_TRANSLATE: await self._admin_translate(uid, text)
        else: self.set_admin_state(uid, self.S_PANEL); await self.send_admin_panel(uid)

    # ══════════════════════════════════════════════════════════════════════════
    # مسار المستخدم العادي — منفصل تماماً
    # ══════════════════════════════════════════════════════════════════════════
    async def send_welcome(self, uid):
        name = await self.get_name(uid)
        await self.send(uid,
            f"👋 أهلاً {name} في {BOT_NAME}!\n\n📋 الأوامر:\n"
            "  • [قائمة] أو [0] — قائمة اللغات\n"
            "  • [من:رقم]       — تغيير لغة المصدر\n"
            "  • [عكس]          — عكس اتجاه الترجمة\n"
            "  • [لغتي]         — إعداداتك الحالية\n\n"
            "⚡ أرسل أي نص للترجمة الفورية!")

    async def _user_logic(self, uid, text):
        # المنطق المشترك للمستخدم العادي + وضع ترجمة الأدمن
        u = self.users.setdefault(uid, {'lang_code':'ar','lang_name':'العربية',
                                         'src_lang_code':'auto','src_lang_name':'تلقائي','count':0})
        upper = text.upper()

        if text in ("0","قائمة") or upper == "MENU":
            await self.send(uid,
                f"⚙️ إعدادات الترجمة\n{'─'*30}\n"
                f"📤 من : {u.get('src_lang_name','تلقائي')}\n"
                f"📥 إلى: {u.get('lang_name','العربية')}\n{'─'*30}\n\n{_LANG_MENU_BODY}\n"
                "💡 أرسل رقم اللغة (1-30) لتغيير لغة الهدف.\n💡 [من:رقم] لتغيير المصدر."); return

        if text in ("مساعدة","help") or upper == "HELP":
            await self.send_welcome(uid); return

        if text in ("لغتي","اعداداتي"):
            await self.send(uid,
                f"📊 إعداداتك\n{'─'*22}\n"
                f"📤 من : {u.get('src_lang_name','تلقائي')}\n"
                f"📥 إلى: {u.get('lang_name','العربية')}\n"
                f"🔤 ترجماتك: {u.get('count',0)}"); return

        if text in ("عكس","reverse") or upper == "REVERSE":
            sc,sn = u.get('src_lang_code','auto'), u.get('src_lang_name','تلقائي')
            dc,dn = u.get('lang_code','ar'),        u.get('lang_name','العربية')
            u['lang_code'] = sc if sc!='auto' else 'ar'; u['lang_name'] = sn if sn!='تلقائي' else 'العربية'
            u['src_lang_code'] = dc; u['src_lang_name'] = dn; self.save_data()
            await self.send(uid, f"🔄 تم العكس\n📤 من: {u['src_lang_name']}\n📥 إلى: {u['lang_name']}"); return

        if text.startswith("من:") or text.startswith("من :"):
            num = text.split(":",1)[1].strip(); clean = str(int(num)) if num.isdigit() else num
            if clean == "0":
                u['src_lang_code']='auto'; u['src_lang_name']='تلقائي'; self.save_data()
                await self.send(uid, "✅ لغة المصدر: تلقائي 🔍"); return
            if clean in LANGUAGES_MAP:
                s=LANGUAGES_MAP[clean]; u['src_lang_code']=s['code']; u['src_lang_name']=s['name']
                self.save_data(); await self.send(uid, f"✅ لغة المصدر: {s['flag']} {s['name']}"); return
            await self.send(uid, "⚠️ رقم غير صحيح (1-30)."); return

        if text.isdigit():
            clean = str(int(text))
            if clean in LANGUAGES_MAP:
                s=LANGUAGES_MAP[clean]; u['lang_code']=s['code']; u['lang_name']=s['name']
                self.save_data(); await self.send(uid, f"✅ لغة الهدف: {s['flag']} {s['name']}"); return
            await self.send(uid, "⚠️ الرقم خارج النطاق (1-30)."); return

        if len(text) < 2: await self.send(uid, "⚠️ النص قصير جداً."); return
        src = u.get('src_lang_code','auto'); dst = u.get('lang_code','ar')
        detected = await self.detect_lang(text) if src=='auto' else src
        if detected == dst:
            await self.send(uid, f"ℹ️ النص بالفعل بلغة الهدف ({u['lang_name']})."); return
        result = await self.translate(text, detected, dst)
        if result:
            u['count'] = u.get('count',0)+1; self.save_data()
            label = detected.upper() if src=='auto' else u.get('src_lang_name', src)
            await self.send(uid, f"✨ [{label} → {u['lang_name']}]\n\n{result}")
        else:
            await self.send(uid, "⚠️ تعذرت الترجمة. حاول مجدداً.")

    async def route_user(self, uid, text):
        """نقطة دخول المستخدم العادي — لا تعرف شيئاً عن الأدمن."""
        await self._user_logic(uid, text)

    # ══════════════════════════════════════════════════════════════════════════
    # البوابة الرئيسية — الفصل التام بين الأدمن والمستخدم
    # ══════════════════════════════════════════════════════════════════════════
    async def handle_message(self, msg):
        uid    = str(msg['from']['id'])
        msg_id = msg['id']
        text   = msg.get('message','').strip()
        if self.seen.get(uid) == msg_id: return
        self.seen[uid] = msg_id
        if uid == str(PAGE_ID): return

        if uid not in self.users:
            self.users[uid] = {'lang_code':'ar','lang_name':'العربية',
                               'src_lang_code':'auto','src_lang_name':'تلقائي','count':0,'is_new':True}
            self.save_data(); await self.send_welcome(uid); return

        # كلمة مرور الأدمن — أولوية قصوى
        if text == ADMIN_PASS:
            self.set_admin_state(uid, self.S_PANEL); await self.send_admin_panel(uid); return

        # الفصل التام: أدمن نشط → مسار الأدمن | غيره → مسار المستخدم
        if self.is_admin(uid): await self.route_admin(uid, text)
        else:                   await self.route_user(uid, text)

    async def fetch_latest(self):
        url = (f"https://graph.facebook.com/{VERSION}/me/conversations"
               f"?fields=messages{{message,from,id}}&access_token={PAGE_ACCESS_TOKEN}")
        try:
            r = await self.client.get(url)
            for convo in r.json().get('data',[]):
                msgs = convo.get('messages',{}).get('data',[])
                if msgs and str(msgs[0]['from']['id']) != str(PAGE_ID): return msgs[0]
        except Exception as e: print(f"❌ fetch: {e}")
        return None

    async def run(self):
        print(f"{'═'*42}\n  {BOT_NAME} v2  |  ONLINE ✅\n{'═'*42}")
        while True:
            msg = await self.fetch_latest()
            if msg: asyncio.create_task(self.handle_message(msg))
            await asyncio.sleep(0.5)

def start_bot(): asyncio.run(SwiftTranslateBot().run())

if __name__ == "__main__":
    threading.Thread(target=run_web_server, daemon=True).start()
    start_bot()
