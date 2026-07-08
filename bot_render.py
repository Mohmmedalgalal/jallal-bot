import json, os, requests, hashlib, hmac, asyncio, threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime, timedelta

TOKEN = "8651597322:AAEeCm43jzclz_CbAUMMIGpNcgkNn4ZL-uk"
TG_API = f"https://api.telegram.org/bot{TOKEN}"
MAIN_USERNAME = "sunrte"
ARCHIVE_LINK = "https://t.me/g9cPgbMOOFL0zNmNk"
OWNER_ID = 7606399570
PORT = int(os.environ.get("PORT", 8080))
DATA_FILE = "bot_data.json"

data = {"main_group_id": None, "archive_group_id": None}
if os.path.exists(DATA_FILE):
    with open(DATA_FILE) as f:
        try: data.update(json.load(f))
        except: pass

def save():
    with open(DATA_FILE, "w") as f: json.dump(data, f, indent=2)

def tg(method, **kwargs):
    try:
        r = requests.post(f"{TG_API}/{method}", json={k:v for k,v in kwargs.items() if v is not None}, timeout=10)
        return r.json()
    except Exception as e:
        return {"ok": False, "error": str(e)}

def tg_send(chat_id, text, reply_markup=None, parse_mode=None, reply_to=None):
    return tg("sendMessage", chat_id=chat_id, text=text, reply_markup=json.dumps(reply_markup) if reply_markup else None, parse_mode=parse_mode, reply_to_message_id=reply_to)

def tg_edit(chat_id, msg_id, text, reply_markup=None):
    return tg("editMessageText", chat_id=chat_id, message_id=msg_id, text=text, reply_markup=json.dumps(reply_markup) if reply_markup else None)

def tg_delete(chat_id, msg_id):
    return tg("deleteMessage", chat_id=chat_id, message_id=msg_id)

def tg_restrict(chat_id, user_id):
    perms = {"can_send_messages":True,"can_send_audios":True,"can_send_documents":True,"can_send_photos":True,"can_send_videos":True,"can_send_video_notes":True,"can_send_voice_notes":True,"can_send_polls":True,"can_send_other_messages":True,"can_add_web_page_previews":True,"can_change_info":False,"can_invite_users":False,"can_pin_messages":False}
    return tg("restrictChatMember", chat_id=chat_id, user_id=user_id, permissions=perms)

def tg_mute(chat_id, user_id):
    perms = {"can_send_messages":False,"can_send_audios":False,"can_send_documents":False,"can_send_photos":False,"can_send_videos":False,"can_send_video_notes":False,"can_send_voice_notes":False,"can_send_polls":False,"can_send_other_messages":False,"can_add_web_page_previews":False,"can_change_info":False,"can_invite_users":False,"can_pin_messages":False}
    return tg("restrictChatMember", chat_id=chat_id, user_id=user_id, permissions=perms)

def tg_member(chat_id, user_id):
    r = tg("getChatMember", chat_id=chat_id, user_id=user_id)
    return r.get("result",{}).get("status") if r.get("ok") else None

def tg_setwebhook(url):
    return tg("setWebhook", url=url)

def tg_deletewebhook():
    return tg("deleteWebhook")

stop_event = threading.Event()

