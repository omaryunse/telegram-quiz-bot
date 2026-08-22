from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Poll
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler, CallbackQueryHandler
import json
import os
from datetime import datetime, timedelta

TOKEN = "8845301824:AAE02vGKIeP4pLNDD_aww1gwkMPf0lY1mQs"

# حالات المحادثة
QUESTION, DESCRIPTION, OPTIONS, CORRECT_ANSWER, PREVIEW = range(5)

# تخزين الاختبارات
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
        [InlineKeyboardButton("📋 الاختبارات المتاحة", callback_data="list_quizzes")],
        [InlineKeyboardButton("ℹ️ مساعدة", callback_data="help")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🎯 **مرحباً بك في بوت الاختبارات!**\n\n"
        "يمكنك:\n"
        "• إنشاء اختبارات تفاعلية\n"
        "• تحديد الإجابات الصحيحة\n"
        "• ضبط مدة الاختبار\n"
        "• مشاركة الاختبار مع الآخرين",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "new_quiz":
        await query.message.reply_text("✍️ أرسل سؤال الاختبار:")
        return QUESTION
    elif query.data == "list_quizzes":
        quizzes = load_quizzes()
        if not quizzes:
            await query.message.reply_text("لا توجد اختبارات بعد!")
            return ConversationHandler.END
        else:
            for quiz_id, quiz in quizzes.items():
                keyboard = [
                    [InlineKeyboardButton("🚀 بدء الاختبار", callback_data=f"start_quiz_{quiz_id}")],
                    [InlineKeyboardButton("📤 مشاركة", callback_data=f"share_quiz_{quiz_id}")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await query.message.reply_text(
                    f"❓ {quiz['question']}\n"
                    f"👥 المشاركون: {quiz.get('participants', 0)}",
                    reply_markup=reply_markup
                )
    elif query.data == "help":
        await query.message.reply_text(
            "📖 **طريقة الاستخدام:**\n\n"
            "1. اضغط إنشاء اختبار جديد\n"
            "2. أرسل السؤال\n"
            "3. أضف الوصف (اختياري)\n"
            "4. أرسل الخيارات\n"
            "5. حدد الإجابة الصحيحة\n"
            "6. اضبط المدة\n"
            "7. انشر الاختبار!"
        )
    elif query.data.startswith("start_quiz_"):
        quiz_id = query.data.replace("start_quiz_", "")
        await show_quiz_settings(query, quiz_id)
    elif query.data.startswith("share_quiz_"):
        quiz_id = query.data.replace("share_quiz_", "")
        await share_quiz(query, quiz_id)
    elif query.data.startswith("duration_"):
        quiz_id = query.data.replace("duration_", "")
        duration = int(query.data.split("_")[-1])
        await start_quiz_poll(query, quiz_id, duration)
    
    return ConversationHandler.END

async def show_quiz_settings(query, quiz_id):
    quizzes = load_quizzes()
    quiz = quizzes.get(quiz_id)
    if not quiz:
        await query.message.reply_text("الاختبار غير موجود!")
        return
    
    keyboard = [
        [InlineKeyboardButton("⏱️ 30 ثانية", callback_data=f"duration_{quiz_id}_30")],
        [InlineKeyboardButton("⏱️ دقيقة", callback_data=f"duration_{quiz_id}_60")],
        [InlineKeyboardButton("⏱️ دقيقتان", callback_data=f"duration_{quiz_id}_120")],
        [InlineKeyboardButton("⏱️ 5 دقائق", callback_data=f"duration_{quiz_id}_300")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.message.reply_text(
        f"⏱️ **اختر مدة الاختبار:**\n\n"
        f"❓ {quiz['question']}",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def share_quiz(query, quiz_id):
    quizzes = load_quizzes()
    quiz = quizzes.get(quiz_id)
    if not quiz:
        await query.message.reply_text("الاختبار غير موجود!")
        return
    
    share_text = (
        f"🎯 **اختبار جديد!**\n\n"
        f"❓ {quiz['question']}\n"
        f"📝 {quiz.get('description', '')}\n\n"
        f"شارك هذا الاختبار مع أصدقائك!"
    )
    
    keyboard = [
        [InlineKeyboardButton("🚀 بدء الاختبار", callback_data=f"start_quiz_{quiz_id}")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.message.reply_text(share_text, reply_markup=reply_markup, parse_mode='Markdown')

async def start_quiz_poll(query, quiz_id, duration):
    quizzes = load_quizzes()
    quiz = quizzes.get(quiz_id)
    if not quiz:
        await query.message.reply_text("الاختبار غير موجود!")
        return
    
    # إرسال الاستفتاء
    poll_message = await query.message.reply_poll(
        question=quiz['question'],
        options=quiz['options'],
        is_anonymous=True,
        type=Poll.QUIZ,
        correct_option_id=quiz.get('correct_answer', 0),
        explanation=quiz.get('description', ''),
        open_period=duration
    )
    
    quiz['participants'] = quiz.get('participants', 0) + 1
    save_quizzes(quizzes)
    
    await query.message.reply_text(
        f"✅ تم بدء الاختبار!\n"
        f"⏱️ المدة: {duration} ثانية\n"
        f"📊 سيتم إغلاق الاختبار تلقائياً"
    )

async def get_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['question'] = update.message.text
    await update.message.reply_text(
        "📝 أرسل وصف الاختبار\n"
        "أو أرسل /skip للتخطي"
    )
    return DESCRIPTION

async def skip_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['description'] = ""
    await update.message.reply_text(
        "🔢 أرسل الخيارات (كل خيار في سطر):\n\n"
        "مثال:\n"
        "باريس\n"
        "لندن\n"
        "مدريد\n"
        "روما"
    )
    return OPTIONS

async def get_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['description'] = update.message.text
    await update.message.reply_text(
        "🔢 أرسل الخيارات (كل خيار في سطر):\n\n"
        "مثال:\n"
        "باريس\n"
        "لندن\n"
        "مدريد\n"
        "روما"
    )
    return OPTIONS

async def get_options(update: Update, context: ContextTypes.DEFAULT_TYPE):
    options = update.message.text.split('\n')
    options = [opt.strip() for opt in options if opt.strip()]
    
    if len(options) < 2:
        await update.message.reply_text("⚠️ يجب إرسال خيارين على الأقل!")
        return OPTIONS
    
    context.user_data['options'] = options
    
    # عرض الخيارات لاختيار الإجابة الصحيحة
    keyboard = []
    for i, opt in enumerate(options):
        keyboard.append([InlineKeyboardButton(f"{opt}", callback_data=f"correct_{i}")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "✅ اختر الإجابة الصحيحة:",
        reply_markup=reply_markup
    )
    return CORRECT_ANSWER

async def correct_answer_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    correct_index = int(query.data.replace("correct_", ""))
    context.user_data['correct_answer'] = correct_index
    
    # إنشاء الاختبار وحفظه
    quiz_id = datetime.now().strftime("%Y%m%d%H%M%S")
    quizzes = load_quizzes()
    quizzes[quiz_id] = {
        'question': context.user_data['question'],
        'description': context.user_data.get('description', ''),
        'options': context.user_data['options'],
        'correct_answer': correct_index,
        'created_by': query.from_user.id,
        'participants': 0
    }
    save_quizzes(quizzes)
    
    # عرض المعاينة مع الأزرار
    keyboard = [
        [InlineKeyboardButton("📤 مشاركة", callback_data=f"share_quiz_{quiz_id}")],
        [InlineKeyboardButton("🚀 بدء الاختبار", callback_data=f"start_quiz_{quiz_id}")],
        [InlineKeyboardButton("➕ سؤال آخر", callback_data="new_quiz")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.message.reply_text(
        f"✅ **تم إنشاء الاختبار بنجاح!**\n\n"
        f"❓ السؤال: {context.user_data['question']}\n"
        f"📝 الوصف: {context.user_data.get('description', 'لا يوجد')}\n"
        f"📊 عدد الخيارات: {len(context.user_data['options'])}\n"
        f"✔️ الإجابة الصحيحة: {context.user_data['options'][correct_index]}\n\n"
        f"ماذا تريد أن تفعل؟",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("تم الإلغاء")
    return ConversationHandler.END

def main():
    app = Application.builder().token(TOKEN).build()
    
    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(button_handler, pattern="^(new_quiz|list_quizzes|help|start_quiz_|share_quiz_|duration_)")],
        states={
            QUESTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_question)],
            DESCRIPTION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_description),
                CommandHandler('skip', skip_description)
            ],
            OPTIONS: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_options)],
            CORRECT_ANSWER: [CallbackQueryHandler(correct_answer_handler, pattern="^correct_")],
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )
    
    app.add_handler(CommandHandler('start', start))
    app.add_handler(conv_handler)
    app.add_handler(CallbackQueryHandler(button_handler))
    
    print("البوت يعمل الآن...")
    app.run_polling()

if __name__ == "__main__":
    main()