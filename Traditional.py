import os
import json
import time
import hashlib
import asyncio
import logging
import aiohttp
from aiogram import Bot, Dispatcher, types, F
from aiogram.enums import ParseMode, ChatAction
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiohttp import web

# إعدادات تسجيل الأخطاء
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# --- المتغيرات الثابتة ---
TOKEN = os.getenv("BOT_TOKEN", "8334265486:AAFquScv4mkArgxUD4nkFV3usc_s3TNthlw")  # يفضل وضع التوكن في البيئة المتغيرة لـ Render
IMAGE_URL = 'https://t.me/Z_O_Z_0o0/36'  
API_URL = 'https://zecora0.serv00.net/ai/NanoBanana.php'  
STICKER_ID = 'CAACAgIAAxkBAAERGrpp6qpwhZeU1z7ksy3kgUrtPadzwAACQgEAAs0bMAgEAoCtK287vjsE'  

# القواميس والموديلات مترجمة للعربية
MODELS = {'NanoBanana': 'نانو بنانا', 'NanoBanana2': 'نانو بنانا 2', 'NanoBananaPro': 'نانو بنانا برو'}
RATIOS = {'1:1': '1:1', '1:4': '1:4', '1:8': '1:8', '2:3': '2:3', '3:2': '3:2', '3:4': '3:4', '4:1': '4:1', '4:3': '4:3', '4:5': '4:5', '5:4': '5:4', '8:1': '8:1', '9:16': '9:16', '16:9': '16:9', '21:9': '21:9', 'auto': 'تلقائي'}
RESOLUTIONS = {'1K': '1K', '2K': '2K', '4K': '4K'}

bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- ذاكرة تخزين مؤقتة متزامنة (بديلة لـ SQLite وملفات JSON لضمان التوافق التام مع Render) ---
USER_STATES = {}       # لحفظ حالات المستخدمين
PROCESSING_USERS = {}  # لمنع تكرار الضغط وقفل العمليات الجارية
REQUESTS_CACHE = {}    # لمنع السبام والطلبات المكررة السريعة

def get_user_state(user_id: int) -> dict:
    return USER_STATES.get(user_id, {})

def save_user_state(user_id: int, data: dict):
    USER_STATES[user_id] = data

def clear_user_state(user_id: int):
    USER_STATES.pop(user_id, None)

async def check_and_lock_user(user_id: int, action: str = 'check') -> bool:
    now = int(time.time())
    
    # تنظيف العمليات المعلقة لأكثر من 5 دقائق تلقائياً
    expired = [uid for uid, timestamp in PROCESSING_USERS.items() if timestamp < now - 300]
    for uid in expired:
        PROCESSING_USERS.pop(uid, None)
        
    if action == 'unlock':
        PROCESSING_USERS.pop(user_id, None)
        return True
        
    is_processing = user_id in PROCESSING_USERS
    
    if is_processing:
        return False
        
    if action == 'lock':
        PROCESSING_USERS[user_id] = now
        return True
    return True

async def check_duplicate_request(chat_id: int, text: str) -> bool:
    if not text:
        return False
    now = int(time.time())
    hash_val = hashlib.md5(f"{chat_id}_{text}".encode('utf-8')).hexdigest()
    
    # تنظيف الكاش القديم (أقدم من 5 ثوانٍ)
    expired = [h for h, timestamp in REQUESTS_CACHE.items() if timestamp < now - 5]
    for h in expired:
        REQUESTS_CACHE.pop(h, None)
        
    if hash_val in REQUESTS_CACHE:
        return True
        
    REQUESTS_CACHE[hash_val] = now
    return False

# --- دالة إرسال الأكشن المكرر ---
async def keep_sending_action(chat_id: int, action: ChatAction, stop_event: asyncio.Event):
    while not stop_event.is_set():
        try:
            await bot.send_chat_action(chat_id=chat_id, action=action)
            await asyncio.sleep(4)
        except:
            break

# --- الأزرار التلقائية المقسمة ---
def build_welcome_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="• تصميم صورة •", callback_data="create_image")
    builder.button(text="• تعديل صورة •", callback_data="edit_image")
    builder.adjust(2)
    return builder.as_markup()

