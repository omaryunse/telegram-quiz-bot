from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Poll
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler, CallbackQueryHandler, PollAnswerHandler
from telegram.constants import ChatType
import json
import os
from datetime import datetime

TOKEN = "8845301824:AAE02vGKIeP4pLNDD_aww1gwkMPf0lY1mQs"
ADMIN_IDS = ["7021041990", "8810965759", "7020921829"]

QUIZZES_FILE = "quizzes.json"
USERS_FILE = "users.json"
SETTINGS_FILE = "settings.json"
GROUPS_FILE = "groups.json"
RESULTS_FILE = "results.json"

TITLE, DESCRIPTION, OPTIONS, CORRECT_OPTION, DURATION, PREVIEW = range(6)

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
        settings = {"allow_anonymous": False, "bot_name": "بوت الاختبارات"}
        save_json(SETTINGS_FILE, settings)
    return settings

def save_settings(data):
    save_json(SETTINGS_FILE, data)

def load_groups():
    return load_json(GROUPS_FILE)

def save_groups(data):
    save_json(GROUPS_FILE, data)

def load_results():
    return load_json(RESULTS_FILE)

def save_results(data):
    save_json(RESULTS_FILE, data)

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

def build_admin_keyboard():
    keyboard = [
        [InlineKeyboardButton("📝 إنشاء اختبار", callback_data="new_quiz")],
        [InlineKeyboardButton("📊 نتائج الاختبارات", callback_data="quiz_results")],
        [InlineKeyboardButton("📋 الاختبارات", callback_data="list_quizzes")],
        [InlineKeyboardButton("🌐 المجموعات", callback_data="list_groups")],
        [InlineKeyboardButton("👥 المستخدمون", callback_data="list_users")],
        [InlineKeyboardButton("📢 بث جماعي", callback_data="broadcast")],
        [InlineKeyboardButton("⚙️ الإعدادات", callback_data="settings")],
    ]
    return InlineKeyboardMarkup(keyboard)

async def start(update, context):
    track_user(update.effective_user)
    if update.effective_chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]:
        track_group(update.effective_chat)
        await update.message.reply_text("👋 أهلاً! أنا بوت الاختبارات.")
        return
    if is_admin(update):
        settings = load_settings()
        await update.message.reply_text(f"🔐 **{settings['bot_name']} - لوحة التحكم**", reply_markup=build_admin_keyboard(), parse_mode='Markdown')
    else:
        await update.message.reply_text("🎯 **مرحباً بك!**")

async def help_command(update, context):
    await update.message.reply_text("/start - لوحة التحكم\n/newquiz - اختبار جديد\n/admin - لوحة التحكم")

