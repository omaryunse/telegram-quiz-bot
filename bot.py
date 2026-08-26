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

BOT_TOKEN = os.getenv("BOT_TOKEN", "PUT_YOUR_BOT_TOKEN_HERE")

# ضع Telegram User ID الخاص بالأدمن هنا

ADMIN_IDS = {
7021041990,
8810965759,
7020921829,
}

DB_FILE = os.getenv("QUIZ_DB_FILE", "quiz_bot.db")

logging.basicConfig(
format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
level=logging.INFO,
)

logger = logging.getLogger("QuizBot")

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
    conn = sqlite3.connect(
    DB_FILE,
    timeout=30,
    )

    conn.row_factory = sqlite3.Row

    conn.execute(
        "PRAGMA foreign_keys = ON"
    )

    return conn

def init_db():
    with get_db() as conn:

        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                first_name TEXT DEFAULT '',
                username TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                last_seen TEXT NOT NULL,
                quizzes_taken INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS groups_table (
                chat_id INTEGER PRIMARY KEY,
                title TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                last_seen TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS quizzes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT DEFAULT '',
                duration INTEGER NOT NULL DEFAULT 30,
                created_by INTEGER NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                quiz_id INTEGER NOT NULL,
                question_text TEXT NOT NULL,
                options TEXT NOT NULL,
                correct_index INTEGER NOT NULL,

                FOREIGN KEY (
                    quiz_id
                )
                REFERENCES quizzes(id)
                ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                quiz_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                first_name TEXT DEFAULT '',
                username TEXT DEFAULT '',
                correct INTEGER NOT NULL,
                total INTEGER NOT NULL,
                percentage REAL NOT NULL,
                finished_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_questions_quiz
            ON questions(quiz_id);

            CREATE INDEX IF NOT EXISTS idx_results_quiz
            ON results(quiz_id);

            CREATE INDEX IF NOT EXISTS idx_results_user
            ON results(user_id);
            """
        )

    # =========================================================

    # أدوات عامة

    # =========================================================

def now():
    return datetime.now().isoformat(
    timespec="seconds"
    )

def is_admin(user_id):
    try:
        return int(user_id) in ADMIN_IDS
    except (TypeError, ValueError):
        return False

def safe_int(value, default=None):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


async def get_bot_username(bot):
    """Return the bot username safely, refreshing it from Telegram if needed."""
    try:
        me = await bot.get_me()
        return me.username or ""
    except Exception:
        logger.exception("Failed to get bot username")
        return ""

def register_user(user):

    if not user:
        return

    current = now()

    with get_db() as conn:

        conn.execute(
            """
            INSERT INTO users (
                user_id,
                first_name,
                username,
                created_at,
                last_seen
            )
            VALUES (?, ?, ?, ?, ?)

            ON CONFLICT(user_id)
            DO UPDATE SET
                first_name = excluded.first_name,
                username = excluded.username,
                last_seen = excluded.last_seen
            """,
            (
                user.id,
                user.first_name or "",
                user.username or "",
                current,
                current,
            ),
        )

def register_group(chat):

    if not chat:
        return

    if chat.type not in (
        ChatType.GROUP,
        ChatType.SUPERGROUP,
    ):
        return

    current = now()

    with get_db() as conn:

        conn.execute(
            """
            INSERT INTO groups_table (
                chat_id,
                title,
                created_at,
                last_seen
            )
            VALUES (?, ?, ?, ?)

            ON CONFLICT(chat_id)
            DO UPDATE SET
                title = excluded.title,
                last_seen = excluded.last_seen
            """,
            (
                chat.id,
                chat.title or "مجموعة بدون اسم",
                current,
                current,
            ),
        )

def get_quiz(quiz_id):

    quiz_id = safe_int(quiz_id)

    if quiz_id is None:
        return None

    with get_db() as conn:

        quiz = conn.execute(
            """
            SELECT *
            FROM quizzes
            WHERE id = ?
            """,
            (quiz_id,),
        ).fetchone()

        if not quiz:
            return None

        questions = conn.execute(
            """
            SELECT *
            FROM questions
            WHERE quiz_id = ?
            ORDER BY id ASC
            """,
            (quiz_id,),
        ).fetchall()

    result = dict(quiz)

    result["questions"] = []

    for question in questions:

        options = question[
            "options"
        ].split("|||")

        result["questions"].append(
            {
                "id": question["id"],
                "text": question["question_text"],
                "options": options,
                "correct": question["correct_index"],
            }
        )

    return result

def cancel_quiz_timer(context):

    job = context.user_data.get(
        "quiz_job"
    )

    if job:

        try:
            job.schedule_removal()
        except Exception:
            logger.exception(
                "Failed to remove quiz timer"
            )

    context.user_data["quiz_job"] = None

def clear_active_quiz(context):

    cancel_quiz_timer(context)

    context.user_data.pop(
        "active_quiz",
        None,
    )

async def answer_callback(
    query,
    text=None,
    alert=False,
    ):

    try:

        await query.answer(
            text=text,
            show_alert=alert,
        )

    except Exception:
        pass
        # =========================================================

    # لوحة الإدارة

    # =========================================================

def admin_keyboard():

    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "📝 إنشاء اختبار",
                    callback_data="admin_create",
                )
            ],

            [
                InlineKeyboardButton(
                    "📚 الاختبارات",
                    callback_data="admin_quizzes",
                ),

                InlineKeyboardButton(
                    "📊 النتائج",
                    callback_data="admin_results",
                ),
            ],

            [
                InlineKeyboardButton(
                    "👥 المستخدمون",
                    callback_data="admin_users",
                ),

                InlineKeyboardButton(
                    "🌐 المجموعات",
                    callback_data="admin_groups",
                ),
            ],

            [
                InlineKeyboardButton(
                    "📈 الإحصائيات",
                    callback_data="admin_stats",
                )
            ],
        ]
    )

async def send_admin_panel(message):

    await message.reply_text(
        "🔐 لوحة تحكم بوت الاختبارات\n\n"
        "اختر العملية التي تريد تنفيذها:",
        reply_markup=admin_keyboard(),
    )

async def admin_panel_callback(
    update,
    context,
    ):

    query = update.callback_query

    if not is_admin(
        query.from_user.id
    ):

        await answer_callback(
            query,
            "❌ ليس لديك صلاحية.",
            True,
        )

        return

    await answer_callback(query)

    await send_admin_panel(
        query.message
    )

    # =========================================================

    # START

    # =========================================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    ):

    user = update.effective_user
    chat = update.effective_chat

    register_user(user)

    # -----------------------------------------
    # المجموعة
    # -----------------------------------------

    if chat.type in (
        ChatType.GROUP,
        ChatType.SUPERGROUP,
    ):

        register_group(chat)

        await update.message.reply_text(
            "👋 تم تسجيل المجموعة بنجاح.\n\n"
            "📌 الاختبارات يتم حلها في الخاص فقط.\n"
            "🚀 عند نشر اختبار اضغط «بدء الاختبار»."
        )

        return

    # -----------------------------------------
    # Deep Link
    # -----------------------------------------

    if context.args:

        argument = (
            context.args[0]
            .strip()
        )

        if argument.startswith(
            "quiz_"
        ):

            quiz_id = safe_int(
                argument[5:]
            )

            if quiz_id is None:

                await update.message.reply_text(
                    "❌ رابط الاختبار غير صالح."
                )

                return

            await start_quiz_from_link(
                update,
                context,
                quiz_id,
            )

            return

    # -----------------------------------------
    # الأدمن
    # -----------------------------------------

    if is_admin(user.id):

        await update.message.reply_text(
            "👑 أهلاً بك في لوحة تحكم بوت الاختبارات.",
            reply_markup=admin_keyboard(),
        )

    else:

        await update.message.reply_text(
            f"👋 أهلاً {user.first_name or 'بك'}!\n\n"
            "🎯 عندما يصلك رابط اختبار، "
            "اضغط «🚀 بدء الاختبار»."
        )

async def help_command(
    update,
    context,
    ):

    await update.message.reply_text(
        "📚 أوامر البوت:\n\n"
        "/start - تشغيل البوت\n"
        "/help - المساعدة\n"
        "/cancel - إلغاء إنشاء الاختبار\n"
        "/cancel_quiz - إلغاء الاختبار الحالي"
    )

    # =========================================================

    # إنشاء اختبار

    # =========================================================

async def create_quiz_start(
    update,
    context,
    ):

    query = update.callback_query

    if query:

        if not is_admin(
            query.from_user.id
        ):

            await answer_callback(
                query,
                "❌ ليس لديك صلاحية.",
                True,
            )

            return ConversationHandler.END

        await answer_callback(query)

        message = query.message

    else:

        if not is_admin(
            update.effective_user.id
        ):

            await update.message.reply_text(
                "❌ هذا الأمر خاص بالأدمن."
            )

            return ConversationHandler.END

        message = update.message

    context.user_data[
        "quiz_build"
    ] = {
        "title": "",
        "description": "",
        "duration": 30,
        "questions": [],
    }

    context.user_data.pop(
        "current_question",
        None,
    )

    await message.reply_text(
        "📝 إنشاء اختبار جديد\n\n"
        "✍️ أرسل عنوان الاختبار:"
    )

    return TITLE

async def handle_title(
    update,
    context,
    ):

    if not is_admin(
        update.effective_user.id
    ):
        return ConversationHandler.END

    build = context.user_data.get(
        "quiz_build"
    )

    if not build:

        await update.message.reply_text(
            "❌ انتهت جلسة إنشاء الاختبار."
        )

        return ConversationHandler.END

    text = (
        update.message.text or ""
    ).strip()

    if len(text) < 2:

        await update.message.reply_text(
            "⚠️ العنوان قصير جدًا."
        )

        return TITLE

    if len(text) > 150:

        await update.message.reply_text(
            "⚠️ الحد الأقصى للعنوان 150 حرفًا."
        )

        return TITLE

    build["title"] = text

    await update.message.reply_text(
        "📝 أرسل وصف الاختبار.\n\n"
        "أو اكتب /skip لتخطي الوصف."
    )

    return DESCRIPTION

async def skip_description(
    update,
    context,
    ):

    build = context.user_data.get(
        "quiz_build"
    )

    if not build:
        return ConversationHandler.END

    build["description"] = ""

    await update.message.reply_text(
        "⏱️ أرسل مدة كل سؤال بالثواني.\n\n"
        "مثال: 30"
    )

    return DURATION

async def handle_description(
    update,
    context,
    ):

    build = context.user_data.get(
        "quiz_build"
    )

    if not build:
        return ConversationHandler.END

    text = (
        update.message.text or ""
    ).strip()

    if len(text) > 1000:

        await update.message.reply_text(
            "⚠️ الحد الأقصى للوصف 1000 حرف."
        )

        return DESCRIPTION

    build["description"] = text

    await update.message.reply_text(
        "⏱️ أرسل مدة كل سؤال بالثواني.\n\n"
        "مثال: 30"
    )

    return DURATION

async def handle_duration(
    update,
    context,
    ):

    build = context.user_data.get(
        "quiz_build"
    )

    if not build:
        return ConversationHandler.END

    text = (
        update.message.text or ""
    ).strip()

    try:
        duration = int(text)

    except ValueError:

        await update.message.reply_text(
            "⚠️ أرسل رقمًا صحيحًا.\n"
            "مثال: 30"
        )

        return DURATION

    if duration < 5:

        await update.message.reply_text(
            "⚠️ أقل مدة مسموحة هي 5 ثوانٍ."
        )

        return DURATION

    if duration > 3600:

        await update.message.reply_text(
            "⚠️ أقصى مدة مسموحة هي 3600 ثانية."
        )

        return DURATION

    build["duration"] = duration

    await update.message.reply_text(
        "❓ أرسل نص السؤال الأول:"
    )

    return QUESTION_TEXT

async def handle_question_text(
    update,
    context,
    ):

    build = context.user_data.get(
        "quiz_build"
    )

    if not build:
        return ConversationHandler.END

    text = (
        update.message.text or ""
    ).strip()

    if len(text) < 2:

        await update.message.reply_text(
            "⚠️ السؤال قصير جدًا."
        )

        return QUESTION_TEXT

    if len(text) > 3000:

        await update.message.reply_text(
            "⚠️ الحد الأقصى للسؤال 3000 حرف."
        )

        return QUESTION_TEXT

    context.user_data[
        "current_question"
    ] = {
        "text": text,
        "options": [],
        "correct": None,
    }

    await update.message.reply_text(
        "🔢 أرسل الخيارات.\n\n"
        "كل خيار في سطر مستقل.\n\n"
        "مثال:\n"
        "بغداد\n"
        "البصرة\n"
        "الموصل\n"
        "أربيل"
    )

    return QUESTION_OPTIONS

async def handle_question_options(
    update,
    context,
    ):

    question = context.user_data.get(
        "current_question"
    )

    if not question:

        await update.message.reply_text(
            "❌ لم يتم العثور على السؤال."
        )

        return QUESTION_TEXT

    lines = (
        update.message.text or ""
    ).splitlines()

    options = [
        line.strip()
        for line in lines
        if line.strip()
    ]

    if len(options) < 2:

        await update.message.reply_text(
            "⚠️ يجب إدخال خيارين على الأقل."
        )

        return QUESTION_OPTIONS

    if len(options) > 10:

        await update.message.reply_text(
            "⚠️ الحد الأقصى 10 خيارات."
        )

        return QUESTION_OPTIONS

    if any(
        len(option) > 300
        for option in options
    ):

        await update.message.reply_text(
            "⚠️ الحد الأقصى لطول الخيار 300 حرف."
        )

        return QUESTION_OPTIONS

    normalized = [
        option.casefold()
        for option in options
    ]

    if len(set(normalized)) != len(
        normalized
    ):

        await update.message.reply_text(
            "⚠️ لا يمكن تكرار نفس الخيار."
        )

        return QUESTION_OPTIONS

    if any(
        "|||" in option
        for option in options
    ):

        await update.message.reply_text(
            "⚠️ الرمز ||| محجوز داخليًا."
        )

        return QUESTION_OPTIONS

    question["options"] = options

    buttons = []

    for i, option in enumerate(
        options
    ):

        buttons.append(
            [
                InlineKeyboardButton(
                    f"{i + 1}. {option}",
                    callback_data=f"correct_{i}",
                )
            ]
        )

    await update.message.reply_text(
        "✅ اختر الإجابة الصحيحة:",
        reply_markup=InlineKeyboardMarkup(
            buttons
        ),
    )

    return QUESTION_CORRECT
    # =========================================================

    # تحديد الإجابة الصحيحة

    # =========================================================

async def handle_correct_answer(
    update,
    context,
    ):

    query = update.callback_query

    if not is_admin(
        query.from_user.id
    ):

        await answer_callback(
            query,
            "❌ ليس لديك صلاحية.",
            True,
        )

        return ConversationHandler.END

    await answer_callback(query)

    question = context.user_data.get(
        "current_question"
    )

    build = context.user_data.get(
        "quiz_build"
    )

    if not question or not build:

        await query.message.reply_text(
            "❌ انتهت جلسة إنشاء الاختبار."
        )

        return ConversationHandler.END

    try:

        index = int(
            query.data.replace(
                "correct_",
                "",
                1,
            )
        )

    except ValueError:

        await query.message.reply_text(
            "❌ اختيار غير صالح."
        )

        return QUESTION_CORRECT

    if index < 0 or index >= len(
        question["options"]
    ):

        await query.message.reply_text(
            "❌ اختيار غير صالح."
        )

        return QUESTION_CORRECT

    question["correct"] = index

    build["questions"].append(
        question.copy()
    )

    context.user_data.pop(
        "current_question",
        None,
    )

    count = len(
        build["questions"]
    )

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
        f"✅ تمت إضافة السؤال رقم {count}.\n\n"
        "ماذا تريد أن تفعل؟",
        reply_markup=InlineKeyboardMarkup(
            buttons
        ),
    )

    return QUESTION_MORE

    # =========================================================

    # بعد إضافة السؤال

    # =========================================================

async def question_more(
    update,
    context,
    ):

    query = update.callback_query

    if not is_admin(
        query.from_user.id
    ):

        await answer_callback(
            query,
            "❌ ليس لديك صلاحية.",
            True,
        )

        return ConversationHandler.END

    await answer_callback(query)

    build = context.user_data.get(
        "quiz_build"
    )

    if not build:

        await query.message.reply_text(
            "❌ لا يوجد اختبار قيد الإنشاء."
        )

        return ConversationHandler.END

    if query.data == "question_add":

        await query.message.reply_text(
            "❓ أرسل نص السؤال التالي:"
        )

        return QUESTION_TEXT

    if query.data == "quiz_preview":

        await send_quiz_preview(
            query.message,
            build,
        )

        return QUESTION_MORE

    if query.data == "quiz_save":

        return await save_quiz(
            update,
            context,
        )

    return QUESTION_MORE

    # =========================================================

    # معاينة الاختبار

    # =========================================================

async def send_quiz_preview(
    message,
    build,
    ):

    lines = [
        "👀 معاينة الاختبار",
        "",
        f"📋 {build['title']}",
        f"📝 {build['description'] or 'بدون وصف'}",
        f"⏱️ {build['duration']} ثانية لكل سؤال",
        f"❓ عدد الأسئلة: {len(build['questions'])}",
        "",
    ]

    for i, question in enumerate(
        build["questions"],
        1,
    ):

        lines.append(
            f"{i}. {question['text']}"
        )

        for j, option in enumerate(
            question["options"]
        ):

            mark = (
                "✅"
                if j == question["correct"]
                else "▫️"
            )

            lines.append(
                f"   {mark} {option}"
            )

        lines.append("")

    text = "\n".join(lines)

    if len(text) > 4000:

        text = (
            text[:3950]
            + "\n\n..."
        )

    await message.reply_text(text)

    # =========================================================

    # حفظ الاختبار

    # =========================================================

async def save_quiz(
    update,
    context,
    ):

    query = update.callback_query

    build = context.user_data.get(
        "quiz_build"
    )

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

    try:

        with get_db() as conn:

            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO quizzes (
                    title,
                    description,
                    duration,
                    created_by,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    build["title"],
                    build["description"],
                    build["duration"],
                    query.from_user.id,
                    now(),
                ),
            )

            quiz_id = cursor.lastrowid

            for question in build[
                "questions"
            ]:

                cursor.execute(
                    """
                    INSERT INTO questions (
                        quiz_id,
                        question_text,
                        options,
                        correct_index
                    )
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        quiz_id,
                        question["text"],
                        "|||".join(
                            question["options"]
                        ),
                        question["correct"],
                    ),
                )

    except sqlite3.Error:

        logger.exception(
            "Failed to save quiz"
        )

        await query.message.reply_text(
            "❌ حدث خطأ أثناء حفظ الاختبار."
        )

        return QUESTION_MORE

    title = build["title"]

    count = len(
        build["questions"]
    )

    context.user_data.pop(
        "quiz_build",
        None,
    )

    context.user_data.pop(
        "current_question",
        None,
    )

    buttons = [
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
    ]

    await query.message.reply_text(
        f"🎉 تم إنشاء الاختبار بنجاح!\n\n"
        f"🆔 رقم الاختبار: {quiz_id}\n"
        f"📋 {title}\n"
        f"❓ عدد الأسئلة: {count}",
        reply_markup=InlineKeyboardMarkup(
            buttons
        ),
    )

    return ConversationHandler.END

    # =========================================================

    # إلغاء إنشاء الاختبار

    # =========================================================