# --- نصوص القائمة الترحيبية ---
WELCOME_CAPTION = (
    "<b>مرحباً أنا نانو بنانا <tg-emoji emoji-id=\"6003660622431001221\">👋</tg-emoji></b>\n"
    "<b>أقدم حلول ذكاء اصطناعي متطورة بأعلى معايير الجودة. <tg-emoji emoji-id=\"6003330781827570462\">👀</tg-emoji></b>\n"
    "<b>القيود والسلوك <tg-emoji emoji-id=\"6001423434096057208\">🤬</tg-emoji> :</b>\n"
    "<blockquote>• القيود: لا يُسمح بانتهاك الحقوق أو المواد المحمية.\n"
    "• قد تتطلب بعض الطلبات الدقيقة عدة تجارب للضبط والوصول للنتيجة المطلوبة.</blockquote>"
)

# --- معالجة الأوامر والرسائل ---

@dp.message(F.text == "/start")
async def cmd_start(message: types.Message):
    clear_user_state(message.from_user.id)
    await bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.TYPING)
    await message.answer_photo(
        photo=IMAGE_URL,
        caption=WELCOME_CAPTION,
        parse_mode=ParseMode.HTML,
        has_spoiler=True,
        reply_markup=build_welcome_keyboard()
    )

@dp.callback_query(F.data == "back")
async def cb_back(callback: types.CallbackQuery):
    clear_user_state(callback.from_user.id)
    try:
        await callback.message.delete()
    except:
        pass
    await bot.send_chat_action(chat_id=callback.message.chat.id, action=ChatAction.TYPING)
    await callback.message.answer_photo(
        photo=IMAGE_URL,
        caption=WELCOME_CAPTION,
        parse_mode=ParseMode.HTML,
        reply_markup=build_welcome_keyboard()
    )

@dp.callback_query(F.data.in_({"create_image", "edit_image"}))
async def cb_choose_mode(callback: types.CallbackQuery):
    mode = 'create' if callback.data == 'create_image' else 'edit'
    save_user_state(callback.from_user.id, {'mode': mode, 'step': 'choose_model'})
    
    txt = "<b>• اختر موديل الذكاء الاصطناعي :</b> <tg-emoji emoji-id=\"6003492753634237241\">😘</tg-emoji>"
    builder = InlineKeyboardBuilder()
    for k, v in MODELS.items():
        builder.button(text=v, callback_data=f"set_model|{k}")
    builder.adjust(2)
    builder.row(types.InlineKeyboardButton(text="• رجوع •", callback_data="back"))
    
    await callback.message.edit_caption(caption=txt, parse_mode=ParseMode.HTML, reply_markup=builder.as_markup())

@dp.callback_query(F.data.startswith("set_model|"))
async def cb_set_model(callback: types.CallbackQuery):
    model = callback.data.split('|')[1]
    state = get_user_state(callback.from_user.id)
    state['model'] = model
    state['step'] = 'choose_ratio'
    save_user_state(callback.from_user.id, state)
    
    txt = "<b>• اختر أبعاد الصورة :</b> <tg-emoji emoji-id=\"6003330781827570462\">👀</tg-emoji>"
    builder = InlineKeyboardBuilder()
    for k, v in RATIOS.items():
        builder.button(text=v, callback_data=f"set_ratio|{k}")
    builder.adjust(3)
    builder.row(types.InlineKeyboardButton(text="• رجوع •", callback_data="back"))
    
    await callback.message.edit_caption(caption=txt, parse_mode=ParseMode.HTML, reply_markup=builder.as_markup())

@dp.callback_query(F.data.startswith("set_ratio|"))
async def cb_set_ratio(callback: types.CallbackQuery):
    ratio = callback.data.split('|')[1]
    state = get_user_state(callback.from_user.id)
    state['ratio'] = ratio
    state['step'] = 'choose_res'
    save_user_state(callback.from_user.id, state)
    
    txt = "<b>• اختر الدقة والوضوح :</b> <tg-emoji emoji-id=\"6003675891039738414\">😅</tg-emoji>"
    builder = InlineKeyboardBuilder()
    for k, v in RESOLUTIONS.items():
        builder.button(text=v, callback_data=f"set_res|{k}")
    builder.adjust(2)
    builder.row(types.InlineKeyboardButton(text="• رجوع •", callback_data="back"))
    
    await callback.message.edit_caption(caption=txt, parse_mode=ParseMode.HTML, reply_markup=builder.as_markup())

