# bot.py
import os
import json
from datetime import datetime
from typing import Dict, Any, List, Optional

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Poll,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ConversationHandler,
    CallbackQueryHandler,
    PollAnswerHandler,
    ContextTypes,
)
from telegram.constants import ChatType

# ---------------------------
# Configuration (ضع التوكن يدوياً هنا)
# ---------------------------
TOKEN = "8845301824:AAGptI-Na__Tp0ZbFgvQ-HSfHOawDCuhFK4"
ADMIN_IDS = ["7021041990", "8810965759", "7020921829"]

QUIZZES_FILE = "quizzes.json"
USERS_FILE = "users.json"
SETTINGS_FILE = "settings.json"
GROUPS_FILE = "groups.json"
RESULTS_FILE = "results.json"

# Conversation states
TITLE, DESCRIPTION, OPTIONS, CORRECT_OPTION, DURATION, PREVIEW = range(6)

# ---------------------------
# Utilities: JSON load/save
# ---------------------------
def load_json(path: str) -> Dict[str, Any]:
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except Exception:
                return {}
    return {}

def save_json(path: str, data: Dict[str, Any]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_quizzes() -> Dict[str, Any]:
    return load_json(QUIZZES_FILE)

def save_quizzes(data: Dict[str, Any]) -> None:
    save_json(QUIZZES_FILE, data)

def load_users() -> Dict[str, Any]:
    return load_json(USERS_FILE)

def save_users(data: Dict[str, Any]) -> None:
    save_json(USERS_FILE, data)

def load_settings() -> Dict[str, Any]:
    settings = load_json(SETTINGS_FILE)
    if not settings:
        settings = {"allow_anonymous": False, "bot_name": "بوت الاختبارات"}
        save_settings(settings)
    return settings

def save_settings(data: Dict[str, Any]) -> None:
    save_json(SETTINGS_FILE, data)

def load_groups() -> Dict[str, Any]:
    return load_json(GROUPS_FILE)

def save_groups(data: Dict[str, Any]) -> None:
    save_json(GROUPS_FILE, data)

def load_results() -> Dict[str, List[Dict[str, Any]]]:
    return load_json(RESULTS_FILE)

def save_results(data: Dict[str, List[Dict[str, Any]]]) -> None:
    save_json(RESULTS_FILE, data)

# ---------------------------
# Helpers: admin check, tracking
# ---------------------------
def is_admin(update: Update) -> bool:
    user = update.effective_user
    if not user and update.callback_query:
        user = update.callback_query.from_user
    if not user:
        return False
    return str(user.id) in ADMIN_IDS

def track_user(user) -> None:
    if not user:
        return
    users = load_users()
    uid = str(user.id)
    if uid not in users:
        users[uid] = {"first_name": user.first_name or "بدون", "username": user.username or "", "total_messages": 0}
    users[uid]["total_messages"] = users[uid].get("total_messages", 0) + 1
    if user.username:
        users[uid]["username"] = user.username
    save_users(users)

def track_group(chat) -> None:
    if not chat:
        return
    if chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]:
        groups = load_groups()
        gid = str(chat.id)
        if gid not in groups:
            groups[gid] = {"title": chat.title or "بدون"}
            save_groups(groups)

# ---------------------------
# UI builders
# ---------------------------
def build_admin_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("📝 إنشاء اختبار", callback_data="new_quiz")],
        [InlineKeyboardButton("📊 نتائج الاختبارات", callback_data="quiz_results")],
        [InlineKeyboardButton("🌐 المجموعات", callback_data="list_groups")],
        [InlineKeyboardButton("👥 المستخدمون", callback_data="list_users")],
        [InlineKeyboardButton("⚙️ الإعدادات", callback_data="settings")],
    ]
    return InlineKeyboardMarkup(keyboard)