async def cancel_creation(
    update,
    context,
    ):

    context.user_data.pop(
        "quiz_build",
        None,
    )

    context.user_data.pop(
        "current_question",
        None,
    )

    await update.message.reply_text(
        "❌ تم إلغاء عملية إنشاء الاختبار."
    )

    return ConversationHandler.END

    # =========================================================

    # مشاركة الاختبار

    # =========================================================

async def share_quiz(
    update,
    context,
    ):

    query = update.callback_query

    if not is_admin(
        query.from_user.id
    ):

        await answer_callback(
            query,
            "❌ ليس لديك صلاحية.",
            True,
        )

        return

    await answer_callback(query)

    quiz_id = safe_int(
        query.data.replace(
            "share_",
            "",
            1,
        )
    )

    if quiz_id is None:

        await query.message.reply_text(
            "❌ رقم الاختبار غير صالح."
        )

        return

    quiz = get_quiz(quiz_id)

    if not quiz:

        await query.message.reply_text(
            "❌ الاختبار غير موجود."
        )

        return

    bot_username = await get_bot_username(
        context.bot
    )

    if not bot_username:

        await query.message.reply_text(
            "❌ تعذر الحصول على اسم البوت."
        )

        return

    deep_link = (
        f"https://t.me/"
        f"{bot_username}"
        f"?start=quiz_{quiz_id}"
    )

    text = (
        "📣 اختبار جديد\n\n"
        f"📋 {quiz['title']}\n\n"
        f"{quiz['description'] or ''}\n\n"
        f"❓ عدد الأسئلة: "
        f"{len(quiz['questions'])}\n"
        f"⏱️ مدة السؤال: "
        f"{quiz['duration']} ثانية\n\n"
        "🔐 الاختبار يتم في الخاص."
    )

    await query.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "🚀 بدء الاختبار",
                        url=deep_link,
                    )
                ]
            ]
        ),
    )

    # =========================================================

    # نشر الاختبار للمجموعات

    # =========================================================

