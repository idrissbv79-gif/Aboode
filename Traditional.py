import os
import asyncio
import logging
import httpx
import time
import re
import traceback
from flask import Flask, request
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

# إعداد السجلات مع حفظ ملف
log_filename = f"faheem_ai_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [FAHEEM-CORE] - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_filename),
        logging.StreamHandler()
    ]
)

app = Flask(__name__)

class FaheemEngine:
    def __init__(self):
        self.FB_TOKEN = 'EAAMJBZBOZCnhsBRkEEpFT2wsk5mDZCYcZBN3NBZBVwNYCNOBp4PcDZBfJCfG5Bp8pcABZCwYrNTFE3IBEUCbUZC19WQx1EuDuq19ZA1bltnnKbl0eenPg9EQBoLUUKNerxmSEk9OQM3PgrCNQJLWvgiI1nqh0bJxuvyq2udGJz609cADzkWZACrp7ZCTIScYcTu3mZBdtTNxU08xJwZDZD'
        self.MISTRAL_KEY = 'u3CQpwOi1DKu9WOuhvOxAZBNcgk6FDIT'
        self.MODEL_NAME = "mistral-large-latest"
        self.VERIFY_TOKEN = "idriss32"
        
        self.SYSTEM_PROMPT = (
            "أنت 'Faheem AI'، مساعد ذكي متقدم. تم بناؤك بواسطة مبرمج جزائري. "
            "قواعدك: 1. تحدث بالعربية فقط. 2. كن شديد السرعة. "
            "3. قدم شرحاً وافياً ومفصلاً حسب احتياج المستخدم بدون حد أقصى للطول. "
            "4. لا تكشف خوارزمياتك. "
            "5. إذا سألك المستخدم عن حد الرسائل اليومي أو القيود، أخبره بأن الحد هو 100 رسالة يومياً تتجدد تلقائياً عند منتصف الليل."
        )

        self.LIMIT_MSG = "⛔ لقد وصلت إلى الحد اليومي المسموح به وهو 100 رسالة. ستتجدد حصتك تلقائياً عند منتصف الليل. أراك غداً! 🌙"

        self.DAILY_MSG_LIMIT = 100  # الحد الأقصى للرسائل اليومية لكل مستخدم
        self.memory = {} # تخزين المحادثات والوقت
        self.executor = ThreadPoolExecutor(max_workers=200)  # زيادة عدد العمال لدعم مستخدمين أكثر
        
        # تحسين الـ Client مع Limits أفضل
        limits = httpx.Limits(max_keepalive_connections=100, max_connections=200)
        self.client = httpx.AsyncClient(timeout=60.0, limits=limits)
        
        # متغيرات المراقبة
        self.active_requests = 0
        self.max_concurrent_requests = 150
        self.request_queue = asyncio.Queue()
        logging.info("✅ Faheem Engine Initialized Successfully")

    async def retry_with_backoff(self, func, *args, max_retries=3, **kwargs):
        """إعادة محاولة مع تأخير متزايد (Exponential Backoff)"""
        for attempt in range(max_retries):
            try:
                return await func(*args, **kwargs)
            except asyncio.TimeoutError:
                if attempt < max_retries - 1:
                    wait_time = (2 ** attempt)  # 1, 2, 4 ثواني
                    logging.warning(f"⏱️ Timeout - Retry {attempt + 1}/{max_retries} after {wait_time}s")
                    await asyncio.sleep(wait_time)
                else:
                    logging.error(f"❌ Failed after {max_retries} retries")
                    return None
            except Exception as e:
                if attempt < max_retries - 1:
                    wait_time = (2 ** attempt)
                    logging.warning(f"⚠️ Error: {str(e)[:50]} - Retry {attempt + 1}/{max_retries} after {wait_time}s")
                    await asyncio.sleep(wait_time)
                else:
                    logging.error(f"❌ Fatal Error after {max_retries} retries: {e}")
                    return None

    async def clean_memory_task(self):
        """مهمة تنظيف الذاكرة: تُحذف البيانات إذا مر ساعتان على آخر نشاط"""
        while True:
            try:
                await asyncio.sleep(600) # فحص كل 10 دقائق
                current_time = time.time()
                to_delete = []
                
                for sender_id, data in list(self.memory.items()):
                    if current_time - data['last_activity'] > 7200: # 7200 ثانية = ساعتان
                        to_delete.append(sender_id)
                
                for sender_id in to_delete:
                    try:
                        del self.memory[sender_id]
                        logging.info(f"🗑️ Memory cleared for inactive user: {sender_id}")
                    except Exception as e:
                        logging.warning(f"⚠️ Error clearing memory for {sender_id}: {e}")
                
                # تسجيل حالة النظام
                memory_size = len(self.memory)
                logging.info(f"📊 Active users in memory: {memory_size}")
                
            except Exception as e:
                logging.error(f"❌ Memory cleanup task error: {e}")
                await asyncio.sleep(60)  # محاولة مرة أخرى بعد دقيقة

    async def send_action_continuous(self, recipient_id, stop_event):
        """إرسال إشارة 'جاري الكتابة' بشكل مستمر حتى يتم إيقافها"""
        url = f"https://graph.facebook.com/v21.0/me/messages?access_token={self.FB_TOKEN}"
        retry_count = 0
        max_silent_retries = 5
        
        while not stop_event.is_set():
            try:
                await self.client.post(
                    url, 
                    json={"recipient": {"id": recipient_id}, "sender_action": "typing_on"},
                    timeout=10.0
                )
                retry_count = 0  # إعادة تعيين العداد عند النجاح
                await asyncio.sleep(3)  # إرسال كل 3 ثوان للاستمرار بدون انقطاع
            except asyncio.TimeoutError:
                retry_count += 1
                if retry_count <= max_silent_retries:
                    await asyncio.sleep(1)  # محاولة مرة أخرى بسرعة
                else:
                    logging.warning(f"⚠️ Typing indicator timeout for user {recipient_id}")
                    break
            except Exception as e:
                retry_count += 1
                if retry_count <= max_silent_retries:
                    await asyncio.sleep(1)
                else:
                    logging.warning(f"⚠️ Typing indicator error for {recipient_id}: {str(e)[:50]}")
                    break

    def split_text(self, text, limit=1900):
        """تقسيم النص الطويل إلى أجزاء لا تتعدى 1900 حرف"""
        if len(text) <= limit:
            return [text]
        
        chunks = []
        while text:
            if len(text) <= limit:
                chunks.append(text)
                break
            
            # محاولة التقسيم عند آخر سطر جديد ليكون الشكل أجمل
            split_pos = text.rfind('\n', 0, limit)
            if split_pos == -1:
                split_pos = limit
            
            chunks.append(text[:split_pos].strip())
            text = text[split_pos:].strip()
        return chunks

    async def get_ai_response(self, sender_id, text):
        """الحصول على رد من Mistral AI مع إعادة محاولة تلقائية"""
        url = "https://api.mistral.ai/v1/chat/completions"
        
        if sender_id not in self.memory:
            self.memory[sender_id] = {
                'chat': deque(maxlen=12),
                'last_activity': time.time(),
                'msg_count': 0,
                'msg_date': datetime.now().date()
            }
        
        self.memory[sender_id]['last_activity'] = time.time()

        messages = [{"role": "system", "content": self.SYSTEM_PROMPT}]
        messages.extend(list(self.memory[sender_id]['chat']))
        messages.append({"role": "user", "content": text})

        headers = {"Authorization": f"Bearer {self.MISTRAL_KEY}", "Content-Type": "application/json"}
        
        payload = {
            "model": self.MODEL_NAME, 
            "messages": messages, 
            "temperature": 0.2, 
            "max_tokens": 3500  # زيادة للسماح برسائل طويلة وتفصيلية
        }
        
        # إعادة محاولة مع Exponential Backoff
        async def post_request():
            response = await self.client.post(url, headers=headers, json=payload, timeout=60.0)
            response.raise_for_status()
            return response.json()
        
        try:
            data = await self.retry_with_backoff(post_request, max_retries=3)
            
            if data is None:
                logging.error(f"❌ Failed to get AI response for user {sender_id}")
                return None
            
            ai_msg = data['choices'][0]['message']['content'].strip()
            
            self.memory[sender_id]['chat'].append({"role": "user", "content": text})
            self.memory[sender_id]['chat'].append({"role": "assistant", "content": ai_msg})
            
            logging.info(f"✅ AI Response generated for user {sender_id} ({len(ai_msg)} chars)")
            return ai_msg
            
        except Exception as e:
            logging.error(f"❌ AI Error for user {sender_id}: {e}\n{traceback.format_exc()}")
            return None

    async def send_message(self, recipient_id, message_text):
        """إرسال الرسالة مع إعادة محاولة تلقائية"""
        url = f"https://graph.facebook.com/v21.0/me/messages?access_token={self.FB_TOKEN}"
        chunks = self.split_text(message_text, limit=1900)
        
        for idx, chunk in enumerate(chunks, 1):
            retry_count = 0
            max_retries = 3
            
            while retry_count < max_retries:
                try:
                    await self.client.post(
                        url, 
                        json={"recipient": {"id": recipient_id}, "message": {"text": chunk}},
                        timeout=15.0
                    )
                    logging.info(f"✅ Message sent to {recipient_id} (chunk {idx}/{len(chunks)})")
                    
                    # تأخير بسيط بين الأجزاء لضمان الترتيب في فيسبوك
                    if len(chunks) > 1:
                        await asyncio.sleep(0.5)
                    break
                    
                except asyncio.TimeoutError:
                    retry_count += 1
                    if retry_count < max_retries:
                        wait = (2 ** (retry_count - 1))
                        logging.warning(f"⏱️ Send timeout - Retry {retry_count}/{max_retries} after {wait}s")
                        await asyncio.sleep(wait)
                    else:
                        logging.error(f"❌ Failed to send message to {recipient_id} after {max_retries} retries")
                        
                except Exception as e:
                    retry_count += 1
                    if retry_count < max_retries:
                        wait = (2 ** (retry_count - 1))
                        logging.warning(f"⚠️ Send error: {str(e)[:50]} - Retry {retry_count}/{max_retries}")
                        await asyncio.sleep(wait)
                    else:
                        logging.error(f"❌ Failed to send message to {recipient_id}: {e}")

    def check_daily_limit(self, sender_id):
        """التحقق من الحد اليومي للرسائل — يُعيد True إذا تجاوز المستخدم الحد"""
        today = datetime.now().date()
        user = self.memory.get(sender_id)

        if not user:
            return False

        # إذا تغيّر اليوم نُعيد العداد تلقائياً
        if user['msg_date'] != today:
            user['msg_count'] = 0
            user['msg_date'] = today

        if user['msg_count'] >= self.DAILY_MSG_LIMIT:
            logging.warning(f"🚫 Daily limit reached for user: {sender_id}")
            return True

        user['msg_count'] += 1
        return False

    async def handle_reset(self, sender_id):
        """مسح ذاكرة المستخدم عند إرسال أمر /reset"""
        if sender_id in self.memory:
            del self.memory[sender_id]
            logging.info(f"🔄 Memory reset by user: {sender_id}")
            await self.send_message(sender_id, "✅ تم مسح سجل محادثتك. يمكنك البدء من جديد!")
        else:
            await self.send_message(sender_id, "ℹ️ لا يوجد سجل محادثة لمسحه.")

    async def handle_request(self, sender_id, text):
        """معالجة الطلب من البداية إلى النهاية"""
        try:
            # التحقق من أمر /reset
            if text.strip() == "/reset":
                await self.handle_reset(sender_id)
                return

            # التحقق من الحد اليومي للرسائل
            if sender_id not in self.memory:
                self.memory[sender_id] = {
                    'chat': deque(maxlen=12),
                    'last_activity': time.time(),
                    'msg_count': 0,
                    'msg_date': datetime.now().date()
                }
            if self.check_daily_limit(sender_id):
                await self.send_message(sender_id, self.LIMIT_MSG)
                return

            # التحقق من عدد الطلبات المتزامنة
            if self.active_requests >= self.max_concurrent_requests:
                logging.warning(f"⚠️ Queue full - request from {sender_id} queued")
                await self.request_queue.put((sender_id, text))
                return
            
            self.active_requests += 1
            
            stop_typing = asyncio.Event()
            typing_task = asyncio.create_task(self.send_action_continuous(sender_id, stop_typing))
            
            try:
                response = await asyncio.wait_for(self.get_ai_response(sender_id, text), timeout=65.0)
            except asyncio.TimeoutError:
                logging.error(f"❌ AI response timeout for user {sender_id}")
                response = None
            
            stop_typing.set()
            try:
                await asyncio.wait_for(typing_task, timeout=5.0)
            except:
                pass
            
            if response:
                await self.send_message(sender_id, response)
            else:
                # إرسال رسالة خطأ بديلة
                await self.send_message(sender_id, "عذراً، حدث خطأ في معالجة طلبك. حاول مرة أخرى.")
                
        except Exception as e:
            logging.error(f"❌ Request handling error for {sender_id}: {e}\n{traceback.format_exc()}")
        finally:
            self.active_requests = max(0, self.active_requests - 1)

