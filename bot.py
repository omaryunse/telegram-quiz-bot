from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Poll
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler, CallbackQueryHandler
from telegram.constants import ChatType
import json, os
from datetime import datetime

# ========== الإعدادات ==========
TOKEN = "8845301824:AAE02vGKIeP4pLNDD_aww1gwkMPf0lY1mQs"
MAIN_ADMIN_ID = "7021041990"  # رقمك كمسؤول رئيسي

# ملفات التخزين
QUIZZES_FILE = "quizzes.json"
USERS_FILE = "users.json"
SETTINGS_FILE = "settings.json"

# حالات المحادثة
TITLE, DESCRIPTION, OPTIONS, CORRECT_OPTION, DURATION, PREVIEW = range(6)

# ========== دوال التخزين ==========
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
        settings = {
            "allow_anonymous": True,
            "bot_name": "بوت الاختبارات",
            "admin_ids": [MAIN_ADMIN_ID]
        }
        save_json(SETTINGS_FILE, settings)
    return settings

def save_settings(settings):
    save_json(SETTINGS_FILE, settings)

# ========== دوال الصلاحيات ==========
def get_admin_ids():
    settings = load_settings()
    return settings.get("admin_ids", [MAIN_ADMIN_ID])

def is_admin(update: Update) -> bool:
    user_id = str(update.effective_user.id)
    return user_id in get_admin_ids()

def is_main_admin(update: Update) -> bool:
    return str(update.effective_user.id) == MAIN_ADMIN_ID

def add_admin_id(user_id):
    settings = load_settings()
    if user_id not in settings.get("admin_ids", []):
        settings["admin_ids"] = settings.get("admin_ids", [])
        settings["admin_ids"].append(user_id)
        save_settings(settings)
        return True
    return False

def remove_admin_id(user_id):
    settings = load_settings()
    if user_id in settings.get("admin_ids", []) and user_id != MAIN_ADMIN_ID:
        settings["admin_ids"].remove(user_id)
        save_settings(settings)
        return True
    return False

# ========== تتبع المستخدمين ==========
def track_user(user):
    users = load_users()
    uid = str(user.id)
    if uid not in users:
        users[uid] = {
            "first_name": user.first_name or "بدون",
            "username": user.username or "",
            "last_seen": datetime.now().isoformat(),
            "total_messages": 0
        }
    users[uid]["last_seen"] = datetime.now().isoformat()
    users[uid]["total_messages"] = users[uid].get("total_messages", 0) + 1
    if user.username:
        users[uid]["username"] = user.username
    save_users(users)