@dp.callback_query(F.data.startswith("set_res|"))
async def cb_set_res(callback: types.CallbackQuery):
    resol = callback.data.split('|')[1]
    state = get_user_state(callback.from_user.id)
    state['res'] = resol
    
    if 'ratio' not in state: state['ratio'] = '1:1'
    if 'model' not in state: state['model'] = 'NanoBanana2'
    if 'mode' not in state:
        clear_user_state(callback.from_user.id)
        return
        
    mode = state['mode']
    state['step'] = 'awaiting_text' if mode == 'create' else 'awaiting_image'
    save_user_state(callback.from_user.id, state)
    
    model_name = MODELS.get(state['model'], state['model'])
    em_m = '<tg-emoji emoji-id="6001051949489724852">🌹</tg-emoji>' if mode == 'create' else '<tg-emoji emoji-id="6001102535614537900">🕺</tg-emoji>'
    em_a = '<tg-emoji emoji-id="6003470660322466579">👨‍💻</tg-emoji>' if mode == 'create' else '<tg-emoji emoji-id="6001111189973639198">😀</tg-emoji>'
    instruction = 'أرسل النص الآن ليتم تصميم صورتك' if mode == 'create' else 'قم بإرسال الصورة المراد تعديلها الآن'
    
    txt = f"<b>الموديل :</b> {model_name} {em_m}\n<b>الأبعاد :</b> {state['ratio']} | <b>الدقة :</b> {resol}\n\n<b>{instruction} {em_a}</b>"
    
    builder = InlineKeyboardBuilder()
    builder.button(text="• رجوع •", callback_data="back")
    
    await callback.message.edit_caption(caption=txt, parse_mode=ParseMode.HTML, reply_markup=builder.as_markup())

# --- استقبال رسائل المستخدمين والمزامنة مع الـ API الخارجي ---

