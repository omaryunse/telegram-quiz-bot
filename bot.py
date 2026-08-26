# bot.py
import os
import json
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
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
# إعدادات أساسية - ضع التوكن هنا
# ---------------------------
TOKEN = "8845301824:AAGptI-Na__Tp0ZbFgvQ-HSfHOawDCuhFK4"
ADMIN_IDS = ["7021041990", "8810965759", "7020921829"]

# ملفات التخزين
QUIZZES_FILE = "quizzes.json"
USERS_FILE = "users.json"
GROUPS_FILE = "groups.json"
RESULTS_FILE = "results.json"
SETTINGS_FILE = "settings.json"

# حالات المحادثة
(
    STATE_TITLE,
    STATE_DESCRIPTION,
    STATE_DURATION,
    STATE_Q_TEXT,
    STATE_Q_OPTIONS,
    STATE_Q_CORRECT,
    STATE_Q_MORE,
    STATE_PREVIEW,
) = range(8)

# جلسات نشطة في الذاكرة لكل مستخدم أثناء الإجابة التتابعية
ACTIVE_SESSIONS: Dict[str, Dict[str, Any]] = {}

# سجل
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------------
# دوال مساعدة للملفات JSON
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

def load_groups() -> Dict[str, Any]:
    return load_json(GROUPS_FILE)

def save_groups(data: Dict[str, Any]) -> None:
    save_json(GROUPS_FILE, data)

def load_results() -> Dict[str, List[Dict[str, Any]]]:
    return load_json(RESULTS_FILE)

def save_results(data: Dict[str, List[Dict[str, Any]]]) -> None:
    save_json(RESULTS_FILE, data)

def load_settings() -> Dict[str, Any]:
    s = load_json(SETTINGS_FILE)
    if not s:
        s = {"allow_anonymous": False, "bot_name": "Quiz Bot"}
        save_json(SETTINGS_FILE, s)
    return s

def save_settings(data: Dict[str, Any]) -> None:
    save_json(SETTINGS_FILE, data)

# ---------------------------
# صلاحيات وتعقب المستخدمين والمجموعات
# ---------------------------
def is_admin(user_id: Optional[int]) -> bool:
    return str(user_id) in ADMIN_IDS if user_id is not None else False

async def require_admin_private(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user = update.effective_user if update.effective_user else (update.callback_query.from_user if update.callback_query else None)
    if not user or not is_admin(user.id):
        if update.effective_chat and update.effective_chat.type == ChatType.PRIVATE:
            if update.message:
                await update.message.reply_text("⚠️ هذا البوت مخصص للمسؤولين فقط.")
            elif update.callback_query:
                await update.callback_query.answer("هذا البوت مخصص للمسؤولين فقط.", show_alert=True)
        return False
    return True

def track_user(user) -> None:
    if not user:
        return
    users = load_users()
    uid = str(user.id)
    if uid not in users:
        users[uid] = {"first_name": user.first_name or "بدون", "username": user.username or "", "total": 0}
    users[uid]["total"] = users[uid].get("total", 0) + 1
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
# واجهة المسؤول (لوحة)
# ---------------------------
def admin_keyboard() -> InlineKeyboardMarkup:
    kb = [
        [InlineKeyboardButton("📝 إنشاء اختبار جديد", callback_data="admin_new")],
        [InlineKeyboardButton("📊 نتائج الاختبارات", callback_data="admin_results")],
        [InlineKeyboardButton("🌐 المجموعات", callback_data="admin_groups")],
        [InlineKeyboardButton("👥 المستخدمون", callback_data="admin_users")],
        [InlineKeyboardButton("⚙️ الإعدادات", callback_data="admin_settings")],
    ]
    return InlineKeyboardMarkup(kb)

# ---------------------------
# معالجات أساسية
# ---------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user:
        track_user(update.effective_user)
    if update.effective_chat and update.effective_chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]:
        track_group(update.effective_chat)
        if update.message:
            await update.message.reply_text("👋 تم تسجيل المجموعة. افتح البوت في الخاص لإدارة الاختبارات (للمسؤولين).")
        return
    user = update.effective_user
    if not user:
        return
    if is_admin(user.id):
        settings = load_settings()
        await update.message.reply_text(f"🔐 {settings.get('bot_name','Quiz Bot')} - لوحة التحكم", reply_markup=admin_keyboard())
    else:
        await update.message.reply_text("🎯 مرحباً! هذا البوت مخصص لإدارة الاختبارات. إذا كنت مسؤولاً استخدم /start بعد إضافة البوت في الخاص.")

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "/start - بدء أو فتح لوحة التحكم (للمسؤولين)\n"
        "/newquiz - إنشاء اختبار جديد (للمسؤولين)\n"
        "/myresults - عرض نتائجك\n"
        "/leaderboard - لوحة المتصدرين\n"
        "/help - هذه الرسالة"
    )
    await update.message.reply_text(text)