async def publish_quiz(
    update,
    context,
    ):

    query = update.callback_query

    if not is_admin(
        query.from_user.id
    ):

        await answer_callback(
            query,
            "❌ ليس لديك صلاحية.",
            True,
        )

        return

    await answer_callback(query)

    quiz_id = safe_int(
        query.data.replace(
            "publish_",
            "",
            1,
        )
    )

    if quiz_id is None:

        await query.message.reply_text(
            "❌ رقم الاختبار غير صالح."
        )

        return

    quiz = get_quiz(quiz_id)

    if not quiz:

        await query.message.reply_text(
            "❌ الاختبار غير موجود."
        )

        return

    with get_db() as conn:

        groups = conn.execute(
            """
            SELECT *
            FROM groups_table
            ORDER BY title COLLATE NOCASE
            """
        ).fetchall()

    if not groups:

        await query.message.reply_text(
            "🌐 لا توجد مجموعات مسجلة.\n\n"
            "أضف البوت إلى المجموعة ثم "
            "استخدم /start داخلها."
        )

        return

    buttons = []

    for group in groups:

        title = (
            group["title"]
            or str(group["chat_id"])
        )

        buttons.append(
            [
                InlineKeyboardButton(
                    f"📢 {title[:40]}",
                    callback_data=(
                        f"sg_"
                        f"{group['chat_id']}_"
                        f"{quiz_id}"
                    ),
                )
            ]
        )

    buttons.append(
        [
            InlineKeyboardButton(
                "📢 نشر للجميع",
                callback_data=f"sa_{quiz_id}",
            )
        ]
    )

    await query.message.reply_text(
        "🌐 اختر مكان نشر الاختبار:",
        reply_markup=InlineKeyboardMarkup(
            buttons
        ),
    )

