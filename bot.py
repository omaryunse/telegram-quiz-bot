# bot.py
import os
import json
from datetime import datetime
from typing import Dict, Any, List, Optional

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ConversationHandler,
    CallbackQueryHandler,
    ContextTypes,
)
from telegram.constants import ChatType

# ---------------------------
# Configuration (ضع التوكن يدوياً هنا)
# ---------------------------
TOKEN = "8845301824:AAGptI-Na__Tp0ZbFgvQ-HSfHOawDCuhFK4"
# قائمة المسؤولين الثلاثة فقط
ADMIN_IDS = ["7021041990", "8810965759", "7020921829"]

# ملفات التخزين المحلية (JSON)
QUIZZES_FILE = "quizzes.json"
USERS_FILE = "users.json"
SETTINGS_FILE = "settings.json"
GROUPS_FILE = "groups.json"
RESULTS_FILE = "results.json"

# Conversation states for quiz creation
(
    QUIZ_TITLE,
    ADD_QUESTION_TEXT,
    ADD_QUESTION_OPTIONS,
    ADD_QUESTION_CORRECT,
    ASK_ADD_MORE,
    SET_DURATION,
    PREVIEW,
) = range(7)

# ---------------------------
# JSON utilities
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
        settings = {"allow_anonymous": False, "bot_name": "Quiz Bot"}
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
def is_admin_user(user_id: Optional[int]) -> bool:
    if user_id is None:
        return False
    return str(user_id) in ADMIN_IDS

def is_admin_update(update: Update) -> bool:
    user = update.effective_user
    if not user and update.callback_query:
        user = update.callback_query.from_user
    return is_admin_user(user.id if user else None)

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

# Decorator-like check for handlers to restrict to admins
async def require_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user = update.effective_user if update.effective_user else (update.callback_query.from_user if update.callback_query else None)
    if not user or not is_admin_user(user.id):
        # For private chats: inform user bot is for admins only
        if update.effective_chat and update.effective_chat.type == ChatType.PRIVATE:
            if update.message:
                await update.message.reply_text("⚠️ هذا البوت خاص بالمسؤولين فقط. لا يمكنك استخدامه.")
            elif update.callback_query:
                await update.callback_query.answer("هذا البوت خاص بالمسؤولين فقط.", show_alert=True)
        else:
            # In groups, do nothing (or track)
            pass
        return False
    return True

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
# Handlers
# ---------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Track user and group
    if update.effective_user:
        track_user(update.effective_user)
    if update.effective_chat and update.effective_chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]:
        track_group(update.effective_chat)
        if update.message:
            await update.message.reply_text("👋 أهلاً! تم تسجيل المجموعة. استخدم البوت في الخاص لإدارة الاختبارات (للمسؤولين).")
        return
    # Private chat
    user = update.effective_user
    if not user:
        return
    if is_admin_user(user.id):
        settings = load_settings()
        await update.message.reply_text(f"🔐 {settings.get('bot_name','Quiz Bot')} - لوحة التحكم", reply_markup=build_admin_keyboard())
    else:
        await update.message.reply_text("⚠️ هذا البوت خاص بالمسؤولين فقط. لا يمكنك تفعيله أو استخدامه.")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await require_admin(update, context):
        return
    text = (
        "/start - افتح لوحة التحكم\n"
        "/newquiz - إنشاء اختبار جديد\n"
        "/help - عرض المساعدة"
    )
    await update.message.reply_text(text)