# ---------------------------
# لوحة المسؤول - أزرار
# ---------------------------
async def admin_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query:
        return
    await query.answer()
    if not await require_admin_private(update, context):
        return
    track_user(query.from_user)
    data = query.data

    if data == "admin_new":
        # بدء إنشاء اختبار جديد (واحد فقط في هذه الجلسة)
        context.user_data["quiz_build"] = {"title": "", "description": "", "duration": 60, "questions": []}
        await query.message.reply_text("✍️ أرسل **عنوان الاختبار** الآن (أي نص):")
        return

    if data == "admin_results":
        quizzes = load_quizzes()
        if not quizzes:
            await query.message.reply_text("لا توجد اختبارات محفوظة.")
            return
        kb = [[InlineKeyboardButton(q.get("title","بدون"), callback_data=f"viewres_{qid}")] for qid, q in quizzes.items()]
        await query.message.reply_text("اختر الاختبار لعرض النتائج:", reply_markup=InlineKeyboardMarkup(kb))
        return

    if data == "admin_groups":
        groups = load_groups()
        if not groups:
            await query.message.reply_text("لا توجد مجموعات مسجلة.")
            return
        text = "🌐 المجموعات المسجلة:\n\n"
        for gid, g in groups.items():
            text += f"• {g.get('title','بدون')} - ID: {gid}\n"
        await query.message.reply_text(text)
        return

    if data == "admin_users":
        users = load_users()
        if not users:
            await query.message.reply_text("لا يوجد مستخدمون مسجلون.")
            return
        text = "👥 المستخدمون:\n\n"
        for uid, u in users.items():
            uname = f"@{u.get('username')}" if u.get('username') else "بدون"
            text += f"• {u.get('first_name','بدون')} ({uname}) - ID: {uid} - تفاعلات: {u.get('total',0)}\n"
        await query.message.reply_text(text)
        return

    if data == "admin_settings":
        s = load_settings()
        status = "مفعل" if s.get("allow_anonymous") else "معطل"
        kb = [
            [InlineKeyboardButton(f"🔄 الاستفتاء السري: {status}", callback_data="toggle_anonymous")],
            [InlineKeyboardButton("↩️ رجوع", callback_data="back_admin")],
        ]
        await query.message.reply_text("⚙️ الإعدادات:", reply_markup=InlineKeyboardMarkup(kb))
        return

    if data == "toggle_anonymous":
        s = load_settings()
        s["allow_anonymous"] = not s.get("allow_anonymous", False)
        save_settings(s)
        await query.message.edit_text(f"⚙️ تم تحديث الإعدادات. الاستفتاء السري: {'مفعل' if s['allow_anonymous'] else 'معطل'}")
        return

    if data == "back_admin":
        await query.message.edit_text("🔐 لوحة التحكم:", reply_markup=admin_keyboard())
        return

# عرض نتائج اختبار محدد
async def view_results_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query:
        return
    await query.answer()
    if not await require_admin_private(update, context):
        return
    qid = query.data.replace("viewres_", "")
    results = load_results().get(qid, [])
    if not results:
        await query.message.reply_text("لا توجد نتائج لهذا الاختبار بعد.")
        return
    # تجميع حسب المستخدم
    per_user: Dict[str, Dict[str, Any]] = {}
    for r in results:
        uid = str(r.get("user_id"))
        if uid not in per_user:
            per_user[uid] = {"name": r.get("first_name",""), "username": r.get("username",""), "correct": 0, "answers": 0}
        per_user[uid]["answers"] += 1
        if r.get("is_correct"):
            per_user[uid]["correct"] += 1
    text = "📊 نتائج الاختبار:\n\n"
    for uid, info in per_user.items():
        uname = f"@{info.get('username')}" if info.get("username") else "بدون"
        text += f"• {info.get('name','')} ({uname}) — صحيح: {info.get('correct')}/{info.get('answers')}\n"
    await query.message.reply_text(text)

