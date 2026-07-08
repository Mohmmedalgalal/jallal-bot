import logging, json, os, asyncio, threading
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ChatPermissions
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes, ChatMemberHandler
from telegram.error import TelegramError
from http.server import HTTPServer, BaseHTTPRequestHandler

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
        with open(DATA_FILE) as f: data = json.load(f)
    else:
        data = {"main_group_id": None, "archive_group_id": None}; save_data()

def save_data():
    with open(DATA_FILE, "w") as f: json.dump(data, f, indent=2)

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.send_header("Content-type", "text/plain"); self.end_headers()
        self.wfile.write(b"Bot is alive!")
    def log_message(self, *args): pass

def run_health():
    HTTPServer(("0.0.0.0", PORT + 1), HealthHandler).serve_forever()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat and update.effective_chat.type != "private": return
    user = update.effective_user
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("\U0001f4e6 الانضمام للأرشيف", url=ARCHIVE_INVITE_LINK)], [InlineKeyboardButton("\u2705 تفعيل الحساب", callback_data="verify")]])
    await update.message.reply_text(f"مرحباً بك {user.first_name} في بوت الجلال \U0001f44b\n\nللتفعيل:\n1\ufe0f\u20e3 اضغط على زر الانضمام للأرشيف\n2\ufe0f\u20e3 ثم اضغط على زر تفعيل الحساب", reply_markup=kb)

async def verify_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    uid = q.from_user.id; name = q.from_user.first_name
    mid = data.get("main_group_id"); aid = data.get("archive_group_id")
    if not mid: await safe_edit(q, "⚠️ البوت لم يربط بعد بالقروب الرئيسي."); return
    if not aid: await safe_edit(q, "⚠️ البوت لم يربط بعد بقروب الأرشيف."); return
    try:
        m = await context.bot.get_chat_member(chat_id=aid, user_id=uid)
        if m.status in ("member","creator","administrator"):
            p = ChatPermissions(can_send_messages=True, can_send_audios=True, can_send_documents=True, can_send_photos=True, can_send_videos=True, can_send_video_notes=True, can_send_voice_notes=True, can_send_polls=True, can_send_other_messages=True, can_add_web_page_previews=True, can_change_info=False, can_invite_users=False, can_pin_messages=False)
            try: await context.bot.restrict_chat_member(chat_id=mid, user_id=uid, permissions=p)
            except TelegramError: await safe_edit(q, "⚠️ لم يتم العثور عليك في القروب الرئيسي."); return
            await safe_edit(q, f"\u2705 {name} تم تفعيل حسابك!")
            try: await context.bot.send_message(uid, "\u2705 تم تفعيل حسابك! يمكنك الآن الكتابة في القروب.")
            except: pass
            asyncio.create_task(delayed_delete(q.message, 20))
        else:
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("\U0001f4e6 انضم للارشيف", url=ARCHIVE_INVITE_LINK)], [InlineKeyboardButton("\u2705 تفعيل الحساب", callback_data="verify")]])
            await safe_edit(q, "❌ لم تنضم إلى قروب الأرشيف بعد.\nالرجاء الانضمام أولاً، ثم اضغط على تفعيل الحساب.", reply_markup=kb)
    except TelegramError as e:
        logger.error(f"Verify error {uid}: {e}"); await safe_edit(q, "❌ حدث خطأ في التحقق.")

async def safe_edit(q, text, reply_markup=None):
    try: await q.edit_message_text(text=text, reply_markup=reply_markup)
    except TelegramError:
        try: await q.message.reply_text(text=text, reply_markup=reply_markup)
        except: pass

async def delayed_delete(msg, delay):
    await asyncio.sleep(delay)
    try: await msg.delete()
    except: pass

