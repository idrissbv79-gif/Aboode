import logging
import random
import string
import os
from flask import Flask
from threading import Thread
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters

# ==================== إعداد Flask ====================
app_flask = Flask(__name__)

@app_flask.route('/')
def home():
    return "🤖 البوت يعمل بنجاح!"

def run_flask():
    app_flask.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

# ==================== إعداد البوت ====================
TOKEN = "8295766685:AAHSJwEBAF5zIXdPIFq6AaNoOB_-UEwMO5E"

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

users_data = {}
waiting_queue = []
invite_codes = {}

def generate_invite_code():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

async def show_main_menu(update_or_context):
    menu = "🏠 *القائمة الرئيسية*\n➖➖➖➖➖➖➖➖➖\n👇 اختر أحد الخيارات:"
    keyboard = [
        [InlineKeyboardButton("🔍 بحث عن شريك", callback_data='find_partner')],
        [InlineKeyboardButton("🎫 إنشاء كود دعوة", callback_data='gen_code')],
        [InlineKeyboardButton("📥 إدخال كود دعوة", callback_data='enter_code')],
        [InlineKeyboardButton("🚪 إنهاء المحادثة", callback_data='exit')],
        [InlineKeyboardButton("⏹️ إلغاء البحث", callback_data='stop_search')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    if hasattr(update_or_context, 'message'):
        await update_or_context.message.reply_text(menu, reply_markup=reply_markup, parse_mode='Markdown')
    else:
        await update_or_context.callback_query.message.edit_text(menu, reply_markup=reply_markup, parse_mode='Markdown')

async def add_to_waiting_queue(user_id, context):
    if user_id not in users_data:
        return False
    if users_data[user_id].get('partner'):
        return False
    if user_id in waiting_queue:
        return False
    waiting_queue.append(user_id)
    users_data[user_id]['in_queue'] = True
    await context.bot.send_message(
        user_id,
        "✅ *تم وضعك في قائمة الانتظار!*\n➖➖➖➖➖➖➖➖➖\n🔍 أنت الآن في قائمة الانتظار.\n⚡ عندما يضغط شخص آخر على 'بحث'، سيتم ربطك به *فوراً*!",
        parse_mode='Markdown'
    )
    logging.info(f"✅ المستخدم {user_id} تمت إضافته لقائمة الانتظار (العدد: {len(waiting_queue)})")
    return True

async def find_and_match(user_id, context):
    if user_id not in users_data:
        return False, None, "⚠️ الرجاء استخدام /start أولاً"
    if users_data[user_id].get('partner'):
        return False, None, "⚠️ أنت بالفعل في محادثة!"
    if user_id in waiting_queue:
        waiting_queue.remove(user_id)
        users_data[user_id]['in_queue'] = False
    for i, partner_id in enumerate(waiting_queue):
        if partner_id != user_id and not users_data[partner_id].get('partner'):
            partner_id = waiting_queue.pop(i)
            users_data[user_id]['partner'] = partner_id
            users_data[partner_id]['partner'] = user_id
            users_data[user_id]['in_queue'] = False
            users_data[partner_id]['in_queue'] = False
            await context.bot.send_message(
                partner_id,
                "🎉 *تم العثور على شريك!*\n➖➖➖➖➖➖➖➖➖\n✅ شخص آخر يريد الدردشة معك!\n💬 ابدأ الدردشة الآن!",
                parse_mode='Markdown'
            )
            await context.bot.send_message(
                user_id,
                "🎉 *تم العثور على شريك!*\n➖➖➖➖➖➖➖➖➖\n✅ ابدأ الدردشة الآن!\n📤 رسائلك ستصل *فوراً*",
                parse_mode='Markdown'
            )
            logging.info(f"🔗 تم ربط {user_id} مع {partner_id}")
            return True, partner_id, "✅ تم العثور على شريك!"
    if user_id not in waiting_queue:
        waiting_queue.append(user_id)
        users_data[user_id]['in_queue'] = True
    return False, None, "⏳ لا يوجد شريك حالياً. تم إضافتك لقائمة الانتظار."

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in users_data:
        keyboard = [[
            InlineKeyboardButton("♂️ ذكر", callback_data='gender_male'),
            InlineKeyboardButton("♀️ أنثى", callback_data='gender_female')
        ]]
        await update.message.reply_text(
            "👋 *أهلاً بك في بوت الدردشة الآمنة!*\n➖➖➖➖➖➖➖➖➖\n📌 يرجى اختيار جنسك للبدء:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        return
    await add_to_waiting_queue(user_id, context)
    await show_main_menu(update)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = update.effective_user.id
    await query.answer()
    if query.data.startswith('gender_'):
        gender = query.data.split('_')[1]
        users_data[user_id] = {'gender': gender, 'partner': None, 'invite_code': None, 'in_queue': False}
        await query.edit_message_text(
            f"✅ *تم تسجيلك كـ {'ذكر' if gender == 'male' else 'أنثى'}.*\n🎉 أهلاً بك في الدردشة الآمنة!",
            parse_mode='Markdown'
        )
        await add_to_waiting_queue(user_id, context)
        await show_main_menu(query)
        return
    elif query.data == 'find_partner':
        if user_id not in users_data:
            await query.edit_message_text("⚠️ الرجاء استخدام /start أولاً")
            return
        if users_data[user_id].get('partner'):
            await query.edit_message_text("⚠️ *أنت بالفعل في محادثة!*\n🚪 استخدم 'إنهاء المحادثة' أولاً.", parse_mode='Markdown')
            return
        matched, partner_id, message = await find_and_match(user_id, context)
        if matched:
            await query.edit_message_text(f"🎉 {message}\n💬 ابدأ الدردشة الآن!", parse_mode='Markdown')
        else:
            await query.edit_message_text(f"{message}\n➖➖➖➖➖➖➖➖➖\n🔄 سيتم ربطك *فوراً* عند دخول مستخدم جديد.", parse_mode='Markdown')
    elif query.data == 'stop_search':
        if user_id in waiting_queue:
            waiting_queue.remove(user_id)
            users_data[user_id]['in_queue'] = False
            await query.edit_message_text("⏹️ *تم إلغاء البحث.*\n🔄 تم إزالتك من قائمة الانتظار.", parse_mode='Markdown')
        else:
            await query.edit_message_text("ℹ️ *أنت لست في قائمة الانتظار.*", parse_mode='Markdown')
        await show_main_menu(query)
    elif query.data == 'gen_code':
        if user_id not in users_data:
            await query.edit_message_text("⚠️ الرجاء استخدام /start أولاً")
            return
        old_code = users_data[user_id].get('invite_code')
        if old_code and old_code in invite_codes:
            del invite_codes[old_code]
        new_code = generate_invite_code()
        invite_codes[new_code] = {'creator_id': user_id, 'used': False}
        users_data[user_id]['invite_code'] = new_code
        copy_keyboard = [[InlineKeyboardButton(f"📋 انسخ الكود: {new_code}", callback_data=f'copy_{new_code}')]]
        await query.edit_message_text(
            f"🎫 *كود الدعوة:*\n`{new_code}`\n➖➖➖➖➖➖➖➖➖\n📤 أرسله لمن تريد الدردشة معه.",
            reply_markup=InlineKeyboardMarkup(copy_keyboard),
            parse_mode='Markdown'
        )
    elif query.data.startswith('copy_'):
        code = query.data.split('_')[1]
        await query.answer(f"✅ تم نسخ الكود: {code}", show_alert=True)
    elif query.data == 'enter_code':
        await query.edit_message_text("✏️ *أرسل كود الدعوة*", parse_mode='Markdown')
        context.user_data['waiting_for_code'] = True
    elif query.data == 'exit':
        partner_id = users_data[user_id].get('partner')
        if partner_id and partner_id in users_data:
            users_data[partner_id]['partner'] = None
            users_data[partner_id]['in_queue'] = False
            await context.bot.send_message(
                partner_id,
                "🚪 *انتهت المحادثة.*\n🔄 يمكنك البحث عن شريك جديد.",
                parse_mode='Markdown'
            )
        users_data[user_id]['partner'] = None
        users_data[user_id]['in_queue'] = False
        if user_id in waiting_queue:
            waiting_queue.remove(user_id)
        await query.edit_message_text("✅ *تم إنهاء المحادثة.*", parse_mode='Markdown')
        await show_main_menu(query)

async def handle_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if context.user_data.get('waiting_for_code'):
        code = update.message.text.strip().upper()
        if code in invite_codes and not invite_codes[code]['used']:
            creator_id = invite_codes[code]['creator_id']
            if creator_id == user_id:
                await update.message.reply_text("❌ *لا يمكنك استخدام كودك الخاص!*", parse_mode='Markdown')
                return
            users_data[user_id]['partner'] = creator_id
            users_data[creator_id]['partner'] = user_id
            invite_codes[code]['used'] = True
            if user_id in waiting_queue:
                waiting_queue.remove(user_id)
            if creator_id in waiting_queue:
                waiting_queue.remove(creator_id)
            users_data[user_id]['in_queue'] = False
            users_data[creator_id]['in_queue'] = False
            await context.bot.send_message(
                creator_id,
                "🎉 *تم الاتصال عبر الكود!*\n✅ ابدأ الدردشة الآن!",
                parse_mode='Markdown'
            )
            await update.message.reply_text("✅ *تم الاتصال!*\n💬 ابدأ الدردشة الآن!", parse_mode='Markdown')
            context.user_data['waiting_for_code'] = False
            await show_main_menu(update)
        else:
            await update.message.reply_text("❌ *كود غير صحيح أو مستخدم!*", parse_mode='Markdown')
        return
    partner_id = users_data.get(user_id, {}).get('partner')
    if not partner_id:
        await update.message.reply_text("⚠️ *أنت غير متصل بشريك.*\n🔍 استخدم 'بحث عن شريك' للبدء.", parse_mode='Markdown')
        return
    if partner_id == user_id or partner_id not in users_data:
        users_data[user_id]['partner'] = None
        await update.message.reply_text("⚠️ *خطأ في الربط. جرب البحث مرة أخرى.*", parse_mode='Markdown')
        return
    try:
        if update.message.text:
            await context.bot.send_message(partner_id, update.message.text)
        elif update.message.photo:
            await context.bot.send_photo(partner_id, update.message.photo[-1].file_id)
        elif update.message.video:
            await context.bot.send_video(partner_id, update.message.video.file_id)
        elif update.message.document:
            await context.bot.send_document(partner_id, update.message.document.file_id)
        elif update.message.voice:
            await context.bot.send_voice(partner_id, update.message.voice.file_id)
        elif update.message.audio:
            await context.bot.send_audio(partner_id, update.message.audio.file_id)
        elif update.message.sticker:
            await context.bot.send_sticker(partner_id, update.message.sticker.file_id)
        elif update.message.animation:
            await context.bot.send_animation(partner_id, update.message.animation.file_id)
        elif update.message.location:
            await context.bot.send_location(partner_id, update.message.location.latitude, update.message.location.longitude)
    except Exception as e:
        await update.message.reply_text("❌ *خطأ في الإرسال.*", parse_mode='Markdown')
        logging.error(f"Error: {e}")

# ==================== تشغيل البوت ====================
if __name__ == '__main__':
    # تشغيل Flask في thread منفصل
    flask_thread = Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    
    # تشغيل البوت
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_messages))
    
    print("🤖 *البوت يعمل الآن...*")
    print("✅ *نظام البحث السريع:*")
    print("   • 📥 المستخدم الأول: /start → يضاف تلقائياً للقائمة")
    print("   • 🔍 المستخدم الثاني: يضغط 'بحث' → ربط فوري!")
    print("   • ⚡ سرعة فائقة في الربط")
    print(f"🌐 خادم Flask يعمل على المنفذ {os.environ.get('PORT', 8080)}")
    
    app.run_polling()