# Admin menu button handler
async def admin_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return
    await query.answer()
    # require admin
    if not await require_admin(update, context):
        return
    track_user(query.from_user)
    data = query.data

    if data == "new_quiz":
        # initialize builder
        context.user_data["building_quiz"] = {"title": "", "questions": [], "duration": 60}
        await query.message.reply_text("✍️ أرسل عنوان مجموعة الأسئلة (اسم الاختبار):")
        return QUIZ_TITLE

    if data == "quiz_results":
        await show_quiz_results(query)
        return

    if data == "list_users":
        users = load_users()
        if not users:
            await query.message.reply_text("لا يوجد مستخدمون مسجلون.")
            return
        text = "👥 المستخدمون:\n\n"
        for uid, u in users.items():
            username = f"@{u['username']}" if u.get("username") else "بدون"
            text += f"• {u.get('first_name','بدون')} ({username}) - ID: {uid} - استخدامات: {u.get('total_messages',0)}\n"
        await query.message.reply_text(text)
        return

    if data == "list_groups":
        groups = load_groups()
        if not groups:
            await query.message.reply_text("لا توجد مجموعات مسجلة.")
            return
        text = "🌐 المجموعات:\n\n"
        for gid, g in groups.items():
            text += f"• {g.get('title','بدون')} - ID: {gid}\n"
        await query.message.reply_text(text)
        return

    if data == "settings":
        settings = load_settings()
        status = "مفعل ✅" if settings.get("allow_anonymous") else "معطل ❌"
        keyboard = [
            [InlineKeyboardButton(f"🔄 السري: {status}", callback_data="toggle_anonymous")],
            [InlineKeyboardButton("↩️ رجوع", callback_data="back_admin")],
        ]
        await query.message.reply_text(f"⚙️ الإعدادات:\n\nالاستفتاء السري: {status}", reply_markup=InlineKeyboardMarkup(keyboard))
        return

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
        return

    if data == "back_admin":
        await query.message.edit_text("🔐 لوحة التحكم:", reply_markup=build_admin_keyboard())
        return

# Show quiz list for results selection
async def show_quiz_results(query):
    quizzes = load_quizzes()
    if not quizzes:
        await query.message.reply_text("لا توجد اختبارات محفوظة.")
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
    if not await require_admin(update, context):
        return
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
        text += f"{status} {r.get('first_name','')} ({username}) - السؤال: {r.get('question_text','')} - اختار: {r.get('selected_text','')}\n"
    await query.message.reply_text(text)

# ---------------------------
# Quiz creation flow
# ---------------------------
async def quiz_title_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, context):
        return ConversationHandler.END
    text = update.message.text.strip() if update.message and update.message.text else ""
    if not text:
        await update.message.reply_text("⚠️ العنوان لا يمكن أن يكون فارغاً. أعد الإرسال:")
        return QUIZ_TITLE
    context.user_data["building_quiz"] = {"title": text, "questions": [], "duration": 60}
    await update.message.reply_text("✍️ أرسل نص السؤال الأول:")
    return ADD_QUESTION_TEXT

async def add_question_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, context):
        return ConversationHandler.END
    text = update.message.text.strip() if update.message and update.message.text else ""
    if not text:
        await update.message.reply_text("⚠️ نص السؤال لا يمكن أن يكون فارغاً. أعد الإرسال:")
        return ADD_QUESTION_TEXT
    context.user_data["current_question"] = {"text": text, "options": [], "correct": None}
    await update.message.reply_text("🔢 أرسل الخيارات (كل خيار في سطر). الحد الأدنى 2 والحد الأقصى 10:")
    return ADD_QUESTION_OPTIONS

async def add_question_options(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, context):
        return ConversationHandler.END
    text = update.message.text if update.message and update.message.text else ""
    options = [line.strip() for line in text.splitlines() if line.strip()]
    if len(options) < 2:
        await update.message.reply_text("⚠️ يجب أن يكون هناك خياران على الأقل. أعد إرسال الخيارات:")
        return ADD_QUESTION_OPTIONS
    if len(options) > 10:
        await update.message.reply_text("⚠️ الحد الأقصى 10 خيارات. أعد إرسال الخيارات:")
        return ADD_QUESTION_OPTIONS
    context.user_data["current_question"]["options"] = options
    # build keyboard for correct option
    keyboard = []
    for i, opt in enumerate(options):
        keyboard.append([InlineKeyboardButton(f"{i+1}. {opt}", callback_data=f"setcorrect_{i}")])
    keyboard.append([InlineKeyboardButton("بدون إجابة صحيحة", callback_data="setcorrect_none")])
    await update.message.reply_text("✅ اختر الإجابة الصحيحة (أو اختر بدون إجابة صحيحة):", reply_markup=InlineKeyboardMarkup(keyboard))
    return ADD_QUESTION_CORRECT