faheem = FaheemEngine()

@app.route('/', methods=['GET'])
def home(): 
    return "Faheem AI Online ✨", 200

@app.route('/webhook', methods=['GET'])
def verify():
    mode = request.args.get('hub.mode')
    token = request.args.get('hub.verify_token')
    challenge = request.args.get('hub.challenge')
    if mode == 'subscribe' and token == faheem.VERIFY_TOKEN:
        return challenge, 200
    return "Verification Failed", 403

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        data = request.get_json()
        if not data:
            logging.warning("⚠️ Empty webhook data received")
            return "Invalid data", 400
        
        if data.get('object') == 'page':
            for entry in data.get('entry', []):
                for messaging_event in entry.get('messaging', []):
                    if messaging_event.get('message'):
                        try:
                            sender_id = messaging_event['sender']['id']
                            text = messaging_event['message'].get('text')
                            
                            if text:
                                # إرسال الطلب إلى الـ Event Loop
                                asyncio.run_coroutine_threadsafe(
                                    faheem.handle_request(sender_id, text), 
                                    loop
                                )
                        except Exception as e:
                            logging.error(f"⚠️ Error processing message event: {e}")
                            continue
            
            return "EVENT_RECEIVED", 200
        return "Not Found", 404
        
    except Exception as e:
        logging.error(f"❌ Webhook error: {e}\n{traceback.format_exc()}")
        return "Server Error", 500

