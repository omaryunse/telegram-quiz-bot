import os
import sqlite3
import logging
from datetime import datetime

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.constants import ChatType
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ConversationHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# =========================================================
# إعدادات البوت
# =========================================================

BOT_TOKEN = os.getenv("8733506822:AAH9CA5_S7M0frI5hJlzNcKPsPudDyHZNSM", "PUT_YOUR_NEW_BOT_TOKEN_HERE")

# ضع IDs الأدمن هنا
ADMIN_IDS = {
    7021041990,
    8810965759,
    7020921829,
}

DB_FILE = "quiz_bot.db"

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)


# =========================================================
# حالات إنشاء الاختبار
# =========================================================

(
    TITLE,
    DESCRIPTION,
    DURATION,
    QUESTION_TEXT,
    QUESTION_OPTIONS,
    QUESTION_CORRECT,
    QUESTION_MORE,
) = range(7)


# =========================================================
# قاعدة البيانات
# =========================================================

def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            first_name TEXT,
            username TEXT,
            created_at TEXT,
            last_seen TEXT,
            quizzes_taken INTEGER DEFAULT 0
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS groups_table (
            chat_id INTEGER PRIMARY KEY,
            title TEXT,
            created_at TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS quizzes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            duration INTEGER DEFAULT 60,
            created_by INTEGER,
            created_at TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            quiz_id INTEGER,
            question_text TEXT,
            options TEXT,
            correct_index INTEGER
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            quiz_id INTEGER,
            user_id INTEGER,
            first_name TEXT,
            username TEXT,
            correct INTEGER,
            total INTEGER,
            percentage REAL,
            finished_at TEXT
        )
    """)

    conn.commit()
    conn.close()


# =========================================================
# أدوات عامة
# =========================================================

def is_admin(user_id):
    return user_id in ADMIN_IDS


def now():
    return datetime.now().isoformat(timespec="seconds")


def register_user(user):
    if not user:
        return

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO users
        (user_id, first_name, username, created_at, last_seen)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            first_name=excluded.first_name,
            username=excluded.username,
            last_seen=excluded.last_seen
    """, (
        user.id,
        user.first_name or "بدون اسم",
        user.username or "",
        now(),
        now(),
    ))

    conn.commit()
    conn.close()


