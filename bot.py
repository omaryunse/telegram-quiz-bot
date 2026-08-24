from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Poll
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler, CallbackQueryHandler
from telegram.constants import ChatType
import json, os
from datetime import datetime

# ========== الإعدادات ==========
TOKEN = "8845301824:AAE02vGKIeP4pLNDD_aww1gwkMPf0lY1mQs"
MAIN_ADMIN_ID = "7021041990"   # رقمك كمسؤول رئيسي

# ملفات التخزين
QUIZZES_FILE = "quizzes.json"
USERS_FILE = "users.json"
SETTINGS_FILE = "settings.json"
GROUPS_FILE = "groups.json"

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
            "admin_ids": [MAIN_ADMIN_ID]
        }
        save_json(SETTINGS_FILE, settings)
    return settings

def save_settings(settings):
    save_json(SETTINGS_FILE, settings)

def load_groups():
    return load_json(GROUPS_FILE)

def save_groups(groups):
    save_json(GROUPS_FILE, groups)

def get_admin_ids():
    settings = load_settings()
    return settings.get("admin_ids", [MAIN_ADMIN_ID])

def is_admin(update):
    return str(update.effective_user.id) in get_admin_ids()

def is_main_admin(update):
    return str(update.effective_user.id) == MAIN_ADMIN_ID

# ========== تتبع المستخدمين والمجموعات ==========
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

def track_group(chat):
    if chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]:
        groups = load_groups()
        gid = str(chat.id)
        if gid not in groups:
            groups[gid] = {
                "title": chat.title or "بدون",
                "type": chat.type,
                "added_at": datetime.now().isoformat()
            }
            save_groups(groups)

# ========== لوحات المفاتيح ==========
def build_admin_keyboard():
    keyboard = [
        [InlineKeyboardButton("📝 إنشاء اختبار", callback_data="new_quiz")],
        [InlineKeyboardButton("👥 المستخدمون", callback_data="list_users")],
        [InlineKeyboardButton("📊 الإحصائيات", callback_data="stats")],
        [InlineKeyboardButton("🌐 المجموعات", callback_data="list_groups")],
        [InlineKeyboardButton("⚙️ الإعدادات", callback_data="settings")],
        [InlineKeyboardButton("➕ إدارة المسؤولين", callback_data="manage_admins")],
    ]
    return InlineKeyboardMarkup(keyboard)

def build_manage_admins_keyboard():
    keyboard = [
        [InlineKeyboardButton("➕ إضافة مسؤول", callback_data="add_admin")],
        [InlineKeyboardButton("➖ إزالة مسؤول", callback_data="remove_admin")],
        [InlineKeyboardButton("↩️ رجوع", callback_data="back_admin")]
    ]
    return InlineKeyboardMarkup(keyboard)

