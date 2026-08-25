# bot.py
import os
import json
import logging
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
# المسؤولون الثلاثة فقط
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
    QUIZ_DESCRIPTION,
    QUIZ_DURATION,
    QUESTION_TEXT,
    QUESTION_OPTIONS,
    QUESTION_CORRECT,
    QUESTION_ADD_MORE,
    PREVIEW_STATE,
) = range(8)

# In-memory active sessions for sequential quizzes (per user)
ACTIVE_SESSIONS: Dict[str, Dict[str, Any]] = {}

# ---------------------------
# Logging
# ---------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------------
# JSON utilities
# ---------------------------
def load_json(path: str) -> Dict[str, Any]:
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
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
    s = load_json(SETTINGS_FILE)
    if not s:
        s = {"allow_anonymous": False, "bot_name": "Quiz Bot"}
        save_settings(s)
    return s

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

async def require_admin_private(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Return True if the user is admin; if not, send a private notice and return False."""
    user = update.effective_user if update.effective_user else (update.callback_query.from_user if update.callback_query else None)
    if not user or not is_admin_user(user.id):
        # If private chat, inform user it's admin-only
        if update.effective_chat and update.effective_chat.type == ChatType.PRIVATE:
            if update.message:
                await update.message.reply_text("⚠️ هذا البوت مخصص للمسؤولين فقط. لا يمكنك استخدامه هنا.")
            elif update.callback_query:
                await update.callback_query.answer("هذا البوت مخصص للمسؤولين فقط.", show_alert=True)
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
            await update.message.reply_text("👋 تم تسجيل المجموعة. لبدء الاختبارات من هنا، استخدم لوحة التحكم في الخاص (للمسؤولين).")
        return
    # Private chat
    user = update.effective_user
    if not user:
        return
    if is_admin_user(user.id):
        settings = load_settings()
        await update.message.reply_text(f"🔐 {settings.get('bot_name','Quiz Bot')} - لوحة التحكم", reply_markup=build_admin_keyboard())
    else:
        await update.message.reply_text("⚠️ هذا البوت مخصص للمسؤولين فقط. لا يمكنك تفعيله هنا.")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await require_admin_private(update, context):
        return
    text = (
        "/start - افتح لوحة التحكم\n"
        "/newquiz - إنشاء مجموعة أسئلة جديدة\n"
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
    if not await require_admin_private(update, context):
        return
    track_user(query.from_user)
    data = query.data

    if data == "new_quiz":
        # initialize builder
        context.user_data["building_quiz"] = {"title": "", "description": "", "duration": 60, "questions": []}
        await query.message.reply_text("✍️ أرسل عنوان مجموعة الأسئلة (اسم الاختبار):")
        return

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
    if not await require_admin_private(update, context):
        return
    qid = query.data.replace("result_", "")
    results = load_results().get(qid, [])
    quizzes = load_quizzes()
    quiz = quizzes.get(qid, {})
    if not results:
        await query.message.reply_text("لا توجد نتائج لهذا الاختبار بعد.")
        return
    # aggregate per user
    per_user: Dict[str, Dict[str, Any]] = {}
    for r in results:
        uid = str(r.get("user_id"))
        if uid not in per_user:
            per_user[uid] = {"first_name": r.get("first_name",""), "username": r.get("username",""), "answers": [], "correct": 0}
        per_user[uid]["answers"].append(r)
        if r.get("is_correct"):
            per_user[uid]["correct"] += 1
    text = f"📊 نتائج: {quiz.get('title','')}\n\n"
    text += f"👥 عدد المشاركين: {len(per_user)}\n\n"
    for uid, info in per_user.items():
        username = f"@{info.get('username')}" if info.get("username") else "بدون"
        text += f"• {info.get('first_name','')} ({username}) - إجابات صحيحة: {info.get('correct')} - إجابات: {len(info.get('answers',[]))}\n"
    await query.message.reply_text(text)

# ---------------------------
# Quiz creation flow handlers
# ---------------------------
async def newquiz_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_admin_private(update, context):
        return
    context.user_data["building_quiz"] = {"title": "", "description": "", "duration": 60, "questions": []}
    await update.message.reply_text("✍️ أرسل عنوان مجموعة الأسئلة (اسم الاختبار):")
    return QUIZ_TITLE

async def quiz_title_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_admin_private(update, context):
        return ConversationHandler.END
    text = update.message.text.strip() if update.message and update.message.text else ""
    if not text:
        await update.message.reply_text("⚠️ العنوان لا يمكن أن يكون فارغاً. أعد الإرسال:")
        return QUIZ_TITLE
    context.user_data["building_quiz"]["title"] = text
    await update.message.reply_text("📝 أرسل وصف الاختبار (أو اكتب /skip لوضع وصف فارغ):")
    return QUIZ_DESCRIPTION

async def quiz_description_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_admin_private(update, context):
        return ConversationHandler.END
    text = update.message.text.strip() if update.message and update.message.text else ""
    context.user_data["building_quiz"]["description"] = text
    await update.message.reply_text("⏳ اختر مدة الإجابة لكل سؤال (بالثواني):\n30, 60, 120, 300, 600\nأو اكتب الرقم مباشرة (مثال: 60)")
    return QUIZ_DURATION

async def quiz_skip_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_admin_private(update, context):
        return ConversationHandler.END
    context.user_data["building_quiz"]["description"] = ""
    await update.message.reply_text("⏳ اختر مدة الإجابة لكل سؤال (بالثواني):\n30, 60, 120, 300, 600\nأو اكتب الرقم مباشرة (مثال: 60)")
    return QUIZ_DURATION

async def quiz_duration_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_admin_private(update, context):
        return ConversationHandler.END
    text = update.message.text.strip() if update.message and update.message.text else ""
    try:
        dur = int(text)
        if dur <= 0:
            raise ValueError
    except Exception:
        await update.message.reply_text("⚠️ قيمة غير صحيحة. أرسل مدة بالثواني مثل 30 أو 60 أو 120.")
        return QUIZ_DURATION
    context.user_data["building_quiz"]["duration"] = dur
    await update.message.reply_text("✍️ الآن أرسل نص السؤال الأول:")
    return QUESTION_TEXT

async def question_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_admin_private(update, context):
        return ConversationHandler.END
    text = update.message.text.strip() if update.message and update.message.text else ""
    if not text:
        await update.message.reply_text("⚠️ نص السؤال لا يمكن أن يكون فارغاً. أعد الإرسال:")
        return QUESTION_TEXT
    context.user_data["current_question"] = {"text": text, "options": [], "correct": None}
    await update.message.reply_text("🔢 أرسل الخيارات (كل خيار في سطر). الحد الأدنى 2 والحد الأقصى 10:")
    return QUESTION_OPTIONS

async def question_options_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_admin_private(update, context):
        return ConversationHandler.END
    text = update.message.text if update.message and update.message.text else ""
    options = [line.strip() for line in text.splitlines() if line.strip()]
    if len(options) < 2:
        await update.message.reply_text("⚠️ يجب أن يكون هناك خياران على الأقل. أعد إرسال الخيارات:")
        return QUESTION_OPTIONS
    if len(options) > 10:
        await update.message.reply_text("⚠️ الحد الأقصى 10 خيارات. أعد إرسال الخيارات:")
        return QUESTION_OPTIONS
    context.user_data["current_question"]["options"] = options
    # build keyboard for correct option
    keyboard = []
    for i, opt in enumerate(options):
        keyboard.append([InlineKeyboardButton(f"{i+1}. {opt}", callback_data=f"correct_{i}")])
    keyboard.append([InlineKeyboardButton("بدون إجابة صحيحة", callback_data="correct_none")])
    await update.message.reply_text("✅ اختر الإجابة الصحيحة (أو اختر بدون إجابة صحيحة):", reply_markup=InlineKeyboardMarkup(keyboard))
    return QUESTION_CORRECT

async def question_correct_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return ConversationHandler.END
    await query.answer()
    if not await require_admin_private(update, context):
        return ConversationHandler.END
    data = query.data
    if data == "correct_none":
        context.user_data["current_question"]["correct"] = None
    else:
        try:
            idx = int(data.replace("correct_", ""))
            context.user_data["current_question"]["correct"] = idx
        except Exception:
            context.user_data["current_question"]["correct"] = None
    # append question
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
    return QUESTION_ADD_MORE

async def question_add_more_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return ConversationHandler.END
    await query.answer()
    if not await require_admin_private(update, context):
        return ConversationHandler.END
    data = query.data
    if data == "add_more":
        await query.message.reply_text("✍️ أرسل نص السؤال التالي:")
        return QUESTION_TEXT
    if data == "finish_quiz":
        # save quiz and preview
        bq = context.user_data.get("building_quiz", {})
        quiz_id = datetime.now().strftime("%Y%m%d%H%M%S")
        quizzes = load_quizzes()
        quizzes[quiz_id] = {
            "title": bq.get("title", ""),
            "description": bq.get("description", ""),
            "duration": bq.get("duration", 60),
            "questions": bq.get("questions", []),
            "created_at": datetime.now().isoformat(),
        }
        save_quizzes(quizzes)
        context.user_data["last_quiz_id"] = quiz_id
        preview_text = f"📋 تم إنشاء مجموعة الأسئلة:\n\n❓ {bq.get('title','')}\nعدد الأسئلة: {len(bq.get('questions',[]))}\nمدة السؤال: {bq.get('duration',60)} ثانية\n\nيمكنك الآن:"
        keyboard = [
            [InlineKeyboardButton("🚀 بدء الاختبار هنا (تتابعي في الخاص)", callback_data=f"start_seq_{quiz_id}")],
            [InlineKeyboardButton("📤 إرسال للمجموعة", callback_data=f"sharegroup_{quiz_id}")],
            [InlineKeyboardButton("➕ إنشاء مجموعة جديدة", callback_data="new_quiz")],
            [InlineKeyboardButton("↩️ رجوع للوحة", callback_data="back_admin")],
        ]
        await query.message.reply_text(preview_text, reply_markup=InlineKeyboardMarkup(keyboard))
        # clear building state
        context.user_data.pop("building_quiz", None)
        return PREVIEW_STATE
    return ConversationHandler.END

# Preview callbacks: start sequential quiz or share to group
async def preview_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return
    await query.answer()
    if not await require_admin_private(update, context):
        return
    data = query.data
    if data.startswith("start_seq_"):
        quiz_id = data.replace("start_seq_", "")
        # start sequential session for this admin (private)
        await start_sequential_quiz_for_user(query.from_user.id, context, quiz_id)
        await query.message.reply_text("✅ بدأ الاختبار في الخاص لديك.")
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
        await query.message.reply_text("اختر المجموعة لإرسال الاختبار (سيظهر زر بدء في المجموعة):", reply_markup=InlineKeyboardMarkup(keyboard))
        return
    if data == "new_quiz":
        context.user_data["building_quiz"] = {"title": "", "description": "", "duration": 60, "questions": []}
        await query.message.reply_text("✍️ أرسل عنوان مجموعة الأسئلة الجديدة:")
        return QUIZ_TITLE
    if data == "back_admin":
        await query.message.edit_text("🔐 لوحة التحكم:", reply_markup=build_admin_keyboard())
        return

# Send group message with Start Test button
async def send_quiz_to_group_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return
    await query.answer()
    if not await require_admin_private(update, context):
        return
    data = query.data
    if not data.startswith("sendgroup_"):
        return
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
    quizzes = load_quizzes()
    quiz = quizzes.get(qid)
    if not quiz:
        await query.message.reply_text("الاختبار غير موجود.")
        return
    # Post an announcement in the group with a Start Test button
    text = f"📢 اختبار جديد: {quiz.get('title','')}\n\n{quiz.get('description','')}\n\nاضغط زر 'بدء الاختبار' لبدء الاختبار في الخاص مع البوت."
    keyboard = [[InlineKeyboardButton("🚀 بدء الاختبار", callback_data=f"group_start_{qid}")]]
    try:
        await context.bot.send_message(chat_id=gid_int, text=text, reply_markup=InlineKeyboardMarkup(keyboard))
        await query.message.reply_text("✅ تم إرسال الإعلان إلى المجموعة.")
    except Exception as e:
        await query.message.reply_text(f"❌ فشل الإرسال إلى المجموعة: {e}")

# ---------------------------
# Sequential quiz runtime (per-user session)
# ---------------------------
async def start_sequential_quiz_for_user(user_id: int, context: ContextTypes.DEFAULT_TYPE, quiz_id: str) -> None:
    quizzes = load_quizzes()
    quiz = quizzes.get(quiz_id)
    if not quiz:
        try:
            await context.bot.send_message(chat_id=user_id, text="❌ الاختبار غير موجود.")
        except Exception:
            pass
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
        await send_question_to_user(user_id, context, quiz, 0)
    except Exception:
        # user may not have opened private chat with bot
        # inform via admin or ignore
        logger.exception("Failed to send first question to user %s", user_id)

async def send_question_to_user(chat_id: int, context: ContextTypes.DEFAULT_TYPE, quiz: Dict[str, Any], q_index: int) -> None:
    questions = quiz.get("questions", [])
    if q_index < 0 or q_index >= len(questions):
        # finished
        try:
            await context.bot.send_message(chat_id=chat_id, text="✅ انتهى الاختبار. شكراً لمشاركتك.")
            await finalize_session(chat_id, context)
        except Exception:
            logger.exception("Failed to finalize session for %s", chat_id)
        return
    q = questions[q_index]
    text = f"سؤال {q_index+1}/{len(questions)}:\n\n{q.get('text','')}"
    options = q.get("options", [])
    keyboard = []
    for i, opt in enumerate(options):
        keyboard.append([InlineKeyboardButton(f"{i+1}. {opt}", callback_data=f"answer_{quiz.get('title','')}_{q_index}_{i}")])
    keyboard.append([InlineKeyboardButton("تخطي السؤال", callback_data=f"answer_{quiz.get('title','')}_{q_index}_-1")])
    await context.bot.send_message(chat_id=chat_id, text=text, reply_markup=InlineKeyboardMarkup(keyboard))

async def answer_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return
    await query.answer()
    user = query.from_user
    if not user:
        return
    uid = str(user.id)
    data = query.data  # format: answer_{quiztitle}_{qindex}_{opt}
    parts = data.split("_")
    # We used quiz title in callback to avoid underscores collision; parse from end
    if len(parts) < 4:
        await query.message.reply_text("بيانات غير صحيحة.")
        return
    # last two parts are qindex and opt
    try:
        q_index = int(parts[-2])
        opt_index = int(parts[-1])
    except Exception:
        await query.message.reply_text("بيانات غير صحيحة.")
        return
    # find session
    session = ACTIVE_SESSIONS.get(uid)
    if not session:
        await query.message.reply_text("لا يوجد اختبار نشط لديك. اطلب من المسؤول بدء الاختبار أو اضغط زر البدء في المجموعة أولاً.")
        return
    quiz_id = session.get("quiz_id")
    quizzes = load_quizzes()
    quiz = quizzes.get(quiz_id)
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
    session["current_index"] = q_index + 1
    # feedback
    feedback = "✅ إجابة صحيحة!" if is_correct else ("⚠️ إجابة خاطئة." if opt_index != -1 else "⚠️ تم تخطي السؤال.")
    try:
        await context.bot.send_message(chat_id=user.id, text=feedback)
    except Exception:
        logger.exception("Failed to send feedback to user %s", user.id)
    # next question or finish
    next_index = session["current_index"]
    if next_index >= len(questions):
        try:
            await context.bot.send_message(chat_id=user.id, text="✅ انتهى الاختبار. جاري حفظ النتائج...")
        except Exception:
            pass
        await finalize_session(user.id, context)
        ACTIVE_SESSIONS.pop(uid, None)
        return
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
    # store summary per user (one entry summarizing their session)
    correct_count = sum(1 for a in session.get("answers", []) if a.get("is_correct"))
    total = len(session.get("answers", []))
    # try to get user info
    first_name = ""
    username = ""
    try:
        chat = await context.bot.get_chat(user_chat_id)
        first_name = chat.first_name or ""
        username = chat.username or ""
    except Exception:
        pass
    results[quiz_id].append({
        "user_id": user_chat_id,
        "first_name": first_name,
        "username": username,
        "correct": correct_count,
        "total_answered": total,
        "answers": session.get("answers", []),
        "finished_at": datetime.now().isoformat(),
    })
    save_results(results)
    # send summary to user
    try:
        await context.bot.send_message(chat_id=user_chat_id, text=f"📊 انتهى الاختبار. إجابات صحيحة: {correct_count} من {total}. شكراً لمشاركتك.")
    except Exception:
        pass
    # notify admins with detailed result
    admins = ADMIN_IDS
    summary_text = f"📥 نتيجة اختبار للمستخدم {first_name} (@{username})\nالاختبار: {load_quizzes().get(quiz_id,{}).get('title','')}\nالنتيجة: {correct_count}/{total}\nوقت الإنهاء: {datetime.now().isoformat()}\n"
    # include per-question details (limited)
    for a in session.get("answers", []):
        qtext = a.get("question_text","")
        sel = a.get("selected_text","")
        ok = "✅" if a.get("is_correct") else "❌"
        summary_text += f"\n{ok} {qtext}\n→ إجابة: {sel}\n"
    for admin_id in admins:
        try:
            await context.bot.send_message(chat_id=int(admin_id), text=summary_text)
        except Exception:
            logger.exception("Failed to send result to admin %s", admin_id)

# ---------------------------
# Group start button handler
# ---------------------------
async def group_start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return
    await query.answer()
    data = query.data  # format: group_start_{quizid}
    if not data.startswith("group_start_"):
        return
    quiz_id = data.replace("group_start_", "")
    user = query.from_user
    if not user:
        return
    # attempt to start private session for this user
    try:
        await start_sequential_quiz_for_user(user.id, context, quiz_id)
        # inform in group that user started (no personal data)
        await query.message.reply_text(f"✅ {user.first_name} بدأ الاختبار في الخاص.")
    except Exception:
        # if bot cannot message user privately, ask user to start bot in private
        try:
            await query.message.reply_text(f"⚠️ لم أتمكن من إرسال رسالة خاصة لـ {user.first_name}. اطلب منه الضغط على /start في الخاص ثم أعد المحاولة.")
        except Exception:
            pass

# ---------------------------
# Register handlers and run
# ---------------------------
def main() -> None:
    if TOKEN == "" or TOKEN == "PUT_YOUR_TOKEN_HERE":
        print("ضع التوكن في متغير TOKEN داخل الملف bot.py ثم أعد التشغيل.")
        return

    app = Application.builder().token(TOKEN).build()

    # Conversation handler for quiz creation
    conv = ConversationHandler(
        entry_points=[CommandHandler("newquiz", newquiz_command), CallbackQueryHandler(admin_button_handler, pattern="^new_quiz$")],
        states={
            QUIZ_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, quiz_title_handler)],
            QUIZ_DESCRIPTION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, quiz_description_handler),
                CommandHandler("skip", quiz_skip_description),
            ],
            QUIZ_DURATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, quiz_duration_handler)],
            QUESTION_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, question_text_handler)],
            QUESTION_OPTIONS: [MessageHandler(filters.TEXT & ~filters.COMMAND, question_options_handler)],
            QUESTION_CORRECT: [CallbackQueryHandler(question_correct_handler, pattern="^correct_")],
            QUESTION_ADD_MORE: [CallbackQueryHandler(question_add_more_handler, pattern="^(add_more|finish_quiz)$")],
            PREVIEW_STATE: [CallbackQueryHandler(preview_callback_handler, pattern="^(start_seq_|sharegroup_|new_quiz|back_admin)$"),
                            CallbackQueryHandler(send_quiz_to_group_callback, pattern="^sendgroup_")],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
    )

    # Basic commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("admin", lambda u, c: None))  # placeholder if needed

    # Admin menu buttons
    app.add_handler(CallbackQueryHandler(admin_button_handler, pattern="^(new_quiz|quiz_results|list_groups|list_users|settings|toggle_anonymous|back_admin)$"))
    # Results selection
    app.add_handler(CallbackQueryHandler(result_callback, pattern="^result_"))
    # Preview send to group
    app.add_handler(CallbackQueryHandler(send_quiz_to_group_callback, pattern="^sendgroup_"))
    # Group announcement send
    app.add_handler(CallbackQueryHandler(send_quiz_to_group_callback, pattern="^sendgroup_"))
    # Group start button
    app.add_handler(CallbackQueryHandler(group_start_handler, pattern="^group_start_"))
    # Answer handlers (private sequential)
    app.add_handler(CallbackQueryHandler(answer_handler, pattern="^answer_"))
    # Conversation handler
    app.add_handler(conv)

    print("البوت يعمل الآن...")
    app.run_polling()

if __name__ == "__main__":
    main()