# ---------------------------
# Handlers (جميع الدوال معرفة قبل الاستخدام)
# ---------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Track user and group
    if update.effective_user:
        track_user(update.effective_user)
    if update.effective_chat and update.effective_chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]:
        track_group(update.effective_chat)
        # In groups, send a simple greeting
        if update.message:
            await update.message.reply_text("👋 أهلاً! أنا بوت الاختبارات. استخدم /start في الخاص للوصول للوحة التحكم.")
        return
    # Private chat
    if is_admin(update):
        settings = load_settings()
        await update.message.reply_text(f"🔐 {settings.get('bot_name','بوت الاختبارات')} - لوحة التحكم", reply_markup=build_admin_keyboard())
    else:
        await update.message.reply_text("🎯 مرحباً! يمكنك استخدام البوت للمشاركة في الاختبارات والاستفتاءات.")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "/start - ابدأ أو افتح لوحة التحكم (للمسؤولين)\n"
        "/newquiz - إنشاء اختبار جديد (للمسؤولين)\n"
        "/help - عرض هذه الرسالة"
    )
    await update.message.reply_text(text)

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update):
        return
    await update.message.reply_text("🔐 لوحة التحكم:", reply_markup=build_admin_keyboard())

# Button handler for admin menu entry actions
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return
    await query.answer()
    track_user(query.from_user)
    if not is_admin(update):
        await query.answer("🚫 للمسؤولين فقط", show_alert=True)
        return ConversationHandler.END

    data = query.data

    if data == "new_quiz":
        await query.message.reply_text("✍️ أرسل عنوان الاختبار:")
        return TITLE

    if data == "quiz_results":
        await show_quiz_results(query)
        return ConversationHandler.END

    if data == "list_users":
        users = load_users()
        if not users:
            await query.message.reply_text("لا يوجد مستخدمون.")
            return ConversationHandler.END
        text = "👥 **المستخدمون:**\n\n"
        for uid, u in users.items():
            username = f"@{u['username']}" if u.get("username") else "بدون"
            text += f"• {u.get('first_name','بدون')} ({username}) - ID: {uid} - استخدامات: {u.get('total_messages',0)}\n"
        await query.message.reply_text(text)
        return ConversationHandler.END

    if data == "list_groups":
        groups = load_groups()
        if not groups:
            await query.message.reply_text("لا توجد مجموعات مسجلة.")
            return ConversationHandler.END
        text = "🌐 **المجموعات:**\n\n"
        for gid, g in groups.items():
            text += f"• {g.get('title','بدون')} - ID: {gid}\n"
        await query.message.reply_text(text)
        return ConversationHandler.END

    if data == "settings":
        settings = load_settings()
        status = "مفعل ✅" if settings.get("allow_anonymous") else "معطل ❌"
        keyboard = [
            [InlineKeyboardButton(f"🔄 السري: {status}", callback_data="toggle_anonymous")],
            [InlineKeyboardButton("✏️ تغيير اسم البوت", callback_data="change_bot_name")],
            [InlineKeyboardButton("↩️ رجوع", callback_data="back_admin")],
        ]
        await query.message.reply_text(f"⚙️ الإعدادات:\n\nالاستفتاء السري: {status}", reply_markup=InlineKeyboardMarkup(keyboard))
        return ConversationHandler.END

    if data == "toggle_anonymous":
        settings = load_settings()
        settings["allow_anonymous"] = not settings.get("allow_anonymous", False)
        save_settings(settings)
        status = "مفعل ✅" if settings.get("allow_anonymous") else "معطل ❌"
        keyboard = [
            [InlineKeyboardButton(f"🔄 السري: {status}", callback_data="toggle_anonymous")],
            [InlineKeyboardButton("↩️ رجوع", callback_data="back_admin")],
        ]
        await query.message.edit_text(f"⚙️ الإعدادات:\n\nالاستفتاء السري: {status}", reply_markup=InlineKeyboardMarkup(keyboard))
        return ConversationHandler.END

    if data == "change_bot_name":
        await query.message.reply_text("✏️ أرسل اسم البوت الجديد:")
        # store a marker to indicate next message will set bot name
        context.user_data["awaiting_bot_name"] = True
        return ConversationHandler.END

    if data == "back_admin":
        await query.message.edit_text("🔐 لوحة التحكم:", reply_markup=build_admin_keyboard())
        return ConversationHandler.END

    return ConversationHandler.END

# Show quiz list for results selection
async def show_quiz_results(query):
    quizzes = load_quizzes()
    if not quizzes:
        await query.message.reply_text("لا توجد اختبارات.")
        return
    keyboard = []
    for qid, q in quizzes.items():
        keyboard.append([InlineKeyboardButton(f"📊 {q.get('title','بدون عنوان')}", callback_data=f"result_{qid}")])
    await query.message.reply_text("📋 اختر الاختبار لعرض النتائج:", reply_markup=InlineKeyboardMarkup(keyboard))

