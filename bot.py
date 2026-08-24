from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

TOKEN = "8845301824:AAE02vGKIeP4pLNDD_aww1gwkMPf0lY1mQs"
ADMIN_ID = "7021041990"

def is_admin(user_id):
    return str(user_id) == ADMIN_ID

async def start(update, context):
    user_id = update.effective_user.id
    if is_admin(user_id):
        keyboard = [
            [InlineKeyboardButton("📝 إنشاء اختبار", callback_data="new_quiz")],
            [InlineKeyboardButton("👥 المستخدمون", callback_data="list_users")],
            [InlineKeyboardButton("📊 الإحصائيات", callback_data="stats")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("🔐 **لوحة التحكم:**", reply_markup=reply_markup, parse_mode='Markdown')
    else:
        await update.message.reply_text("مرحباً! أنا بوت الاختبارات.")

async def button_handler(update, context):
    query = update.callback_query
    await query.answer()
    data = query.data
    
    if data == "new_quiz":
        await query.message.reply_text("✍️ أرسل عنوان الاختبار:")
        context.user_data['state'] = 'title'
    elif data == "list_users":
        await query.message.reply_text("قائمة المستخدمين (فارغة حالياً)")
    elif data == "stats":
        await query.message.reply_text("لا توجد إحصائيات بعد")

async def handle_message(update, context):
    state = context.user_data.get('state')
    if state == 'title':
        context.user_data['quiz_title'] = update.message.text
        context.user_data['state'] = 'options'
        await update.message.reply_text("🔢 أرسل الخيارات (كل خيار في سطر):")
    elif state == 'options':
        options = [line.strip() for line in update.message.text.split('\n') if line.strip()]
        context.user_data['quiz_options'] = options
        context.user_data['state'] = None
        await update.message.reply_text(f"✅ تم حفظ الاختبار: {context.user_data['quiz_title']}")

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("البوت جاهز")
    app.run_polling()

if __name__ == "__main__":
    main()