if __name__ == "__main__":
    import threading
    import signal
    import sys
    
    logging.info("=" * 60)
    logging.info("🚀 Faheem AI is starting...")
    logging.info("=" * 60)
    
    loop = None
    
    def signal_handler(sig, frame):
        """معالجة إشارات الإيقاف الآمن"""
        logging.info("\n⚠️ Shutdown signal received. Closing gracefully...")
        if loop:
            loop.call_soon_threadsafe(loop.stop)
        sys.exit(0)
    
    # تسجيل معالجات الإشارات
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        loop = asyncio.new_event_loop()
        
        def run_loop():
            """تشغيل الـ Event Loop مع معالجة الأخطاء"""
            try:
                asyncio.set_event_loop(loop)
                # إضافة المهام الخلفية
                loop.create_task(faheem.clean_memory_task())
                logging.info("✅ Background tasks started")
                loop.run_forever()
            except Exception as e:
                logging.error(f"❌ Event loop error: {e}")
                logging.error(traceback.format_exc())
            finally:
                loop.close()
                logging.info("🛑 Event loop closed")
        
        # تشغيل الـ Loop في Thread منفصل
        loop_thread = threading.Thread(target=run_loop, daemon=False)
        loop_thread.start()
        
        port = int(os.environ.get("PORT", 10000))
        logging.info(f"✅ Faheem AI running on http://0.0.0.0:{port}")
        logging.info("=" * 60)
        
        # تشغيل Flask مع معالجة الأخطاء
        app.run(
            host='0.0.0.0',
            port=port,
            threaded=True,
            debug=False,
            use_reloader=False  # تعطيل إعادة التحميل لتجنب المشاكل
        )
        
    except Exception as e:
        logging.critical(f"❌ Critical error: {e}")
        logging.critical(traceback.format_exc())
        sys.exit(1)