# ---------------------------
# إنشاء اختبار (تدفق مبسط ومنظم)
# ---------------------------
async def newquiz_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_admin_private(update, context):
        return ConversationHandler.END
    context.user_data["quiz_build"] = {"title": "", "description": "", "duration": 60, "questions": []}
    await update.message.reply_text("✍️ أرسل عنوان الاختبار الآن:")
    return STATE_TITLE

async def handle_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_admin_private(update, context):
        return ConversationHandler.END
    text = update.message.text.strip() if update.message and update.message.text else ""
    if not text:
        await update.message.reply_text("⚠️ العنوان لا يمكن أن يكون فارغاً. أعد الإرسال:")
        return STATE_TITLE
    context.user_data["quiz_build"]["title"] = text
    await update.message.reply_text("📝 أرسل وصف الاختبار (أو اكتب /skip لتخطي الوصف):")
    return STATE_DESCRIPTION

async def skip_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_admin_private(update, context):
        return ConversationHandler.END
    context.user_data["quiz_build"]["description"] = ""
    await update.message.reply_text("⏳ أرسل مدة الإجابة لكل سؤال بالثواني (مثال: 30 أو 60):")
    return STATE_DURATION

async def handle_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_admin_private(update, context):
        return ConversationHandler.END
    context.user_data["quiz_build"]["description"] = update.message.text.strip() if update.message and update.message.text else ""
    await update.message.reply_text("⏳ أرسل مدة الإجابة لكل سؤال بالثواني (مثال: 30 أو 60):")
    return STATE_DURATION

async def handle_duration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_admin_private(update, context):
        return ConversationHandler.END
    text = update.message.text.strip() if update.message and update.message.text else ""
    try:
        dur = int(text)
        if dur <= 0:
            raise ValueError
    except Exception:
        await update.message.reply_text("⚠️ قيمة غير صحيحة. أرسل مدة بالثواني مثل 30 أو 60.")
        return STATE_DURATION
    context.user_data["quiz_build"]["duration"] = dur
    await update.message.reply_text("✍️ أرسل نص السؤال الأول:")
    return STATE_Q_TEXT

async def handle_q_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_admin_private(update, context):
        return ConversationHandler.END
    text = update.message.text.strip() if update.message and update.message.text else ""
    if not text:
        await update.message.reply_text("⚠️ نص السؤال لا يمكن أن يكون فارغاً. أعد الإرسال:")
        return STATE_Q_TEXT
    context.user_data["current_q"] = {"text": text, "options": [], "correct": None}
    await update.message.reply_text("🔢 أرسل الخيارات (كل خيار في سطر). الحد الأدنى 2 والحد الأقصى 10:")
    return STATE_Q_OPTIONS

