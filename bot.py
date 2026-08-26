from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler, CallbackQueryHandler
from telegram.constants import ChatType
import json
import os
from datetime import datetime

TOKEN = "8733506822:AAH9CA5_S7M0frI5hJlzNcKPsPudDyHZNSM"
ADMIN_IDS = ["7021041990", "8810965759", "7020921829"]

QUIZZES_FILE = "quizzes.json"
USERS_FILE = "users.json"
GROUPS_FILE = "groups.json"
RESULTS_FILE = "results.json"

STATE_TITLE, STATE_DESCRIPTION, STATE_DURATION, STATE_Q_TEXT, STATE_Q_OPTIONS, STATE_Q_CORRECT, STATE_Q_MORE = range(7)

def load_json(file):
    if os.path.exists(file):
        with open(file, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_json(file, data):
    with open(file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_quizzes():
    return load_json(QUIZZES_FILE)

def save_quizzes(data):
    save_json(QUIZZES_FILE, data)

def load_users():
    return load_json(USERS_FILE)

def save_users(data):
    save_json(USERS_FILE, data)

def load_groups():
    return load_json(GROUPS_FILE)

def save_groups(data):
    save_json(GROUPS_FILE, data)

def load_results():
    return load_json(RESULTS_FILE)

def save_results(data):
    save_json(RESULTS_FILE, data)

def is_admin(user_id):
    return str(user_id) in ADMIN_IDS

def track_user(user):
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

def track_group(chat):
    if chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]:
        groups = load_groups()
        gid = str(chat.id)
        if gid not in groups:
            groups[gid] = {"title": chat.title or "بدون"}
            save_groups(groups)

def admin_keyboard():
    kb = [
        [InlineKeyboardButton("📝 إنشاء اختبار", callback_data="admin_new")],
        [InlineKeyboardButton("📊 نتائج الاختبارات", callback_data="admin_results")],
        [InlineKeyboardButton("🌐 المجموعات", callback_data="admin_groups")],
        [InlineKeyboardButton("👥 المستخدمون", callback_data="admin_users")],
    ]
    return InlineKeyboardMarkup(kb)

async def start(update, context):
    track_user(update.effective_user)
    if update.effective_chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]:
        track_group(update.effective_chat)
        await update.message.reply_text("👋 تم تسجيل المجموعة. لبدء اختبار استخدم الزر المخصص أو اكتب /start في الخاص.")
        return
    if is_admin(update.effective_user.id):
        await update.message.reply_text("🔐 لوحة التحكم:", reply_markup=admin_keyboard())
    else:
        await update.message.reply_text("🎯 أهلاً! يمكنك بدء الاختبار من خلال زر المشاركة الذي يصلك من المسؤول.")

async def help_cmd(update, context):
    await update.message.reply_text("/start - فتح القائمة\n/newquiz - إنشاء اختبار (للمسؤولين فقط)")

async def admin_new_start(update, context):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return ConversationHandler.END
    context.user_data["quiz_build"] = {"title": "", "description": "", "duration_per_question": 60, "questions": []}
    await query.message.reply_text("✍️ أرسل عنوان الاختبار:")
    return STATE_TITLE

async def handle_title(update, context):
    if not is_admin(update.effective_user.id):
        return ConversationHandler.END
    context.user_data["quiz_build"]["title"] = update.message.text.strip()
    await update.message.reply_text("📝 أرسل وصف الاختبار (أو اكتب /skip للتخطي):")
    return STATE_DESCRIPTION

async def skip_description(update, context):
    context.user_data["quiz_build"]["description"] = ""
    await update.message.reply_text("⏱️ أرسل مدة كل سؤال بالثواني (مثال: 30):")
    return STATE_DURATION

async def handle_description(update, context):
    context.user_data["quiz_build"]["description"] = update.message.text.strip()
    await update.message.reply_text("⏱️ أرسل مدة كل سؤال بالثواني (مثال: 30):")
    return STATE_DURATION

async def handle_duration(update, context):
    txt = update.message.text.strip()
    try:
        dur = int(txt)
        if dur <= 0:
            raise ValueError
    except:
        await update.message.reply_text("⚠️ أدخل رقمًا صحيحًا موجبًا.")
        return STATE_DURATION
    context.user_data["quiz_build"]["duration_per_question"] = dur
    await update.message.reply_text("✍️ أرسل نص السؤال الأول:")
    return STATE_Q_TEXT

async def handle_q_text(update, context):
    context.user_data["current_q"] = {"text": update.message.text.strip(), "options": [], "correct": None}
    await update.message.reply_text("🔢 أرسل الخيارات (كل خيار في سطر، من 2 إلى 10):")
    return STATE_Q_OPTIONS

