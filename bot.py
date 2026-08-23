from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Poll
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler, CallbackQueryHandler
import json, os
from datetime import datetime, timedelta

TOKEN = "ضع_التوك8845301824:AAE02vGKIeP4pLNDD_aww1gwkMPf0lY1mQsن_هنا"

# حالات المحادثة
TITLE, DESCRIPTION, OPTIONS, CORRECT_OPTION, DURATION, PREVIEW = range(6)

# ملف حفظ الاختبارات
QUIZZES_FILE = "quizzes.json"

def load_quizzes():
    if os.path.exists(QUIZZES_FILE):
        with open(QUIZZES_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_quizzes(quizzes):
    with open(QUIZZES_FILE, 'w', encoding='utf-8') as f:
        json.dump(quizzes, f, ensure_ascii=False, indent=2)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📝 إنشاء اختبار جديد", callback_data="new_quiz")],
        [InlineKeyboardButton("📋 اختباراتي السابقة", callback_data="list_quizzes")],
        [InlineKeyboardButton("ℹ️ مساعدة", callback_data="help")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "🎯 **مرحباً بك في بوت الاختبارات التفاعلية!**\n\n"
        "أنشئ اختبارات سريعة، شاركها مع الآخرين، وتابع النتائج.\n\n"
        "اختر من الأزرار التالية:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "new_quiz":
        await query.message.reply_text("✍️ أرسل عنوان الاختبار (السؤال):")
        return TITLE
    elif data == "list_quizzes":
        quizzes = load_quizzes()
        if not quizzes:
            await query.message.reply_text("لا توجد اختبارات سابقة.")
            return ConversationHandler.END
        else:
            text = "📋 **اختباراتك السابقة:**\n\n"
            for qid, quiz in quizzes.items():
                text += f"• {quiz['title']} (المشاركون: {quiz.get('participants', 0)})\n"
            keyboard = [[InlineKeyboardButton("🔄 تحديث", callback_data="list_quizzes")]]
            await query.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    elif data == "help":
        await query.message.reply_text(
            "📖 **كيفية الاستخدام:**\n"
            "1. اضغط على إنشاء اختبار جديد\n"
            "2. أرسل عنوان الاختبار\n"
            "3. أرسل وصفاً (اختياري)\n"
            "4. أرسل الخيارات (كل خيار في سطر)\n"
            "5. حدد الإجابة الصحيحة (اختياري)\n"
            "6. اختر مدة الاختبار\n"
            "7. اضغط بدء الاختبار وسيتم إرسال الاستفتاء\n\n"
            "يمكنك أيضاً مشاركة الاختبار مع الآخرين."
        )
    return ConversationHandler.END

# الدالة التي تعالج عنوان الاختبار
async def get_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['title'] = update.message.text
    keyboard = [
        [InlineKeyboardButton("⏭️ تخطي الوصف", callback_data="skip_description")]
    ]
    await update.message.reply_text(
        "📝 أرسل وصفاً للاختبار (اختياري):\n\n"
        "أو اضغط على الزر لتخطي هذه الخطوة.",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return DESCRIPTION

# معالجة تخطي الوصف
async def skip_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['description'] = ""
    await query.message.reply_text(
        "🔢 أرسل الخيارات الآن.\n"
        "كل خيار في سطر منفصل.\n\n"
        "مثال:\n"
        "باريس\n"
        "لندن\n"
        "مدريد"
    )
    return OPTIONS

# معالجة الوصف
async def get_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['description'] = update.message.text
    await update.message.reply_text(
        "🔢 أرسل الخيارات الآن.\n"
        "كل خيار في سطر منفصل.\n\n"
        "مثال:\n"
        "باريس\n"
        "لندن\n"
        "مدريد"
    )
    return OPTIONS

# معالجة الخيارات
async def get_options(update: Update, context: ContextTypes.DEFAULT_TYPE):
    options = [line.strip() for line in update.message.text.split('\n') if line.strip()]
    if len(options) < 2:
        await update.message.reply_text("⚠️ تحتاج إلى خيارين على الأقل! أعد الإرسال.")
        return OPTIONS
    if len(options) > 10:
        await update.message.reply_text("⚠️ الحد الأقصى 10 خيارات! أعد الإرسال.")
        return OPTIONS

    context.user_data['options'] = options

    # عرض خيارات الإجابة الصحيحة مع زر تخطي
    keyboard = []
    for i, opt in enumerate(options):
        keyboard.append([InlineKeyboardButton(f"✔️ {opt}", callback_data=f"correct_{i}")])
    keyboard.append([InlineKeyboardButton("⏭️ بدون إجابة صحيحة", callback_data="no_correct")])

    await update.message.reply_text(
        "✅ هل يوجد إجابة صحيحة؟ اختر من الأزرار:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return CORRECT_OPTION

# معالجة اختيار الإجابة الصحيحة
async def correct_answer_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "no_correct":
        context.user_data['correct_option'] = None
    else:
        idx = int(data.replace("correct_", ""))
        context.user_data['correct_option'] = idx

    # الانتقال لاختيار المدة
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

# معالجة اختيار المدة
async def duration_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    duration = int(query.data.replace("duration_", ""))
    context.user_data['duration'] = duration

    # إنشاء معرف فريد للاختبار
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

    # معاينة الاختبار
    preview_text = f"📋 **معاينة الاختبار:**\n\n"
    preview_text += f"❓ العنوان: {context.user_data['title']}\n"
    if context.user_data.get('description'):
        preview_text += f"📝 الوصف: {context.user_data['description']}\n"
    preview_text += f"⏱️ المدة: {duration} ثانية\n"
    preview_text += f"🔢 عدد الخيارات: {len(context.user_data['options'])}\n"
    if context.user_data.get('correct_option') is not None:
        preview_text += f"✔️ الإجابة الصحيحة: {context.user_data['options'][context.user_data['correct_option']]}\n"

    keyboard = [
        [InlineKeyboardButton("🚀 بدء الاختبار الآن", callback_data="start_quiz_now")],
        [InlineKeyboardButton("📤 مشاركة الاختبار", callback_data="share_quiz")],
        [InlineKeyboardButton("➕ إنشاء سؤال آخر", callback_data="new_quiz")]
    ]
    await query.message.reply_text(
        preview_text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )
    return PREVIEW

# معالجة أزرار المعاينة
async def preview_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "start_quiz_now":
        quiz_id = context.user_data.get('quiz_id')
        if not quiz_id:
            await query.message.reply_text("تعذر العثور على الاختبار.")
            return ConversationHandler.END
        await send_poll(query.message.chat_id, context, quiz_id)
        await query.message.reply_text("✅ تم بدء الاختبار! سيغلق تلقائياً بعد انتهاء الوقت.")
        return ConversationHandler.END
    elif data == "share_quiz":
        quiz_id = context.user_data.get('quiz_id')
        if not quiz_id:
            await query.message.reply_text("تعذر العثور على الاختبار.")
            return ConversationHandler.END
        quizzes = load_quizzes()
        quiz = quizzes.get(quiz_id)
        if quiz:
            share_text = f"🎯 **اختبار جديد!**\n\n❓ {quiz['title']}\n"
            if quiz['description']:
                share_text += f"📝 {quiz['description']}\n"
            share_text += f"⏱️ المدة: {quiz['duration']} ثانية\n"
            share_text += "شارك هذا الاختبار مع أصدقائك!"
            keyboard = [[InlineKeyboardButton("🚀 بدء الاختبار", callback_data=f"start_shared_{quiz_id}")]]
            await query.message.reply_text(share_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        return ConversationHandler.END
    elif data == "new_quiz":
        await query.message.reply_text("✍️ أرسل عنوان الاختبار الجديد:")
        return TITLE
    return ConversationHandler.END

# إرسال الاستفتاء الفعلي
async def send_poll(chat_id, context, quiz_id):
    quizzes = load_quizzes()
    quiz = quizzes.get(quiz_id)
    if not quiz:
        return

    options = quiz['options']
    correct_option = quiz.get('correct_option')
    duration = quiz.get('duration', 60)

    if correct_option is not None:
        # وضع Quiz
        await context.bot.send_poll(
            chat_id=chat_id,
            question=quiz['title'],
            options=options,
            type=Poll.QUIZ,
            correct_option_id=correct_option,
            explanation=quiz.get('description', ''),
            is_anonymous=True,
            open_period=duration
        )
    else:
        # استفتاء عادي
        await context.bot.send_poll(
            chat_id=chat_id,
            question=quiz['title'],
            options=options,
            is_anonymous=True,
            open_period=duration
        )
    # تحديث عدد المشاركين
    quiz['participants'] = quiz.get('participants', 0) + 1
    save_quizzes(quizzes)

# معالجة بدء اختبار مشترك
async def shared_quiz_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    quiz_id = query.data.replace("start_shared_", "")
    await send_poll(query.message.chat_id, context, quiz_id)
    await query.message.reply_text("✅ تم بدء الاختبار! سيغلق تلقائياً بعد انتهاء الوقت.")

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("تم إلغاء العملية.")
    return ConversationHandler.END

def main():
    app = Application.builder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(button_handler, pattern="^(new_quiz|list_quizzes|help)$")],
        states={
            TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_title)],
            DESCRIPTION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_description),
                CallbackQueryHandler(skip_description, pattern="^skip_description$")
            ],
            OPTIONS: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_options)],
            CORRECT_OPTION: [CallbackQueryHandler(correct_answer_handler, pattern="^(correct_|no_correct)")],
            DURATION: [CallbackQueryHandler(duration_handler, pattern="^duration_")],
            PREVIEW: [CallbackQueryHandler(preview_handler, pattern="^(start_quiz_now|share_quiz|new_quiz)$")],
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )

    app.add_handler(CommandHandler('start', start))
    app.add_handler(conv_handler)
    app.add_handler(CallbackQueryHandler(shared_quiz_handler, pattern="^start_shared_"))

    print("البوت يعمل الآن...")
    app.run_polling()

if __name__ == "__main__":
    main()