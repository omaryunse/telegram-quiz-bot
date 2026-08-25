import os
import json
import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Poll
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters,
    ConversationHandler, CallbackQueryHandler, PollAnswerHandler, ContextTypes
)
from telegram.constants import ChatType

# إعداد السجل
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("8845301824:AAGptI-Na__Tp0ZbFgvQ-HSfHOawDCuhFK4")  # ضع التوكن في متغير بيئة BOT_TOKEN
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

# ... (باقي دوال التحميل/الحفظ كما في الأصل) ...

def is_admin(update):
    user = getattr(update, "effective_user", None)
    if not user and getattr(update, "callback_query", None):
        user = update.callback_query.from_user
    return str(user.id) in ADMIN_IDS if user else False

# تتبع المستخدم والمجموعة كما في الأصل (track_user, track_group) بدون تغيير أساسي

# دوال بناء لوحة التحكم كما في الأصل (build_admin_keyboard)

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

# ... بقية المعالجات كما في الأصل مع التصحيحات التالية ...

async def get_description(update, context):
    context.user_data['description'] = update.message.text
    await update.message.reply_text("🔢 أرسل الخيارات (كل خيار في سطر):")
    return OPTIONS

# في preview_handler: استخدام query.message.chat.id عند بدء الاختبار محلياً
async def preview_handler(update, context):
    query = update.callback_query
    await query.answer()
    data = query.data
    quiz_id = context.user_data.get('quiz_id')
    if data == "start_here":
        if quiz_id:
            await send_poll(query.message.chat.id, context, quiz_id)
            await query.message.reply_text("✅ تم بدء الاختبار!")
        return ConversationHandler.END
    # بقية الفروع كما في الأصل، مع معالجة sendgroup_.* بشكل صحيح

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
    try:
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
        quiz['participants'] = quiz.get('participants', 0) + 1
        save_quizzes(quizzes)
    except Exception as e:
        logger.exception("Failed to send poll: %s", e)
        raise

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
            save_quizzes(quizzes)
            break

async def cancel(update, context):
    await update.message.reply_text("تم الإلغاء.")
    return ConversationHandler.END

def main():
    if not TOKEN:
        logger.error("BOT_TOKEN environment variable not set.")
        return
    app = Application.builder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('newquiz', new_quiz_command), CallbackQueryHandler(button_handler)],
        states={
            TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_title)],
            DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_description), CallbackQueryHandler(skip_description, pattern="^skip_description$")],
            OPTIONS: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_options)],
            CORRECT_OPTION: [CallbackQueryHandler(correct_answer_handler, pattern="^(correct_|no_correct)")],
            DURATION: [CallbackQueryHandler(duration_handler, pattern="^duration_")],
            PREVIEW: [CallbackQueryHandler(preview_handler, pattern=r"^(start_here|share_quiz|new_quiz|back_to_preview|sendgroup_.*)$")],
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )

    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('help', help_command))
    app.add_handler(CommandHandler('admin', admin_command))
    app.add_handler(conv_handler)
    app.add_handler(CallbackQueryHandler(result_callback, pattern="^result_"))
    app.add_handler(CallbackQueryHandler(button_handler))  # عام كاحتياط بعد handlers المتخصصة
    app.add_handler(PollAnswerHandler(poll_answer_handler))

    logger.info("البوت يعمل الآن...")
    app.run_polling()

if __name__ == "__main__":
    main()
