from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Poll
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler, CallbackQueryHandler
from telegram.constants import ChatType
import json, os
from datetime import datetime

TOKEN = "8845301824:AAE02vGKIeP4pLNDD_aww1gwkMPf0lY1mQs"
ADMIN_ID = "7021041990"  # رقمك

# حالات المحادثة
TITLE, DESCRIPTION, OPTIONS, CORRECT_OPTION, DURATION, PREVIEW = range(6)

QUIZZES_FILE = "quizzes.json"
USERS_FILE = "users.json"
SETTINGS_FILE = "settings.json"

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

def save_quizzes(quizzes):
    save_json(QUIZZES_FILE, quizzes)

def load_users():
    return load_json(USERS_FILE)

def save_users(users):
    save_json(USERS_FILE, users)

def load_settings():
    settings = load_json(SETTINGS_FILE)
    if not settings:
        settings = {"bot_name": "بوت الاختبارات", "allow_anonymous": True}
        save_json(SETTINGS_FILE, settings)
    return settings

def is_admin(update: Update) -> bool:
    return str(update.effective_user.id) == ADMIN_ID

def track_user(user):
    users = load_users()
    uid = str(user.id)
    if uid not in users:
        users[uid] = {
            "first_name": user.first_name,
            "username": user.username,
            "last_seen": datetime.now().isoformat(),
            "total_messages": 0
        }
    users[uid]["last_seen"] = datetime.now().isoformat()
    users[uid]["total_messages"] = users[uid].get("total_messages", 0) + 1
    if user.username:
        users[uid]["username"] = user.username
    save_users(users)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    track_user(update.effective_user)
    if is_admin(update):
        keyboard = [
            [InlineKeyboardButton("📝 إنشاء اختبار جديد", callback_data="new_quiz")],
            [InlineKeyboardButton("📋 اختباراتي", callback_data="list_quizzes")],
            [InlineKeyboardButton("👥 المستخدمون", callback_data="list_users")],
            [InlineKeyboardButton("⚙️ الإعدادات", callback_data="settings")],
            [InlineKeyboardButton("📊 الإحصائيات", callback_data="stats")]
        ]
        await update.message.reply_text(
            "🔐 **لوحة تحكم المسؤول**\n\n"
            "مرحباً بك! اختر من الأزرار:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text(
            "🎯 **مرحباً بك في بوت الاختبارات!**\n\n"
            "أرسل /quiz لبدء اختبار جديد\n"
            "أو أرسل /help للمساعدة"
        )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    track_user(update.effective_user)
    await update.message.reply_text(
        "📖 **الأوامر المتاحة:**\n\n"
        "/start - الرئيسية\n"
        "/quiz - إنشاء اختبار (المسؤول فقط)\n"
        "/admin - لوحة التحكم (المسؤول فقط)\n"
        "/help - هذه المساعدة"
    )

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    track_user(update.effective_user)
    if not is_admin(update):
        await update.message.reply_text("🚫 هذا الأمر للمسؤول فقط")
        return
    keyboard = [
        [InlineKeyboardButton("📝 إنشاء اختبار", callback_data="new_quiz")],
        [InlineKeyboardButton("📋 الاختبارات", callback_data="list_quizzes")],
        [InlineKeyboardButton("👥 المستخدمون", callback_data="list_users")],
        [InlineKeyboardButton("⚙️ الإعدادات", callback_data="settings")],
        [InlineKeyboardButton("📊 الإحصائيات", callback_data="stats")]
    ]
    await update.message.reply_text(
        "🔐 **لوحة التحكم:**",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    track_user(update.effective_user)

    if data == "new_quiz":
        if not is_admin(update):
            await query.answer("🚫 للمسؤول فقط", show_alert=True)
            return ConversationHandler.END
        await query.message.reply_text("✍️ أرسل عنوان الاختبار:")
        return TITLE

    elif data == "list_quizzes":
        quizzes = load_quizzes()
        if not quizzes:
            await query.message.reply_text("لا توجد اختبارات.")
            return ConversationHandler.END
        text = "📋 **الاختبارات:**\n\n"
        for qid, q in quizzes.items():
            text += f"• {q['title']} (👥 {q.get('participants', 0)})\n"
        await query.message.reply_text(text, parse_mode='Markdown')
        return ConversationHandler.END

    elif data == "list_users":
        if not is_admin(update):
            await query.answer("🚫 للمسؤول فقط", show_alert=True)
            return ConversationHandler.END
        users = load_users()
        if not users:
            await query.message.reply_text("لا يوجد مستخدمون بعد.")
            return ConversationHandler.END
        text = "👥 **المستخدمون:**\n\n"
        for uid, u in users.items():
            username = f"@{u['username']}" if u.get('username') else "بدون"
            text += f"• {u['first_name']} ({username}) - ID: {uid}\n"
        await query.message.reply_text(text, parse_mode='Markdown')
        return ConversationHandler.END

    elif data == "stats":
        if not is_admin(update):
            await query.answer("🚫 للمسؤول فقط", show_alert=True)
            return ConversationHandler.END
        quizzes = load_quizzes()
        users = load_users()
        total_participants = sum(q.get('participants', 0) for q in quizzes.values())
        await query.message.reply_text(
            f"📊 **الإحصائيات:**\n\n"
            f"عدد الاختبارات: {len(quizzes)}\n"
            f"عدد المستخدمين: {len(users)}\n"
            f"إجمالي المشاركين: {total_participants}",
            parse_mode='Markdown'
        )
        return ConversationHandler.END

    elif data == "settings":
        if not is_admin(update):
            await query.answer("🚫 للمسؤول فقط", show_alert=True)
            return ConversationHandler.END
        settings = load_settings()
        keyboard = [
            [InlineKeyboardButton("🔄 تبديل: " + ("سري ✅" if settings.get("allow_anonymous") else "علني ❌"), callback_data="toggle_anonymous")],
            [InlineKeyboardButton("↩️ رجوع", callback_data="back_admin")]
        ]
        await query.message.reply_text(
            f"⚙️ **الإعدادات:**\n\n"
            f"اسم البوت: {settings.get('bot_name', '')}\n"
            f"الاستفتاء السري: {'مفعل ✅' if settings.get('allow_anonymous') else 'معطل ❌'}",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        return ConversationHandler.END

    elif data == "toggle_anonymous":
        if not is_admin(update):
            return ConversationHandler.END
        settings = load_settings()
        settings["allow_anonymous"] = not settings.get("allow_anonymous", True)
        save_json(SETTINGS_FILE, settings)
        await query.answer("تم التحديث ✅")
        keyboard = [
            [InlineKeyboardButton("🔄 تبديل: " + ("سري ✅" if settings["allow_anonymous"] else "علني ❌"), callback_data="toggle_anonymous")],
            [InlineKeyboardButton("↩️ رجوع", callback_data="back_admin")]
        ]
        await query.message.edit_text(
            f"⚙️ **الإعدادات:**\n\n"
            f"الاستفتاء السري: {'مفعل ✅' if settings['allow_anonymous'] else 'معطل ❌'}",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        return ConversationHandler.END

    elif data == "back_admin":
        keyboard = [
            [InlineKeyboardButton("📝 إنشاء اختبار", callback_data="new_quiz")],
            [InlineKeyboardButton("📋 الاختبارات", callback_data="list_quizzes")],
            [InlineKeyboardButton("👥 المستخدمون", callback_data="list_users")],
            [InlineKeyboardButton("⚙️ الإعدادات", callback_data="settings")],
            [InlineKeyboardButton("📊 الإحصائيات", callback_data="stats")]
        ]
        await query.message.edit_text(
            "🔐 **لوحة التحكم:**",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        return ConversationHandler.END

    return ConversationHandler.END

async def get_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    track_user(update.effective_user)
    if not is_admin(update):
        return ConversationHandler.END
    context.user_data['title'] = update.message.text
    keyboard = [[InlineKeyboardButton("⏭️ تخطي الوصف", callback_data="skip_description")]]
    await update.message.reply_text(
        "📝 أرسل الوصف (اختياري):",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return DESCRIPTION

async def skip_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['description'] = ""
    await query.message.reply_text(
        "🔢 أرسل الخيارات (كل خيار في سطر):\n\n"
        "مثال:\nباريس\nلندن\nمدريد"
    )
    return OPTIONS

async def get_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    track_user(update.effective_user)
    context.user_data['description'] = update.message.text
    await update.message.reply_text(
        "🔢 أرسل الخيارات (كل خيار في سطر):\n\n"
        "مثال:\nباريس\nلندن\nمدريد"
    )
    return OPTIONS

async def get_options(update: Update, context: ContextTypes.DEFAULT_TYPE):
    track_user(update.effective_user)
    options = [line.strip() for line in update.message.text.split('\n') if line.strip()]
    if len(options) < 2:
        await update.message.reply_text("⚠️ خياران على الأقل!")
        return OPTIONS
    if len(options) > 10:
        await update.message.reply_text("⚠️ الحد الأقصى 10!")
        return OPTIONS
    context.user_data['options'] = options
    keyboard = []
    for i, opt in enumerate(options):
        keyboard.append([InlineKeyboardButton(f"✔️ {opt}", callback_data=f"correct_{i}")])
    keyboard.append([InlineKeyboardButton("⏭️ بدون إجابة صحيحة", callback_data="no_correct")])
    await update.message.reply_text(
        "✅ اختر الإجابة الصحيحة:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return CORRECT_OPTION

async def correct_answer_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
    await query.message.reply_text(
        "⏳ اختر مدة الاختبار:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return DURATION

async def duration_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
        'created_by': query.from_user.id,
        'participants': 0,
        'created_at': datetime.now().isoformat()
    }
    save_quizzes(quizzes)
    context.user_data['quiz_id'] = quiz_id

    preview_text = f"📋 **معاينة:**\n\n"
    preview_text += f"❓ {context.user_data['title']}\n"
    if context.user_data.get('description'):
        preview_text += f"📝 {context.user_data['description']}\n"
    preview_text += f"⏱️ {duration} ثانية\n"

    keyboard = [
        [InlineKeyboardButton("🚀 بدء الاختبار هنا", callback_data="start_here")],
        [InlineKeyboardButton("📤 مشاركة للمجموعات", callback_data="share_quiz")],
        [InlineKeyboardButton("➕ سؤال آخر", callback_data="new_quiz")]
    ]
    await query.message.reply_text(
        preview_text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )
    return PREVIEW

async def preview_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
        if quiz_id:
            quizzes = load_quizzes()
            quiz = quizzes.get(quiz_id)
            if quiz:
                share_text = f"🎯 **اختبار جديد!**\n\n❓ {quiz['title']}\n"
                if quiz['description']:
                    share_text += f"📝 {quiz['description']}\n"
                share_text += f"⏱️ {quiz['duration']} ثانية\n\n"
                share_text += "أرسل هذا الاختبار إلى أي مجموعة ثم اضغط الزر!"
                keyboard = [[InlineKeyboardButton("🚀 بدء الاختبار", callback_data=f"start_shared_{quiz_id}")]]
                await query.message.reply_text(
                    share_text,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode='Markdown'
                )
        return ConversationHandler.END

    elif data == "new_quiz":
        await query.message.reply_text("✍️ أرسل عنوان الاختبار الجديد:")
        return TITLE

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

async def shared_quiz_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    quiz_id = query.data.replace("start_shared_", "")
    await send_poll(query.message.chat_id, context, quiz_id)
    await query.message.reply_text("✅ تم بدء الاختبار!")

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("تم الإلغاء.")
    return ConversationHandler.END

def main():
    app = Application.builder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(button_handler, pattern="^(new_quiz|list_quizzes|list_users|stats|settings|toggle_anonymous|back_admin)$")],
        states={
            TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_title)],
            DESCRIPTION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_description),
                CallbackQueryHandler(skip_description, pattern="^skip_description$")
            ],
            OPTIONS: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_options)],
            CORRECT_OPTION: [CallbackQueryHandler(correct_answer_handler, pattern="^(correct_|no_correct)")],
            DURATION: [CallbackQueryHandler(duration_handler, pattern="^duration_")],
            PREVIEW: [CallbackQueryHandler(preview_handler, pattern="^(start_here|share_quiz|new_quiz)$")],
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )

    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('help', help_command))
    app.add_handler(CommandHandler('admin', admin_command))
    app.add_handler(conv_handler)
    app.add_handler(CallbackQueryHandler(shared_quiz_handler, pattern="^start_shared_"))

    print("البوت يعمل الآن...")
    app.run_polling()

if __name__ == "__main__":
    main()