async def handle_q_options(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_admin_private(update, context):
        return ConversationHandler.END
    raw = update.message.text if update.message and update.message.text else ""
    opts = [line.strip() for line in raw.splitlines() if line.strip()]
    if len(opts) < 2:
        await update.message.reply_text("⚠️ يجب أن يكون هناك خياران على الأقل. أعد الإرسال:")
        return STATE_Q_OPTIONS
    if len(opts) > 10:
        await update.message.reply_text("⚠️ الحد الأقصى 10 خيارات. أعد الإرسال:")
        return STATE_Q_OPTIONS
    context.user_data["current_q"]["options"] = opts
    kb = [[InlineKeyboardButton(f"{i+1}. {o}", callback_data=f"setcorr_{i}")] for i, o in enumerate(opts)]
    kb.append([InlineKeyboardButton("بدون إجابة صحيحة", callback_data="setcorr_none")])
    await update.message.reply_text("✅ اختر الإجابة الصحيحة (أو اختر بدون إجابة صحيحة):", reply_markup=InlineKeyboardMarkup(kb))
    return STATE_Q_CORRECT

async def handle_q_correct(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return ConversationHandler.END
    await query.answer()
    if not await require_admin_private(update, context):
        return ConversationHandler.END
    data = query.data
    if data == "setcorr_none":
        context.user_data["current_q"]["correct"] = None
    else:
        try:
            idx = int(data.replace("setcorr_", ""))
            context.user_data["current_q"]["correct"] = idx
        except Exception:
            context.user_data["current_q"]["correct"] = None
    # إضافة السؤال للمجموعة
    b = context.user_data.get("quiz_build", {"questions": []})
    b["questions"].append(context.user_data["current_q"])
    context.user_data["quiz_build"] = b
    context.user_data.pop("current_q", None)
    kb = [
        [InlineKeyboardButton("➕ إضافة سؤال آخر", callback_data="add_more")],
        [InlineKeyboardButton("✅ إنهاء وإنشاء الاختبار", callback_data="finish_quiz")],
    ]
    await query.message.reply_text("هل تريد إضافة سؤال آخر أم إنهاء وإنشاء الاختبار؟", reply_markup=InlineKeyboardMarkup(kb))
    return STATE_Q_MORE

async def handle_q_more(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return ConversationHandler.END
    await query.answer()
    if not await require_admin_private(update, context):
        return ConversationHandler.END
    if query.data == "add_more":
        await query.message.reply_text("✍️ أرسل نص السؤال التالي:")
        return STATE_Q_TEXT
    if query.data == "finish_quiz":
        b = context.user_data.get("quiz_build", {})
        quiz_id = datetime.now().strftime("%Y%m%d%H%M%S")
        quizzes = load_quizzes()
        quizzes[quiz_id] = {
            "id": quiz_id,
            "title": b.get("title", ""),
            "description": b.get("description", ""),
            "duration": b.get("duration", 60),
            "questions": b.get("questions", []),
            "created_at": datetime.now().isoformat(),
        }
        save_quizzes(quizzes)
        context.user_data["last_quiz"] = quiz_id
        preview = (
            f"📋 تم إنشاء الاختبار:\n\n"
            f"❓ {b.get('title','')}\n"
            f"📝 {b.get('description','')}\n"
            f"⏱ مدة السؤال: {b.get('duration',60)} ثانية\n"
            f"🔢 عدد الأسئلة: {len(b.get('questions',[]))}\n\n"
            "اختر إجراء:"
        )
        kb = [
            [InlineKeyboardButton("🚀 بدء الاختبار هنا (في الخاص)", callback_data=f"start_local_{quiz_id}")],
            [InlineKeyboardButton("📤 إرسال إعلان للمجموعة", callback_data=f"announce_{quiz_id}")],
            [InlineKeyboardButton("↩️ رجوع للوحة", callback_data="back_admin")],
        ]
        await query.message.reply_text(preview, reply_markup=InlineKeyboardMarkup(kb))
        context.user_data.pop("quiz_build", None)
        return STATE_PREVIEW
    return ConversationHandler.END

# ---------------------------
# إرسال إعلان للمجموعة وزر البدء
# ---------------------------
async def announce_to_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return
    await query.answer()
    if not await require_admin_private(update, context):
        return
    data = query.data
    if not data.startswith("announce_"):
        return
    quiz_id = data.replace("announce_", "")
    groups = load_groups()
    if not groups:
        await query.message.reply_text("لا توجد مجموعات مسجلة لإرسال الإعلان.")
        return
    kb = [[InlineKeyboardButton(g.get("title","بدون"), callback_data=f"sendto_{gid}_{quiz_id}")] for gid, g in groups.items()]
    kb.append([InlineKeyboardButton("↩️ رجوع", callback_data="back_admin")])
    await query.message.reply_text("اختر المجموعة لإرسال الإعلان:", reply_markup=InlineKeyboardMarkup(kb))

async def send_to_group_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return
    await query.answer()
    if not await require_admin_private(update, context):
        return
    data = query.data
    if not data.startswith("sendto_"):
        return
    parts = data.split("_", 2)
    if len(parts) < 3:
        await query.message.reply_text("معرف غير صالح.")
        return
    gid = parts[1]
    quiz_id = parts[2]
    try:
        gid_int = int(gid)
    except Exception:
        await query.message.reply_text("معرف المجموعة غير صالح.")
        return
    quizzes = load_quizzes()
    quiz = quizzes.get(quiz_id)
    if not quiz:
        await query.message.reply_text("الاختبار غير موجود.")
        return
    text = f"📢 اختبار جديد: {quiz.get('title','')}\n\n{quiz.get('description','')}\n\nاضغط زر 'بدء الاختبار' لبدء الاختبار في الخاص مع البوت."
    kb = [[InlineKeyboardButton("🚀 بدء الاختبار", callback_data=f"group_start_{quiz_id}")]]
    try:
        await context.bot.send_message(chat_id=gid_int, text=text, reply_markup=InlineKeyboardMarkup(kb))
        await query.message.reply_text("✅ تم إرسال الإعلان إلى المجموعة.")
    except Exception as e:
        await query.message.reply_text(f"❌ فشل الإرسال: {e}")

# ---------------------------
# بدء الاختبار للمستخدم (من الخاص أو من زر المجموعة)
# ---------------------------
async def start_local_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return
    await query.answer()
    if not await require_admin_private(update, context):
        return
    quiz_id = query.data.replace("start_local_", "")
    await start_quiz_for_user(query.from_user.id, context, quiz_id)
    await query.message.reply_text("✅ بدأ الاختبار في الخاص لديك.")

async def group_start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return
    await query.answer()
    data = query.data
    if not data.startswith("group_start_"):
        return
    quiz_id = data.replace("group_start_", "")
    user = query.from_user
    if not user:
        return
    # حاول بدء الاختبار في الخاص للمستخدم
    try:
        await start_quiz_for_user(user.id, context, quiz_id)
        await query.message.reply_text(f"✅ {user.first_name} بدأ الاختبار في الخاص.")
    except Exception:
        await query.message.reply_text(f"⚠️ لم أتمكن من إرسال رسالة خاصة لـ {user.first_name}. اطلب منه الضغط على /start في الخاص ثم أعد المحاولة.")

async def start_quiz_for_user(user_id: int, context: ContextTypes.DEFAULT_TYPE, quiz_id: str) -> None:
    quizzes = load_quizzes()
    quiz = quizzes.get(quiz_id)
    if not quiz:
        try:
            await context.bot.send_message(chat_id=user_id, text="❌ الاختبار غير موجود.")
        except Exception:
            pass
        return
    # تهيئة الجلسة
    ACTIVE_SESSIONS[str(user_id)] = {"quiz_id": quiz_id, "current": 0, "answers": [], "started_at": datetime.now().isoformat()}
    # إرسال السؤال الأول
    await send_question_to_user(user_id, context, quiz, 0)

async def send_question_to_user(chat_id: int, context: ContextTypes.DEFAULT_TYPE, quiz: Dict[str, Any], q_index: int) -> None:
    questions = quiz.get("questions", [])
    if q_index < 0 or q_index >= len(questions):
        try:
            await context.bot.send_message(chat_id=chat_id, text="✅ انتهى الاختبار. شكراً لمشاركتك.")
            await finalize_session(chat_id, context)
        except Exception:
            logger.exception("خطأ أثناء إنهاء الجلسة")
        return
    q = questions[q_index]
    text = f"سؤال {q_index+1}/{len(questions)}:\n\n{q.get('text','')}"
    kb = []
    for i, opt in enumerate(q.get("options", [])):
        kb.append([InlineKeyboardButton(f"{i+1}. {opt}", callback_data=f"ans_{quiz.get('id')}_{q_index}_{i}")])
    kb.append([InlineKeyboardButton("تخطي السؤال", callback_data=f"ans_{quiz.get('id')}_{q_index}_-1")])
    await context.bot.send_message(chat_id=chat_id, text=text, reply_markup=InlineKeyboardMarkup(kb))

async def answer_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return
    await query.answer()
    user = query.from_user
    if not user:
        return
    uid = str(user.id)
    data = query.data  # ans_{quizid}_{qindex}_{opt}
    parts = data.split("_")
    if len(parts) < 4:
        await query.message.reply_text("بيانات غير صحيحة.")
        return
    quiz_id = parts[1]
    try:
        q_index = int(parts[2])
        opt_index = int(parts[3])
    except Exception:
        await query.message.reply_text("بيانات غير صحيحة.")
        return
    session = ACTIVE_SESSIONS.get(uid)
    if not session or session.get("quiz_id") != quiz_id:
        await query.message.reply_text("لا يوجد اختبار نشط لديك. اضغط زر 'بدء الاختبار' في المجموعة أولاً.")
        return
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
    session["answers"].append({
        "question_index": q_index,
        "question_text": q.get("text",""),
        "selected_index": opt_index,
        "selected_text": selected_text,
        "is_correct": is_correct,
        "answered_at": datetime.now().isoformat(),
    })
    session["current"] = q_index + 1
    # تغذية راجعة للمستخدم
    try:
        await context.bot.send_message(chat_id=user.id, text="✅ إجابة صحيحة!" if is_correct else ("⚠️ إجابة خاطئة." if opt_index != -1 else "⚠️ تم تخطي السؤال."))
    except Exception:
        logger.exception("فشل إرسال تغذية راجعة للمستخدم")
    # السؤال التالي أو إنهاء
    next_idx = session["current"]
    if next_idx >= len(questions):
        try:
            await context.bot.send_message(chat_id=user.id, text="✅ انتهى الاختبار. جاري حفظ النتائج...")
        except Exception:
            pass
        await finalize_session(user.id, context)
        ACTIVE_SESSIONS.pop(uid, None)
        return
    await send_question_to_user(user.id, context, quiz, next_idx)

# ---------------------------
# حفظ النتائج وإرسال ملخص للمسؤولين
# ---------------------------
async def finalize_session(user_chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    uid = str(user_chat_id)
    session = ACTIVE_SESSIONS.get(uid)
    if not session:
        return
    quiz_id = session.get("quiz_id")
    results = load_results()
    if quiz_id not in results:
        results[quiz_id] = []
    correct_count = sum(1 for a in session.get("answers", []) if a.get("is_correct"))
    total = len(session.get("answers", []))
    first_name = ""
    username = ""
    try:
        chat = await context.bot.get_chat(user_chat_id)
        first_name = chat.first_name or ""
        username = chat.username or ""
    except Exception:
        pass
    for a in session.get("answers", []):
        results[quiz_id].append({
            "user_id": user_chat_id,
            "first_name": first_name,
            "username": username,
            "question_index": a.get("question_index"),
            "question_text": a.get("question_text"),
            "selected_index": a.get("selected_index"),
            "selected_text": a.get("selected_text"),
            "is_correct": a.get("is_correct"),
            "answered_at": a.get("answered_at"),
        })
    save_results(results)
    # رسالة للمستخدم
    try:
        await context.bot.send_message(chat_id=user_chat_id, text=f"📊 انتهى الاختبار. إجابات صحيحة: {correct_count} من {total}.")
    except Exception:
        pass
    # إرسال ملخص للمسؤولين
    quiz_title = load_quizzes().get(quiz_id, {}).get("title", "")
    summary = f"📥 نتيجة: {first_name} (@{username})\nالاختبار: {quiz_title}\nالنتيجة: {correct_count}/{total}\nوقت: {datetime.now().isoformat()}\n"
    for a in session.get("answers", []):
        ok = "✅" if a.get("is_correct") else "❌"
        summary += f"\n{ok} {a.get('question_text','')}\n→ إجابة: {a.get('selected_text','')}\n"
    for admin in ADMIN_IDS:
        try:
            await context.bot.send_message(chat_id=int(admin), text=summary)
        except Exception:
            logger.exception("فشل إرسال النتيجة للمسؤول %s", admin)

# ---------------------------
# أوامر مفيدة للمستخدمين
# ---------------------------
async def myresults(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user:
        return
    results = load_results()
    quizzes = load_quizzes()
    lines = []
    for qid, entries in results.items():
        user_entries = [e for e in entries if str(e.get("user_id")) == str(user.id)]
        if not user_entries:
            continue
        quiz_title = quizzes.get(qid, {}).get("title", qid)
        correct = sum(1 for e in user_entries if e.get("is_correct"))
        total = len(user_entries)
        lines.append(f"{quiz_title}: {correct}/{total}")
    if not lines:
        await update.message.reply_text("لم تشارك في أي اختبارات بعد.")
        return
    await update.message.reply_text("📋 نتائجك:\n" + "\n".join(lines))

async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    results = load_results()
    scores: Dict[str, int] = {}
    names: Dict[str, str] = {}
    for qid, entries in results.items():
        for e in entries:
            uid = str(e.get("user_id"))
            if uid not in scores:
                scores[uid] = 0
            if e.get("is_correct"):
                scores[uid] += 1
            names[uid] = e.get("first_name","") or names.get(uid,"")
    if not scores:
        await update.message.reply_text("لا توجد نتائج بعد.")
        return
    top = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:10]
    text = "🏆 لوحة المتصدرين:\n\n"
    for uid, sc in top:
        text += f"{names.get(uid,'بدون')} - {sc} نقطة\n"
    await update.message.reply_text(text)

# ---------------------------
# إلغاء المحادثة
# ---------------------------
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        await update.message.reply_text("تم الإلغاء.")
    elif update.callback_query:
        await update.callback_query.answer("تم الإلغاء.")
    return ConversationHandler.END

# ---------------------------
# التسجيل والتشغيل
# ---------------------------
def main() -> None:
    if TOKEN == "" or TOKEN == "PUT_YOUR_TOKEN_HERE":
        print("ضع التوكن في متغير TOKEN داخل الملف bot.py ثم أعد التشغيل.")
        return

    app = Application.builder().token(TOKEN).build()

    conv = ConversationHandler(
        entry_points=[
            CommandHandler("newquiz", newquiz_start),
            CallbackQueryHandler(admin_button_handler, pattern="^admin_new$"),
        ],
        states={
            STATE_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_title)],
            STATE_DESCRIPTION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_description),
                CommandHandler("skip", skip_description),
            ],
            STATE_DURATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_duration)],
            STATE_Q_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_q_text)],
            STATE_Q_OPTIONS: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_q_options)],
            STATE_Q_CORRECT: [CallbackQueryHandler(handle_q_correct, pattern="^setcorr_")],
            STATE_Q_MORE: [CallbackQueryHandler(handle_q_more, pattern="^(add_more|finish_quiz)$")],
            STATE_PREVIEW: [
                CallbackQueryHandler(start_local_handler, pattern="^start_local_"),
                CallbackQueryHandler(announce_to_group, pattern="^announce_"),
                CallbackQueryHandler(send_to_group_callback, pattern="^sendto_"),
                CallbackQueryHandler(admin_button_handler, pattern="^back_admin$"),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
    )

    # أوامر عامة
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("myresults", myresults))
    app.add_handler(CommandHandler("leaderboard", leaderboard))
    app.add_handler(CommandHandler("newquiz", newquiz_start))

    # أزرار لوحة المسؤول
    app.add_handler(CallbackQueryHandler(admin_button_handler, pattern="^(admin_new|admin_results|admin_groups|admin_users|admin_settings|toggle_anonymous|back_admin)$"))
    app.add_handler(CallbackQueryHandler(view_results_handler, pattern="^viewres_"))
    app.add_handler(CallbackQueryHandler(handle_q_correct, pattern="^setcorr_"))
    app.add_handler(CallbackQueryHandler(announce_to_group, pattern="^announce_"))
    app.add_handler(CallbackQueryHandler(send_to_group_callback, pattern="^sendto_"))
    app.add_handler(CallbackQueryHandler(start_local_handler, pattern="^start_local_"))
    app.add_handler(CallbackQueryHandler(group_start_handler, pattern="^group_start_"))
    app.add_handler(CallbackQueryHandler(answer_callback, pattern="^ans_|^ans_"))  # older patterns safe
    app.add_handler(CallbackQueryHandler(answer_callback, pattern="^ans_"))
    app.add_handler(CallbackQueryHandler(answer_callback, pattern="^ans_"))
    app.add_handler(CallbackQueryHandler(answer_callback, pattern="^ans_"))
    # handler for answers using our ans_ prefix
    app.add_handler(CallbackQueryHandler(answer_callback, pattern="^ans_"))
    # handler for answers using ans_ with id
    app.add_handler(CallbackQueryHandler(answer_callback, pattern="^ans_"))

    # conv handler آخر
    app.add_handler(conv)

    print("البوت يعمل الآن...")
    app.run_polling()

if __name__ == "__main__":
    main()
