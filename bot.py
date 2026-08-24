from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Poll
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler, CallbackQueryHandler
from telegram.constants import ChatType
import json
import os
from datetime import datetime

# ====== الإعدادات ======
TOKEN = "8845301824:AAE02vGKIeP4pLNDD_aww1gwkMPf0lY1mQs"
ADMIN_IDS = ["7021041990", "8810965759", "7020921829"]

# ملفات التخزين
QUIZZES_FILE = "quizzes.json"
USERS_FILE = "users.json"
SETTINGS_FILE = "settings.json"
GROUPS_FILE = "groups.json"

# حالات المحادثة
TITLE, DESCRIPTION, OPTIONS, CORRECT_OPTION, DURATION, PREVIEW = range(6)

# ====== دوال التخزين ======
def load_json(file):
    if os.path.exists(file):
        with open(file, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_json(file, data):
    with open(file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_quizzes():
    return load_json(QUIZZES_FILE)

def save_quizzes(data):
    save_json(QUIZZES_FILE, data)

def load_users():
    return load_json(USERS_FILE)

def save_users(data):
    save_json(USERS_FILE, data)

def load_settings():
    settings = load_json(SETTINGS_FILE)
    if not settings:
        settings = {"allow_anonymous": True}
        save_json(SETTINGS_FILE, settings)
    return settings

def save_settings(data):
    save_json(SETTINGS_FILE, data)

def load_groups():
    return load_json(GROUPS_FILE)

def save_groups(data):
    save_json(GROUPS_FILE, data)

def is_admin(update):
    return str(update.effective_user.id) in ADMIN_IDS

def track_user(user):
    users = load_users()
    uid = str(user.id)
    if uid not in users:
        users[uid] = {"first_name": user.first_name or "بدون", "username": user.username or "", "total_messages": 0}
    users[uid]["total_messages"] = users[uid].get("total_messages", 0) + 1
    if user.username:
        users[uid]["username"] = user.username
    save_users(users)

def track_group(chat):
    if chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]:
        groups = load_groups()
        gid = str(chat.id)
        if gid not in groups:
            groups[gid] = {"title": chat.title or "بدون"}
            save_groups(groups)

# ====== لوحة المفاتيح الرئيسية ======
def build_admin_keyboard():
    keyboard = [
        [InlineKeyboardButton("📝 إنشاء اختبار", callback_data="new_quiz")],
        [InlineKeyboardButton("🌐 المجموعات", callback_data="list_groups")],
        [InlineKeyboardButton("⚙️ الإعدادات", callback_data="settings")],
        [InlineKeyboardButton("👥 المستخدمون", callback_data="list_users")],
        [InlineKeyboardButton("📊 الإحصائيات", callback_data="stats")],
    ]
    return InlineKeyboardMarkup(keyboard)

# ====== الأوامر الأساسية ======
async def start(update, context):
    track_user(update.effective_user)
    if update.effective_chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]:
        track_group(update.effective_chat)
        await update.message.reply_text("👋 أهلاً! أنا بوت الاختبارات.\nأرسل /start في الخاص للتحكم.")
        return
    if is_admin(update):
        await update.message.reply_text("🔐 **لوحة تحكم المسؤول**\n\nاختر من الأزرار:", reply_markup=build_admin_keyboard(), parse_mode='Markdown')
    else:
        await update.message.reply_text("🎯 **مرحباً بك!**\n\nهذا البوت مخصص للمسؤولين.")

async def help_command(update, context):
    await update.message.reply_text("/start - بدء\n/newquiz - اختبار جديد\n/admin - لوحة التحكم")

async def admin_command(update, context):
    if not is_admin(update):
        return
    await update.message.reply_text("🔐 **لوحة التحكم:**", reply_markup=build_admin_keyboard(), parse_mode='Markdown')

