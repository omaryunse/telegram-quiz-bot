from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Poll
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler, CallbackQueryHandler
import json, os
from datetime import datetime

TOKEN = "8845301824:AAE02vGKIeP4pLNDD_aww1gwkMPf0lY1mQs"
ADMIN_ID = "7021041990"

TITLE = 1
OPTIONS = 2
DURATION = 3

async def start(update, context):
    if str(update.effective_user.id) == ADMIN_ID:
        keyboard = [[InlineKeyboardButton("📝 إنشاء اختبار", callback_data="new_quiz")]]
        await update.message.reply_text("لوحة التحكم:", reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.message.reply_text("مرحباً!")

async def button_handler(update, context):
    query = update.callback_query
    await query.answer()
    if query.data == "new_quiz":
        await query.message.reply_text("✍️ أرسل عنوان الاختبار:")
        return TITLE
    return ConversationHandler.END

async def get_title(update, context):
    context.user_data['title'] = update.message.text
    await update.message.reply_text("🔢 أرسل الخيارات (كل خيار في سطر):")
    return OPTIONS

async def get_options(update, context):
    options = [line.strip() for line in update.message.text.split('\n') if line.strip()]
    context.user_data['options'] = options
    keyboard = [[InlineKeyboardButton("⏱️ 30 ثانية", callback_data="dur_30")], [InlineKeyboardButton("⏱️ دقيقة", callback_data="dur_60")]]
    await update.message.reply_text("⏳ اختر المدة:", reply_markup=InlineKeyboardMarkup(keyboard))
    return DURATION

async def duration_handler(update, context):
    query = update.callback_query
    await query.answer()
    duration = int(query.data.replace("dur_", ""))
    await context.bot.send_poll(
        chat_id=query.message.chat_id,
        question=context.user_data['title'],
        options=context.user_data['options'],
        is_anonymous=True,
        open_period=duration
    )
    await query.message.reply_text("✅ تم بدء الاختبار!")
    return ConversationHandler.END

def main():
    app = Application.builder().token(TOKEN).build()
    conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(button_handler)],
        states={
            TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_title)],
            OPTIONS: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_options)],
            DURATION: [CallbackQueryHandler(duration_handler)],
        },
        fallbacks=[]
    )
    app.add_handler(CommandHandler('start', start))
    app.add_handler(conv)
    print("البوت يعمل")
    app.run_polling()

if __name__ == "__main__":
    main()