async def send_to_group(
    update,
    context,
    ):

    query = update.callback_query

    if not is_admin(
        query.from_user.id
    ):

        await answer_callback(
            query,
            "❌ ليس لديك صلاحية.",
            True,
        )

        return

    await answer_callback(query)

    parts = query.data.split("_")

    if len(parts) != 3:

        await query.message.reply_text(
            "❌ بيانات النشر غير صالحة."
        )

        return

    chat_id = safe_int(
        parts[1]
    )

    quiz_id = safe_int(
        parts[2]
    )

    if chat_id is None or quiz_id is None:

        await query.message.reply_text(
            "❌ بيانات النشر غير صالحة."
        )

        return

    success = await publish_to_chat(
        context,
        chat_id,
        quiz_id,
    )

    if success:

        await query.message.reply_text(
            "✅ تم نشر الاختبار في المجموعة."
        )

    else:

        await query.message.reply_text(
            "❌ تعذر النشر في المجموعة.\n\n"
            "تأكد أن البوت موجود في المجموعة "
            "ولديه صلاحية إرسال الرسائل."
        )

async def send_to_all(
    update,
    context,
    ):

    query = update.callback_query

    if not is_admin(
        query.from_user.id
    ):

        await answer_callback(
            query,
            "❌ ليس لديك صلاحية.",
            True,
        )

        return

    await answer_callback(query)

    quiz_id = safe_int(
        query.data.replace(
            "sa_",
            "",
            1,
        )
    )

    if quiz_id is None:

        await query.message.reply_text(
            "❌ رقم الاختبار غير صالح."
        )

        return

    with get_db() as conn:

        groups = conn.execute(
            "SELECT chat_id FROM groups_table"
        ).fetchall()

    success = 0
    failed = 0

    for group in groups:

        try:

            ok = await publish_to_chat(
                context,
                group["chat_id"],
                quiz_id,
            )

            if ok:
                success += 1
            else:
                failed += 1

        except Exception:

            failed += 1

            logger.exception(
                "Publishing failed"
            )

    await query.message.reply_text(
        f"📢 انتهى النشر.\n\n"
        f"✅ نجح: {success}\n"
        f"❌ فشل: {failed}"
    )