# ====== معالج الأزرار الرئيسي ======
async def button_handler(update, context):
    query = update.callback_query
    await query.answer()
    data = query.data
    track_user(update.effective_user)
    if not is_admin(update):
        await query.answer("🚫 للمسؤولين فقط", show_alert=True)
        return ConversationHandler.END
    if data == "new_quiz":
        await query.message.reply_text("✍️ أرسل عنوان الاختبار:")
        return TITLE
    elif data == "list_users":
        users = load_users()
        if not users:
            await query.message.reply_text("لا يوجد مستخدمون.")
            return ConversationHandler.END
        text = "👥 **المستخدمون:**\n\n"
        for uid, u in users.items():
            username = f"@{u['username']}" if u.get('username') else "بدون"
            text += f"• {u['first_name']} ({username}) - ID: {uid}\n"
        await query.message.reply_text(text, parse_mode='Markdown')
        return ConversationHandler.END
    elif data == "stats":
        quizzes = load_quizzes()
        users = load_users()
        groups = load_groups()
        total = sum(q.get('participants', 0) for q in quizzes.values())
        await query.message.reply_text(f"📊 الاختبارات: {len(quizzes)}\nالمستخدمون: {len(users)}\nالمجموعات: {len(groups)}\nالمشاركون: {total}")
        return ConversationHandler.END
    elif data == "list_groups":
        groups = load_groups()
        if not groups:
            await query.message.reply_text("لا توجد مجموعات مسجلة.\nأضف البوت إلى مجموعة وأرسل /start فيها.")
            return ConversationHandler.END
        text = "🌐 **المجموعات:**\n\n"
        for gid, g in groups.items():
            text += f"• {g['title']} - ID: {gid}\n"
        await query.message.reply_text(text, parse_mode='Markdown')
        return ConversationHandler.END
    elif data == "settings":
        settings = load_settings()
        status = "مفعل ✅" if settings.get("allow_anonymous") else "معطل ❌"
        keyboard = [
            [InlineKeyboardButton(f"🔄 الاستفتاء السري: {status}", callback_data="toggle_anonymous")],
            [InlineKeyboardButton("📖 الأوامر", callback_data="show_commands")],
            [InlineKeyboardButton("↩️ رجوع", callback_data="back_admin")]
        ]
        await query.message.reply_text(f"⚙️ **الإعدادات:**\n\nالاستفتاء السري: {status}", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        return ConversationHandler.END
    elif data == "toggle_anonymous":
        settings = load_settings()
        settings["allow_anonymous"] = not settings.get("allow_anonymous", True)
        save_settings(settings)
        status = "مفعل ✅" if settings["allow_anonymous"] else "معطل ❌"
        keyboard = [
            [InlineKeyboardButton(f"🔄 الاستفتاء السري: {status}", callback_data="toggle_anonymous")],
            [InlineKeyboardButton("📖 الأوامر", callback_data="show_commands")],
            [InlineKeyboardButton("↩️ رجوع", callback_data="back_admin")]
        ]
        await query.message.edit_text(f"⚙️ **الإعدادات:**\n\nالاستفتاء السري: {status}", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        return ConversationHandler.END
    elif data == "show_commands":
        await query.message.reply_text("📖 **الأوامر:**\n/start - لوحة التحكم\n/newquiz - اختبار جديد\n/admin - لوحة التحكم\n/help - مساعدة")
        return ConversationHandler.END
    elif data == "back_admin":
        await query.message.edit_text("🔐 **لوحة التحكم:**", reply_markup=build_admin_keyboard(), parse_mode='Markdown')
        return ConversationHandler.END
    return ConversationHandler.END

# ====== إنشاء الاختبار ======
async def new_quiz_command(update, context):
    if not is_admin(update):
        return ConversationHandler.END
    await update.message.reply_text("✍️ أرسل عنوان الاختبار:")
    return TITLE

async def get_title(update, context):
    context.user_data['title'] = update.message.text
    keyboard = [[InlineKeyboardButton("⏭️ تخطي الوصف", callback_data="skip_description")]]
    await update.message.reply_text("📝 أرسل وصف الاختبار (اختياري):", reply_markup=InlineKeyboardMarkup(keyboard))
    return DESCRIPTION

async def skip_description(update, context):
    query = update.callback_query
    await query.answer()
    context.user_data['description'] = ""
    await query.message.reply_text("🔢 أرسل الخيارات (كل خيار في سطر):")
    return OPTIONS

async def get_description(update, context):
    context.user_data['description'] = update.message.text
    await query.message.reply_text("🔢 أرسل الخيارات (كل خيار في سطر):")
    return OPTIONS

async def get_options(update, context):
    options = [line.strip() for line in update.message.text.split('\n') if line.strip()]
    if len(options) < 2:
        await query.message.reply_text("⚠️ خياران على الأقل!")
        return OPTIONS
    context.user_data['options'] = options
    keyboard = []
    for i, opt in enumerate(options):
        keyboard.append([InlineKeyboardButton(f"✔️ {opt}", callback_data=f"correct_{i}")])
    keyboard.append([InlineKeyboardButton("⏭️ بدون إجابة صحيحة", callback_data="no_correct")])
    await query.message.reply_text("✅ اختر الإجابة الصحيحة:", reply_markup=InlineKeyboardMarkup(keyboard))
    return CORRECT_OPTION

async def correct_answer_handler(update, context):
    query = update.callback_query
    await query.answer()
    data = query.data
    if data == "no_correct":
        context.user_data['correct_option'] = None
    else:
        context.user_data['correct_option'] = int(data.replace("correct_", ""))
    keyboard = [
        [InlineKeyboardButton("⏱️ 30 ثانية", callback_data="duration_30")],
        [InlineKeyboardButton("⏱️ دقيقة", callback_data="duration_60")],
        [InlineKeyboardButton("⏱️ دقيقتان", callback_data="duration_120")],
        [InlineKeyboardButton("⏱️ 5 دقائق", callback_data="duration_300")],
        [InlineKeyboardButton("⏱️ 10 دقائق", callback_data="duration_600")],
    ]
    await query.message.reply_text("⏳ اختر مدة الاختبار:", reply_markup=InlineKeyboardMarkup(keyboard))
    return DURATION

async def duration_handler(update, context):
    query = update.callback_query
    await query.answer()
    duration = int(query.data.replace("duration_", ""))
    context.user_data['duration'] = duration
    quiz_id = datetime.now().strftime("%Y%m%d%H%M%S")
    quizzes = load_quizzes()
    quizzes[quiz_id] = {
        'title': context.user_data['title'],
        'description': context.user_data.get('description', ''),
        'options': context.user_data['options'],
        'correct_option': context.user_data.get('correct_option'),
        'duration': duration,
        'participants': 0
    }
    save_quizzes(quizzes)
    context.user_data['quiz_id'] = quiz_id
    preview_text = f"📋 **معاينة:**\n\n❓ {context.user_data['title']}\n"
    if context.user_data.get('description'):
        preview_text += f"📝 {context.user_data['description']}\n"
    preview_text += f"⏱️ {duration} ثانية\n"
    keyboard = [
        [InlineKeyboardButton("🚀 بدء هنا", callback_data="start_here")],
        [InlineKeyboardButton("📤 بدء في مجموعة", callback_data="share_quiz")],
        [InlineKeyboardButton("➕ سؤال آخر", callback_data="new_quiz")]
    ]
    await query.message.reply_text(preview_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    return PREVIEW

async def preview_handler(update, context):
    query = update.callback_query
    await query.answer()
    data = query.data
    quiz_id = context.user_data.get('quiz_id')
    if data == "start_here":
        if quiz_id:
            await send_poll(query.message.chat_id, context, quiz_id)
            await query.message.reply_text("✅ تم بدء الاختبار!")
        return ConversationHandler.END
    elif data == "share_quiz":
        groups = load_groups()
        if not groups:
            await query.message.reply_text("لا توجد مجموعات مسجلة.\nأضف البوت إلى مجموعة وأرسل /start فيها.")
            return ConversationHandler.END
        keyboard = []
        for gid, g in groups.items():
            keyboard.append([InlineKeyboardButton(f"📤 {g['title']}", callback_data=f"sendgroup_{gid}_{quiz_id}")])
        keyboard.append([InlineKeyboardButton("↩️ رجوع", callback_data="back_to_preview")])
        await query.message.reply_text("🌐 اختر المجموعة:", reply_markup=InlineKeyboardMarkup(keyboard))
        return PREVIEW
    elif data == "new_quiz":
        await query.message.reply_text("✍️ أرسل عنوان الاختبار الجديد:")
        return TITLE
    elif data == "back_to_preview":
        quiz_id = context.user_data.get('quiz_id')
        if quiz_id:
            quizzes = load_quizzes()
            quiz = quizzes.get(quiz_id)
            if quiz:
                preview_text = f"📋 **معاينة:**\n\n❓ {quiz['title']}\n"
                if quiz.get('description'):
                    preview_text += f"📝 {quiz['description']}\n"
                preview_text += f"⏱️ {quiz['duration']} ثانية\n"
                keyboard = [
                    [InlineKeyboardButton("🚀 بدء هنا", callback_data="start_here")],
                    [InlineKeyboardButton("📤 بدء في مجموعة", callback_data="share_quiz")],
                    [InlineKeyboardButton("➕ سؤال آخر", callback_data="new_quiz")]
                ]
                await query.message.edit_text(preview_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        return PREVIEW
    elif data.startswith("sendgroup_"):
        parts = data.split("_")
        if len(parts) >= 3:
            group_id = parts[1]
            quiz_id = parts[2]
            try:
                await send_poll(group_id, context, quiz_id)
                await query.message.reply_text("✅ تم إرسال الاختبار إلى المجموعة وبدءه.")
            except Exception as e:
                await query.message.reply_text(f"❌ فشل الإرسال: {e}")
        return ConversationHandler.END
    return ConversationHandler.END

async def send_poll(chat_id, context, quiz_id):
    quizzes = load_quizzes()
    quiz = quizzes.get(quiz_id)
    if not quiz:
        return
    settings = load_settings()
    options = quiz['options']
    correct_option = quiz.get('correct_option')
    duration = quiz.get('duration', 60)
    is_anonymous = settings.get('allow_anonymous', True)
    if correct_option is not None:
        await context.bot.send_poll(
            chat_id=chat_id,
            question=quiz['title'],
            options=options,
            type=Poll.QUIZ,
            correct_option_id=correct_option,
            explanation=quiz.get('description', ''),
            is_anonymous=is_anonymous,
            open_period=duration
        )
    else:
        await context.bot.send_poll(
            chat_id=chat_id,
            question=quiz['title'],
            options=options,
            is_anonymous=is_anonymous,
            open_period=duration
        )
    quiz['participants'] = quiz.get('participants', 0) + 1
    save_quizzes(quizzes)

async def cancel(update, context):
    await update.message.reply_text("تم الإلغاء.")
    return ConversationHandler.END

def main():
    app = Application.builder().token(TOKEN).build()
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('newquiz', new_quiz_command), CallbackQueryHandler(button_handler)],
        states={
            TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_title)],
            DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_description), CallbackQueryHandler(skip_description, pattern="^skip_description$")],
            OPTIONS: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_options)],
            CORRECT_OPTION: [CallbackQueryHandler(correct_answer_handler, pattern="^(correct_|no_correct)")],
            DURATION: [CallbackQueryHandler(duration_handler, pattern="^duration_")],
            PREVIEW: [CallbackQueryHandler(preview_handler, pattern="^(start_here|share_quiz|new_quiz|back_to_preview|sendgroup_)")],
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('help', help_command))
    app.add_handler(CommandHandler('admin', admin_command))
    app.add_handler(conv_handler)
    app.add_handler(CallbackQueryHandler(button_handler))
    print("البوت يعمل الآن...")
    app.run_polling()

if __name__ == "__main__":
    main()
