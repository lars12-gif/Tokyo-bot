import streamlit as st
import re
import difflib
import os
import time
import threading
import logging
from supabase import create_client, Client
from neonize.client import NewClient
from neonize.events import MessageEv, ConnectedEv

# إخفاء سجلات النظام المزعجة
logging.getLogger("neonize").setLevel(logging.ERROR)

st.set_page_config(page_title="TOKYO Work System", page_icon="👑", layout="centered")
st.title("👑 TOKYO Work System - WhatsApp Bot")

PAIR_CODE_FILE = "pair_code.txt"
LINKED_FLAG_FILE = "linked.flag"
SESSION_NAME = "tokyo_fixed_session"

# ---------------------------------------------------------
# إعدادات قاعدة البيانات Supabase
# ---------------------------------------------------------
SUPABASE_URL = "https://igskxyazuomofeqvkwcy.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imlnc2t4eWF6dW9tb2ZlcXZrd2N5Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODYxNTkyNTksImV4cCI6MjEwMTczNTI1OX0.HadeqymBYWETFaauKYFNtlD-ahg3GfoOGoH0XKu_mWg"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
FOOTER_CREDITS = "\n\n👑 *TOKYO Work System © 2026*\n⚡ *Developed By Aurther*"

# ---------------------------------------------------------
# دوال معالجة النصوص والبحث
# ---------------------------------------------------------
def normalize_arabic(text: str) -> str:
    if not text: 
        return ""
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
    if not query_nick:
        return "⚠️ *يرجى كتابة اللقب بعد الأمر.* \nمثال: `$فحص ارين`"
    
    members = fetch_all_members()
    if not members: 
        return "⚠️ *تعذر جلب البيانات من الداتا بيس حالياً.*"

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
            norm_orig = normalize_arabic(orig)
            if difflib.SequenceMatcher(None, normalized_query, norm_orig).ratio() >= 0.68:
                similar_nicks.append(orig)

    if exact_match:
        msg = f"❌ *نتائج فحص اللقب:*\n━━━━━━━━━━━━━━━━━━━━━━\n📌 اللقب: *[{exact_match['nickname']}]*\n🚨 *اللقب مسجل مسبقاً بالنظام!* لا يمكنك استخدامه."
    elif similar_nicks:
        matches_str = " - ".join(similar_nicks)
        msg = f"⚠️ *تنبيه تشابه ألقاب:*\n━━━━━━━━━━━━━━━━━━━━━━\nاللقب *[{query_nick}]* غير مسجل بالضبط، لكن توجد ألقاب قريبة منه:\n\n📌 *الألقاب المتشابهة:* `{matches_str}`"
    else:
        msg = f"✅ *نتائج فحص اللقب:*\n━━━━━━━━━━━━━━━━━━━━━━\n📌 اللقب: *[{query_nick}]*\n🎉 *اللقب متوفر وغير مسجل بالنظام!*"

    return msg + FOOTER_CREDITS

def cmd_info(query_text: str) -> str:
    if not query_text: 
        return "⚠️ *يرجى كتابة اللقب أو الرقم بعد الأمر.* \nمثال: `$انفو ارين`"
    
    members = fetch_all_members()
    if not members: 
        return "⚠️ *تعذر الاتصال بقاعدة البيانات.*"

    normalized_query = normalize_arabic(query_text)
    found_member = next((m for m in members if normalize_arabic(m.get("nickname", "")) == normalized_query or str(m.get("phone", "")).strip() == query_text.strip()), None)

    if not found_member:
        return f"❌ لا يوجد عضو مسجل باللقب أو الرقم: *[{query_text}]*" + FOOTER_CREDITS

    msg = (
        f"👑 *بطاقة معلومات عضو TOKYO Work System*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 *اللقب:* {found_member.get('nickname')}\n"
        f"📱 *الرقم:* {found_member.get('phone')}\n"
        f"👑 *المستضيف:* {found_member.get('referrer', 'مباشر')}\n"
        f"🤝 *مسؤول الاستقبال:* {found_member.get('received_by', 'غير محدد')}\n"
        f"📅 *تاريخ التسجيل:* {found_member.get('date', 'غير مؤرخ')}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━"
    )
    return msg + FOOTER_CREDITS

# ---------------------------------------------------------
# تشغيل البوت ومعالجة الرسائل بآمان
# ---------------------------------------------------------
@st.cache_resource
def start_bot_instance():
    client = NewClient(SESSION_NAME)

    @client.event(ConnectedEv)
    def on_connected(_: NewClient, __: ConnectedEv):
        with open(LINKED_FLAG_FILE, "w") as f: 
            f.write("true")

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
            if not msg_text.startswith("$"):
                return

            parts = msg_text.split(" ", 1)
            cmd = parts[0].lower()
            args = parts[1].strip() if len(parts) > 1 else ""

            if cmd == "$فحص":
                client.reply_message(cmd_check(args), message)
            elif cmd == "$انفو":
                client.reply_message(cmd_info(args), message)
            elif cmd in ["$الاوامر", "$اوامر"]:
                reply = (
                    f"👑 *قائمة أوامر بوت TOKYO Work System*\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"🔹 `$فحص [اللقب]` : تفحص توفر اللقب وتمنع التكرار.\n"
                    f"🔹 `$انفو [اللقب أو الرقم]` : كافة معلومات العضو.\n"
                    f"🔹 `$اوامر` : لعرض هذه القائمة.\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━"
                    f"{FOOTER_CREDITS}"
                )
                client.reply_message(reply, message)
        except Exception:
            # تجاهل أخطاء حزم المزامنة والرسائل غير النصية
            pass

    def runner():
        try: 
            client.connect()
        except Exception as e: 
            print(f"Client error: {e}")

    threading.Thread(target=runner, daemon=True).start()
    return client

bot_client = start_bot_instance()

# ---------------------------------------------------------
# واجهة التحكم في Streamlit
# ---------------------------------------------------------
if os.path.exists(LINKED_FLAG_FILE):
    st.success("🟢 **البوت مرتبط ومشغّل أونلاين بنجاح!**")
    st.info("الأوامر المتاحة حالياً بجروبات الواتساب:\n* `$فحص` \n* `$انفو` \n* `$اوامر`")
else:
    st.subheader("🔑 ربط الواتساب")
    
    if os.path.exists(PAIR_CODE_FILE):
        with open(PAIR_CODE_FILE, "r") as f: 
            pair_code = f.read().strip()
        st.success("🎉 **رمز الربط الحالي:**")
        st.code(pair_code, language="text")
        st.caption("ادخل للواتساب 👈 الأجهزة المرتبطة 👈 ربط باستخدام رقم الهاتف واكتب الكود أعلاه.")
    else:
        st.warning("اضغط الزر أدناه لتوليد رمز الربط يدويًا:")
        if st.button("⚡ طلب رمز الربط الآن"):
            phone = os.getenv("PHONE_NUMBER", "").replace("+", "").replace(" ", "").replace("-", "")
            try:
                code = bot_client.PairPhone(phone, True)
                with open(PAIR_CODE_FILE, "w") as f: 
                    f.write(code)
                st.success("تم توليد الرمز!")
                st.rerun()
            except Exception as e:
                err = str(e)
                if "429" in err or "rate-overlimit" in err:
                    st.error("🚨 سيرفرات واتساب قفلت طلب الرموز للرقم مؤقتاً بسبب كثرة المحاولات. انتظر ساعة بدون إرسال محاولات جديدة لتفك الحظر تلقائياً.")
                else:
                    st.error(f"خطأ: {err}")