async def handle_q_options(update, context):
    opts = [line.strip() for line in update.message.text.splitlines() if line.strip()]
    if len(opts) < 2 or len(opts) > 10:
        await update.message.reply_text("⚠️ يجب أن يكون عدد الخيارات بين 2 و10.")
        return STATE_Q_OPTIONS
    context.user_data["current_q"]["options"] = opts
    kb = [[InlineKeyboardButton(f"{i+1}. {opt}", callback_data=f"corr_{i}")] for i, opt in enumerate(opts)]
    kb.append([InlineKeyboardButton("بدون إجابة صحيحة", callback_data="corr_none")])
    await update.message.reply_text("✅ اختر الإجابة الصحيحة:", reply_markup=InlineKeyboardMarkup(kb))
    return STATE_Q_CORRECT

async def handle_q_correct(update, context):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return ConversationHandler.END
    data = query.data
    if data == "corr_none":
        correct = None
    else:
        correct = int(data.replace("corr_", ""))
    q = context.user_data["current_q"]
    q["correct"] = correct
    context.user_data["quiz_build"]["questions"].append(q)
    context.user_data.pop("current_q", None)
    kb = [
        [InlineKeyboardButton("➕ إضافة سؤال آخر", callback_data="add_more")],
        [InlineKeyboardButton("✅ إنهاء وحفظ الاختبار", callback_data="finish_quiz")],
    ]
    await query.message.reply_text("تمت إضافة السؤال. ماذا تريد أن تفعل؟", reply_markup=InlineKeyboardMarkup(kb))
    return STATE_Q_MORE

async def handle_q_more(update, context):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return ConversationHandler.END
    if query.data == "add_more":
        await query.message.reply_text("✍️ أرسل نص السؤال التالي:")
        return STATE_Q_TEXT
    elif query.data == "finish_quiz":
        quiz = context.user_data["quiz_build"]
        quiz_id = datetime.now().strftime("%Y%m%d%H%M%S")
        quizzes = load_quizzes()
        quizzes[quiz_id] = quiz
        save_quizzes(quizzes)
        context.user_data.pop("quiz_build", None)
        preview = f"📋 **{quiz['title']}**\n📝 {quiz['description']}\n⏱️ مدة السؤال: {quiz['duration_per_question']} ثانية\nعدد الأسئلة: {len(quiz['questions'])}\n\n"
        kb = [
            [InlineKeyboardButton("📤 مشاركة الاختبار", callback_data=f"share_{quiz_id}")],
            [InlineKeyboardButton("📢 نشر للمجموعات", callback_data=f"publish_{quiz_id}")],
            [InlineKeyboardButton("↩️ رجوع للوحة", callback_data="back_admin")],
        ]
        await query.message.reply_text(preview + "استخدم زر المشاركة لنشر الاختبار.", reply_markup=InlineKeyboardMarkup(kb))
        return ConversationHandler.END

