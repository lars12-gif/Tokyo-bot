import streamlit as st
import re
import difflib
import os
import glob
import time
import threading
import logging
from supabase import create_client, Client
from neonize.client import NewClient
from neonize.events import MessageEv, ConnectedEv

# إخفاء السجلات المزعجة
logging.getLogger("neonize").setLevel(logging.ERROR)

st.set_page_config(page_title="TOKYO Work System", page_icon="👑", layout="centered")
st.title("👑 TOKYO Work System - WhatsApp Bot")

PAIR_CODE_FILE = "pair_code.txt"
LINKED_FLAG_FILE = "linked.flag"
SESSION_NAME = "tokyo_fixed_session"

# ---------------------------------------------------------
# لوحة التحكم الجانبية
# ---------------------------------------------------------
with st.sidebar:
    st.header("⚙️ لوحة التحكم")
    if st.button("🔴 مسح الجلسة وإعادة الربط"):
        for f in glob.glob(f"{SESSION_NAME}*") + [PAIR_CODE_FILE, LINKED_FLAG_FILE]:
            if os.path.exists(f):
                try: os.remove(f)
                except Exception: pass
        st.cache_resource.clear()
        st.success("تم مسح الجلسة! أعد تحميل الصفحة.")
        time.sleep(2)
        st.rerun()

SUPABASE_URL = "https://igskxyazuomofeqvkwcy.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imlnc2t4eWF6dW9tb2ZlcXZrd2N5Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODYxNTkyNTksImV4cCI6MjEwMTczNTI1OX0.HadeqymBYWETFaauKYFNtlD-ahg3GfoOGoH0XKu_mWg"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
FOOTER_CREDITS = "\n\n👑 *TOKYO Work System © 2026*\n⚡ *Developed By Aurther*"

def normalize_arabic(text: str) -> str:
    if not text: return ""
    text = re.sub(r"[أإآ]", "ا", text)
    text = re.sub(r"ى", "ي", text)
    text = re.sub(r"ة", "ه", text)
    text = re.sub(r"[\u064B-\u0652]", "", text)
    return text.strip().lower()

def fetch_all_members():
    try:
        res = supabase.table("work_members").select("*").execute()
        return res.data if res.data else []
    except Exception:
        return []

def cmd_check(query_nick: str) -> str:
    if not query_nick: return "⚠️ *يرجى كتابة اللقب بعد الأمر.* \nمثال: `$فحص ارين`"
    members = fetch_all_members()
    if not members: return "⚠️ *تعذر جلب البيانات حالياً.*"

    normalized_query = normalize_arabic(query_nick)
    exact_match = None
    similar_nicks = []
    registered_nicks = [m.get("nickname", "") for m in members]

    for member in members:
        orig = member.get("nickname", "")
        if query_nick.strip().lower() == orig.lower() or normalized_query == normalize_arabic(orig):
            exact_match = member
            break

    if not exact_match:
        for orig in registered_nicks:
            if difflib.SequenceMatcher(None, normalized_query, normalize_arabic(orig)).ratio() >= 0.68:
                similar_nicks.append(orig)

    if exact_match:
        msg = f"❌ *نتائج فحص اللقب:*\n📌 اللقب: *[{exact_match['nickname']}]*\n🚨 *اللقب مسجل مسبقاً بالنظام!*"
    elif similar_nicks:
        msg = f"⚠️ *تنبيه تشابه ألقاب:*\nالألقاب القريبة: `{' - '.join(similar_nicks)}`"
    else:
        msg = f"✅ *نتائج فحص اللقب:*\n📌 اللقب: *[{query_nick}]*\n🎉 *اللقب متوفر بالنظام!*"

    return msg + FOOTER_CREDITS