async def admin_command(update, context):
    if not is_admin(update):
        return
    await update.message.reply_text("🔐 **لوحة التحكم:**", reply_markup=build_admin_keyboard(), parse_mode='Markdown')

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
    elif data == "quiz_results":
        await show_quiz_results(query)
        return ConversationHandler.END
    elif data == "list_quizzes":
        quizzes = load_quizzes()
        if not quizzes:
            await query.message.reply_text("لا توجد اختبارات.")
            return ConversationHandler.END
        text = "📋 **الاختبارات:**\n\n"
        for qid, q in quizzes.items():
            text += f"• {q['title']} - 👥 {q.get('participants', 0)}\n"
        keyboard = [[InlineKeyboardButton("🗑️ حذف اختبار", callback_data="delete_quiz")]]
        await query.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        return ConversationHandler.END
    elif data == "delete_quiz":
        quizzes = load_quizzes()
        keyboard = []
        for qid, q in quizzes.items():
            keyboard.append([InlineKeyboardButton(f"🗑️ {q['title']}", callback_data=f"delquiz_{qid}")])
        keyboard.append([InlineKeyboardButton("↩️ رجوع", callback_data="back_admin")])
        await query.message.reply_text("اختر الاختبار للحذف:", reply_markup=InlineKeyboardMarkup(keyboard))
        return ConversationHandler.END
    elif data.startswith("delquiz_"):
        qid = data.replace("delquiz_", "")
        quizzes = load_quizzes()
        if qid in quizzes:
            del quizzes[qid]
            save_quizzes(quizzes)
            await query.message.reply_text("✅ تم حذف الاختبار.")
        return ConversationHandler.END
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
            await query.message.reply_text("لا توجد مجموعات مسجلة.")
            return ConversationHandler.END
        text = "🌐 **المجموعات:**\n\n"
        for gid, g in groups.items():
            text += f"• {g['title']} - ID: {gid}\n"
        await query.message.reply_text(text, parse_mode='Markdown')
        return ConversationHandler.END
    elif data == "broadcast":
        await query.message.reply_text("📢 أرسل الرسالة التي تريد إرسالها للجميع:")
        context.user_data['awaiting_broadcast'] = True
        return ConversationHandler.END
    elif data == "settings":
        settings = load_settings()
        status = "مفعل ✅" if settings.get("allow_anonymous") else "معطل ❌"
        keyboard = [
            [InlineKeyboardButton(f"🔄 الاستفتاء السري: {status}", callback_data="toggle_anonymous")],
            [InlineKeyboardButton("✏️ تغيير اسم البوت", callback_data="rename_bot")],
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
            [InlineKeyboardButton("✏️ تغيير اسم البوت", callback_data="rename_bot")],
            [InlineKeyboardButton("↩️ رجوع", callback_data="back_admin")]
        ]
        await query.message.edit_text(f"⚙️ **الإعدادات:**\n\nالاستفتاء السري: {status}", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        return ConversationHandler.END
    elif data == "rename_bot":
        await query.message.reply_text("✏️ أرسل الاسم الجديد للبوت:")
        context.user_data['awaiting_rename'] = True
        return ConversationHandler.END
    elif data == "back_admin":
        await query.message.edit_text("🔐 **لوحة التحكم:**", reply_markup=build_admin_keyboard(), parse_mode='Markdown')
        return ConversationHandler.END
    return ConversationHandler.END

async def show_quiz_results(query):
    quizzes = load_quizzes()
    if not quizzes:
        await query.message.reply_text("لا توجد اختبارات.")
        return
    keyboard = []
    for qid, q in quizzes.items():
        keyboard.append([InlineKeyboardButton(f"📊 {q['title']}", callback_data=f"result_{qid}")])
    await query.message.reply_text("📋 اختر الاختبار لعرض النتائج:", reply_markup=InlineKeyboardMarkup(keyboard))

async def result_callback(update, context):
    query = update.callback_query
    await query.answer()
    qid = query.data.replace("result_", "")
    results = load_results().get(qid, [])
    quizzes = load_quizzes()
    quiz = quizzes.get(qid, {})
    if not results:
        await query.message.reply_text("لا توجد نتائج لهذا الاختبار بعد.")
        return
    correct_count = sum(1 for r in results if r.get("is_correct"))
    wrong_count = len(results) - correct_count
    text = f"📊 **نتائج:** {quiz.get('title', '')}\n\n"
    text += f"👥 عدد المشاركين: {len(results)}\n"
    text += f"✅ إجابات صحيحة: {correct_count}\n"
    text += f"❌ إجابات خاطئة: {wrong_count}\n\n"
    text += "**التفاصيل:**\n"
    for r in results:
        username = f"@{r.get('username')}" if r.get('username') else "بدون"
        status = "✅" if r.get("is_correct") else "❌"
        text += f"{status} {r.get('first_name','')} ({username}) - اختار: {r.get('selected_option','')}\n"
    await query.message.reply_text(text, parse_mode='Markdown')

async def handle_extra_inputs(update, context):
    if context.user_data.get('awaiting_broadcast'):
        context.user_data['awaiting_broadcast'] = False
        message = update.message.text
        users = load_users()
        sent = 0
        for uid in users:
            try:
                await context.bot.send_message(chat_id=uid, text=f"📢 {message}")
                sent += 1
            except:
                pass
        await update.message.reply_text(f"✅ تم الإرسال إلى {sent} مستخدم.")
        return
    if context.user_data.get('awaiting_rename'):
        context.user_data['awaiting_rename'] = False
        new_name = update.message.text.strip()
        settings = load_settings()
        settings["bot_name"] = new_name
        save_settings(settings)
        await update.message.reply_text(f"✅ تم تغيير اسم البوت إلى: {new_name}")
        return

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
        await update.message.reply_text("⚠️ خياران على الأقل!")
        return OPTIONS
    context.user_data['options'] = options
    keyboard = []
    for i, opt in enumerate(options):
        keyboard.append([InlineKeyboardButton(f"✔️ {opt}", callback_data=f"correct_{i}")])
    keyboard.append([InlineKeyboardButton("⏭️ بدون إجابة صحيحة", callback_data="no_correct")])
    await update.message.reply_text("✅ اختر الإجابة الصحيحة:", reply_markup=InlineKeyboardMarkup(keyboard))
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
            await query.message.reply_text("لا توجد مجموعات مسجلة.")
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
    is_anonymous = settings.get('allow_anonymous', False)
    if correct_option is not None:
        message = await context.bot.send_poll(
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
        message = await context.bot.send_poll(
            chat_id=chat_id,
            question=quiz['title'],
            options=options,
            is_anonymous=is_anonymous,
            open_period=duration
        )
    quiz['poll_id'] = message.poll.id
    quiz['chat_id'] = chat_id
    quiz['participants'] = quiz.get('participants', 0)
    save_quizzes(quizzes)

async def poll_answer_handler(update, context):
    answer = update.poll_answer
    poll_id = answer.poll_id
    user = answer.user
    selected_option = answer.option_ids[0] if answer.option_ids else None
    quizzes = load_quizzes()
    for qid, q in quizzes.items():
        if q.get('poll_id') == poll_id:
            results = load_results()
            if qid not in results:
                results[qid] = []
            is_correct = False
            if q.get('correct_option') is not None and selected_option is not None:
                is_correct = (selected_option == q['correct_option'])
            results[qid].append({
                "user_id": user.id if user else "غير معروف",
                "first_name": user.first_name if user else "غير معروف",
                "username": user.username if user else "",
                "selected_option": selected_option if selected_option is not None else "بدون",
                "is_correct": is_correct,
                "answered_at": datetime.now().isoformat()
            })
            save_results(results)
            q['participants'] = q.get('participants', 0) + 1