async def publish_to_chat(
    context,
    chat_id,
    quiz_id,
    ):

    quiz = get_quiz(quiz_id)

    if not quiz:
        return False

    bot_username = await get_bot_username(
        context.bot
    )

    if not bot_username:
        return False

    deep_link = (
        f"https://t.me/"
        f"{bot_username}"
        f"?start=quiz_{quiz_id}"
    )

    text = (
        "📣 اختبار جديد\n\n"
        f"📋 {quiz['title']}\n\n"
        f"{quiz['description'] or ''}\n\n"
        f"❓ عدد الأسئلة: "
        f"{len(quiz['questions'])}\n"
        f"⏱️ مدة السؤال: "
        f"{quiz['duration']} ثانية\n\n"
        "اضغط الزر للبدء في الخاص:"
    )

    try:

        await context.bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "🚀 بدء الاختبار",
                            url=deep_link,
                        )
                    ]
                ]
            ),
        )

        with get_db() as conn:

            conn.execute(
                """
                UPDATE groups_table
                SET last_seen = ?
                WHERE chat_id = ?
                """,
                (
                    now(),
                    chat_id,
                ),
            )

        return True

    except Exception as exc:

        logger.warning(
            "Could not publish quiz %s to %s: %s",
            quiz_id,
            chat_id,
            exc,
        )

        return False
        # =========================================================

    # بدء الاختبار من الرابط

    # =========================================================

async def start_quiz_from_link(
    update,
    context,
    quiz_id,
    ):

    if (
        update.effective_chat.type
        != ChatType.PRIVATE
    ):

        await update.message.reply_text(
            "🔐 الاختبارات يتم حلها في الخاص."
        )

        return

    quiz = get_quiz(quiz_id)

    if not quiz:

        await update.message.reply_text(
            "❌ الاختبار غير موجود أو تم حذفه."
        )

        return

    if not quiz["questions"]:

        await update.message.reply_text(
            "❌ هذا الاختبار لا يحتوي على أسئلة."
        )

        return

    # إلغاء اختبار سابق
    clear_active_quiz(context)

    context.user_data[
        "active_quiz"
    ] = {
        "user_id": update.effective_user.id,
        "quiz_id": quiz_id,
        "question_index": 0,
        "correct": 0,
        "answers": 0,
    }

    await update.message.reply_text(
        f"🎯 {quiz['title']}\n\n"
        f"{quiz['description'] or ''}\n\n"
        f"❓ عدد الأسئلة: "
        f"{len(quiz['questions'])}\n"
        f"⏱️ مدة كل سؤال: "
        f"{quiz['duration']} ثانية\n\n"
        "🚀 يبدأ الاختبار الآن."
    )

    await send_current_question(
        update.effective_chat.id,
        context,
    )

    # =========================================================

    # إرسال السؤال الحالي

    # =========================================================

async def send_current_question(
    chat_id,
    context,
    ):

    session = context.user_data.get(
        "active_quiz"
    )

    if not session:
        return

    quiz = get_quiz(
        session["quiz_id"]
    )

    if not quiz:

        clear_active_quiz(context)

        await context.bot.send_message(
            chat_id=chat_id,
            text="❌ لم يعد الاختبار موجودًا."
        )

        return

    index = session[
        "question_index"
    ]

    if index >= len(
        quiz["questions"]
    ):

        await finish_quiz(
            chat_id,
            context,
        )

        return

    question = quiz[
        "questions"
    ][index]

    buttons = []

    for i, option in enumerate(
        question["options"]
    ):

        buttons.append(
            [
                InlineKeyboardButton(
                    f"{i + 1}. {option}",
                    callback_data=(
                        f"ans_"
                        f"{quiz['id']}_"
                        f"{index}_"
                        f"{i}"
                    ),
                )
            ]
        )

    buttons.append(
        [
            InlineKeyboardButton(
                "❌ إلغاء الاختبار",
                callback_data="quiz_cancel",
            )
        ]
    )

    await context.bot.send_message(
        chat_id=chat_id,
        text=(
            f"❓ السؤال {index + 1} "
            f"من {len(quiz['questions'])}\n\n"
            f"{question['text']}\n\n"
            f"⏱️ لديك "
            f"{quiz['duration']} ثانية."
        ),
        reply_markup=InlineKeyboardMarkup(
            buttons
        ),
    )

    # إزالة المؤقت السابق
    cancel_quiz_timer(context)

    if context.job_queue is None:

        logger.error(
            "JobQueue unavailable."
        )

        await context.bot.send_message(
            chat_id=chat_id,
            text=(
                "⚠️ المؤقت غير متاح في إعداد المكتبة.\n"
                "ثبت python-telegram-bot[job-queue]."
            ),
        )

        return

    # حفظ رقم السؤال الحالي
    session[
        "timer_question_index"
    ] = index

    context.user_data[
        "quiz_job"
    ] = context.job_queue.run_once(
        quiz_timeout,
        when=quiz["duration"],
        data={
            "chat_id": chat_id,
            "user_id": session["user_id"],
            "question_index": index,
        },
    )

    # =========================================================

    # انتهاء وقت السؤال

    # =========================================================

async def quiz_timeout(
    context,
    ):

    job = context.job

    if not job:
        return

    data = job.data or {}

    chat_id = data.get(
        "chat_id"
    )

    user_id = data.get(
        "user_id"
    )

    question_index = data.get(
        "question_index"
    )

    if (
        chat_id is None
        or user_id is None
        or question_index is None
    ):
        return

    user_data = (
        context.application.user_data.get(
            user_id
        )
    )

    if not user_data:
        return

    session = user_data.get(
        "active_quiz"
    )

    if not session:
        return

    if session.get(
        "question_index"
    ) != question_index:
        return

    quiz = get_quiz(
        session["quiz_id"]
    )

    if not quiz:
        user_data.pop(
            "active_quiz",
            None,
        )
        return

    # السؤال انتهى بدون إجابة
    session["answers"] += 1
    session["question_index"] += 1

    user_data["quiz_job"] = None

    await context.bot.send_message(
        chat_id=chat_id,
        text=(
            "⏰ انتهى الوقت.\n"
            "لم يتم تسجيل إجابة لهذا السؤال."
        ),
    )

    await send_question_for_user(
        chat_id,
        user_id,
        context,
    )

    # =========================================================

    # إرسال السؤال باستخدام user_id

    # =========================================================