def register_group(chat):
    if chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        return

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO groups_table
        (chat_id, title, created_at)
        VALUES (?, ?, ?)
        ON CONFLICT(chat_id) DO UPDATE SET
            title=excluded.title
    """, (
        chat.id,
        chat.title or "مجموعة بدون اسم",
        now(),
    ))

    conn.commit()
    conn.close()


def get_quiz(quiz_id):
    conn = get_db()
    cur = conn.cursor()

    quiz = cur.execute(
        "SELECT * FROM quizzes WHERE id = ?",
        (quiz_id,)
    ).fetchone()

    if not quiz:
        conn.close()
        return None

    questions = cur.execute(
        "SELECT * FROM questions WHERE quiz_id = ? ORDER BY id",
        (quiz_id,)
    ).fetchall()

    conn.close()

    result = dict(quiz)
    result["questions"] = []

    for q in questions:
        options = q["options"].split("|||")

        result["questions"].append({
            "id": q["id"],
            "text": q["question_text"],
            "options": options,
            "correct": q["correct_index"],
        })

    return result


# =========================================================
# لوحة الأدمن
# =========================================================

def admin_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "📝 إنشاء اختبار",
                callback_data="admin_create"
            )
        ],
        [
            InlineKeyboardButton(
                "📚 الاختبارات",
                callback_data="admin_quizzes"
            ),
            InlineKeyboardButton(
                "📊 النتائج",
                callback_data="admin_results"
            )
        ],
        [
            InlineKeyboardButton(
                "👥 المستخدمون",
                callback_data="admin_users"
            ),
            InlineKeyboardButton(
                "🌐 المجموعات",
                callback_data="admin_groups"
            )
        ],
        [
            InlineKeyboardButton(
                "📈 إحصائيات البوت",
                callback_data="admin_stats"
            )
        ],
    ])


async def show_admin_panel(query):
    await query.message.edit_text(
        "🔐 **لوحة تحكم البوت**\n\n"
        "اختر العملية التي تريد تنفيذها:",
        reply_markup=admin_keyboard(),
        parse_mode="Markdown",
    )


# =========================================================
# START
# =========================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat

    register_user(user)

    if chat.type in (ChatType.GROUP, ChatType.SUPERGROUP):
        register_group(chat)

        await update.message.reply_text(
            "👋 تم تسجيل المجموعة.\n\n"
            "📌 الاختبارات يتم حلها في الخاص فقط.\n"
            "اضغط زر «🚀 بدء الاختبار» عندما يتم نشر اختبار."
        )
        return

    if is_admin(user.id):
        await update.message.reply_text(
            "👑 أهلاً بك في لوحة تحكم بوت الاختبارات.",
            reply_markup=admin_keyboard(),
        )
    else:
        await update.message.reply_text(
            f"👋 أهلاً {user.first_name}!\n\n"
            "🎯 عندما يصلك اختبار اضغط «🚀 بدء الاختبار» "
            "وسينقلك البوت إلى جلسة الاختبار الخاصة بك."
        )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📚 أوامر البوت:\n\n"
        "/start - فتح البوت\n"
        "/help - المساعدة\n"
        "/cancel - إلغاء العملية الحالية"
    )


# =========================================================
# إنشاء اختبار
# =========================================================

async def create_quiz_start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    query = update.callback_query

    if query:
        await query.answer()

        if not is_admin(query.from_user.id):
            return ConversationHandler.END

        await query.message.reply_text(
            "📝 إنشاء اختبار جديد\n\n"
            "✍️ أرسل عنوان الاختبار:"
        )

    else:
        if not is_admin(update.effective_user.id):
            await update.message.reply_text(
                "❌ هذا الأمر خاص بالأدمن."
            )
            return ConversationHandler.END

        await update.message.reply_text(
            "📝 إنشاء اختبار جديد\n\n"
            "✍️ أرسل عنوان الاختبار:"
        )

    context.user_data["quiz_build"] = {
        "title": "",
        "description": "",
        "duration": 60,
        "questions": [],
    }

    return TITLE


async def handle_title(update, context):
    if not is_admin(update.effective_user.id):
        return ConversationHandler.END

    title = update.message.text.strip()

    if len(title) < 2:
        await update.message.reply_text(
            "⚠️ العنوان قصير جدًا، أرسل عنوانًا آخر:"
        )
        return TITLE

    context.user_data["quiz_build"]["title"] = title

    await update.message.reply_text(
        "📝 أرسل وصف الاختبار.\n\n"
        "أو اكتب /skip لتخطي الوصف."
    )

    return DESCRIPTION


async def skip_description(update, context):
    context.user_data["quiz_build"]["description"] = ""

    await update.message.reply_text(
        "⏱️ أرسل مدة السؤال بالثواني.\n"
        "مثال: 30"
    )

    return DURATION


async def handle_description(update, context):
    context.user_data["quiz_build"]["description"] = (
        update.message.text.strip()
    )

    await update.message.reply_text(
        "⏱️ أرسل مدة السؤال بالثواني.\n"
        "مثال: 30"
    )

    return DURATION


async def handle_duration(update, context):
    try:
        duration = int(update.message.text.strip())

        if duration <= 0:
            raise ValueError

        if duration > 3600:
            await update.message.reply_text(
                "⚠️ الحد الأقصى للمدة هو 3600 ثانية."
            )
            return DURATION

    except ValueError:
        await update.message.reply_text(
            "⚠️ أرسل رقمًا صحيحًا.\nمثال: 30"
        )
        return DURATION

    context.user_data["quiz_build"]["duration"] = duration

    await update.message.reply_text(
        "❓ أرسل نص السؤال الأول:"
    )

    return QUESTION_TEXT


async def handle_question_text(update, context):
    text = update.message.text.strip()

    if len(text) < 2:
        await update.message.reply_text(
            "⚠️ السؤال قصير جدًا."
        )
        return QUESTION_TEXT

    context.user_data["current_question"] = {
        "text": text,
        "options": [],
        "correct": None,
    }

    await update.message.reply_text(
        "🔢 أرسل الخيارات.\n\n"
        "كل خيار في سطر مستقل.\n"
        "مثال:\n\n"
        "بغداد\n"
        "البصرة\n"
        "الموصل\n"
        "أربيل"
    )

    return QUESTION_OPTIONS


async def handle_question_options(update, context):
    options = [
        line.strip()
        for line in update.message.text.splitlines()
        if line.strip()
    ]

    if len(options) < 2 or len(options) > 10:
        await update.message.reply_text(
            "⚠️ يجب أن يكون عدد الخيارات بين 2 و10."
        )
        return QUESTION_OPTIONS

    context.user_data["current_question"]["options"] = options

    buttons = []

    for i, option in enumerate(options):
        buttons.append([
            InlineKeyboardButton(
                f"{i + 1}. {option}",
                callback_data=f"correct_{i}",
            )
        ])

    await update.message.reply_text(
        "✅ اختر الإجابة الصحيحة:",
        reply_markup=InlineKeyboardMarkup(buttons),
    )

    return QUESTION_CORRECT


async def handle_correct_answer(update, context):
    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        return ConversationHandler.END

    index = int(query.data.replace("correct_", ""))

    context.user_data["current_question"]["correct"] = index

    context.user_data["quiz_build"]["questions"].append(
        context.user_data["current_question"]
    )

    context.user_data.pop("current_question", None)

    buttons = [
        [
            InlineKeyboardButton(
                "➕ إضافة سؤال",
                callback_data="question_add",
            )
        ],
        [
            InlineKeyboardButton(
                "👀 معاينة الاختبار",
                callback_data="quiz_preview",
            )
        ],
        [
            InlineKeyboardButton(
                "💾 حفظ الاختبار",
                callback_data="quiz_save",
            )
        ],
    ]

    await query.message.reply_text(
        "✅ تمت إضافة السؤال بنجاح.\n\n"
        "ماذا تريد أن تفعل؟",
        reply_markup=InlineKeyboardMarkup(buttons),
    )

    return QUESTION_MORE


async def question_more(update, context):
    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        return ConversationHandler.END

    if query.data == "question_add":
        await query.message.reply_text(
            "❓ أرسل نص السؤال التالي:"
        )
        return QUESTION_TEXT

    if query.data == "quiz_preview":
        build = context.user_data["quiz_build"]

        text = (
            f"📋 {build['title']}\n\n"
            f"📝 {build['description'] or 'بدون وصف'}\n"
            f"⏱️ {build['duration']} ثانية لكل سؤال\n"
            f"❓ عدد الأسئلة: {len(build['questions'])}\n\n"
        )

        for i, q in enumerate(build["questions"], 1):
            text += f"{i}. {q['text']}\n"

            for j, option in enumerate(q["options"]):
                mark = "✅" if j == q["correct"] else "▫️"
                text += f"   {mark} {option}\n"

            text += "\n"

        await query.message.reply_text(text)

        return QUESTION_MORE

    if query.data == "quiz_save":
        return await save_quiz(update, context)


async def save_quiz(update, context):
    query = update.callback_query

    build = context.user_data.get("quiz_build")

    if not build:
        await query.message.reply_text(
            "❌ لا يوجد اختبار قيد الإنشاء."
        )
        return ConversationHandler.END

    if not build["questions"]:
        await query.message.reply_text(
            "⚠️ يجب إضافة سؤال واحد على الأقل."
        )
        return QUESTION_MORE

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO quizzes
        (title, description, duration, created_by, created_at)
        VALUES (?, ?, ?, ?, ?)
    """, (
        build["title"],
        build["description"],
        build["duration"],
        query.from_user.id,
        now(),
    ))

    quiz_id = cur.lastrowid

    for q in build["questions"]:
        options = "|||".join(q["options"])

        cur.execute("""
            INSERT INTO questions
            (quiz_id, question_text, options, correct_index)
            VALUES (?, ?, ?, ?)
        """, (
            quiz_id,
            q["text"],
            options,
            q["correct"],
        ))

    conn.commit()
    conn.close()

    context.user_data.pop("quiz_build", None)

    await query.message.reply_text(
        f"🎉 تم إنشاء الاختبار بنجاح!\n\n"
        f"🆔 رقم الاختبار: `{quiz_id}`\n"
        f"📋 العنوان: {build['title']}\n"
        f"❓ الأسئلة: {len(build['questions'])}",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "📤 مشاركة الاختبار",
                    callback_data=f"share_{quiz_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    "📢 نشر للمجموعات",
                    callback_data=f"publish_{quiz_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    "↩️ لوحة التحكم",
                    callback_data="admin_back",
                )
            ],
        ]),
    )

    return ConversationHandler.END


