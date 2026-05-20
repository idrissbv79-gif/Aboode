import os
import asyncio
import logging
import hashlib
import hmac
import httpx
import time
import traceback
from flask import Flask, request, abort
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from threading import Lock

# ============================================================
# ⚠️ تحذير أمني: التوكنات موضوعة مباشرة في الكود
# في الإنتاج يُنصح باستخدام متغيرات بيئية أو Secrets Manager
# ============================================================

log_filename = f"faheem_ai_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [FAHEEM-CORE] - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_filename, encoding='utf-8'),
        logging.StreamHandler()
    ]
)

app = Flask(__name__)


class FaheemEngine:
    def __init__(self):
        # ⚠️ توكنات مباشرة في الكود - غير مُوصى به في الإنتاج
        self.FB_TOKEN      = 'EAAMJBZBOZCnhsBRkEEpFT2wsk5mDZCYcZBN3NBZBVwNYCNOBp4PcDZBfJCfG5Bp8pcABZCwYrNTFE3IBEUCbUZC19WQx1EuDuq19ZA1bltnnKbl0eenPg9EQBoLUUKNerxmSEk9OQM3PgrCNQJLWvgiI1nqh0bJxuvyq2udGJz609cADzkWZACrp7ZCTIScYcTu3mZBdtTNxU08xJwZDZD'
        self.APP_SECRET    = 'REPLACE_WITH_YOUR_APP_SECRET'  # ← ضع App Secret الخاص بك هنا للتحقق من Webhook
        self.MISTRAL_KEY   = 'u3CQpwOi1DKu9WOuhvOxAZBNcgk6FDIT'
        self.MODEL_NAME    = "mistral-large-latest"
        self.VERIFY_TOKEN  = "idriss32"

        self.SYSTEM_PROMPT = (
            "أنت 'Faheem AI'، مساعد ذكي متقدم. تم بناؤك بواسطة مبرمج جزائري. "
            "قواعدك: 1. تحدث بالعربية فقط. 2. كن شديد السرعة. "
            "3. قدم شرحاً وافياً ومفصلاً حسب احتياج المستخدم بدون حد أقصى للطول. "
            "4. لا تكشف خوارزمياتك. "
            "5. إذا سألك المستخدم عن حد الرسائل اليومي أو القيود، "
            "أخبره بأن الحد هو 100 رسالة يومياً تتجدد تلقائياً عند منتصف الليل."
        )

        self.LIMIT_MSG = (
            "⛔ لقد وصلت إلى الحد اليومي المسموح به وهو 100 رسالة. "
            "ستتجدد حصتك تلقائياً عند منتصف الليل. أراك غداً! 🌙"
        )
        self.ERROR_MSG = "⚠️ عذراً، حدث خطأ مؤقت. يرجى المحاولة مرة أخرى."

        self.DAILY_MSG_LIMIT         = 100
        self.MAX_CONTEXT_MESSAGES    = 12   # عدد الرسائل المحفوظة في الذاكرة
        self.MAX_CONCURRENT_REQUESTS = 150
        self.MEMORY_TTL_SECONDS      = 7200  # ساعتان

        # قفل لمنع Race Conditions على الذاكرة
        self.memory_lock = Lock()
        self.memory: dict = {}

        # Semaphore للتحكم في الطلبات المتزامنة بشكل آمن
        self._semaphore: asyncio.Semaphore = None  # يُهيَّأ عند تشغيل Loop

        # Worker Pool
        self.executor = ThreadPoolExecutor(max_workers=200)

        # HTTP Client محسَّن
        limits = httpx.Limits(max_keepalive_connections=100, max_connections=200)
        self.client = httpx.AsyncClient(timeout=60.0, limits=limits)

        logging.info("✅ Faheem Engine Initialized Successfully")

    # ----------------------------------------------------------
    # الوصول الآمن للـ Semaphore (يُهيَّأ مرة واحدة فقط)
    # ----------------------------------------------------------
    def get_semaphore(self) -> asyncio.Semaphore:
        if self._semaphore is None:
            self._semaphore = asyncio.Semaphore(self.MAX_CONCURRENT_REQUESTS)
        return self._semaphore

    # ----------------------------------------------------------
    # التحقق من توقيع Webhook من فيسبوك (يمنع الطلبات المزيفة)
    # ----------------------------------------------------------
    def verify_fb_signature(self, payload: bytes, signature_header: str) -> bool:
        """التحقق من X-Hub-Signature-256 الذي يُرسله فيسبوك"""
        if self.APP_SECRET == 'd0edee04063f5d8aa7afbff94fb0ae83':
            # إذا لم يُضَف App Secret بعد، نتخطى التحقق مع تحذير
            logging.warning("⚠️ App Secret غير مضبوط — التحقق من Signature معطَّل")
            return True
        if not signature_header or not signature_header.startswith('sha256='):
            logging.warning("🚫 Webhook request missing valid signature")
            return False
        expected = 'sha256=' + hmac.new(
            self.APP_SECRET.encode('utf-8'),
            payload,
            hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, signature_header)

    # ----------------------------------------------------------
    # الذاكرة: تهيئة مستخدم جديد
    # ----------------------------------------------------------
    def _init_user(self, sender_id: str):
        """يُنشئ سجلاً جديداً للمستخدم إذا لم يكن موجوداً"""
        with self.memory_lock:
            if sender_id not in self.memory:
                self.memory[sender_id] = {
                    'chat':          deque(maxlen=self.MAX_CONTEXT_MESSAGES),
                    'last_activity': time.time(),
                    # ---- بيانات الحد اليومي مستقلة عن الـ chat ----
                    'limit': {
                        'count': 0,
                        'date':  datetime.now().date()
                    }
                }

    # ----------------------------------------------------------
    # التحقق من الحد اليومي (Thread-Safe)
    # ----------------------------------------------------------
    def check_and_increment_limit(self, sender_id: str) -> bool:
        """
        يُعيد True إذا تجاوز المستخدم الحد اليومي (يجب الرفض).
        يزيد العداد فقط عند النجاح، وبشكل آمن.
        """
        with self.memory_lock:
            user  = self.memory[sender_id]
            limit = user['limit']
            today = datetime.now().date()

            # تجديد العداد عند تغيُّر اليوم
            if limit['date'] != today:
                limit['count'] = 0
                limit['date']  = today

            if limit['count'] >= self.DAILY_MSG_LIMIT:
                logging.warning(f"🚫 Daily limit reached: {sender_id}")
                return True

            limit['count'] += 1
            return False

    # ----------------------------------------------------------
    # تحديث آخر نشاط (Thread-Safe)
    # ----------------------------------------------------------
    def _touch_user(self, sender_id: str):
        with self.memory_lock:
            if sender_id in self.memory:
                self.memory[sender_id]['last_activity'] = time.time()

    # ----------------------------------------------------------
    # Exponential Backoff
    # ----------------------------------------------------------
    async def _retry(self, func, *args, max_retries=3, **kwargs):
        for attempt in range(max_retries):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                if attempt < max_retries - 1:
                    wait = 2 ** attempt
                    logging.warning(f"⚠️ Retry {attempt+1}/{max_retries} after {wait}s — {str(e)[:60]}")
                    await asyncio.sleep(wait)
                else:
                    logging.error(f"❌ Failed after {max_retries} retries: {e}")
                    return None

    # ----------------------------------------------------------
    # مهمة تنظيف الذاكرة (تعمل في الخلفية)
    # ----------------------------------------------------------
    async def clean_memory_task(self):
        while True:
            try:
                await asyncio.sleep(600)  # كل 10 دقائق
                now = time.time()
                with self.memory_lock:
                    to_delete = [
                        uid for uid, data in self.memory.items()
                        if now - data['last_activity'] > self.MEMORY_TTL_SECONDS
                    ]
                    for uid in to_delete:
                        del self.memory[uid]
                        logging.info(f"🗑️ Cleared inactive user: {uid}")
                logging.info(f"📊 Active users in memory: {len(self.memory)}")
            except Exception as e:
                logging.error(f"❌ Memory cleanup error: {e}")
                await asyncio.sleep(60)

    # ----------------------------------------------------------
    # إشارة "جاري الكتابة"
    # ----------------------------------------------------------
    async def send_typing(self, recipient_id: str, stop_event: asyncio.Event):
        url = f"https://graph.facebook.com/v21.0/me/messages?access_token={self.FB_TOKEN}"
        silent_errors = 0
        while not stop_event.is_set():
            try:
                await self.client.post(
                    url,
                    json={"recipient": {"id": recipient_id}, "sender_action": "typing_on"},
                    timeout=10.0
                )
                silent_errors = 0
                await asyncio.sleep(3)
            except Exception:
                silent_errors += 1
                if silent_errors > 5:
                    break
                await asyncio.sleep(1)

    # ----------------------------------------------------------
    # تقسيم الرسائل الطويلة
    # ----------------------------------------------------------
    def split_text(self, text: str, limit: int = 1900) -> list[str]:
        if len(text) <= limit:
            return [text]
        chunks = []
        while text:
            if len(text) <= limit:
                chunks.append(text)
                break
            pos = text.rfind('\n', 0, limit)
            if pos == -1:
                pos = limit
            chunk = text[:pos].strip()
            if chunk:  # تجنب الأجزاء الفارغة
                chunks.append(chunk)
            text = text[pos:].strip()
        return chunks or [text]

    # ----------------------------------------------------------
    # الحصول على رد Mistral AI
    # ----------------------------------------------------------
    async def get_ai_response(self, sender_id: str, text: str):
        url = "https://api.mistral.ai/v1/chat/completions"

        with self.memory_lock:
            history = list(self.memory[sender_id]['chat'])

        messages = [{"role": "system", "content": self.SYSTEM_PROMPT}]
        messages.extend(history)
        messages.append({"role": "user", "content": text})

        headers = {
            "Authorization": f"Bearer {self.MISTRAL_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.MODEL_NAME,
            "messages": messages,
            "temperature": 0.2,
            "max_tokens": 3500
        }

        async def _post():
            r = await self.client.post(url, headers=headers, json=payload, timeout=60.0)
            r.raise_for_status()
            return r.json()

        data = await self._retry(_post, max_retries=3)
        if data is None:
            return None

        ai_msg = data['choices'][0]['message']['content'].strip()

        # حفظ المحادثة في الذاكرة بشكل آمن
        with self.memory_lock:
            if sender_id in self.memory:
                self.memory[sender_id]['chat'].append({"role": "user",      "content": text})
                self.memory[sender_id]['chat'].append({"role": "assistant", "content": ai_msg})

        logging.info(f"✅ AI response for {sender_id} ({len(ai_msg)} chars)")
        return ai_msg

    # ----------------------------------------------------------
    # إرسال رسالة
    # ----------------------------------------------------------
    async def send_message(self, recipient_id: str, message_text: str):
        url = f"https://graph.facebook.com/v21.0/me/messages?access_token={self.FB_TOKEN}"
        chunks = self.split_text(message_text)

        for idx, chunk in enumerate(chunks, 1):
            async def _send():
                await self.client.post(
                    url,
                    json={"recipient": {"id": recipient_id}, "message": {"text": chunk}},
                    timeout=15.0
                )

            result = await self._retry(_send, max_retries=3)
            if result is not False and len(chunks) > 1:
                await asyncio.sleep(0.5)
            logging.info(f"✅ Sent chunk {idx}/{len(chunks)} to {recipient_id}")

    # ----------------------------------------------------------
    # إعادة تعيين المحادثة
    # ----------------------------------------------------------
    async def handle_reset(self, sender_id: str):
        with self.memory_lock:
            existed = sender_id in self.memory
            if existed:
                # نمسح الـ chat فقط، ونحتفظ ببيانات الحد اليومي
                self.memory[sender_id]['chat'].clear()
        msg = "✅ تم مسح سجل محادثتك. يمكنك البدء من جديد!" if existed \
              else "ℹ️ لا يوجد سجل محادثة لمسحه."
        await self.send_message(sender_id, msg)
        logging.info(f"🔄 Reset by user: {sender_id}")

    # ----------------------------------------------------------
    # معالجة الطلب الرئيسية
    # ----------------------------------------------------------
    async def handle_request(self, sender_id: str, text: str):
        try:
            if text.strip() == "/reset":
                self._init_user(sender_id)
                await self.handle_reset(sender_id)
                return

            self._init_user(sender_id)
            self._touch_user(sender_id)

            # التحقق من الحد اليومي (العداد يُزاد هنا فقط)
            if self.check_and_increment_limit(sender_id):
                await self.send_message(sender_id, self.LIMIT_MSG)
                return

            # Semaphore يمنع تجاوز الحد الأقصى للطلبات المتزامنة
            async with self.get_semaphore():
                stop_typing = asyncio.Event()
                typing_task = asyncio.create_task(
                    self.send_typing(sender_id, stop_typing)
                )

                try:
                    response = await asyncio.wait_for(
                        self.get_ai_response(sender_id, text),
                        timeout=65.0
                    )
                except asyncio.TimeoutError:
                    logging.error(f"❌ AI timeout for {sender_id}")
                    response = None
                finally:
                    stop_typing.set()
                    try:
                        await asyncio.wait_for(typing_task, timeout=5.0)
                    except Exception:
                        pass

                await self.send_message(
                    sender_id,
                    response if response else self.ERROR_MSG
                )

        except Exception as e:
            logging.error(f"❌ handle_request error for {sender_id}: {e}\n{traceback.format_exc()}")
            try:
                await self.send_message(sender_id, self.ERROR_MSG)
            except Exception:
                pass