async def handle_new_members(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.new_chat_members: return
    chat = update.effective_chat; cu = chat.username.lower() if chat.username else None
    mid = data.get("main_group_id")
    if cu == MAIN_GROUP_USERNAME.lower() and (not mid or mid != chat.id):
        data["main_group_id"] = chat.id; save_data(); mid = chat.id
        try: await context.bot.send_message(OWNER_ID, f"✅ تم ربط القروب الرئيسي:\n{chat.title}")
        except: pass
    if chat.id != mid: return
    for member in update.message.new_chat_members:
        if member.id == context.bot.id: continue
        try:
            mp = ChatPermissions(can_send_messages=False, can_send_audios=False, can_send_documents=False, can_send_photos=False, can_send_videos=False, can_send_video_notes=False, can_send_voice_notes=False, can_send_polls=False, can_send_other_messages=False, can_add_web_page_previews=False, can_change_info=False, can_invite_users=False, can_pin_messages=False)
            await chat.restrict_member(user_id=member.id, permissions=mp)
        except TelegramError as e: logger.error(f"Mute fail {member.id}: {e}"); continue
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("\U0001f4e6 الانضمام للأرشيف", url=ARCHIVE_INVITE_LINK)], [InlineKeyboardButton("\u2705 تفعيل الحساب", callback_data="verify")]])
        try:
            await chat.send_message(f"أهلا بك {member.mention_html()}، أنت مكتوم حالياً.\nاضغط على زر الانضمام للأرشيف ثم تفعيل الحساب.", reply_markup=kb, parse_mode="HTML")
        except TelegramError as e: logger.error(f"Welcome fail {member.id}: {e}")

async def handle_my_chat_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.my_chat_member: return
    c = update.my_chat_member.chat; o = update.my_chat_member.old_chat_member; n = update.my_chat_member.new_chat_member
    if o.status in ("left","kicked") and n.status in ("member","administrator"):
        cu = c.username.lower() if c.username else None; aid = data.get("archive_group_id")
        if cu == MAIN_GROUP_USERNAME.lower():
            data["main_group_id"] = c.id; save_data()
            try: await context.bot.send_message(OWNER_ID, f"✅ تم ربط القروب الرئيسي:\n{c.title}")
            except: pass
            await context.bot.send_message(c.id, "✅ بوت الجلال جاهز!")
        elif not aid:
            data["archive_group_id"] = c.id; save_data()
            try: await context.bot.send_message(OWNER_ID, f"✅ تم ربط قروب الأرشيف:\n{c.title}")
            except: pass
            await context.bot.send_message(c.id, "✅ بوت الجلال جاهز في قروب الأرشيف!")

async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID: return
    m = data.get("main_group_id"); a = data.get("archive_group_id")
    await update.message.reply_text(f"حالة البوت\nالقروب الرئيسي: {m or '❌'}\nقروب الأرشيف: {a or '❌'}")

async def setmain_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID: return
    if not update.message.reply_to_message: await update.message.reply_text("رد على رسالة من القروب"); return
    data["main_group_id"] = update.message.reply_to_message.chat_id; save_data()
    await update.message.reply_text(f"✅ تم تعيين: {data['main_group_id']}")

async def setarchive_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID: return
    if not update.message.reply_to_message: await update.message.reply_text("رد على رسالة من قروب الأرشيف"); return
    data["archive_group_id"] = update.message.reply_to_message.chat_id; save_data()
    await update.message.reply_text(f"✅ تم تعيين: {data['archive_group_id']}")

async def reset_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID: return
    data["main_group_id"] = None; data["archive_group_id"] = None; save_data()
    await update.message.reply_text("✅ تم إعادة التعيين.")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Error: {context.error}")

def main():
    load_data()
    t = threading.Thread(target=run_health, daemon=True); t.start()
    app = Application.builder().token(TOKEN).updater(None).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status_cmd))
    app.add_handler(CommandHandler("setmain", setmain_cmd))
    app.add_handler(CommandHandler("setarchive", setarchive_cmd))
    app.add_handler(CommandHandler("reset", reset_cmd))
    app.add_handler(CallbackQueryHandler(verify_callback, pattern="^verify$"))
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, handle_new_members))
    app.add_handler(ChatMemberHandler(handle_my_chat_member, ChatMemberHandler.MY_CHAT_MEMBER))
    app.add_error_handler(error_handler)
    if RENDER_URL:
        wh_url = f"{RENDER_URL}/wh"
        logger.info(f"Starting webhook on port {PORT}, url: {wh_url}")
        app.run_webhook(listen="0.0.0.0", port=PORT, url_path="wh", webhook_url=wh_url, close_loop=False)
    else:
        logger.info("Polling mode (no RENDER_EXTERNAL_URL)")
        app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)

if __name__ == "__main__":
    main()