async def cancel(update, context):
    context.user_data.pop("quiz_build", None)
    context.user_data.pop("current_question", None)

    await update.message.reply_text(
        "❌ تم إلغاء العملية."
    )

    return ConversationHandler.END


# =========================================================
# مشاركة الاختبار
# =========================================================

async def share_quiz(update, context):
    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        return

    quiz_id = int(query.data.replace("share_", ""))
    quiz = get_quiz(quiz_id)

    if not quiz:
        await query.message.reply_text(
            "❌ الاختبار غير موجود."
        )
        return

    bot_username = context.bot.username

    deep_link = (
        f"https://t.me/{bot_username}?start=quiz_{quiz_id}"
    )

    text = (
        f"📣 **{quiz['title']}**\n\n"
        f"{quiz['description'] or ''}\n\n"
        f"❓ عدد الأسئلة: {len(quiz['questions'])}\n"
        f"⏱️ مدة السؤال: {quiz['duration']} ثانية\n\n"
        "🔐 الاختبار يتم في الخاص."
    )

    buttons = [
        [
            InlineKeyboardButton(
                "🚀 بدء الاختبار",
                url=deep_link,
            )
        ]
    ]

    await query.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode="Markdown",
    )


# =========================================================
# نشر للمجموعات
# =========================================================