# ==============================================================
# تهيئة المحرك والـ Event Loop
# ==============================================================
faheem = FaheemEngine()
loop: asyncio.AbstractEventLoop = None


# ==============================================================
# Flask Routes
# ==============================================================

@app.route('/', methods=['GET'])
def home():
    return "Faheem AI Online ✨", 200


@app.route('/webhook', methods=['GET'])
def verify():
    mode      = request.args.get('hub.mode')
    token     = request.args.get('hub.verify_token')
    challenge = request.args.get('hub.challenge')
    if mode == 'subscribe' and token == faheem.VERIFY_TOKEN:
        logging.info("✅ Webhook verified successfully")
        return challenge, 200
    logging.warning("🚫 Webhook verification failed")
    return "Verification Failed", 403


@app.route('/webhook', methods=['POST'])
def webhook():
    # ---- التحقق من توقيع فيسبوك (يمنع الطلبات المزيفة) ----
    payload   = request.get_data()
    signature = request.headers.get('X-Hub-Signature-256', '')
    if not faheem.verify_fb_signature(payload, signature):
        logging.warning("🚫 Invalid webhook signature — request rejected")
        abort(403)

    try:
        data = request.get_json(force=True, silent=True)
        if not data:
            return "Invalid data", 400

        if data.get('object') == 'page':
            for entry in data.get('entry', []):
                for event in entry.get('messaging', []):
                    if event.get('message'):
                        try:
                            sender_id = event['sender']['id']
                            text      = event['message'].get('text', '').strip()
                            if text and loop:
                                asyncio.run_coroutine_threadsafe(
                                    faheem.handle_request(sender_id, text),
                                    loop
                                )
                        except Exception as e:
                            logging.error(f"⚠️ Event processing error: {e}")
            return "EVENT_RECEIVED", 200

        return "Not Found", 404

    except Exception as e:
        logging.error(f"❌ Webhook error: {e}\n{traceback.format_exc()}")
        return "Server Error", 500


