import logging
import json
import os
import asyncio
from http import HTTPStatus
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ChatPermissions
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes, ChatMemberHandler
from telegram.error import TelegramError

TOKEN = "8651597322:AAEeCm43jzclz_CbAUMMIGpNcgkNn4ZL-uk"
MAIN_GROUP_USERNAME = "sunrte"
ARCHIVE_INVITE_LINK = "https://t.me/g9cPgbMOOFL0zNmNk"
OWNER_ID = 7606399570
DATA_FILE = "bot_data.json"
PORT = int(os.environ.get("PORT", 8080))
RENDER_URL = os.environ.get("RENDER_EXTERNAL_URL", "")

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

data = {}

def load_data():
    global data
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            data = json.load(f)
    else:
        data = {"main_group_id": None, "archive_group_id": None}
        save_data()

def save_data():
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat and update.effective_chat.type != "private":
        return
    user = update.effective_user
    keyboard = [
        [InlineKeyboardButton("📦 الانضمام للأرشيف", url=ARCHIVE_INVITE_LINK)],
        [InlineKeyboardButton("✅ تفعيل الحساب", callback_data="verify")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        f"مرحباً بك {user.first_name} في بوت الجلال 👋\n\n"
        "للتفعيل في القروب الرئيسي:\n"
        "1️⃣ اضغط على زر الانضمام للأرشيف\n"
        "2️⃣ ثم اضغط على زر تفعيل الحساب",
        reply_markup=reply_markup
    )

async def verify_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user_name = query.from_user.first_name
    main_id = data.get("main_group_id")
    archive_id = data.get("archive_group_id")
    logger.info(f"Verify clicked by user {user_id} ({user_name})")
    if not main_id:
        await safe_edit(query, "⚠️ البوت لم يربط بعد بالقروب الرئيسي. أبلغ المشرف."); return
    if not archive_id:
        await safe_edit(query, "⚠️ البوت لم يربط بعد بقروب الأرشيف. أبلغ المشرف."); return
    try:
        member = await context.bot.get_chat_member(chat_id=archive_id, user_id=user_id)
        logger.info(f"User {user_id} archive status: {member.status}")
        if member.status in ("member", "creator", "administrator"):
            permissions = ChatPermissions(
                can_send_messages=True, can_send_audios=True, can_send_documents=True,
                can_send_photos=True, can_send_videos=True, can_send_video_notes=True,
                can_send_voice_notes=True, can_send_polls=True, can_send_other_messages=True,
                can_add_web_page_previews=True, can_change_info=False, can_invite_users=False,
                can_pin_messages=False
            )
            try:
                await context.bot.restrict_chat_member(chat_id=main_id, user_id=user_id, permissions=permissions)
                logger.info(f"User {user_id} unmuted")
            except TelegramError:
                await safe_edit(query, "⚠️ لم يتم العثور عليك في القروب الرئيسي."); return
            await safe_edit(query, f"✅ {user_name} تم تفعيل حسابك بنجاح!")
            try:
                await context.bot.send_message(user_id, "✅ تم تفعيل حسابك! يمكنك الآن الكتابة في القروب.")
            except TelegramError:
                pass
            asyncio.create_task(delayed_delete(query.message, 20))
        else:
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("📦 انضم للارشيف", url=ARCHIVE_INVITE_LINK)],
                [InlineKeyboardButton("✅ تفعيل الحساب", callback_data="verify")]
            ])
            await safe_edit(query, "❌ لم تنضم إلى قروب الأرشيف بعد.\nالرجاء الانضمام أولاً، ثم اضغط على تفعيل الحساب مرة أخرى.", reply_markup=keyboard)
    except TelegramError as e:
        logger.error(f"Verify error for {user_id}: {e}")
        await safe_edit(query, "❌ حدث خطأ في التحقق.")

async def safe_edit(query, text, reply_markup=None):
    try:
        await query.edit_message_text(text=text, reply_markup=reply_markup)
    except TelegramError:
        try:
            await query.message.reply_text(text=text, reply_markup=reply_markup)
        except TelegramError:
            pass

async def delayed_delete(msg, delay):
    await asyncio.sleep(delay)
    try:
        await msg.delete()
    except TelegramError:
        pass