async def set_correct_option(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return ConversationHandler.END
    await query.answer()
    if not await require_admin(update, context):
        return ConversationHandler.END
    data = query.data
    if data == "setcorrect_none":
        context.user_data["current_question"]["correct"] = None
    else:
        try:
            idx = int(data.replace("setcorrect_", ""))
            context.user_data["current_question"]["correct"] = idx
        except Exception:
            context.user_data["current_question"]["correct"] = None
    # append question to quiz
    bq = context.user_data.get("building_quiz", {"questions": []})
    bq["questions"].append(context.user_data["current_question"])
    context.user_data["building_quiz"] = bq
    context.user_data.pop("current_question", None)
    # ask add more or finish
    keyboard = [
        [InlineKeyboardButton("➕ إضافة سؤال آخر", callback_data="add_more")],
        [InlineKeyboardButton("✅ إنهاء وإنشاء الاختبار", callback_data="finish_quiz")],
    ]
    await query.message.reply_text("هل تريد إضافة سؤال آخر أم إنهاء مجموعة الأسئلة؟", reply_markup=InlineKeyboardMarkup(keyboard))
    return ASK_ADD_MORE

async def ask_add_more_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return ConversationHandler.END
    await query.answer()
    if not await require_admin(update, context):
        return ConversationHandler.END
    data = query.data
    if data == "add_more":
        await query.message.reply_text("✍️ أرسل نص السؤال التالي:")
        return ADD_QUESTION_TEXT
    if data == "finish_quiz":
        # ask duration
        keyboard = [
            [InlineKeyboardButton("⏱️ 30 ثانية", callback_data="dur_30")],
            [InlineKeyboardButton("⏱️ دقيقة", callback_data="dur_60")],
            [InlineKeyboardButton("⏱️ دقيقتان", callback_data="dur_120")],
            [InlineKeyboardButton("⏱️ 5 دقائق", callback_data="dur_300")],
            [InlineKeyboardButton("⏱️ 10 دقائق", callback_data="dur_600")],
        ]
        await query.message.reply_text("⏳ اختر مدة الإجابة لكل سؤال (بالثواني):", reply_markup=InlineKeyboardMarkup(keyboard))
        return SET_DURATION
    return ConversationHandler.END

async def set_duration_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return ConversationHandler.END
    await query.answer()
    if not await require_admin(update, context):
        return ConversationHandler.END
    data = query.data
    try:
        dur = int(data.replace("dur_", ""))
    except Exception:
        dur = 60
    bq = context.user_data.get("building_quiz", {"questions": []})
    bq["duration"] = dur
    # save quiz
    quiz_id = datetime.now().strftime("%Y%m%d%H%M%S")
    quizzes = load_quizzes()
    quizzes[quiz_id] = {
        "title": bq.get("title", ""),
        "questions": bq.get("questions", []),
        "duration": bq.get("duration", 60),
        "created_at": datetime.now().isoformat(),
    }
    save_quizzes(quizzes)
    context.user_data["last_quiz_id"] = quiz_id
    # preview
    preview_text = f"📋 تم إنشاء مجموعة الأسئلة:\n\n❓ {bq.get('title','')}\nعدد الأسئلة: {len(bq.get('questions',[]))}\nمدة السؤال: {bq.get('duration',60)} ثانية\n\nيمكنك الآن:\n"
    keyboard = [
        [InlineKeyboardButton("🚀 بدء الاختبار هنا (تتابعي)", callback_data=f"start_seq_{quiz_id}")],
        [InlineKeyboardButton("📤 إرسال للمجموعة", callback_data=f"sharegroup_{quiz_id}")],
        [InlineKeyboardButton("➕ إنشاء مجموعة جديدة", callback_data="new_quiz")],
        [InlineKeyboardButton("↩️ رجوع للوحة", callback_data="back_admin")],
    ]
    await query.message.reply_text(preview_text, reply_markup=InlineKeyboardMarkup(keyboard))
    # clear building state
    context.user_data.pop("building_quiz", None)
    return PREVIEW

# Preview callbacks: start sequential quiz or share to group
async def preview_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return
    await query.answer()
    if not await require_admin(update, context):
        return
    data = query.data
    if data.startswith("start_seq_"):
        quiz_id = data.replace("start_seq_", "")
        # start sequential session for this admin (private)
        await start_sequential_quiz_for_user(query.from_user.id, context, quiz_id, query.message)
        return
    if data.startswith("sharegroup_"):
        quiz_id = data.replace("sharegroup_", "")
        groups = load_groups()
        if not groups:
            await query.message.reply_text("لا توجد مجموعات مسجلة.")
            return
        keyboard = []
        for gid, g in groups.items():
            keyboard.append([InlineKeyboardButton(f"{g.get('title','بدون')}", callback_data=f"sendgroup_{gid}_{quiz_id}")])
        keyboard.append([InlineKeyboardButton("↩️ رجوع", callback_data="back_admin")])
        await query.message.reply_text("اختر المجموعة لإرسال الاختبار (سيتم إرسال كل سؤال كرسالة تتابعية):", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if data == "new_quiz":
        # start new creation
        context.user_data["building_quiz"] = {"title": "", "questions": [], "duration": 60}
        await query.message.reply_text("✍️ أرسل عنوان مجموعة الأسئلة الجديدة:")
        return QUIZ_TITLE

    if data == "back_admin":
        await query.message.edit_text("🔐 لوحة التحكم:", reply_markup=build_admin_keyboard())
        return

    if data.startswith("sendgroup_"):
        # pattern sendgroup_{gid}_{quizid}
        parts = data.split("_", 2)
        if len(parts) < 3:
            await query.message.reply_text("معرف غير صالح.")
            return
        gid = parts[1]
        qid = parts[2]
        try:
            gid_int = int(gid)
        except Exception:
            await query.message.reply_text("معرف المجموعة غير صالح.")
            return
        # send sequential quiz to group as series of messages with inline buttons for options
        await send_sequential_quiz_to_group(gid_int, context, qid)
        await query.message.reply_text("✅ تم إرسال الاختبار إلى المجموعة.")
        return

# ---------------------------
# Sequential quiz runtime (per-user session using inline buttons)
# ---------------------------
# We'll maintain active sessions in memory (not persisted). Keyed by user_id -> session dict
ACTIVE_SESSIONS: Dict[str, Dict[str, Any]] = {}

async def start_sequential_quiz_for_user(user_id: int, context: ContextTypes.DEFAULT_TYPE, quiz_id: str, reply_target) -> None:
    quizzes = load_quizzes()
    quiz = quizzes.get(quiz_id)
    if not quiz:
        await reply_target.reply_text("❌ الاختبار غير موجود.")
        return
    # initialize session
    session = {
        "quiz_id": quiz_id,
        "user_id": user_id,
        "current_index": 0,
        "answers": [],
        "started_at": datetime.now().isoformat(),
    }
    ACTIVE_SESSIONS[str(user_id)] = session
    # send first question to the user (private)
    try:
        chat_id = user_id
        await send_question_to_user(chat_id, context, quiz, 0)
    except Exception as e:
        await reply_target.reply_text(f"❌ فشل بدء الاختبار: {e}")

async def send_question_to_user(chat_id: int, context: ContextTypes.DEFAULT_TYPE, quiz: Dict[str, Any], q_index: int) -> None:
    questions = quiz.get("questions", [])
    if q_index < 0 or q_index >= len(questions):
        # finished
        await context.bot.send_message(chat_id=chat_id, text="✅ انتهى الاختبار. شكراً لمشاركتك.")
        # save results summary
        await finalize_session(chat_id, context)
        return
    q = questions[q_index]
    text = f"سؤال {q_index+1}/{len(questions)}:\n\n{q.get('text','')}"
    options = q.get("options", [])
    keyboard = []
    for i, opt in enumerate(options):
        keyboard.append([InlineKeyboardButton(f"{i+1}. {opt}", callback_data=f"answer_{q_index}_{i}")])
    # add skip option
    keyboard.append([InlineKeyboardButton("تخطي السؤال", callback_data=f"answer_{q_index}_-1")])
    await context.bot.send_message(chat_id=chat_id, text=text, reply_markup=InlineKeyboardMarkup(keyboard))

# Handle user's answer callbacks in sequential session
async def sequential_answer_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return
    await query.answer()
    user = query.from_user
    uid = str(user.id)
    if uid not in ACTIVE_SESSIONS:
        await query.message.reply_text("لا يوجد اختبار نشط لديك. اطلب من المسؤول بدء الاختبار.")
        return
    session = ACTIVE_SESSIONS[uid]
    data = query.data  # format: answer_{q_index}_{opt_index}
    parts = data.split("_")
    if len(parts) < 3:
        await query.message.reply_text("بيانات غير صحيحة.")
        return
    try:
        q_index = int(parts[1])
        opt_index = int(parts[2])
    except Exception:
        await query.message.reply_text("بيانات غير صحيحة.")
        return
    quizzes = load_quizzes()
    quiz = quizzes.get(session["quiz_id"])
    if not quiz:
        await query.message.reply_text("الاختبار غير موجود.")
        ACTIVE_SESSIONS.pop(uid, None)
        return
    questions = quiz.get("questions", [])
    if q_index < 0 or q_index >= len(questions):
        await query.message.reply_text("السؤال غير موجود.")
        return
    q = questions[q_index]
    selected_text = "تخطي" if opt_index == -1 else (q.get("options", [])[opt_index] if 0 <= opt_index < len(q.get("options", [])) else "غير معروف")
    is_correct = False
    if q.get("correct") is not None and opt_index != -1:
        is_correct = (opt_index == q.get("correct"))
    # record answer
    session["answers"].append({
        "question_index": q_index,
        "question_text": q.get("text", ""),
        "selected_index": opt_index,
        "selected_text": selected_text,
        "is_correct": is_correct,
        "answered_at": datetime.now().isoformat(),
    })
    # advance index
    session["current_index"] = q_index + 1
    # save partial results to persistent storage (optional)
    # send feedback and next question
    feedback = "✅ إجابة صحيحة!" if is_correct else ("⚠️ إجابة خاطئة." if opt_index != -1 else "⚠️ تم تخطي السؤال.")
    await query.message.reply_text(feedback)
    # send next question or finish
    next_index = session["current_index"]
    if next_index >= len(questions):
        await context.bot.send_message(chat_id=user.id, text="✅ انتهى الاختبار. جاري حفظ النتائج...")
        await finalize_session(user.id, context)
        ACTIVE_SESSIONS.pop(uid, None)
        return
    # send next
    await send_question_to_user(user.id, context, quiz, next_index)

async def finalize_session(user_chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    uid = str(user_chat_id)
    session = ACTIVE_SESSIONS.get(uid)
    if not session:
        return
    quiz_id = session.get("quiz_id")
    results = load_results()
    if quiz_id not in results:
        results[quiz_id] = []
    # store each answer as separate record for reporting
    for ans in session.get("answers", []):
        results[quiz_id].append({
            "user_id": user_chat_id,
            "first_name": context.bot.get_chat(user_chat_id).first_name if context.bot.get_chat(user_chat_id) else "",
            "username": context.bot.get_chat(user_chat_id).username if context.bot.get_chat(user_chat_id) else "",
            "question_index": ans.get("question_index"),
            "question_text": ans.get("question_text"),
            "selected_index": ans.get("selected_index"),
            "selected_text": ans.get("selected_text"),
            "is_correct": ans.get("is_correct"),
            "answered_at": ans.get("answered_at"),
        })
    save_results(results)

# Send sequential quiz to a group: posts questions one by one to the group; users answer via inline buttons (session per user still tracked)
async def send_sequential_quiz_to_group(group_id: int, context: ContextTypes.DEFAULT_TYPE, quiz_id: str):
    quizzes = load_quizzes()
    quiz = quizzes.get(quiz_id)
    if not quiz:
        return
    # For group mode, we will post the first question to the group; each user who clicks will start their own session
    q0 = quiz.get("questions", [])[0] if quiz.get("questions") else None
    if not q0:
        await context.bot.send_message(chat_id=group_id, text="لا توجد أسئلة في هذا الاختبار.")
        return
    text = f"📢 اختبار: {quiz.get('title','')}\n\nالسؤال 1: {q0.get('text','')}\n\nاضغط على خيارك لبدء المشاركة (كل مشارك سيجيب تتابعياً على الأسئلة)."
    keyboard = []
    for i, opt in enumerate(q0.get("options", [])):
        # callback will start a session for that user and record answer 0
        keyboard.append([InlineKeyboardButton(f"{i+1}. {opt}", callback_data=f"group_answer_{quiz_id}_0_{i}")])
    keyboard.append([InlineKeyboardButton("تخطي السؤال", callback_data=f"group_answer_{quiz_id}_0_-1")])
    await context.bot.send_message(chat_id=group_id, text=text, reply_markup=InlineKeyboardMarkup(keyboard))

# Handle group answer callbacks: start or continue session for that user
async def group_answer_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return
    await query.answer()
    user = query.from_user
    if not user:
        return
    data = query.data  # format: group_answer_{quizid}_{qindex}_{opt}
    parts = data.split("_", 3)
    if len(parts) < 4:
        await query.message.reply_text("بيانات غير صحيحة.")
        return
    _, _, quiz_id, rest = parts[0], parts[1], parts[2], parts[3]
    # rest contains "{qindex}_{opt}"
    try:
        qindex_str, opt_str = rest.split("_", 1)
        qindex = int(qindex_str)
        opt_index = int(opt_str)
    except Exception:
        await query.message.reply_text("بيانات غير صحيحة.")
        return
    uid = str(user.id)
    # ensure session exists for this user and quiz
    session = ACTIVE_SESSIONS.get(uid)
    if not session or session.get("quiz_id") != quiz_id:
        # start new session for this user and quiz
        ACTIVE_SESSIONS[uid] = {
            "quiz_id": quiz_id,
            "user_id": user.id,
            "current_index": 0,
            "answers": [],
            "started_at": datetime.now().isoformat(),
        }
        session = ACTIVE_SESSIONS[uid]
    # emulate same logic as sequential_answer_handler but using group context
    quizzes = load_quizzes()
    quiz = quizzes.get(quiz_id)
    if not quiz:
        await query.message.reply_text("الاختبار غير موجود.")
        return
    questions = quiz.get("questions", [])
    if qindex < 0 or qindex >= len(questions):
        await query.message.reply_text("السؤال غير موجود.")
        return
    q = questions[qindex]
    selected_text = "تخطي" if opt_index == -1 else (q.get("options", [])[opt_index] if 0 <= opt_index < len(q.get("options", [])) else "غير معروف")
    is_correct = False
    if q.get("correct") is not None and opt_index != -1:
        is_correct = (opt_index == q.get("correct"))
    session["answers"].append({
        "question_index": qindex,
        "question_text": q.get("text", ""),
        "selected_index": opt_index,
        "selected_text": selected_text,
        "is_correct": is_correct,
        "answered_at": datetime.now().isoformat(),
    })
    session["current_index"] = qindex + 1
    # send feedback privately to user and next question privately
    try:
        feedback = "✅ إجابة صحيحة!" if is_correct else ("⚠️ إجابة خاطئة." if opt_index != -1 else "⚠️ تم تخطي السؤال.")
        await context.bot.send_message(chat_id=user.id, text=f"ردك على السؤال {qindex+1}: {feedback}\nسوف يتم إرسال السؤال التالي هنا في الخاص.")
        # send next question privately
        next_index = session["current_index"]
        if next_index >= len(questions):
            await context.bot.send_message(chat_id=user.id, text="✅ انتهى الاختبار. جاري حفظ النتائج...")
            await finalize_session(user.id, context)
            ACTIVE_SESSIONS.pop(uid, None)
            await query.message.reply_text(f"تمت مشاركة إجابة {user.first_name}. انتهى الاختبار لديهم.")
            return
        await send_question_to_user(user.id, context, quiz, next_index)
        await query.message.reply_text(f"تم تسجيل إجابة {user.first_name}. السؤال التالي أُرسل في الخاص.")
    except Exception:
        await query.message.reply_text("تعذر إرسال السؤال التالي في الخاص للمستخدم (ربما أغلق المحادثة).")

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
            CallbackQueryHandler(admin_button_handler, pattern="^new_quiz$"),
            CommandHandler("newquiz", lambda u, c: new_quiz_command_wrapper(u, c)),
        ],
        states={
            QUIZ_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, quiz_title_handler)],
            ADD_QUESTION_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_question_text)],
            ADD_QUESTION_OPTIONS: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_question_options)],
            ADD_QUESTION_CORRECT: [CallbackQueryHandler(set_correct_option, pattern="^setcorrect_")],
            ASK_ADD_MORE: [CallbackQueryHandler(ask_add_more_handler, pattern="^(add_more|finish_quiz)$")],
            SET_DURATION: [CallbackQueryHandler(set_duration_handler, pattern="^dur_")],
            PREVIEW: [CallbackQueryHandler(preview_callback_handler, pattern="^(start_seq_|sharegroup_|new_quiz|back_admin|sendgroup_).*")],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
    )

    # wrapper for /newquiz to ensure admin
    async def new_quiz_command_wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await require_admin(update, context):
            return ConversationHandler.END
        # simulate pressing new_quiz
        context.user_data["building_quiz"] = {"title": "", "questions": [], "duration": 60}
        await update.message.reply_text("✍️ أرسل عنوان مجموعة الأسئلة (اسم الاختبار):")
        return QUIZ_TITLE

    # Register handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("admin", lambda u, c: admin_command_wrapper(u, c)))
    # admin menu general buttons
    app.add_handler(CallbackQueryHandler(admin_button_handler, pattern="^(new_quiz|quiz_results|list_groups|list_users|settings|toggle_anonymous|change_bot_name|back_admin)$"))
    # results selection
    app.add_handler(CallbackQueryHandler(result_callback, pattern="^result_"))
    # preview and send group callbacks
    app.add_handler(CallbackQueryHandler(preview_callback_handler, pattern="^(start_seq_|sharegroup_|new_quiz|back_admin|sendgroup_).*"))
    # sequential answer handlers (private)
    app.add_handler(CallbackQueryHandler(sequential_answer_handler, pattern="^answer_"))
    # group answer handlers
    app.add_handler(CallbackQueryHandler(group_answer_handler, pattern="^group_answer_"))
    # conv handler for creation
    app.add_handler(conv_handler)

    print("البوت يعمل الآن...")
    app.run_polling()

# small wrapper for /admin command to show admin keyboard if admin
async def admin_command_wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, context):
        return
    await update.message.reply_text("🔐 لوحة التحكم:", reply_markup=build_admin_keyboard())

if __name__ == "__main__":
    main()