async def share_quiz_callback(update, context):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return
    quiz_id = query.data.replace("share_", "")
    quiz = load_quizzes().get(quiz_id)
    if not quiz:
        await query.message.reply_text("الاختبار غير موجود.")
        return
    kb = [[InlineKeyboardButton("🚀 بدء الاختبار", callback_data=f"startquiz_{quiz_id}")]]
    share_text = f"📣 **{quiz['title']}**\n\nاضغط الزر لبدء الاختبار فورًا!"
    await query.message.reply_text(share_text, reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')

async def publish_quiz_callback(update, context):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return
    quiz_id = query.data.replace("publish_", "")
    quiz = load_quizzes().get(quiz_id)
    if not quiz:
        await query.message.reply_text("الاختبار غير موجود.")
        return
    groups = load_groups()
    if not groups:
        await query.message.reply_text("لا توجد مجموعات مسجلة.")
        return
    kb = [[InlineKeyboardButton(g["title"], callback_data=f"sendtogroup_{gid}_{quiz_id}")] for gid, g in groups.items()]
    kb.append([InlineKeyboardButton("↩️ رجوع", callback_data=f"share_{quiz_id}")])
    await query.message.reply_text("اختر المجموعة التي تريد نشر الاختبار فيها:", reply_markup=InlineKeyboardMarkup(kb))

async def send_to_group_callback(update, context):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return
    data = query.data
    parts = data.split("_")
    if len(parts) < 3:
        await query.message.reply_text("معرف غير صالح.")
        return
    gid = parts[1]
    quiz_id = parts[2]
    quiz = load_quizzes().get(quiz_id)
    if not quiz:
        await query.message.reply_text("الاختبار غير موجود.")
        return
    try:
        gid_int = int(gid)
    except:
        await query.message.reply_text("معرف المجموعة غير صالح.")
        return
    kb = [[InlineKeyboardButton("🚀 بدء الاختبار", callback_data=f"startquiz_{quiz_id}")]]
    share_text = f"📣 **{quiz['title']}**\n\nاضغط الزر لبدء الاختبار فورًا!"
    try:
        await context.bot.send_message(chat_id=gid_int, text=share_text, reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')
        await query.message.reply_text("✅ تم نشر الاختبار في المجموعة.")
    except Exception as e:
        await query.message.reply_text(f"❌ فشل النشر: {e}")

async def start_quiz_callback(update, context):
    query = update.callback_query
    await query.answer()
    quiz_id = query.data.replace("startquiz_", "")
    quiz = load_quizzes().get(quiz_id)
    if not quiz:
        await query.message.reply_text("الاختبار غير متوفر.")
        return
    user = query.from_user
    track_user(user)
    session = {
        "quiz_id": quiz_id,
        "current_q": 0,
        "answers": [],
        "start_time": datetime.now().isoformat()
    }
    context.user_data["quiz_session"] = session
    await show_question(query.message.chat_id, context, session, quiz)

async def show_question(chat_id, context, session, quiz):
    idx = session["current_q"]
    if idx >= len(quiz["questions"]):
        await finish_quiz(chat_id, context)
        return
    q = quiz["questions"][idx]
    kb = [[InlineKeyboardButton(opt, callback_data=f"answer_{idx}_{i}")] for i, opt in enumerate(q["options"])]
    # إرسال السؤال مع عداد زمني (سنعرض وقت البدء فقط هنا، لكن سنضيف job_queue لاحقًا)
    sent_msg = await context.bot.send_message(
        chat_id=chat_id,
        text=f"❓ سؤال {idx+1} من {len(quiz['questions'])}\n\n{q['text']}\n\n⏱️ لديك {quiz['duration_per_question']} ثانية",
        reply_markup=InlineKeyboardMarkup(kb)
    )
    # حفظ معرّف الرسالة لاستخدامه في التحديثات
    session["current_message_id"] = sent_msg.message_id
    session["question_start_time"] = datetime.now()
    # جدولة انتهاء الوقت
    context.job_queue.run_once(
        time_out_callback,
        quiz["duration_per_question"],
        data={"chat_id": chat_id, "session": session, "quiz": quiz, "context": context}
    )

async def time_out_callback(context):
    job = context.job
    data = job.data
    session = data["session"]
    quiz = data["quiz"]
    chat_id = data["chat_id"]
    ctx = data["context"]
    # التحقق من أن السؤال لم يُجب عليه بعد
    if session["current_q"] < len(quiz["questions"]) and session.get("current_message_id"):
        # إرسال رسالة انتهاء الوقت
        await ctx.bot.send_message(chat_id=chat_id, text="⏰ انتهى الوقت!")
        # اعتبار عدم الإجابة كإجابة خاطئة
        q_index = session["current_q"]
        session["answers"].append({
            "question_index": q_index,
            "selected": None,
            "is_correct": False
        })
        session["current_q"] += 1
        if session["current_q"] >= len(quiz["questions"]):
            await finish_quiz(chat_id, ctx)
        else:
            await show_question(chat_id, ctx, session, quiz)

async def answer_callback(update, context):
    query = update.callback_query
    await query.answer()
    data = query.data
    if not data.startswith("answer_"):
        return
    parts = data.split("_")
    q_index = int(parts[1])
    option_index = int(parts[2])
    session = context.user_data.get("quiz_session")
    if not session:
        await query.message.reply_text("لا توجد جلسة اختبار نشطة.")
        return
    quiz = load_quizzes().get(session["quiz_id"])
    if not quiz:
        await query.message.reply_text("الاختبار غير موجود.")
        return
    current_q = quiz["questions"][q_index]
    is_correct = (current_q.get("correct") == option_index)
    session["answers"].append({
        "question_index": q_index,
        "selected": option_index,
        "is_correct": is_correct
    })
    session["current_q"] += 1
    # حذف المهمة المجدولة لتجنب انتهاء الوقت بعد الإجابة
    if "current_job" in session:
        session["current_job"].schedule_removal()
    if session["current_q"] >= len(quiz["questions"]):
        await finish_quiz(query.message.chat_id, context)
    else:
        await show_question(query.message.chat_id, context, session, quiz)

async def finish_quiz(chat_id, context):
    session = context.user_data.pop("quiz_session", None)
    if not session:
        return
    quiz = load_quizzes().get(session["quiz_id"])
    if not quiz:
        return
    correct_count = sum(1 for a in session["answers"] if a["is_correct"])
    total = len(quiz["questions"])
    result_text = f"📊 انتهى الاختبار!\n\n✅ الإجابات الصحيحة: {correct_count} من {total}\n"
    # حفظ النتيجة
    results = load_results()
    qid = session["quiz_id"]
    if qid not in results:
        results[qid] = []
    user = context.user_data.get("user")
    if not user:
        user = None
    results[qid].append({
        "user_id": user.id if user else "غير معروف",
        "first_name": user.first_name if user else "",
        "username": user.username if user else "",
        "correct": correct_count,
        "total": total,
        "finished_at": datetime.now().isoformat()
    })
    save_results(results)
    await context.bot.send_message(chat_id, result_text)

async def admin_results_callback(update, context):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return
    results = load_results()
    if not results:
        await query.message.reply_text("لا توجد نتائج بعد.")
        return
    kb = [[InlineKeyboardButton(f"اختبار {qid}", callback_data=f"showres_{qid}")] for qid in results.keys()]
    await query.message.reply_text("اختر الاختبار لعرض نتائجه:", reply_markup=InlineKeyboardMarkup(kb))

async def show_results_handler(update, context):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return
    qid = query.data.replace("showres_", "")
    results = load_results().get(qid, [])
    if not results:
        await query.message.reply_text("لا نتائج لهذا الاختبار.")
        return
    text = f"📊 نتائج الاختبار {qid}:\n\n"
    for r in results:
        username = f"@{r['username']}" if r.get('username') else "بدون"
        text += f"• {r['first_name']} ({username}) - صحيح: {r['correct']}/{r['total']}\n"
    await query.message.reply_text(text)

async def admin_groups_callback(update, context):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return
    groups = load_groups()
    if not groups:
        await query.message.reply_text("لا توجد مجموعات مسجلة.")
    else:
        text = "🌐 المجموعات:\n\n"
        for gid, g in groups.items():
            text += f"• {g['title']} - ID: {gid}\n"
        await query.message.reply_text(text)

async def admin_users_callback(update, context):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return
    users = load_users()
    if not users:
        await query.message.reply_text("لا يوجد مستخدمون.")
    else:
        text = "👥 المستخدمون:\n\n"
        for uid, u in users.items():
            uname = f"@{u.get('username')}" if u.get('username') else "بدون"
            text += f"• {u.get('first_name','')} ({uname}) - ID: {uid}\n"
        await query.message.reply_text(text)

async def back_admin_callback(update, context):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return
    await query.message.edit_text("🔐 لوحة التحكم:", reply_markup=admin_keyboard())

def main():
    app = Application.builder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("newquiz", admin_new_start),
            CallbackQueryHandler(admin_new_start, pattern="^admin_new$")
        ],
        states={
            STATE_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_title)],
            STATE_DESCRIPTION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_description),
                CommandHandler("skip", skip_description)
            ],
            STATE_DURATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_duration)],
            STATE_Q_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_q_text)],
            STATE_Q_OPTIONS: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_q_options)],
            STATE_Q_CORRECT: [CallbackQueryHandler(handle_q_correct, pattern="^(corr_|corr_none)")],
            STATE_Q_MORE: [CallbackQueryHandler(handle_q_more, pattern="^(add_more|finish_quiz)")],
        },
        fallbacks=[CommandHandler("cancel", lambda u,c: ConversationHandler.END)]
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(conv_handler)

    # معالجات الأزرار العامة
    app.add_handler(CallbackQueryHandler(share_quiz_callback, pattern="^share_"))
    app.add_handler(CallbackQueryHandler(publish_quiz_callback, pattern="^publish_"))
    app.add_handler(CallbackQueryHandler(send_to_group_callback, pattern="^sendtogroup_"))
    app.add_handler(CallbackQueryHandler(start_quiz_callback, pattern="^startquiz_"))
    app.add_handler(CallbackQueryHandler(answer_callback, pattern="^answer_"))
    app.add_handler(CallbackQueryHandler(admin_results_callback, pattern="^admin_results$"))
    app.add_handler(CallbackQueryHandler(show_results_handler, pattern="^showres_"))
    app.add_handler(CallbackQueryHandler(admin_groups_callback, pattern="^admin_groups$"))
    app.add_handler(CallbackQueryHandler(admin_users_callback, pattern="^admin_users$"))
    app.add_handler(CallbackQueryHandler(back_admin_callback, pattern="^back_admin$"))

    print("البوت يعمل الآن...")
    app.run_polling()

if __name__ == "__main__":
    main()