@dp.message()
async def handle_all_messages(message: types.Message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    text = message.text
    
    if text == "/start":
        return

    if text:
        if await check_duplicate_request(chat_id, text):
            return

    if not await check_and_lock_user(user_id, 'check'):
        return

    state = get_user_state(user_id)
    step = state.get('step')
    mode = state.get('mode')

    # 1. حالة تصميم صورة جديدة
    if step == 'awaiting_text' and mode == 'create' and text:
        if not await check_and_lock_user(user_id, 'lock'): return
        
        current_state = state.copy()
        clear_user_state(user_id)
        
        model = current_state.get('model', 'NanoBanana2')
        ratio = current_state.get('ratio', '1:1')
        resol = current_state.get('res', '1K')
        api_model = 'NanoBanana2' if model == 'NanoBananaPro' else model
        
        sticker_msg = await message.answer_sticker(sticker=STICKER_ID)
        
        stop_action = asyncio.Event()
        action_task = asyncio.create_task(keep_sending_action(chat_id, ChatAction.UPLOAD_PHOTO, stop_action))
        
        payload = {'text': text, 'model': api_model, 'ratio': ratio, 'res': resol}
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(API_URL, data=payload, timeout=120) as resp:
                    status = resp.status
                    res_text = await resp.text()
            
            stop_action.set()
            await action_task
            if sticker_msg: await sticker_msg.delete()
            
            if status == 200 and res_text:
                res_data = json.loads(res_text)
                if res_data.get('success') and res_data.get('url'):
                    m_name = MODELS.get(current_state.get('model'), current_state.get('model'))
                    caption = f"<b>الموديل: {m_name} <tg-emoji emoji-id=\"6001051949489724852\">🌹</tg-emoji>\nالأبعاد: {ratio} | الدقة: {res_data.get('resolution')}</b>"
                    
                    builder = InlineKeyboardBuilder()
                    builder.button(text="• رجوع •", callback_data="back")
                    
                    await message.answer_photo(photo=res_data.get('url'), caption=caption, parse_mode=ParseMode.HTML, has_spoiler=True, reply_markup=builder.as_markup())
                else:
                    raise Exception()
            else:
                raise Exception()
        except:
            stop_action.set()
            if sticker_msg: 
                try: await sticker_msg.delete()
                except: pass
            builder = InlineKeyboardBuilder()
            builder.button(text="• رجوع •", callback_data="back")
            await message.answer("<b>حدث خطأ غير متوقع أثناء معالجة طلبك <tg-emoji emoji-id=\"6001087142451748852\">😔</tg-emoji></b>", parse_mode=ParseMode.HTML, reply_markup=builder.as_markup())
            
        await check_and_lock_user(user_id, 'unlock')
        return

    # 2. حالة استقبال الصورة المراد تعديلها
    if step == 'awaiting_image' and mode == 'edit' and message.photo:
        await bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
        file_id = message.photo[-1].file_id
        file_info = await bot.get_file(file_id)
        
        if file_info and file_info.file_path:
            img_link = f"https://api.telegram.org/file/bot{TOKEN}/{file_info.file_path}"
            state['image'] = img_link
            state['step'] = 'awaiting_text_edit'
            save_user_state(user_id, state)
            
            builder = InlineKeyboardBuilder()
            builder.button(text="• رجوع •", callback_data="back")
            await message.answer("<b>تم استلام الصورة بنجاح! أرسل الآن نص التعديلات المطلوبة عليها <tg-emoji emoji-id=\"6003646513463434273\">😀</tg-emoji></b>", parse_mode=ParseMode.HTML, reply_markup=builder.as_markup())
        return

    # 3. حالة استقبال نص التعديل بعد استقبال الصورة
    if step == 'awaiting_text_edit' and mode == 'edit' and text and 'image' in state:
        if not await check_and_lock_user(user_id, 'lock'): return
        
        current_state = state.copy()
        clear_user_state(user_id)
        
        model = current_state.get('model', 'NanoBanana2')
        ratio = current_state.get('ratio', '1:1')
        resol = current_state.get('res', '1K')
        api_model = 'NanoBanana2' if model == 'NanoBananaPro' else model
        
        sticker_msg = await message.answer_sticker(sticker=STICKER_ID)
        
        stop_action = asyncio.Event()
        action_task = asyncio.create_task(keep_sending_action(chat_id, ChatAction.UPLOAD_PHOTO, stop_action))
        
        payload = {'text': text, 'model': api_model, 'links': current_state['image'], 'ratio': ratio, 'res': resol}
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(API_URL, data=payload, timeout=120) as resp:
                    status = resp.status
                    res_text = await resp.text()
                    
            stop_action.set()
            await action_task
            if sticker_msg: await sticker_msg.delete()
            
            if status == 200 and res_text:
                res_data = json.loads(res_text)
                if res_data.get('success') and res_data.get('url'):
                    m_name = MODELS.get(current_state.get('model'), current_state.get('model'))
                    caption = f"<b>الموديل: {m_name} <tg-emoji emoji-id=\"6001051949489724852\">🌹</tg-emoji>\nالأبعاد: {ratio} | الدقة: {res_data.get('resolution')}</b>"
                    
                    builder = InlineKeyboardBuilder()
                    builder.button(text="• رجوع •", callback_data="back")
                    
                    await message.answer_photo(photo=res_data.get('url'), caption=caption, parse_mode=ParseMode.HTML, has_spoiler=True, reply_markup=builder.as_markup())
                else:
                    raise Exception()
            else:
                raise Exception()
        except:
            stop_action.set()
            if sticker_msg: 
                try: await sticker_msg.delete()
                except: pass
            builder = InlineKeyboardBuilder()
            builder.button(text="• رجوع •", callback_data="back")
            await message.answer("<b>حدث خطأ غير متوقع أثناء تعديل الصورة <tg-emoji emoji-id=\"6001436301818076004\">😱</tg-emoji></b>", parse_mode=ParseMode.HTML, reply_markup=builder.as_markup())
            
        await check_and_lock_user(user_id, 'unlock')
        return

    if text != '/start':
        if user_id not in USER_STATES:
            await bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
            builder = InlineKeyboardBuilder()
            builder.button(text="• ابدأ الآن •", callback_data="back")
            await message.answer("<b>مرحباً بك يا صديقي! تفضل بتشغيل البوت لتستمتع بوقتك وتصاميمك <tg-emoji emoji-id=\"6001524374417447769\">😛</tg-emoji></b>", parse_mode=ParseMode.HTML, reply_markup=builder.as_markup())

# --- خادم ويب وهمي لـ Render لمنع الـ Timeout خطأ البورت ---
async def handle_health_check(request):
    return web.Response(text="Bot is running smoothly!", status=200)

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle_health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    # جلب البورت التلقائي الذي تفرضه منصة Render
    port = int(os.getenv("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    print(f"خادم الوهمي يعمل ويستمع على المنفذ: {port}")

# --- نقطة انطلاق التطبيق ---
async def main():
    # تشغيل سيرفر الويب والبوت معاً بشكل متوازي
    await start_web_server()
    print("البوت يعمل الآن بنظام المهام غير المتزامنة ومستعد لـ Render...")
    await dp.start_polling(bot)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("تم إيقاف البوت.")
              