# ========== أوامر أساسية ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    track_user(update.effective_user)
    if update.effective_chat.type == ChatType.PRIVATE:
        if is_admin(update):
            keyboard = build_admin_keyboard()
            await update.message.reply_text(
                "🔐 **لوحة تحكم المسؤول**\n\n"
                "اختر من الأزرار:",
                reply_markup=keyboard,
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(
                "🎯 **مرحباً بك في بوت الاختبارات!**\n\n"
                "أرسل /help للتعرف على الأوامر المتاحة.\n"
                "هذا البوت مخصص للمسؤول فقط، يمكنك استخدامه للاختبارات."
            )
    else:
        # في المجموعة
        await update.message.reply_text(
            "👋 **أهلاً!**\n"
            "أنا بوت الاختبارات. يمكن للمسؤول إنشاء اختبارات في هذه المجموعة.\n"
            "لبدء اختبار، اطلب من المسؤول إرسال الاختبار هنا."
        )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    track_user(update.effective_user)
    help_text = (
        "📖 **الأوامر المتاحة:**\n\n"
        "/start - بدء البوت\n"
        "/help - هذه المساعدة\n"
        "/newquiz - إنشاء اختبار جديد (المسؤول فقط)\n"
        "/admin - لوحة التحكم (المسؤول فقط)\n"
        "/stats - عرض الإحصائيات (المسؤول فقط)\n"
        "/users - عرض المستخدمين (المسؤول فقط)\n"
        "/broadcast <رسالة> - إرسال رسالة للجميع (المسؤول الرئيسي فقط)\n"
        "/addadmin <id> - إضافة مسؤول جديد (المسؤول الرئيسي فقط)\n"
        "/removeadmin <id> - إزالة مسؤول (المسؤول الرئيسي فقط)\n"
    )
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    track_user(update.effective_user)
    if not is_admin(update):
        await update.message.reply_text("🚫 هذا الأمر للمسؤولين فقط.")
        return
    keyboard = build_admin_keyboard()
    await update.message.reply_text(
        "🔐 **لوحة التحكم:**",
        reply_markup=keyboard,
        parse_mode='Markdown'
    )

def build_admin_keyboard():
    keyboard = [
        [InlineKeyboardButton("📝 إنشاء اختبار", callback_data="new_quiz")],
        [InlineKeyboardButton("📋 الاختبارات", callback_data="list_quizzes")],
        [InlineKeyboardButton("👥 المستخدمون", callback_data="list_users")],
        [InlineKeyboardButton("📊 الإحصائيات", callback_data="stats")],
        [InlineKeyboardButton("⚙️ الإعدادات", callback_data="settings")],
        [InlineKeyboardButton("➕ إضافة مسؤول", callback_data="add_admin")],
        [InlineKeyboardButton("➖ إزالة مسؤول", callback_data="remove_admin")],
    ]
    return InlineKeyboardMarkup(keyboard)

# ========== معالجات الأزرار (خارج المحادثة) ==========
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    track_user(update.effective_user)

    if not is_admin(update):
        await query.answer("🚫 للمسؤولين فقط", show_alert=True)
        return

    if data == "new_quiz":
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
        settings = load_settings()
        anonymous_status = "مفعل ✅" if settings.get("allow_anonymous", True) else "معطل ❌"
        keyboard = [
            [InlineKeyboardButton(f"🔄 تبديل الاستفتاء السري: {anonymous_status}", callback_data="toggle_anonymous")],
            [InlineKeyboardButton("↩️ رجوع", callback_data="back_admin")]
        ]
        await query.message.reply_text(
            f"⚙️ **الإعدادات:**\n\n"
            f"اسم البوت: {settings.get('bot_name', 'بوت الاختبارات')}\n"
            f"الاستفتاء السري: {anonymous_status}",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        return ConversationHandler.END

    elif data == "toggle_anonymous":
        settings = load_settings()
        settings["allow_anonymous"] = not settings.get("allow_anonymous", True)
        save_settings(settings)
        anonymous_status = "مفعل ✅" if settings["allow_anonymous"] else "معطل ❌"
        keyboard = [
            [InlineKeyboardButton(f"🔄 تبديل الاستفتاء السري: {anonymous_status}", callback_data="toggle_anonymous")],
            [InlineKeyboardButton("↩️ رجوع", callback_data="back_admin")]
        ]
        await query.message.edit_text(
            f"⚙️ **الإعدادات:**\n\n"
            f"الاستفتاء السري: {anonymous_status}",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        return ConversationHandler.END

    elif data == "back_admin":
        keyboard = build_admin_keyboard()
        await query.message.edit_text(
            "🔐 **لوحة التحكم:**",
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
        return ConversationHandler.END

    elif data == "add_admin":
        await query.message.reply_text(
            "➕ أرسل ID المستخدم الذي تريد إضافته كمسؤول:"
        )
        context.user_data['awaiting_admin_id'] = True
        return ConversationHandler.END

    elif data == "remove_admin":
        admins = get_admin_ids()
        keyboard = []
        for admin_id in admins:
            if admin_id != MAIN_ADMIN_ID:
                keyboard.append([InlineKeyboardButton(f"❌ {admin_id}", callback_data=f"remove_{admin_id}")])
        if not keyboard:
            await query.message.reply_text("لا يوجد مسؤولون إضافيون.")
            return ConversationHandler.END
        await query.message.reply_text(
            "➖ اختر المسؤول الذي تريد إزالته:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return ConversationHandler.END

    return ConversationHandler.END

async def remove_admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    admin_id = query.data.replace("remove_", "")
    if remove_admin_id(admin_id):
        await query.message.reply_text(f"✅ تم إزالة المسؤول: {admin_id}")
    else:
        await query.message.reply_text("❌ فشل الإزالة.")
    return ConversationHandler.END

# ========== إنشاء الاختبار (المحادثة) ==========
async def new_quiz_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    track_user(update.effective_user)
    if not is_admin(update):
        await update.message.reply_text("🚫 هذا الأمر للمسؤولين فقط.")
        return ConversationHandler.END
    await update.message.reply_text("✍️ أرسل عنوان الاختبار:")
    return TITLE

async def get_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    track_user(update.effective_user)
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
    await query.message.reply_text(
        "🔢 أرسل الخيارات (كل خيار في سطر):\n\n"
        "مثال:\nباريس\nلندن\nمدريد"
    )
    return OPTIONS

async def get_options(update: Update, context: ContextTypes.DEFAULT_TYPE):
    track_user(update.effective_user)
    options = [line.strip() for line in update.message.text.split('\n') if line.strip()]
    if len(options) < 2:
        await update.message.reply_text("⚠️ تحتاج خيارين على الأقل! أعد الإرسال.")
        return OPTIONS
    if len(options) > 10:
        await update.message.reply_text("⚠️ الحد الأقصى 10 خيارات! أعد الإرسال.")
        return OPTIONS
    context.user_data['options'] = options

    keyboard = []
    for i, opt in enumerate(options):
        keyboard.append([InlineKeyboardButton(f"✔️ {opt}", callback_data=f"correct_{i}")])
    keyboard.append([InlineKeyboardButton("⏭️ بدون إجابة صحيحة", callback_data="no_correct")])

    await update.message.reply_text(
        "✅ هل يوجد إجابة صحيحة؟ اختر من الأزرار:",
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

    preview_text = "📋 **معاينة الاختبار:**\n\n"
    preview_text += f"❓ السؤال: {context.user_data['title']}\n"
    if context.user_data.get('description'):
        preview_text += f"📝 الوصف: {context.user_data['description']}\n"
    preview_text += f"⏱️ المدة: {duration} ثانية\n"
    preview_text += f"🔢 عدد الخيارات: {len(context.user_data['options'])}\n"
    if context.user_data.get('correct_option') is not None:
        preview_text += f"✔️ الإجابة الصحيحة: {context.user_data['options'][context.user_data['correct_option']]}\n"

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
                share_text += f"⏱️ المدة: {quiz['duration']} ثانية\n\n"
                share_text += "انقل هذه الرسالة إلى المجموعة ثم اضغط الزر لبدء الاختبار!"
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

# ========== إرسال الاستفتاء ==========
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

# ========== أوامر إضافية (إدارة) ==========
async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    track_user(update.effective_user)
    if not is_admin(update):
        await update.message.reply_text("🚫 للمسؤولين فقط.")
        return
    quizzes = load_quizzes()
    users = load_users()
    total_participants = sum(q.get('participants', 0) for q in quizzes.values())
    await update.message.reply_text(
        f"📊 **الإحصائيات:**\n\n"
        f"الاختبارات: {len(quizzes)}\n"
        f"المستخدمون: {len(users)}\n"
        f"المشاركون: {total_participants}",
        parse_mode='Markdown'
    )

async def users_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    track_user(update.effective_user)
    if not is_admin(update):
        await update.message.reply_text("🚫 للمسؤولين فقط.")
        return
    users = load_users()
    if not users:
        await update.message.reply_text("لا يوجد مستخدمون.")
        return
    text = "👥 **المستخدمون:**\n\n"
    for uid, u in users.items():
        username = f"@{u['username']}" if u.get('username') else "بدون"
        text += f"• {u['first_name']} ({username}) - ID: {uid} - رسائل: {u.get('total_messages',0)}\n"
    await update.message.reply_text(text, parse_mode='Markdown')

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    track_user