async def send_question_for_user(
    chat_id,
    user_id,
    context,
    ):

    user_data = (
        context.application.user_data.get(
            user_id
        )
    )

    if not user_data:
        return

    session = user_data.get(
        "active_quiz"
    )

    if not session:
        return

    quiz = get_quiz(
        session["quiz_id"]
    )

    if not quiz:
        user_data.pop(
            "active_quiz",
            None,
        )
        return

    index = session[
        "question_index"
    ]

    if index >= len(
        quiz["questions"]
    ):

        await finish_quiz_for_user(
            chat_id,
            user_id,
            context,
        )

        return

    question = quiz[
        "questions"
    ][index]

    buttons = []

    for i, option in enumerate(
        question["options"]
    ):

        buttons.append(
            [
                InlineKeyboardButton(
                    f"{i + 1}. {option}",
                    callback_data=(
                        f"ans_"
                        f"{quiz['id']}_"
                        f"{index}_"
                        f"{i}"
                    ),
                )
            ]
        )

    buttons.append(
        [
            InlineKeyboardButton(
                "❌ إلغاء الاختبار",
                callback_data="quiz_cancel",
            )
        ]
    )

    await context.bot.send_message(
        chat_id=chat_id,
        text=(
            f"❓ السؤال {index + 1} "
            f"من {len(quiz['questions'])}\n\n"
            f"{question['text']}\n\n"
            f"⏱️ لديك "
            f"{quiz['duration']} ثانية."
        ),
        reply_markup=InlineKeyboardMarkup(
            buttons
        ),
    )

    cancel_user_timer(
        user_data
    )

    if context.job_queue:

        user_data[
            "quiz_job"
        ] = context.job_queue.run_once(
            quiz_timeout,
            when=quiz["duration"],
            data={
                "chat_id": chat_id,
                "user_id": user_id,
                "question_index": index,
            },
        )

def cancel_user_timer(
    user_data
    ):

    job = user_data.get(
        "quiz_job"
    )

    if job:

        try:
            job.schedule_removal()
        except Exception:
            pass

    user_data["quiz_job"] = None

    # =========================================================

    # الإجابة عن السؤال

    # =========================================================

async def answer_quiz(
    update,
    context,
    ):

    query = update.callback_query

    await answer_callback(query)

    parts = query.data.split("_")

    if len(parts) != 4:

        await query.message.reply_text(
            "❌ إجابة غير صالحة."
        )

        return

    quiz_id = safe_int(
        parts[1]
    )

    question_index = safe_int(
        parts[2]
    )

    answer_index = safe_int(
        parts[3]
    )

    if None in (
        quiz_id,
        question_index,
        answer_index,
    ):

        await query.message.reply_text(
            "❌ إجابة غير صالحة."
        )

        return

    session = context.user_data.get(
        "active_quiz"
    )

    if not session:

        await query.message.reply_text(
            "ℹ️ لا يوجد اختبار نشط حاليًا."
        )

        return

    if session["quiz_id"] != quiz_id:

        await query.message.reply_text(
            "❌ هذه الإجابة تخص اختبارًا آخر."
        )

        return

    if session[
        "question_index"
    ] != question_index:

        await answer_callback(
            query,
            "⏰ انتهى هذا السؤال أو تمت الإجابة عليه.",
            True,
        )

        return

    quiz = get_quiz(
        quiz_id
    )

    if not quiz:

        clear_active_quiz(context)

        await query.message.reply_text(
            "❌ الاختبار غير موجود."
        )

        return

    if question_index >= len(
        quiz["questions"]
    ):

        clear_active_quiz(context)

        await query.message.reply_text(
            "❌ السؤال غير موجود."
        )

        return

    question = quiz[
        "questions"
    ][question_index]

    if (
        answer_index < 0
        or answer_index >= len(
            question["options"]
        )
    ):

        await answer_callback(
            query,
            "❌ اختيار غير صالح.",
            True,
        )

        return

    # إلغاء المؤقت
    cancel_quiz_timer(
        context
    )

    if answer_index == question[
        "correct"
    ]:

        session["correct"] += 1

        result_text = (
            "✅ إجابة صحيحة!"
        )

    else:

        correct_text = question[
            "options"
        ][question["correct"]]

        result_text = (
            "❌ إجابة خاطئة.\n\n"
            f"الإجابة الصحيحة: "
            f"{correct_text}"
        )

    session["answers"] += 1

    session[
        "question_index"
    ] += 1

    await query.message.reply_text(
        result_text
    )

    await send_current_question(
        update.effective_chat.id,
        context,
    )

    # =========================================================

    # إلغاء الاختبار

    # =========================================================

async def cancel_active_quiz(
    update,
    context,
    ):

    query = update.callback_query

    if query:
        await answer_callback(query)

        message = query.message

    else:
        message = update.message

    if context.user_data.get(
        "active_quiz"
    ):

        clear_active_quiz(
            context
        )

        await message.reply_text(
            "❌ تم إلغاء الاختبار.\n"
            "لن يتم تسجيل النتيجة."
        )

    else:

        await message.reply_text(
            "ℹ️ لا يوجد اختبار نشط."
        )

async def cancel_quiz_command(
    update,
    context,
    ):

    await cancel_active_quiz(
        update,
        context,
    )

    # =========================================================

    # إنهاء الاختبار

    # =========================================================

async def finish_quiz(
    chat_id,
    context,
    ):

    session = context.user_data.get(
        "active_quiz"
    )

    if not session:
        return

    quiz = get_quiz(
        session["quiz_id"]
    )

    if not quiz:

        clear_active_quiz(
            context
        )

        await context.bot.send_message(
            chat_id=chat_id,
            text="❌ تعذر العثور على الاختبار."
        )

        return

    await finish_quiz_for_user(
        chat_id,
        session["user_id"],
        context,
    )