async def publish_quiz(update, context):
    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        return

    quiz_id = int(query.data.replace("publish_", ""))

    conn = get_db()
    groups = conn.execute(
        "SELECT * FROM groups_table ORDER BY title"
    ).fetchall()
    conn.close()

    if not groups:
        await query.message.reply_text(
            "🌐 لا توجد مجموعات مسجلة."
        )
        return

    buttons = []

    for group in groups:
        buttons.append([
            InlineKeyboardButton(
                f"📢 {group['title']}",
                callback_data=f"sendgroup_{group['chat_id']}_{quiz_id}",
            )
        ])

    buttons.append([
        InlineKeyboardButton(
            "📢 نشر للجميع",
            callback_data=f"sendall_{quiz_id}",
        )
    ])

    await query.message.reply_text(
        "🌐 اختر مكان نشر الاختبار:",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


async def send_to_group(update, context):
    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        return

    data = query.data
    parts = data.split("_")

    chat_id = int(parts[1])
    quiz_id = int(parts[2])

    await publish_to_chat(
        context,
        chat_id,
        quiz_id,
    )

    await query.message.reply_text(
        "✅ تم نشر الاختبار."
    )


async def send_to_all(update, context):
    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        return

    quiz_id = int(query.data.replace("sendall_", ""))

    conn = get_db()
    groups = conn.execute(
        "SELECT chat_id FROM groups_table"
    ).fetchall()
    conn.close()

    success = 0

    for group in groups:
        try:
            await publish_to_chat(
                context,
                group["chat_id"],
                quiz_id,
            )
            success += 1
        except Exception as e:
            logger.error(
                "فشل النشر للمجموعة %s: %s",
                group["chat_id"],
                e,
            )

    await query.message.reply_text(
        f"📢 تم النشر بنجاح في {success} مجموعة."
    )


async def publish_to_chat(context, chat_id, quiz_id):
    quiz = get_quiz(quiz_id)

    if not quiz:
        return

    bot_username = context.bot.username

    deep_link = (
        f"https://t.me/{bot_username}?start=quiz_{quiz_id}"
    )

    text = (
        f"📣 **اختبار جديد**\n\n"
        f"📋 {quiz['title']}\n\n"
        f"📝 {quiz['description'] or ''}\n\n"
        f"❓ عدد الأسئلة: {len(quiz['questions