# Result callback when admin selects a quiz to view results
async def result_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return
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
    text = f"📊 نتائج: {quiz.get('title','')}\n\n"
    text += f"👥 عدد المشاركين: {len(results)}\n"
    text += f"✅ إجابات صحيحة: {correct_count}\n"
    text += f"❌ إجابات خاطئة: {wrong_count}\n\n"
    text += "التفاصيل:\n"
    for r in results:
        username = f"@{r.get('username')}" if r.get('username') else "بدون"
        status = "✅" if r.get("is_correct") else "❌"
        selected = r.get("selected_option", "بدون")
        # If selected is an index, try to map to option text
        option_text = selected
        try:
            if isinstance(selected, int):
                option_text = quiz.get("options", [])[selected]
        except Exception:
            option_text = str(selected)
        text += f"{status} {r.get('first_name','')} ({username}) - اختار: {option_text}\n"
    await query.message.reply_text(text)

# Start new quiz via command
async def new_quiz_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return ConversationHandler.END
    track_user(update.effective_user)
    await update.message.reply_text("✍️ أرسل عنوان الاختبار:")
    return TITLE

# Get title
async def get_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip() if update.message and update.message.text else ""
    context.user_data["title"] = text
    keyboard = [[InlineKeyboardButton("⏭️ تخطي الوصف", callback_data="skip_description")]]
    await update.message.reply_text("📝 أرسل وصف الاختبار (اختياري):", reply_markup=InlineKeyboardMarkup(keyboard))
    return DESCRIPTION

# Skip description via button
async def skip_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return ConversationHandler.END
    await query.answer()
    context.user_data["description"] = ""
    await query.message.reply_text("🔢 أرسل الخيارات (كل خيار في سطر):")
    return OPTIONS

# Receive description text
async def get_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip() if update.message and update.message.text else ""
    context.user_data["description"] = text
    await update.message.reply_text("🔢 أرسل الخيارات (كل خيار في سطر):")
    return OPTIONS