# ========== الأوامر الأساسية ==========
async def start(update, context):
    track_user(update.effective_user)
    # في المجموعة
    if update.effective_chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]:
        track_group(update.effective_chat)
        await update.message.reply_text("👋 أهلاً! أنا بوت الاختبارات.\nيمكن للمسؤول إرسال اختبارات هنا.")
        return
    # في الخاص
    if is_admin(update):
        await update.message.reply_text(
            "🔐 **لوحة تحكم المسؤول**\n\nاختر من الأزرار:",
            reply_markup=build_admin_keyboard(),
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text(
            "🎯 **مرحباً بك!**\n\n"
            "هذا البوت مخصص للمسؤولين.\n"
            "أرسل /help للمساعدة."
        )

async def help_command(update, context):
    track_user(update.effective_user)
    text = (
        "📖 **الأوامر المتاحة:**\n\n"
        "/start - بدء البوت\n"
        "/newquiz - إنشاء اختبار جديد\n"
        "/admin - لوحة التحكم\n"
        "/stats - الإحصائيات\n"
        "/users - المستخدمون\n"
        "/groups - المجموعات\n"
        "/broadcast - رسالة للجميع\n"
        "/help - المساعدة"
    )
    await update.message.reply_text(text, parse_mode='Markdown')

async def admin_command(update, context):
    track_user(update.effective_user)
    if not is_admin(update):
        await update.message.reply_text("🚫 للمسؤولين فقط.")
        return
    await update.message.reply_text(
        "🔐 **لوحة التحكم:**",
        reply_markup=build_admin_keyboard(),
        parse_mode='Markdown'
    )

# ========== معالج الأزرار الرئيسي ==========
async def button_handler(update, context):
    query = update.callback_query
    await query.answer()
    data = query.data
    track_user(update.effective_user)

    if not is_admin(update):
        await query.answer("🚫 للمسؤولين فقط", show_alert=True)
        return ConversationHandler.END

    # إنشاء اختبار جديد
    if data == "new_quiz":
        await query.message.reply_text("✍️ أرسل عنوان الاختبار:")
        return TITLE

    # عرض المستخدمين
    elif data == "list_users":
        users = load_users()
        if not users:
            await query.message.reply_text("لا يوجد مستخدمون بعد.")
            return ConversationHandler.END
        text = "👥 **المستخدمون:**\n\n"
        for uid, u in users.items():
            username = f"@{u['username']}" if u.get('username') else "بدون"
            text += f"• {u['first_name']} ({username}) - ID: {uid} - رسائل: {u.get('total_messages', 0)}\n"
        await query.message.reply_text(text, parse_mode='Markdown')
        return ConversationHandler.END

    # عرض الإحصائيات
    elif data == "stats":
        quizzes = load_quizzes()
        users = load_users()
        groups = load_groups()
        total = sum(q.get('participants', 0) for q in quizzes.values())
        await query.message.reply_text(
            f"📊 **الإحصائيات:**\n\n"
            f"الاختبارات: {len(quizzes)}\n"
            f"المستخدمون: {len(users)}\n"
            f"المجموعات: {len(groups)}\n"
            f"المشاركون: {total}",
            parse_mode='Markdown'
        )
        return ConversationHandler.END

    # عرض المجموعات
    elif data == "list_groups":
        groups = load_groups()
        if not groups:
            await query.message.reply_text("لا توجد مجموعات مسجلة.\nأضف البوت إلى مجموعة ثم أرسل /start فيها.")
            return ConversationHandler.END
        text = "🌐 **المجموعات:**\n\n"
        for gid, g in groups.items():
            text += f"• {g['title']} - ID: {gid}\n"
        await query.message.reply_text(text, parse_mode='Markdown')
        return ConversationHandler.END

    # الإعدادات
    elif data == "settings":
        settings = load_settings()
        status = "مفعل ✅" if settings.get("allow_anonymous") else "معطل ❌"
        keyboard = [
            [InlineKeyboardButton(f"🔄 تبديل الاستفتاء السري: {status}", callback_data="toggle_anonymous")],
            [InlineKeyboardButton("↩️ رجوع", callback_data="back_admin")]
        ]
        await query.message.reply_text(
            f"⚙️ **الإعدادات:**\n\nالاستفتاء السري: {status}",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        return ConversationHandler.END

    # تبديل الاستفتاء السري
    elif data == "toggle_anonymous":
        settings = load_settings()
        settings["allow_anonymous"] = not settings.get("allow_anonymous", True)
        save_settings(settings)
        status = "مفعل ✅" if settings["allow_anonymous"] else "معطل ❌"
        keyboard = [
            [InlineKeyboardButton(f"🔄 تبديل الاستفتاء السري: {status}", callback_data="toggle_anonymous")],
            [InlineKeyboardButton("↩️ رجوع", callback_data="back_admin")]
        ]
        await query.message.edit_text(
            f"⚙️ **الإعدادات:**\n\nالاستفتاء السري: {status}",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        return ConversationHandler.END

    # إدارة المسؤولين
    elif data == "manage_admins":
        await query.message.reply_text(
            "➕➖ **إدارة المسؤولين:**",
            reply_markup=build_manage_admins_keyboard()
        )
        return ConversationHandler.END

    # طلب إضافة مسؤول
    elif data == "add_admin":
        await query.message.reply_text("➕ أرسل ID المستخدم الذي تريد إضافته كمسؤول:")
        context.user_data['awaiting_admin_id'] = True
        return ConversationHandler.END

    # عرض المسؤولين لإزالة أحدهم
    elif data == "remove_admin":
        admins = get_admin_ids()
        keyboard = []
        for admin_id in admins:
            if admin_id != MAIN_ADMIN_ID:
                keyboard.append([InlineKeyboardButton(f"❌ {admin_id}", callback_data=f"removeadmin_{admin_id}")])
        if not keyboard:
            await query.message.reply_text("لا يوجد مسؤولون إضافيون.")
            return ConversationHandler.END
        keyboard.append([InlineKeyboardButton("↩️ رجوع", callback_data="back_admin")])
        await query.message.reply_text(
            "➖ اختر المسؤول الذي تريد إزالته:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return ConversationHandler.END

    # إزالة مسؤول محدد
    elif data.startswith("removeadmin_"):
        admin_id = data.replace("removeadmin_", "")
        settings = load_settings()
        if admin_id in settings.get("admin_ids", []):
            settings["admin_ids"].remove(admin_id)
            save_settings(settings)
            await query.message.reply_text(f"✅ تم إزالة المسؤول: {admin_id}")
        else:
            await query.message.reply_text("هذا المستخدم ليس مسؤولاً.")
        return ConversationHandler.END

    # رجوع للوحة التحكم
    elif data == "back_admin":
        await query.message.edit_text(
            "🔐 **لوحة التحكم:**",
            reply_markup=build_admin_keyboard(),
            parse_mode='Markdown'
        )
        return ConversationHandler.END

    return ConversationHandler.END

# ========== معالج إدخال ID المسؤول ==========
async def handle_awaiting_admin_id(update, context):
    if context.user_data.get('awaiting_admin_id'):
        context.user_data['awaiting_admin_id'] = False
        user_id = update.message.text.strip()
        settings = load_settings()
        if user_id not in settings.get("admin_ids", []):
            settings["admin_ids"] = settings.get("admin_ids", [])
            settings["admin_ids"].append(user_id)
            save_settings(settings)
            await update.message.reply_text(f"✅ تمت إضافة {user_id} كمسؤول.")
        else:
            await update.message.reply_text("هذا المستخدم مسؤول بالفعل.")

# ========== إنشاء الاختبار (محادثة) ==========
async def new_quiz_command(update, context):
    track_user(update.effective_user)
    if not is_admin(update):
        await update.message.reply_text("🚫 للمسؤولين فقط.")
        return ConversationHandler.END
    await update.message.reply_text("✍️ أرسل عنوان الاختبار:")
    return TITLE

async def get_title(update, context):
    track_user(update.effective_user)
    context.user_data['title'] = update.message.text
    keyboard = [[InlineKeyboardButton("⏭️ تخطي الوصف", callback_data="skip_description")]]
    await update.message.reply_text(
        "📝 أرسل الوصف (اختياري):",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return DESCRIPTION

async def skip_description(update, context):
    query = update.callback_query
    await query.answer()
    context.user_data['description'] = ""
    await query.message.reply_text(
        "🔢 أرسل الخيارات (كل خيار في سطر):\n\n"
        "مثال:\nباريس\nلندن\nمدريد"
    )
    return OPTIONS

async def get_description(update, context):
    track_user(update.effective_user)
    context.user_data['description'] = update.message.text
    await query.message.reply_text(
        "🔢 أرسل الخيارات (كل خيار في سطر):\n\n"
        "مثال:\nباريس\nلندن\nمدريد"
    )
    return OPTIONS

async def get_options(update, context):
    track_user(update.effective_user)
    options = [line.strip() for line in update.message.text.split('\n') if line.strip()]
    if len(options) < 2:
        await update.message.reply_text("⚠️ تحتاج خيارين على الأقل!")
        return OPTIONS
    if len(options) > 10:
        await update.message.reply_text("⚠️ الحد الأقصى 10 خيارات!")
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
    ]
    await query.message.reply_text(
        "⏳ اختر مدة الاختبار:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
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
        'created_by': query.from_user.id,
        'participants': 0
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
        [InlineKeyboardButton("📤 مشاركة إلى مجموعة", callback_data="share_quiz")],
        [InlineKeyboardButton("➕ سؤال آخر", callback_data="new_quiz")]
    ]
    await query.message.reply_text(
        preview_text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )
    return PREVIEW

# ========== معالج أزرار المعاينة ==========
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
            await query.message.reply_text(
                "لا توجد مجموعات مسجلة.\n"
                "أضف البوت إلى مجموعة ثم أرسل /start فيها لتسجيلها."
            )
            return ConversationHandler.END
        keyboard = []
        for gid, g in groups.items():
            keyboard.append([InlineKeyboardButton(f"📤 {g['title']}", callback_data=f"sendgroup_{gid}_{quiz_id}")])
        keyboard.append([InlineKeyboardButton("↩️ رجوع", callback_data="back_to_preview")])
        await query.message.reply_text(
            "🌐 اختر المجموعة التي تريد إرسال الاختبار إليها:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return PREVIEW

    elif data == "new_quiz":
        await query.message.reply_text("✍️ أرسل عنوان الاختبار الجديد:")
        return TITLE

    elif data == "back_to_preview":
        if quiz_id:
            quizzes = load_quizzes()
            quiz = quizzes.get(quiz_id)
            if quiz:
                preview_text = f"📋 **معاينة الاختبار:**\n\n❓ {quiz['title']}\n"
                if quiz.get('description'):
                    preview_text += f"📝 {quiz['description']}\n"
                preview_text += f"⏱️ {quiz['duration']} ثانية\n"
                keyboard = [
                    [InlineKeyboardButton("🚀 بدء الاختبار هنا", callback_data="start_here")],
                    [InlineKeyboardButton("📤 مشاركة إلى مجموعة", callback_data="share_quiz")],
                    [InlineKeyboardButton("➕ سؤال آخر", callback_data="new_quiz")]
                ]
                await query.message.edit_text(
                    preview_text,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode='Markdown'
                )
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

# =========