def cmd_info(query_text: str) -> str:
    if not query_text: return "⚠️ *يرجى كتابة اللقب أو الرقم.*"
    members = fetch_all_members()
    if not members: return "⚠️ *تعذر الاتصال بقاعدة البيانات.*"

    normalized_query = normalize_arabic(query_text)
    found_member = next((m for m in members if normalize_arabic(m.get("nickname", "")) == normalized_query or str(m.get("phone", "")).strip() == query_text.strip()), None)

    if not found_member:
        return f"❌ لا يوجد عضو مسجل باللقب أو الرقم: *[{query_text}]*" + FOOTER_CREDITS

    return (
        f"👑 *بطاقة معلومات عضو TOKYO Work System*\n━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 *اللقب:* {found_member.get('nickname')}\n📱 *الرقم:* {found_member.get('phone')}\n"
        f"👑 *المستضيف:* {found_member.get('referrer', 'مباشر')}\n🤝 *مسؤول الاستقبال:* {found_member.get('received_by', 'غير محدد')}\n"
        f"📅 *تاريخ التسجيل:* {found_member.get('date', 'غير مؤرخ')}\n━━━━━━━━━━━━━━━━━━━━━━"
    ) + FOOTER_CREDITS

# ---------------------------------------------------------
# محرك إعادة الاتصال التلقائي
# ---------------------------------------------------------
def run_whatsapp_client():
    while True:
        try:
            print("⚡ جاري فتح سوكيت مستقر للواتساب...")
            client = NewClient(SESSION_NAME)

            @client.event(ConnectedEv)
            def on_connected(_: NewClient, __: ConnectedEv):
                with open(LINKED_FLAG_FILE, "w") as f: f.write("true")
                print("\n🟢 [ONLINE] البوت متصل وجاهز للاستجابة للأوامر!")

            @client.event(MessageEv)
            def on_message(client: NewClient, message: MessageEv):
                try:
                    if not hasattr(message, "message") or not message.message:
                        return

                    msg_obj = message.message
                    msg_text = ""

                    if hasattr(msg_obj, "conversation") and msg_obj.conversation:
                        msg_text = msg_obj.conversation
                    elif hasattr(msg_obj, "extendedTextMessage") and msg_obj.extendedTextMessage and hasattr(msg_obj.extendedTextMessage, "text"):
                        msg_text = msg_obj.extendedTextMessage.text

                    msg_text = msg_text.strip()
                    if not msg_text or not msg_text.startswith("$"):
                        return

                    print(f"📩 [أمر جديد]: {msg_text}")

                    parts = msg_text.split(" ", 1)
                    cmd = parts[0].lower()
                    args = parts[1].strip() if len(parts) > 1 else ""

                    if cmd == "$فحص":
                        client.reply_message(cmd_check(args), message)
                    elif cmd == "$انفو":
                        client.reply_message(cmd_info(args), message)
                    elif cmd in ["$الاوامر", "$اوامر"]:
                        reply = f"👑 *أوامر بوت TOKYO Work System*\n🔹 `$فحص [اللقب]`\n🔹 `$انفو [اللقب/الرقم]`\n🔹 `$اوامر`" + FOOTER_CREDITS
                        client.reply_message(reply, message)
                except Exception as e:
                    print(f"⚠️ خطأ معالجة: {e}")

            client.connect()
        except Exception as e:
            print(f"🔄 إعادة الاتصال السريع بعد 3 ثوانٍ...")
            time.sleep(3)

@st.cache_resource
def start_runner_thread():
    t = threading.Thread(target=run_whatsapp_client, daemon=True)
    t.start()
    return True

start_runner_thread()

# ---------------------------------------------------------
# الواجهة الرئيسية
# ---------------------------------------------------------
if os.path.exists(LINKED_FLAG_FILE):
    st.success("🟢 **البوت مرتبط ومشغّل أونلاين بنجاح!**")
    st.info("جرّب الآن أرسل `$اوامر` بالواتساب.")
else:
    st.subheader("🔑 ربط الواتساب")
    if os.path.exists(PAIR_CODE_FILE):
        with open(PAIR_CODE_FILE, "r") as f: pair_code = f.read().strip()
        st.success("🎉 **رمز الربط الحالي:**")
        st.code(pair_code, language="text")
    else:
        st.warning("إذا لم يظهر الكود تلقائياً، أعد تحميل الصفحة.")