async def handle_new_members(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.new_chat_members: return
    chat = update.effective_chat
    chat_username = chat.username.lower() if chat.username else None
    main_id = data.get("main_group_id")
    if chat_username == MAIN_GROUP_USERNAME.lower() and (not main_id or main_id != chat.id):
        data["main_group_id"] = chat.id; save_data(); main_id = chat.id
        logger.info(f"Main group set: {chat.title} (ID: {chat.id})")
        try:
            await context.bot.send_message(OWNER_ID, f"✅ تم ربط القروب الرئيسي:\n{chat.title} (ID: {chat.id})")
        except TelegramError: pass
    if chat.id != main_id: return
    for member in update.message.new_chat_members:
        if member.id == context.bot.id: continue
        try:
            mute_permissions = ChatPermissions(can_send_messages=False, can_send_audios=False, can_send_documents=False, can_send_photos=False, can_send_videos=False, can_send_video_notes=False, can_send_voice_notes=False, can_send_polls=False, can_send_other_messages=False, can_add_web_page_previews=False, can_change_info=False, can_invite_users=False, can_pin_messages=False)
            await chat.restrict_member(user_id=member.id, permissions=mute_permissions)
            logger.info(f"Muted user {member.id}")
        except TelegramError as e: logger.error(f"Mute failed {member.id}: {e}"); continue
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("📦 الانضمام للأرشيف", url=ARCHIVE_INVITE_LINK)], [InlineKeyboardButton("✅ تفعيل الحساب", callback_data="verify")]])
        try:
            await chat.send_message(f"أهلا بك {member.mention_html()}، أنت مكتوم حالياً.\nاضغط على زر الانضمام للأرشيف أولاً، ثم زر تفعيل الحساب للتحقق وفك الكتم.", reply_markup=keyboard, parse_mode="HTML")
        except TelegramError as e: logger.error(f"Welcome failed {member.id}: {e}")

async def handle_my_chat_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.my_chat_member: return
    chat = update.my_chat_member.chat; old = update.my_chat_member.old_chat_member; new = update.my_chat_member.new_chat_member
    if old.status in ("left", "kicked") and new.status in ("member", "administrator"):
        chat_username = chat.username.lower() if chat.username else None; archive_id = data.get("archive_group_id")
        if chat_username == MAIN_GROUP_USERNAME.lower():
            data["main_group_id"] = chat.id; save_data()
            try: await context.bot.send_message(OWNER_ID, f"✅ تم ربط القروب الرئيسي:\n{chat.title} (ID: {chat.id})")
            except TelegramError: pass
            await context.bot.send_message(chat.id, "✅ بوت الجلال جاهز!")
        elif not archive_id:
            data["archive_group_id"] = chat.id; save_data()
            try: await context.bot.send_message(OWNER_ID, f"✅ تم ربط قروب الأرشيف:\n{chat.title} (ID: {chat.id})")
            except TelegramError: pass
            await context.bot.send_message(chat.id, "✅ بوت الجلال جاهز في قروب الأرشيف!")

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID: return
    m = data.get("main_group_id"); a = data.get("archive_group_id")
    await update.message.reply_text(f"📊 حالة البوت\n\nالقروب الرئيسي: {m if m else '❌ غير محدد'}\nقروب الأرشيف: {a if a else '❌ غير محدد'}\nرابط الأرشيف: {ARCHIVE_INVITE_LINK}")

async def setmain_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID: return
    if not update.message.reply_to_message: await update.message.reply_text("الرجاء الرد على رسالة من القروب الرئيسي"); return
    data["main_group_id"] = update.message.reply_to_message.chat_id; save_data()
    await update.message.reply_text(f"✅ تم تعيين القروب الرئيسي: {data['main_group_id']}")

async def setarchive_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID: return
    if not update.message.reply_to_message: await update.message.reply_text("الرجاء الرد على رسالة من قروب الأرشيف"); return
    data["archive_group_id"] = update.message.reply_to_message.chat_id; save_data()
    await update.message.reply_text(f"✅ تم تعيين قروب الأرشيف: {data['archive_group_id']}")

async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID: return
    data["main_group_id"] = None; data["archive_group_id"] = None; save_data()
    await update.message.reply_text("✅ تم إعادة التعيين.")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Error: {context.error}")

async def webhook_health(request):
    return "Bot is alive!"

def main():
    load_data()
    app = Application.builder().token(TOKEN).updater(None).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("setmain", setmain_command))
    app.add_handler(CommandHandler("setarchive", setarchive_command))
    app.add_handler(CommandHandler("reset", reset_command))
    app.add_handler(CallbackQueryHandler(verify_callback, pattern="^verify$"))
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, handle_new_members))
    app.add_handler(ChatMemberHandler(handle_my_chat_member, ChatMemberHandler.MY_CHAT_MEMBER))
    app.add_error_handler(error_handler)
    if RENDER_URL:
        from telegram.ext import Updater
        webhook_url = f"{RENDER_URL}/webhook"
        app.run_webhook(listen="0.0.0.0", port=PORT, url_path="webhook", webhook_url=webhook_url)
        logger.info(f"Bot running on webhook: {webhook_url}")
    else:
        logger.info("Bot started (polling)...")
        app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)

if __name__ == "__main__":
    main()