import os
import json
import time
import hashlib
import logging
import asyncio
import aiohttp
import aiosqlite
from quart import Quart, request, jsonify

# إعدادات تسجيل الأخطاء
logging.basicConfig(filename='error_log.txt', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- المتغيرات الأساسية ---
z1 = '8798290585:AAFCcecMtoYjVNnQi-tzHG-o5sBiD3nxSU4'  # توكن البوت الخاص بك
z2 = 'https://t.me/Z_O_Z_0o0/36'  # رابط الصورة الشخصية للبوت
z3 = 'https://zecora0.serv00.net/ai/NanoBanana.php'  # رابط الـ API

# مسار قاعدة البيانات المؤقتة على سيرفر Render
z5 = os.path.join('/tmp', 'duplicate_cache.db')

# تهيئة قاعدة البيانات بشكل غير متزامن
async def init_db():
    async with aiosqlite.connect(z5) as conn:
        await conn.execute("CREATE TABLE IF NOT EXISTS requests (hash TEXT PRIMARY KEY, created_at INTEGER)")
        await conn.execute("CREATE TABLE IF NOT EXISTS processing (user_id INTEGER PRIMARY KEY, started_at INTEGER)")
        await conn.commit()

# تهيئة تطبيق Quart للويب هوك
app = Quart(__name__)

# جلسة اتصال موحدة لتسريع الطلبات
async_session = None

@app.before_serving
async def startup():
    global async_session
    await init_db()
    async_session = aiohttp.ClientSession()

@app.after_serving
async def shutdown():
    global async_session
    if async_session:
        await async_session.close()

# --- دالة إرسال الطلبات إلى تليجرام ---
async def ze(method, datas=None):
    global z1, async_session
    if datas is None:
        datas = {}
    url = f"https://api.telegram.org/bot{z1}/{method}"
    try:
        if async_session:
            async with async_session.post(url, data=datas, timeout=30) as response:
                return await response.json()
    except Exception as e:
        logging.error(f"Telegram API Error ({method}): {e}")
        return {}

# --- دالة إرسال إشعار الرفع المستمر (جاري التحميل...) ---
async def keep_sending_action(chat_id, stop_event):
    while not stop_event.is_set():
        await ze('sendChatAction', {'chat_id': chat_id, 'action': 'upload_photo'})
        try:
            await asyncio.sleep(4)
        except asyncio.CancelledError:
            break

# --- دالة التحكم في قفل التكرار للمستخدمين ---
async def zec(uid, act='check'):
    now = int(time.time())
    async with aiosqlite.connect(z5) as conn:
        await conn.execute("DELETE FROM processing WHERE started_at < ?", (now - 300,))
        await conn.commit()
        
        if act == 'unlock':
            await conn.execute("DELETE FROM processing WHERE user_id = ?", (uid,))
            await conn.commit()
            return True
            
        async with conn.execute("SELECT 1 FROM processing WHERE user_id = ?", (uid,)) as cursor:
            row = await cursor.fetchone()
        
        if row:
            return False
            
        if act == 'lock':
            await conn.execute("INSERT OR REPLACE INTO processing (user_id, started_at) VALUES (?, ?)", (uid, now))
            await conn.commit()
            return True
            
        return True

# --- معالجة البيانات القادمة من التليجرام ---
async def handle_telegram_update(zupd):
    global z2, z3, z5, async_session
    if not zupd:
        return

    zmsg = zupd.get('message')
    zcbq = zupd.get('callback_query')
    
    zch = None
    if zmsg and 'chat' in zmsg:
        zch = zmsg['chat']['id']
    elif zcbq and 'message' in zcbq and 'chat' in zcbq['message']:
        zch = zcbq['message']['chat']['id']
        
    zfr = None
    if zmsg and 'from' in zmsg:
        zfr = zmsg['from']['id']
    elif zcbq and 'from' in zcbq:
        zfr = zcbq['from']['id']
        
    zmid = None
    if zmsg:
        zmid = zmsg.get('message_id')
    elif zcbq and 'message' in zcbq:
        zmid = zcbq['message'].get('message_id')
        
    ztx = zmsg.get('text') if zmsg else None
    zda = zcbq.get('data') if zcbq else None
    zpho = zmsg.get('photo') if zmsg else None
    zsd = zcbq.get('id') if zcbq else None

    if not zfr:
        return

    if zcbq:
        await ze('answerCallbackQuery', {'callback_query_id': zsd})

    if zmsg and ztx:
        hash_val = hashlib.md5(f"{zch}_{ztx}".encode('utf-8')).hexdigest()
        now = int(time.time())
        
        async with aiosqlite.connect(z5) as conn:
            await conn.execute("DELETE FROM requests WHERE created_at < ?", (now - 5,))
            async with conn.execute("SELECT 1 FROM requests WHERE hash = ?", (hash_val,)) as cursor:
                duplicated = await cursor.fetchone()
            if duplicated:
                return
                
            await conn.execute("INSERT INTO requests (hash, created_at) VALUES (?, ?)", (hash_val, now))
            await conn.commit()

    zstf = f"/tmp/{zfr}.json"
    zstd = {}
    if os.path.exists(zstf):
        try:
            with open(zstf, 'r') as f:
                zstd = json.load(f)
        except:
            zstd = {}

    if zmsg and ztx and ztx != '/start' and zstd.get('step') == 'awaiting_text' and zstd.get('mode') == 'create':
        zst_msg = await ze('sendMessage', {'chat_id': zch, 'text': "<b>⏳ جاري إنشاء صورتك بسرعة، يرجى الانتظار...</b>", 'parse_mode': 'HTML'})
        zstd['current_loading_id'] = zst_msg.get('result', {}).get('message_id') if zst_msg else None
    elif zmsg and ztx and zstd.get('step') == 'awaiting_text_edit' and zstd.get('mode') == 'edit' and 'image' in zstd:
        zst_msg = await ze('sendMessage', {'chat_id': zch, 'text': "<b>⏳ جاري تعديل صورتك بسرعة، يرجى الانتظار...</b>", 'parse_mode': 'HTML'})
        zstd['current_loading_id'] = zst_msg.get('result', {}).get('message_id') if zst_msg else None

    if not await zec(zfr, 'check'):
        if zstd.get('current_loading_id'):
            await ze('deleteMessage', {'chat_id': zch, 'message_id': zstd['current_loading_id']})
        return

    zmod = {'NanoBanana': 'NanoBanana', 'NanoBanana2': 'NanoBanana 2', 'NanoBananaPro': 'NanoBanana Pro'}
    zrat = {'1:1': '1:1', '1:4': '1:4', '1:8': '1:8', '2:3': '2:3', '3:2': '3:2', '3:4': '3:4', '4:1': '4:1', '4:3': '4:3', '4:5': '4:5', '5:4': '5:4', '8:1': '8:1', '9:16': '9:16', '16:9': '16:9', '21:9': '21:9', 'auto': 'تلقائي'}
    zres = {'1K': '1K', '2K': '2K', '4K': '4K'}

    if ztx == "/start":
        if os.path.exists(zstf):
            os.remove(zstf)
        zcap = "<b>مرحباً، أنا نانو بنانا (NanoBanana) 👋</b>\n<b>أقدم حلول ذكاء اصطناعي متطورة بأعلى معايير الجودة. 👀</b>\n<b>القيود والسلوك 🤬 :</b>\n<blockquote>• القيود: لا يُسمح بانتهاك الحقوق أو المواد المحمية.\n• قد تتطلب بعض الطلبات الدقيقة عدة محاولات وتعديلات للوصول للنتيجة المطلوبة.</blockquote>"
        reply_markup = {
            'inline_keyboard': [[
                {'text': '• إنشاء صورة •', 'callback_data': 'create_image'},
                {'text': '• تعديل صورة •', 'callback_data': 'edit_image'}
            ]]
        }
        await ze('sendPhoto', {
            'chat_id': zch,
            'photo': z2,
            'caption': zcap,
            'parse_mode': 'HTML',
            'has_spoiler': True,
            'reply_markup': json.dumps(reply_markup)
        })
        return

    if zda == 'back':
        if os.path.exists(zstf):
            os.remove(zstf)
        await ze('deleteMessage', {'chat_id': zch, 'message_id': zmid})
        reply_markup = {
            'inline_keyboard': [[
                {'text': '• إنشاء صورة •', 'callback_data': 'create_image'},
                {'text': '• تعديل صورة •', 'callback_data': 'edit_image'}
            ]]
        }
        await ze('sendPhoto', {'chat_id': zch, 'photo': z2, 'caption': "<b>مرحباً، أنا نانو بنانا (NanoBanana) 👋</b>\n<b>أقدم حلول ذكاء اصطناعي متطورة بأعلى معايير الجودة.</b>", 'parse_mode': 'HTML', 'reply_markup': json.dumps(reply_markup)})
        return

    if zda in ['create_image', 'edit_image']:
        zmode = 'create' if zda == 'create_image' else 'edit'
        zstd = {'mode': zmode, 'step': 'choose_model'}
        with open(zstf, 'w') as f:
            json.dump(zstd, f)
            
        ztmsg = "<b>• اختر نموذج الذكاء الاصطناعي :</b>"
        inline_keyboard = []
        zkeys = list(zmod.keys())
        for i in range(0, len(zkeys), 2):
            row = [{'text': zmod[zkeys[i]], 'callback_data': f"set_model|{zkeys[i]}"}]
            if i + 1 < len(zkeys):
                row.append({'text': zmod[zkeys[i+1]], 'callback_data': f"set_model|{zkeys[i+1]}"})
            inline_keyboard.append(row)
        inline_keyboard.append([{'text': '• عودة •', 'callback_data': 'back'}])
        
        await ze('editMessageCaption', {'chat_id': zch, 'message_id': zmid, 'caption': ztmsg, 'parse_mode': 'HTML', 'reply_markup': json.dumps({'inline_keyboard': inline_keyboard})})
        return

    if zda and zda.startswith('set_model|'):
        zmodel = zda.split('|')[1]
        zstd['model'] = zmodel
        zstd['step'] = 'choose_ratio'
        with open(zstf, 'w') as f:
            json.dump(zstd, f)
            
        ztmsg = "<b>• اختر الأبعاد (النسبة) :</b>"
        inline_keyboard = []
        zrkeys = list(zrat.keys())
        for i in range(0, len(zrkeys), 3):
            row = []
            for j in range(3):
                if i + j < len(zrkeys):
                    v = zrkeys[i + j]
                    row.append({'text': zrat[v], 'callback_data': f"set_ratio|{v}"})
            inline_keyboard.append(row)
        inline_keyboard.append([{'text': '• عودة •', 'callback_data': 'back'}])
        
        await ze('editMessageCaption', {'chat_id': zch, 'message_id': zmid, 'caption': ztmsg, 'parse_mode': 'HTML', 'reply_markup': json.dumps({'inline_keyboard': inline_keyboard})})
        return

    if zda and zda.startswith('set_ratio|'):
        zratio = zda.split('|')[1]
        zstd['ratio'] = zratio
        zstd['step'] = 'choose_res'
        with open(zstf, 'w') as f:
            json.dump(zstd, f)
            
        ztmsg = "<b>• اختر الدقة والجودة :</b>"
        inline_keyboard = []
        zreskeys = list(zres.keys())
        for i in range(0, len(zreskeys), 2):
            row = []
            for j in range(2):
                if i + j < len(zreskeys):
                    v = zreskeys[i + j]
                    row.append({'text': zres[v], 'callback_data': f"set_res|{v}"})
            inline_keyboard.append(row)
        inline_keyboard.append([{'text': '• عودة •', 'callback_data': 'back'}])
        
        await ze('editMessageCaption', {'chat_id': zch, 'message_id': zmid, 'caption': ztmsg, 'parse_mode': 'HTML', 'reply_markup': json.dumps({'inline_keyboard': inline_keyboard})})
        return

    if zda and zda.startswith('set_res|'):
        zresol = zda.split('|')[1]
        zstd['res'] = zresol
        if 'ratio' not in zstd: zstd['ratio'] = '1:1'
        if 'model' not in zstd: zstd['model'] = 'NanoBanana2'
        if 'mode' not in zstd:
            if os.path.exists(zstf): os.remove(zstf)
            return
            
        zmode = zstd['mode']
        zstd['step'] = 'awaiting_text' if zmode == 'create' else 'awaiting_image'
        with open(zstf, 'w') as f:
            json.dump(zstd, f)
            
        zmd = zmod.get(zstd['model'], zstd['model'])
        zat = 'أرسل النص الآن لإنشاء صورتك' if zmode == 'create' else 'يرجى إرسال الصورة لتعديلها'
        znt = f"<b>النموذج :</b> {zmd}\n<b>أبعاد :</b> {zstd['ratio']} | <b>الدقة :</b> {zresol}\n\n<b>{zat}</b>"
        await ze('editMessageCaption', {'chat_id': zch, 'message_id': zmid, 'caption': znt, 'parse_mode': 'HTML', 'reply_markup': json.dumps({'inline_keyboard': [[{'text': '• عودة •', 'callback_data': 'back'}]]})})
        return

    # --- معالجة طلب إنشاء الصورة ---
    if zmsg and ztx and ztx != '/start' and zstd.get('step') == 'awaiting_text' and zstd.get('mode') == 'create':
        zcur = zstd.copy()
        if os.path.exists(zstf): os.remove(zstf)
            
        zmodel = zcur.get('model', 'NanoBanana2')
        zratio = zcur.get('ratio', '1:1')
        zresol = zcur.get('res', '1K')
        zapim = 'NanoBanana2' if zmodel == 'NanoBananaPro' else zmodel
        zstid = zcur.get('current_loading_id')
        
        stop_action = asyncio.Event()
        action_task = asyncio.create_task(keep_sending_action(zch, stop_action))
        
        zpdata = {'text': ztx, 'model': zapim, 'ratio': zratio, 'res': zresol}
        try:
            if async_session:
                async with async_session.post(z3, data=zpdata, timeout=120) as resp_curl:
                    zresp = await resp_curl.text()
                    zhttp = resp_curl.status
            else:
                zresp, zhttp = None, 0
        except:
            zresp, zhttp = None, 0
            
        stop_action.set()
        try:
            action_task.cancel()
            await action_task
        except asyncio.CancelledError:
            pass
        
        if zstid: await ze('deleteMessage', {'chat_id': zch, 'message_id': zstid})
            
        if zresp and zhttp == 200:
            try: zresarr = json.loads(zresp)
            except: zresarr = {}
            if zresarr.get('success') and zresarr.get('url'):
                zmd = zmod.get(zcur['model'], zcur['model'])
                zcap = f"<b>النموذج: {zmd}\nالأبعاد: {zratio} | الدقة: {zresarr.get('resolution')}</b>"
                await ze('sendPhoto', {'chat_id': zch, 'photo': zresarr['url'], 'caption': zcap, 'parse_mode': 'HTML', 'has_spoiler': True, 'reply_markup': json.dumps({'inline_keyboard': [[{'text': '• عودة •', 'callback_data': 'back'}]]})})
            else:
                await ze('sendMessage', {'chat_id': zch, 'text': "<b>عذراً، حدث خطأ أثناء المعالجة</b>", 'parse_mode': 'HTML', 'reply_markup': json.dumps({'inline_keyboard': [[{'text': '• عودة •', 'callback_data': 'back'}]]})})
        else:
            await ze('sendMessage', {'chat_id': zch, 'text': "<b>للأسف حدث خطأ في النظام الخارجي</b>", 'parse_mode': 'HTML', 'reply_markup': json.dumps({'inline_keyboard': [[{'text': '• عودة •', 'callback_data': 'back'}]]})})
            
        await zec(zfr, 'unlock')
        return

    # --- استقبال الصورة للتعديل ---
    if zstd.get('step') == 'awaiting_image' and zstd.get('mode') == 'edit' and zpho:
        zfid = zpho[-1]['file_id']
        zfinfo = await ze('getFile', {'file_id': zfid})
        if zfinfo.get('ok') and zfinfo.get('result', {}).get('file_path'):
            zlink = f"https://api.telegram.org/file/bot{z1}/{zfinfo['result']['file_path']}"
            zstd['image'] = zlink
            zstd['step'] = 'awaiting_text_edit'
            with open(zstf, 'w') as f:
                json.dump(zstd, f)
            await ze('sendMessage', {'chat_id': zch, 'text': "<b>تم استلام الصورة بنجاح! أرسل الآن نص التعديل المطلوب</b>", 'parse_mode': 'HTML', 'reply_markup': json.dumps({'inline_keyboard': [[{'text': '• عودة •', 'callback_data': 'back'}]]})})
        return

    # --- معالجة طلب تعديل الصورة ---
    if zmsg and ztx and zstd.get('step') == 'awaiting_text_edit' and zstd.get('mode') == 'edit' and 'image' in zstd:
        zcur = zstd.copy()
        if os.path.exists(zstf): os.remove(zstf)
            
        zmodel = zcur.get('model', 'NanoBanana2')
        zratio = zcur.get('ratio', '1:1')
        zresol = zcur.get('res', '1K')
        zapim = 'NanoBanana2' if zmodel == 'NanoBananaPro' else zmodel
        zstid = zcur.get('current_loading_id')
        
        stop_action = asyncio.Event()
        action_task = asyncio.create_task(keep_sending_action(zch, stop_action))
        
        zpdata = {'text': ztx, 'model': zapim, 'links': zcur['image'], 'ratio': zratio, 'res': zresol}
        try:
            if async_session:
                async with async_session.post(z3, data=zpdata, timeout=120) as resp_curl:
                    zresp = await resp_curl.text()
                    zhttp = resp_curl.status
            else:
                zresp, zhttp = None, 0
        except:
            zresp, zhttp = None, 0
            
        stop_action.set()
        try:
            action_task.cancel()
            await action_task
        except asyncio.CancelledError:
            pass
        
        if zstid: await ze('deleteMessage', {'chat_id': zch, 'message_id': zstid})
            
        if zresp and zhttp == 200:
            try: zresarr = json.loads(zresp)
            except: zresarr = {}
            if zresarr.get('success') and zresarr.get('url'):
                zmd = zmod.get(zcur['model'], zcur['model'])
                zcap = f"<b>النموذج: {zmd}\nأبعاد: {zratio} | الدقة: {zresarr.get('resolution')}</b>"
                await ze('sendPhoto', {'chat_id': zch, 'photo': zresarr['url'], 'caption': zcap, 'parse_mode': 'HTML', 'has_spoiler': True, 'reply_markup': json.dumps({'inline_keyboard': [[{'text': '• عودة •', 'callback_data': 'back'}]]})})
            else:
                await ze('sendMessage', {'chat_id': zch, 'text': "<b>عذراً، حدث خطأ أثناء المعالجة</b>", 'parse_mode': 'HTML', 'reply_markup': json.dumps({'inline_keyboard': [[{'text': '• عودة •', 'callback_data': 'back'}]]})})
        else:
            await ze('sendMessage', {'chat_id': zch, 'text': "<b>للأسف حدث خطأ في النظام الخارجي</b>", 'parse_mode': 'HTML', 'reply_markup': json.dumps({'inline_keyboard': [[{'text': '• عودة •', 'callback_data': 'back'}]]})})
            
        await zec(zfr, 'unlock')
        return

    if ztx and ztx != '/start':
        if not os.path.exists(zstf) and await zec(zfr, 'check'):
            await ze('sendMessage', {'chat_id': zch, 'text': "<b>مرحباً يا صديقي، يرجى تشغيل البوت والبدء في استكشاف الميزات المتوفرة</b>", 'parse_mode': 'HTML', 'reply_markup': json.dumps({'inline_keyboard': [[{'text': '• تشغيل •', 'callback_data': 'back'}]]})})
        return

# --- مسارات Quart المخصصة لـ الويب هوك السحابي ---

@app.route('/')
async def index():
    return "Bot is running perfectly via High-Performance Async Webhook!", 200

@app.route(f'/{z1}', methods=['POST'])
async def telegram_webhook():
    update = await request.get_json()
    if update:
        # معالجة فورية وتمرير الطلب في الخلفية لتفادي توقف الويب هوك (Timeout)
        asyncio.create_task(handle_telegram_update(update))
    return jsonify({'status': 'success'}), 200
        