def handle_update(upd):
    if "message" not in upd and "callback_query" not in upd and "my_chat_member" not in upd:
        return
    msg = upd.get("message", {})
    cb = upd.get("callback_query", {})
    mcm = upd.get("my_chat_member", {})
    chat = msg.get("chat") or cb.get("message",{}).get("chat") or mcm.get("chat", {})
    chat_id = chat.get("id")
    if not chat_id:
        return

    # Callback query
    if cb:
        qid = cb["id"]
        uid = cb["from"]["id"]
        name = cb["from"]["first_name"]
        tg("answerCallbackQuery", callback_query_id=qid)
        mid = data.get("main_group_id"); aid = data.get("archive_group_id")
        if not mid or not aid:
            tg_edit(chat_id, cb["message"]["message_id"], "⚠️ البوت لم يربط بعد.")
            return
        status = tg_member(aid, uid)
        if status in ("member","creator","administrator"):
            r = tg_restrict(mid, uid)
            if r.get("ok"):
                tg_edit(chat_id, cb["message"]["message_id"], f"\u2705 {name} تم تفعيل حسابك!")
                tg_send(uid, "\u2705 تم تفعيل حسابك! يمكنك الآن الكتابة في القروب.")
                threading.Thread(target=delayed_delete, args=(chat_id, cb["message"]["message_id"], 20), daemon=True).start()
            else:
                tg_edit(chat_id, cb["message"]["message_id"], "⚠️ لم يتم العثور عليك في القروب الرئيسي.")
        else:
            kb = {"inline_keyboard":[[{"text":"\U0001f4e6 انضم للارشيف","url":ARCHIVE_LINK}],[{"text":"\u2705 تفعيل الحساب","callback_data":"verify"}]]}
            tg_edit(chat_id, cb["message"]["message_id"], "❌ لم تنضم إلى قروب الأرشيف بعد.\nالرجاء الانضمام أولاً، ثم اضغط على تفعيل الحساب.", reply_markup=kb)
        return

    # My Chat Member (bot added to group)
    if mcm:
        cid = mcm["chat"]["id"]
        n = mcm["new_chat_member"]
        o = mcm["old_chat_member"]
        username = (mcm["chat"].get("username") or "").lower()
        if o.get("status") in ("left","kicked") and n.get("status") in ("member","administrator"):
            if username == MAIN_USERNAME:
                data["main_group_id"] = cid; save()
                tg_send(OWNER_ID, f"✅ تم ربط القروب الرئيسي: {mcm['chat']['title']}")
                tg_send(cid, "✅ بوت الجلال جاهز!")
            elif not data.get("archive_group_id"):
                data["archive_group_id"] = cid; save()
                tg_send(OWNER_ID, f"✅ تم ربط قروب الأرشيف: {mcm['chat']['title']}")
                tg_send(cid, "✅ بوت الجلال جاهز في قروب الأرشيف!")
        return

    # New chat members
    new_members = msg.get("new_chat_members", [])
    if new_members:
        cu = (chat.get("username") or "").lower()
        if cu == MAIN_USERNAME and data.get("main_group_id") != chat_id:
            data["main_group_id"] = chat_id; save()
            tg_send(OWNER_ID, f"✅ تم ربط القروب الرئيسي: {chat.get('title')}")
        if chat_id != data.get("main_group_id"):
            return
        for member in new_members:
            if member.get("is_bot"):
                continue
            uid = member["id"]
            tg_mute(chat_id, uid)
            kb = {"inline_keyboard":[[{"text":"\U0001f4e6 انضم للارشيف","url":ARCHIVE_LINK}],[{"text":"\u2705 تفعيل الحساب","callback_data":"verify"}]]}
            name = member.get("first_name","")
            tg_send(chat_id, f"أهلا بك {name}، أنت مكتوم حالياً.\nاضغط على زر الانضمام للأرشيف ثم تفعيل الحساب.", reply_markup=kb)
        return

    # /start private
    if msg.get("text") == "/start" and chat.get("type") == "private":
        uid = msg["from"]["id"]
        name = msg["from"]["first_name"]
        kb = {"inline_keyboard":[[{"text":"\U0001f4e6 الانضمام للأرشيف","url":ARCHIVE_LINK}],[{"text":"\u2705 تفعيل الحساب","callback_data":"verify"}]]}
        tg_send(chat_id, f"مرحباً بك {name} في بوت الجلال \U0001f44b\n\nللتفعيل:\n1\ufe0f\u20e3 اضغط على زر الانضمام للأرشيف\n2\ufe0f\u20e3 ثم اضغط على زر تفعيل الحساب", reply_markup=kb)
        return

    # Commands for owner
    if msg.get("text") and msg["from"]["id"] == OWNER_ID:
        text = msg["text"]
        if text == "/status":
            m = data.get("main_group_id"); a = data.get("archive_group_id")
            tg_send(chat_id, f"حالة البوت\nالقروب الرئيسي: {m or '❌'}\nقروب الأرشيف: {a or '❌'}")
        elif text == "/reset":
            data["main_group_id"] = None; data["archive_group_id"] = None; save()
            tg_send(chat_id, "✅ تم إعادة التعيين.")

    # /setmain or /setarchive (reply)
    if msg.get("text") and msg["from"]["id"] == OWNER_ID and msg.get("reply_to_message"):
        text = msg["text"]
        target_id = msg["reply_to_message"]["chat"]["id"]
        if text == "/setmain":
            data["main_group_id"] = target_id; save()
            tg_send(chat_id, f"✅ تم تعيين القروب الرئيسي: {target_id}")
        elif text == "/setarchive":
            data["archive_group_id"] = target_id; save()
            tg_send(chat_id, f"✅ تم تعيين قروب الأرشيف: {target_id}")

def delayed_delete(chat_id, msg_id, delay):
    import time
    time.sleep(delay)
    tg_delete(chat_id, msg_id)

def process_updates():
    offset = 0
    while not stop_event.is_set():
        try:
            r = requests.post(f"{TG_API}/getUpdates", json={"offset": offset, "timeout": 30, "allowed_updates": ["message","callback_query","my_chat_member"]}, timeout=35)
            res = r.json()
            if res.get("ok"):
                for upd in res["result"]:
                    offset = upd["update_id"] + 1
                    threading.Thread(target=handle_update, args=(upd,), daemon=True).start()
        except requests.Timeout:
            continue
        except Exception as e:
            import time; time.sleep(5)

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/wh":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length).decode() if length else ""
            if body:
                try:
                    upd = json.loads(body)
                    threading.Thread(target=handle_update, args=(upd,), daemon=True).start()
                except: pass
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Bot is alive!")
    def do_POST(self):
        self.do_GET()
    def log_message(self, *args): pass

def main():
    tg_setwebhook("")
    t = threading.Thread(target=process_updates, daemon=True)
    t.start()
    server = HTTPServer(("0.0.0.0", PORT), HealthHandler)
    print(f"Server on {PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        stop_event.set()
        server.shutdown()

if __name__ == "__main__":
    main()