# Receive options
async def get_options(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text if update.message and update.message.text else ""
    options = [line.strip() for line in text.splitlines() if line.strip()]
    if len(options) < 2:
        await update.message.reply_text("⚠️ يجب أن يكون هناك خياران على الأقل. أعد إرسال الخيارات (كل خيار في سطر).")
        return OPTIONS
    if len(options) > 10:
        await update.message.reply_text("⚠️ الحد الأقصى 10 خيارات. أعد إرسال الخيارات.")
        return OPTIONS
    context.user_data["options"] = options
    keyboard = []
    for i, opt in enumerate(options):
        keyboard.append([InlineKeyboardButton(f"✔️ {opt}", callback_data=f"correct_{i}")])
    keyboard.append([InlineKeyboardButton("⏭️ بدون إجابة صحيحة", callback_data="no_correct")])
    await update.message.reply_text("✅ اختر الإجابة الصحيحة:", reply_markup=InlineKeyboardMarkup(keyboard))
    return CORRECT_OPTION

# Handle correct answer selection
async def correct_answer_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return ConversationHandler.END
    await query.answer()
    data = query.data
    if data == "no_correct":
        context.user_data["correct_option"] = None
    else:
        try:
            context.user_data["correct_option"] = int(data.replace("correct_", ""))
        except Exception:
            context.user_data["correct_option"] = None
    keyboard = [
        [InlineKeyboardButton("⏱️ 30 ثانية", callback_data="duration_30")],
        [InlineKeyboardButton("⏱️ دقيقة", callback_data="duration_60")],
        [InlineKeyboardButton("⏱️ دقيقتان", callback_data="duration_120")],
        [InlineKeyboardButton("⏱️ 5 دقائق", callback_data="duration_300")],
        [InlineKeyboardButton("⏱️ 10 دقائق", callback_data="duration_600")],
    ]
    await query.message.reply_text("⏳ اختر مدة الاختبار:", reply_markup=InlineKeyboardMarkup(keyboard))
    return DURATION

# Handle duration selection and save quiz
async def duration_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return ConversationHandler.END
    await query.answer()
    data = query.data
    try:
        duration = int(data.replace("duration_", ""))
    except Exception:
        duration = 60
    context.user_data["duration"] = duration
    quiz_id = datetime.now().strftime("%Y%m%d%H%M%S")
    quizzes = load_quizzes()
    quizzes[quiz_id] = {
        "title": context.user_data.get("title", ""),
        "description": context.user_data.get("description", ""),
        "options": context.user_data.get("options", []),
        "correct_option": context.user_data.get("correct_option"),
        "duration": duration,
        "participants": 0,
        "poll_id": None,
        "chat_id": None,
    }
    save_quizzes(quizzes)
    context.user_data["quiz_id"] = quiz_id
    preview_text = f"📋 معاينة:\n\n❓ {context.user_data.get('title','')}\n"
    if context.user_data.get("description"):
        preview_text += f"📝 {context.user_data.get('description')}\n"
    preview_text += f"⏱️ {duration} ثانية\n"
    keyboard = [
        [InlineKeyboardButton("🚀 بدء هنا", callback_data="start_here")],
        [InlineKeyboardButton("📤 بدء في مجموعة", callback_data="share_quiz")],
        [InlineKeyboardButton("➕ سؤال آخر", callback_data="new_quiz")],
    ]
    await query.message.reply_text(preview_text, reply_markup=InlineKeyboardMarkup(keyboard))
    return PREVIEW

# Preview handler: start here, share to group, new quiz, back to preview, sendgroup_
async def preview_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return ConversationHandler.END
    await query.answer()
    data = query.data
    quiz_id = context.user_data.get("quiz_id")
    if data == "start_here":
        if quiz_id:
            chat_id = query.message.chat.id
            await send_poll(chat_id, context, quiz_id)
            await query.message.reply_text("✅ تم بدء الاختبار!")
        return ConversationHandler.END

    if data == "share_quiz":
        groups = load_groups()
        if not groups:
            await query.message.reply_text("لا توجد مجموعات مسجلة.")
            return ConversationHandler.END
        keyboard = []
        for gid, g in groups.items():
            keyboard.append([InlineKeyboardButton(f"📤 {g.get('title','بدون')}", callback_data=f"sendgroup_{gid}_{quiz_id}")])
        keyboard.append([InlineKeyboardButton("↩️ رجوع", callback_data="back_to_preview")])
        await query.message.reply_text("🌐 اختر المجموعة:", reply_markup=InlineKeyboardMarkup(keyboard))
        return PREVIEW

    if data == "new_quiz":
        await query.message.reply_text("✍️ أرسل عنوان الاختبار الجديد:")
        return TITLE

    if data == "back_to_preview":
        if quiz_id:
            quizzes = load_quizzes()
            quiz = quizzes.get(quiz_id)
            if quiz:
                preview_text = f"📋 معاينة:\n\n❓ {quiz.get('title','')}\n"
                if quiz.get("description"):
                    preview_text += f"📝 {quiz.get('description')}\n"
                preview_text += f"⏱️ {quiz.get('duration',60)} ثانية\n"
                keyboard = [
                    [InlineKeyboardButton("🚀 بدء هنا", callback_data="start_here")],
                    [InlineKeyboardButton("📤 بدء في مجموعة", callback_data="share_quiz")],
                    [InlineKeyboardButton("➕ سؤال آخر", callback_data="new_quiz")],
                ]
                await query.message.edit_text(preview_text, reply_markup=InlineKeyboardMarkup(keyboard))
        return PREVIEW

    if data.startswith("sendgroup_"):
        parts = data.split("_", 2)
        if len(parts) >= 3:
            group_id = parts[1]
            qid = parts[2]
            try:
                gid_int = int(group_id)
            except Exception:
                try:
                    gid_int = int(group_id)
                except Exception:
                    gid_int = None
            if gid_int is None:
                await query.message.reply_text("❌ معرف المجموعة غير صالح.")
                return ConversationHandler.END
            try:
                await send_poll(gid_int, context, qid)
                await query.message.reply_text("✅ تم إرسال الاختبار إلى المجموعة وبدءه.")
            except Exception as e:
                await query.message.reply_text(f"❌ فشل الإرسال: {e}")
        return ConversationHandler.END

    return ConversationHandler.END

# Send poll to chat_id (int)
async def send_poll(chat_id: int, context: ContextTypes.DEFAULT_TYPE, quiz_id: str) -> None:
    quizzes = load_quizzes()
    quiz = quizzes.get(quiz_id)
    if not quiz:
        return
    settings = load_settings()
    options = quiz.get("options", [])
    correct_option = quiz.get("correct_option")
    duration = quiz.get("duration", 60)
    is_anonymous = settings.get("allow_anonymous", False)
    try:
        if correct_option is not None:
            message = await context.bot.send_poll(
                chat_id=chat_id,
                question=quiz.get("title", ""),
                options=options,
                type=Poll.QUIZ,
                correct_option_id=correct_option,
                explanation=quiz.get("description", ""),
                is_anonymous=is_anonymous,
                open_period=duration,
            )
        else:
            message = await context.bot.send_poll(
                chat_id=chat_id,
                question=quiz.get("title", ""),
                options=options,
                is_anonymous=is_anonymous,
                open_period=duration,
            )
        # Save poll id and chat id
        quiz["poll_id"] = message.poll.id
        quiz["chat_id"] = str(chat_id)
        quiz["participants"] = quiz.get("participants", 0) + 0  # participants incremented on answers
        save_quizzes(quizzes)
    except Exception as e:
        raise

# Poll answer handler to record answers
async def poll_answer_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    answer = update.poll_answer
    if not answer:
        return
    poll_id = answer.poll_id
    user = answer.user
    selected_option = answer.option_ids[0] if answer.option_ids else None
    quizzes = load_quizzes()
    for qid, q in quizzes.items():
        if q.get("poll_id") == poll_id:
            results = load_results()
            if qid not in results:
                results[qid] = []
            is_correct = False
            if q.get("correct_option") is not None and selected_option is not None:
                is_correct = (selected_option == q.get("correct_option"))
            results[qid].append({
                "user_id": user.id if user else "غير معروف",
                "first_name": user.first_name if user else "غير معروف",
                "username": user.username if user else "",
                "selected_option": selected_option if selected_option is not None else "بدون",
                "is_correct": is_correct,
                "answered_at": datetime.now().isoformat()
            })
            save_results(results)
            q["participants"] = q.get("participants", 0) + 1
            save_quizzes(quizzes)
            break

# Cancel handler
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        await update.message.reply_text("تم الإلغاء.")
    elif update.callback_query:
        await update.callback_query.answer("تم الإلغاء.")
    return ConversationHandler.END

# ---------------------------
# Main: register handlers and run
# ---------------------------
def main() -> None:
    if TOKEN == "" or TOKEN == "PUT_YOUR_TOKEN_HERE":
        print("ضع التوكن في متغير TOKEN داخل الملف bot.py ثم أعد التشغيل.")
        return

    app = Application.builder().token(TOKEN).build()

    # Conversation handler for quiz creation flow
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("newquiz", new_quiz_command),
            CallbackQueryHandler(button_handler, pattern="^new_quiz$"),
        ],
        states={
            TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_title)],
            DESCRIPTION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_description),
                CallbackQueryHandler(skip_description, pattern="^skip_description$"),
            ],
            OPTIONS: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_options)],
            CORRECT_OPTION: [CallbackQueryHandler(correct_answer_handler, pattern="^(correct_.*|no_correct)$")],
            DURATION: [CallbackQueryHandler(duration_handler, pattern="^duration_")],
            PREVIEW: [CallbackQueryHandler(preview_handler, pattern="^(start_here|share_quiz|new_quiz|back_to_preview|sendgroup_.*)$")],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
    )

    # Register handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("admin", admin_command))
    app.add_handler(conv_handler)
    # Admin menu general buttons
    app.add_handler(CallbackQueryHandler(button_handler, pattern="^(quiz_results|list_groups|list_users|settings|toggle_anonymous|change_bot_name|back_admin)$"))
    # Results selection
    app.add_handler(CallbackQueryHandler(result_callback, pattern="^result_"))
    # Poll answers
    app.add_handler(PollAnswerHandler(poll_answer_handler))

    print("البوت يعمل الآن...")
    app.run_polling()

if __name__ == "__main__":
    main()