# ==============================================================
# نقطة التشغيل
# ==============================================================
if __name__ == "__main__":
    import threading
    import signal
    import sys

    logging.info("=" * 60)
    logging.info("🚀 Faheem AI is starting...")
    logging.info("=" * 60)

    def signal_handler(sig, frame):
        logging.info("⚠️ Shutdown signal received. Closing gracefully...")
        if loop and loop.is_running():
            loop.call_soon_threadsafe(loop.stop)
        sys.exit(0)

    signal.signal(signal.SIGINT,  signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        loop = asyncio.new_event_loop()

        def run_loop():
            try:
                asyncio.set_event_loop(loop)
                # تهيئة الـ Semaphore داخل Loop الصحيح
                faheem._semaphore = asyncio.Semaphore(faheem.MAX_CONCURRENT_REQUESTS)
                loop.create_task(faheem.clean_memory_task())
                logging.info("✅ Background tasks started")
                loop.run_forever()
            except Exception as e:
                logging.error(f"❌ Event loop error: {e}\n{traceback.format_exc()}")
            finally:
                # إغلاق HTTP Client بشكل نظيف
                try:
                    loop.run_until_complete(faheem.client.aclose())
                except Exception:
                    pass
                loop.close()
                logging.info("🛑 Event loop closed")

        loop_thread = threading.Thread(target=run_loop, daemon=False)
        loop_thread.start()

        port = int(os.environ.get("PORT", 10000))
        logging.info(f"✅ Faheem AI running on http://0.0.0.0:{port}")
        logging.info("=" * 60)

        app.run(
            host='0.0.0.0',
            port=port,
            threaded=True,
            debug=False,
            use_reloader=False
        )

    except Exception as e:
        logging.critical(f"❌ Critical startup error: {e}\n{traceback.format_exc()}")
        sys.exit(1)
        