async def finish_quiz_for_user(
    chat_id,
    user_id,
    context,
    ):

    user_data = (
        context.application.user_data.get(
            user_id
        )
    )

    if not user_data:
        return

    session = user_data.get(
        "active_quiz"
    )

    if not session:
        return

    quiz = get_quiz(
        session["quiz_id"]
    )

    if not quiz:
        user_data.pop(
            "active_quiz",
            None,
        )
        return

    cancel_user_timer(
        user_data
    )

    total = len(
        quiz["questions"]
    )

    correct = min(
        session.get(
            "correct",
            0,
        ),
        total,
    )

    percentage = (
        round(
            correct / total * 100,
            2,
        )
        if total
        else 0
    )

    try:

        user = await context.bot.get_chat(
            user_id
        )

        first_name = (
            user.first_name or ""
        )

        username = (
            user.username or ""
        )

    except Exception:

        first_name = ""
        username = ""

    with get_db() as conn:

        conn.execute(
            """
            INSERT INTO results (
                quiz_id,
                user_id,
                first_name,
                username,
                correct,
                total,
                percentage,
                finished_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                quiz["id"],
                user_id,
                first_name,
                username,
                correct,
                total,
                percentage,
                now(),
            ),
        )

        conn.execute(
            """
            UPDATE users
            SET quizzes_taken =
                    quizzes_taken + 1,
                last_seen = ?
            WHERE user_id = ?
            """,
            (
                now(),
                user_id,
            ),
        )

    user_data.pop(
        "active_quiz",
        None,
    )

    user_data["quiz_job"] = None

    await context.bot.send_message(
        chat_id=chat_id,
        text=(
            "🏁 انتهى الاختبار!\n\n"
            f"📋 {quiz['title']}\n\n"
            f"✅ الصحيحة: {correct}\n"
            f"❌ الخاطئة/غير المجابة: "
            f"{total - correct}\n"
            f"📊 النتيجة: "
            f"{percentage:.2f}%\n\n"
            "🎉 أحسنت، بالتوفيق!"
        ),
    )
    # =========================================================

    # قائمة الاختبارات

    # =========================================================

async def admin_quizzes(
    update,
    context,
    ):

    query = update.callback_query

    if not is_admin(
        query.from_user.id
    ):

        await answer_callback(
            query,
            "❌ ليس لديك صلاحية.",
            True,
        )

        return

    await answer_callback(query)

    with get_db() as conn:

        quizzes = conn.execute(
            """
            SELECT
                q.id,
                q.title,
                q.duration,
                q.created_at,
                COUNT(qq.id) AS question_count

            FROM quizzes q

            LEFT JOIN questions qq
                ON qq.quiz_id = q.id

            GROUP BY q.id

            ORDER BY q.id DESC

            LIMIT 30
            """
        ).fetchall()

    if not quizzes:

        await query.message.reply_text(
            "📚 لا توجد اختبارات حتى الآن."
        )

        return

    lines = [
        "📚 آخر الاختبارات:",
        "",
    ]

    buttons = []

    for quiz in quizzes:

        lines.append(
            f"🆔 {quiz['id']} | "
            f"{quiz['title']} | "
            f"{quiz['question_count']} سؤال"
        )

        buttons.append(
            [
                InlineKeyboardButton(
                    f"📤 مشاركة #{quiz['id']}",
                    callback_data=(
                        f"share_{quiz['id']}"
                    ),
                ),

                InlineKeyboardButton(
                    f"📢 نشر #{quiz['id']}",
                    callback_data=(
                        f"publish_{quiz['id']}"
                    ),
                ),
            ]
        )

    buttons.append(
        [
            InlineKeyboardButton(
                "↩️ لوحة التحكم",
                callback_data="admin_back",
            )
        ]
    )

    await query.message.reply_text(
        "\n".join(lines),
        reply_markup=InlineKeyboardMarkup(
            buttons
        ),
    )

    # =========================================================

    # النتائج

    # =========================================================

async def admin_results(
    update,
    context,
    ):

    query = update.callback_query

    if not is_admin(
        query.from_user.id
    ):

        await answer_callback(
            query,
            "❌ ليس لديك صلاحية.",
            True,
        )

        return

    await answer_callback(query)

    with get_db() as conn:

        rows = conn.execute(
            """
            SELECT
                r.*,
                q.title

            FROM results r

            LEFT JOIN quizzes q
                ON q.id = r.quiz_id

            ORDER BY r.id DESC

            LIMIT 30
            """
        ).fetchall()

    if not rows:

        await query.message.reply_text(
            "📊 لا توجد نتائج حتى الآن."
        )

        return

    lines = [
        "📊 آخر النتائج:",
        "",
    ]

    for row in rows:

        name = (
            row["first_name"]
            or row["username"]
            or str(row["user_id"])
        )

        lines.append(
            f"👤 {name}\n"
            f"📋 {row['title'] or 'اختبار محذوف'}\n"
            f"🎯 {row['correct']}/"
            f"{row['total']} "
            f"({row['percentage']:.2f}%)\n"
            f"🕐 {row['finished_at']}\n"
        )

    text = "\n".join(lines)

    if len(text) > 4000:

        text = (
            text[:3950]
            + "\n..."
        )

    await query.message.reply_text(
        text
    )

    # =========================================================

    # المستخدمون

    # =========================================================

async def admin_users(
    update,
    context,
    ):

    query = update.callback_query

    if not is_admin(
        query.from_user.id
    ):

        await answer_callback(
            query,
            "❌ ليس لديك صلاحية.",
            True,
        )

        return

    await answer_callback(query)

    with get_db() as conn:

        total = conn.execute(
            """
            SELECT COUNT(*) AS count
            FROM users
            """
        ).fetchone()["count"]

        top = conn.execute(
            """
            SELECT
                first_name,
                username,
                quizzes_taken

            FROM users

            ORDER BY
                quizzes_taken DESC,
                last_seen DESC

            LIMIT 10
            """
        ).fetchall()

    lines = [
        "👥 المستخدمون",
        "",
        f"👤 إجمالي المستخدمين: {total}",
        "",
        "🏆 الأكثر استخدامًا:",
    ]

    for user in top:

        name = (
            user["first_name"]
            or user["username"]
            or "بدون اسم"
        )

        lines.append(
            f"• {name}: "
            f"{user['quizzes_taken']} اختبار"
        )

    await query.message.reply_text(
        "\n".join(lines)
    )

    # =========================================================

    # المجموعات

    # =========================================================

async def admin_groups(
    update,
    context,
    ):

    query = update.callback_query

    if not is_admin(
        query.from_user.id
    ):

        await answer_callback(
            query,
            "❌ ليس لديك صلاحية.",
            True,
        )

        return

    await answer_callback(query)

    with get_db() as conn:

        groups = conn.execute(
            """
            SELECT *
            FROM groups_table

            ORDER BY
                title COLLATE NOCASE

            LIMIT 50
            """
        ).fetchall()

    if not groups:

        await query.message.reply_text(
            "🌐 لا توجد مجموعات مسجلة."
        )

        return

    lines = [
        "🌐 المجموعات المسجلة:",
        "",
    ]

    for group in groups:

        lines.append(
            f"• {group['title'] or 'بدون اسم'}\n"
            f"  ID: {group['chat_id']}\n"
            f"  آخر ظهور: "
            f"{group['last_seen']}\n"
        )

    text = "\n".join(lines)

    if len(text) > 4000:

        text = (
            text[:3950]
            + "\n..."
        )

    await query.message.reply_text(
        text
    )

    # =========================================================

    # الإحصائيات

    # =========================================================

async def admin_stats(
    update,
    context,
    ):

    query = update.callback_query

    if not is_admin(
        query.from_user.id
    ):

        await answer_callback(
            query,
            "❌ ليس لديك صلاحية.",
            True,
        )

        return

    await answer_callback(query)

    with get_db() as conn:

        users = conn.execute(
            """
            SELECT COUNT(*) AS count
            FROM users
            """
        ).fetchone()["count"]

        groups = conn.execute(
            """
            SELECT COUNT(*) AS count
            FROM groups_table
            """
        ).fetchone()["count"]

        quizzes = conn.execute(
            """
            SELECT COUNT(*) AS count
            FROM quizzes
            """
        ).fetchone()["count"]

        questions = conn.execute(
            """
            SELECT COUNT(*) AS count
            FROM questions
            """
        ).fetchone()["count"]

        results = conn.execute(
            """
            SELECT COUNT(*) AS count
            FROM results
            """
        ).fetchone()["count"]

        average = conn.execute(
            """
            SELECT AVG(percentage) AS average
            FROM results
            """
        ).fetchone()["average"]

    average_text = (
        f"{average:.2f}%"
        if average is not None
        else "لا توجد نتائج"
    )

    await query.message.reply_text(
        "📈 إحصائيات البوت\n\n"
        f"👥 المستخدمون: {users}\n"
        f"🌐 المجموعات: {groups}\n"
        f"📚 الاختبارات: {quizzes}\n"
        f"❓ الأسئلة: {questions}\n"
        f"🏁 النتائج: {results}\n"
        f"📊 متوسط الدرجات: {average_text}"
    )

    # =========================================================

    # معالجة الأخطاء

    # =========================================================

async def error_handler(
    update,
    context,
    ):

    logger.error(
        "Unhandled exception",
        exc_info=context.error,
    )

    try:

        if (
            update
            and update.effective_message
        ):

            await update.effective_message.reply_text(
                "⚠️ حدث خطأ غير متوقع. "
                "حاول مرة أخرى."
            )

    except Exception:

        pass

    # =========================================================

    # بناء التطبيق

    # =========================================================

def build_application():

    if (
        not BOT_TOKEN
        or BOT_TOKEN
        == "PUT_YOUR_BOT_TOKEN_HERE"
    ):

        raise RuntimeError(
            "BOT_TOKEN غير مضبوط. "
            "ضع توكن البوت في متغير البيئة BOT_TOKEN."
        )

    init_db()

    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .build()
    )

    # =====================================================
    # ConversationHandler لإنشاء الاختبار
    # =====================================================

    creation_conversation = ConversationHandler(

        entry_points=[
            CallbackQueryHandler(
                create_quiz_start,
                pattern=r"^admin_create$",
            )
        ],

        states={

            TITLE: [
                MessageHandler(
                    filters.TEXT
                    & ~filters.COMMAND,
                    handle_title,
                )
            ],

            DESCRIPTION: [
                CommandHandler(
                    "skip",
                    skip_description,
                ),

                MessageHandler(
                    filters.TEXT
                    & ~filters.COMMAND,
                    handle_description,
                ),
            ],

            DURATION: [
                MessageHandler(
                    filters.TEXT
                    & ~filters.COMMAND,
                    handle_duration,
                )
            ],

            QUESTION_TEXT: [
                MessageHandler(
                    filters.TEXT
                    & ~filters.COMMAND,
                    handle_question_text,
                )
            ],

            QUESTION_OPTIONS: [
                MessageHandler(
                    filters.TEXT
                    & ~filters.COMMAND,
                    handle_question_options,
                )
            ],

            QUESTION_CORRECT: [
                CallbackQueryHandler(
                    handle_correct_answer,
                    pattern=r"^correct_\d+$",
                )
            ],

            QUESTION_MORE: [
                CallbackQueryHandler(
                    question_more,
                    pattern=(
                        r"^("
                        r"question_add|"
                        r"quiz_preview|"
                        r"quiz_save"
                        r")$"
                    ),
                )
            ],
        },

        fallbacks=[
            CommandHandler(
                "cancel",
                cancel_creation,
            )
        ],

        per_user=True,
        per_chat=True,
    )

    application.add_handler(
        creation_conversation
    )

    # =====================================================
    # الأوامر
    # =====================================================

    application.add_handler(
        CommandHandler(
            "start",
            start,
        )
    )

    application.add_handler(
        CommandHandler(
            "help",
            help_command,
        )
    )

    application.add_handler(
        CommandHandler(
            "cancel_quiz",
            cancel_quiz_command,
        )
    )

    # =====================================================
    # لوحة الإدارة
    # =====================================================

    application.add_handler(
        CallbackQueryHandler(
            admin_panel_callback,
            pattern=r"^admin_back$",
        )
    )

    application.add_handler(
        CallbackQueryHandler(
            admin_quizzes,
            pattern=r"^admin_quizzes$",
        )
    )

    application.add_handler(
        CallbackQueryHandler(
            admin_results,
            pattern=r"^admin_results$",
        )
    )

    application.add_handler(
        CallbackQueryHandler(
            admin_users,
            pattern=r"^admin_users$",
        )
    )

    application.add_handler(
        CallbackQueryHandler(
            admin_groups,
            pattern=r"^admin_groups$",
        )
    )

    application.add_handler(
        CallbackQueryHandler(
            admin_stats,
            pattern=r"^admin_stats$",
        )
    )

    # =====================================================
    # مشاركة ونشر
    # =====================================================

    application.add_handler(
        CallbackQueryHandler(
            share_quiz,
            pattern=r"^share_\d+$",
        )
    )

    application.add_handler(
        CallbackQueryHandler(
            publish_quiz,
            pattern=r"^publish_\d+$",
        )
    )

    application.add_handler(
        CallbackQueryHandler(
            send_to_group,
            pattern=r"^sg_-?\d+_\d+$",
        )
    )

    application.add_handler(
        CallbackQueryHandler(
            send_to_all,
            pattern=r"^sa_\d+$",
        )
    )

    # =====================================================
    # الاختبار
    # =====================================================

    application.add_handler(
        CallbackQueryHandler(
            answer_quiz,
            pattern=r"^ans_\d+_\d+_\d+$",
        )
    )

    application.add_handler(
        CallbackQueryHandler(
            cancel_active_quiz,
            pattern=r"^quiz_cancel$",
        )
    )

    # =====================================================
    # الأخطاء
    # =====================================================

    application.add_error_handler(
        error_handler
    )

    return application

    # =========================================================

    # تشغيل البوت

    # =========================================================

def main():

    application = build_application()

    logger.info(
        "Quiz bot is starting..."
    )

    application.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True,
    )

if __name__ == "__main__":
    main()
