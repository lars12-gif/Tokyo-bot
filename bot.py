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

# إخفاء رسائل الـ QR والسجلات المزعجة
logging.getLogger("neonize").setLevel(logging.ERROR)

st.set_page_config(page_title="TOKYO Work System", page_icon="👑", layout="centered")

st.title("👑 TOKYO Work System - WhatsApp Bot")

PAIR_CODE_FILE = "pair_code.txt"
LINKED_FLAG_FILE = "linked.flag"
RATE_LIMIT_FILE = "rate_limit.flag"
VERSION_FILE = "session_version.txt"

def get_session_name():
    if not os.path.exists(VERSION_FILE):
        with open(VERSION_FILE, "w") as f:
            f.write("1")
        return "tokyo_session_v1"
    with open(VERSION_FILE, "r") as f:
        ver = f.read().strip() or "1"
    return f"tokyo_session_v{ver}"

SESSION_NAME = get_session_name()

# ---------------------------------------------------------
# زر التحكم الجانبي
# ---------------------------------------------------------
with st.sidebar:
    st.header("⚙️ لوحة التحكم")
    st.write("إذا سجلت خروج أو أردت بداية جلسة جديدة، اضغط الزر أدناه:")
    if st.button("🔴 إعادة ضبط وبدء جلسة جديدة"):
        current_ver = 1
        if os.path.exists(VERSION_FILE):
            try:
                with open(VERSION_FILE, "r") as f:
                    current_ver = int(f.read().strip())
            except Exception:
                current_ver = 1
        
        new_ver = current_ver + 1
        with open(VERSION_FILE, "w") as f:
            f.write(str(new_ver))
        
        for f in [PAIR_CODE_FILE, LINKED_FLAG_FILE, RATE_LIMIT_FILE]:
            if os.path.exists(f):
                try:
                    os.remove(f)
                except Exception:
                    pass
                
        st.cache_resource.clear()
        st.success(f"تم بدء جلسة جديدة (v{new_ver})! جاري إعادة التشغيل...")
        time.sleep(2)
        st.rerun()

# ---------------------------------------------------------
# 1. إعدادات قاعدة البيانات Supabase
# ---------------------------------------------------------
SUPABASE_URL = "https://igskxyazuomofeqvkwcy.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imlnc2t4eWF6dW9tb2ZlcXZrd2N5Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODYxNTkyNTksImV4cCI6MjEwMTczNTI1OX0.HadeqymBYWETFaauKYFNtlD-ahg3GfoOGoH0XKu_mWg"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
FOOTER_CREDITS = "\n\n👑 *TOKYO Work System © 2026*\n⚡ *Developed By Aurther*"

# ---------------------------------------------------------
# 2. دوال البحث والتحقق من الألقاب
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
    except Exception as e:
        print(f"❌ خطأ في الاتصال بقاعدة البيانات: {e}")
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
            similarity = difflib.SequenceMatcher(None, normalized_query, norm_orig).ratio()
            if similarity >= 0.68:
                similar_nicks.append(orig)

    if exact_match:
        msg = (
            f"❌ *نتائج فحص اللقب:*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📌 اللقب: *[{exact_match['nickname']}]*\n"
            f"🚨 *اللقب مسجل مسبقاً بالنظام!* لا يمكنك استخدامه."
        )
    elif similar_nicks:
        matches_str = " - ".join(similar_nicks)
        msg = (
            f"⚠️ *تنبيه تشابه ألقاب:*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"اللقب *[{query_nick}]* غير مسجل بالضبط، لكن توجد ألقاب قريبة منه جداً بالنظام:\n\n"
            f"📌 *الألقاب المتشابهة:* `{matches_str}`\n\n"
            f"💡 *يرجى التأكد من العضو لتجنب التكرار.*"
        )
    else:
        msg = (
            f"✅ *نتائج فحص اللقب:*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📌 اللقب: *[{query_nick}]*\n"
            f"🎉 *اللقب متوفر وغير مسجل بالنظام!* يمكنك تسجيله."
        )

    return msg + FOOTER_CREDITS

def cmd_info(query_text: str) -> str:
    if not query_text:
        return "⚠️ *يرجى كتابة اللقب أو الرقم بعد الأمر.* \nمثال: `$انفو ارين`"

    members = fetch_all_members()
    if not members:
        return "⚠️ *تعذر الاتصال بقاعدة البيانات.*"

    normalized_query = normalize_arabic(query_text)
    found_member = None

    for m in members:
        nick = m.get("nickname", "")
        phone = str(m.get("phone", ""))
        if (normalized_query == normalize_arabic(nick)) or (query_text.strip() == phone):
            found_member = m
            break

    if not found_member:
        return f"❌ لا يوجد عضو مسجل باللقب أو الرقم: *[{query_text}]*" + FOOTER_CREDITS

    msg = (
        f"👑 *بطاقة معلومات عضو TOKYO Work System*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 *اللقب:* {found_member.get('nickname')}\n"
        f"📱 *الرقم:* {found_member.get('phone')}\n"
        f"👑 *المستضيف (من طرف):* {found_member.get('referrer', 'مباشر')}\n"
        f"🤝 *مسؤول الاستقبال:* {found_member.get('received_by', 'غير محدد')}\n"
        f"📅 *تاريخ التسجيل:* {found_member.get('date', 'غير مؤرخ')}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━"
    )
    return msg + FOOTER_CREDITS

# ---------------------------------------------------------
# 3. تشغيل الكلاينت للجلسة الحالية
# ---------------------------------------------------------
@st.cache_resource
def start_bot_singleton(sess_name):
    client = NewClient(sess_name)

    @client.event(ConnectedEv)
    def on_connected(_: NewClient, __: ConnectedEv):
        with open(LINKED_FLAG_FILE, "w") as f:
            f.write("true")
        if os.path.exists(RATE_LIMIT_FILE):
            os.remove(RATE_LIMIT_FILE)
        print(f"\n🟢 تم الاتصال بنجاح بالجلسة {sess_name}! البوت أونلاين الآن.")

    @client.event(MessageEv)
    def on_message(client: NewClient, message: MessageEv):
        if not message.message:
            return

        msg_text = ""
        if message.message.conversation:
            msg_text = message.message.conversation
        elif message.message.extendedTextMessage and message.message.extendedTextMessage.text:
            msg_text = message.message.extendedTextMessage.text

        msg_text = msg_text.strip()

        if not msg_text.startswith("$"):
            return

        parts = msg_text.split(" ", 1)
        command = parts[0].lower()
        args = parts[1].strip() if len(parts) > 1 else ""

        if command == "$فحص":
            reply = cmd_check(args)
            client.reply_message(reply, message)
        elif command == "$انفو":
            reply = cmd_info(args)
            client.reply_message(reply, message)
        elif command in ["$الاوامر", "$اوامر"]:
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

    def pairing_worker():
        time.sleep(6)
        if not os.path.exists(LINKED_FLAG_FILE):
            phone = os.getenv("PHONE_NUMBER", "").replace("+", "").replace(" ", "").replace("-", "")
            if phone:
                try:
                    print(f"⏳ طلب رمز الربط للجلسة {sess_name}...")
                    code = client.PairPhone(phone, True)
                    with open(PAIR_CODE_FILE, "w") as f:
                        f.write(code)
                    if os.path.exists(RATE_LIMIT_FILE):
                        os.remove(RATE_LIMIT_FILE)
                    print(f"🔑 تم توليد الرمز بنجاح: {code}")
                except Exception as e:
                    err_str = str(e)
                    print(f"⚠️ فشل طلب الرمز: {err_str}")
                    if "429" in err_str or "rate-overlimit" in err_str:
                        with open(RATE_LIMIT_FILE, "w") as f:
                            f.write("429")

    def runner():
        threading.Thread(target=pairing_worker, daemon=True).start()
        try:
            client.connect()
        except Exception as e:
            print(f"❌ خطأ الاتصال: {e}")

    thread = threading.Thread(target=runner, daemon=True)
    thread.start()
    return True

# تشغيل الجلسة الحالية
start_bot_singleton(SESSION_NAME)

# ---------------------------------------------------------
# 4. الشاشة الرئيسية
# ---------------------------------------------------------
if os.path.exists(LINKED_FLAG_FILE):
    st.success(f"🟢 **البوت مرتبط ومشغّل أونلاين بنجاح!** (`{SESSION_NAME}`)")
    st.info("⚡ البوت جاهز ويستقبل الأوامر حالياً في الواتساب ($فحص ، $انفو ، $اوامر).")

elif os.path.exists(RATE_LIMIT_FILE):
    st.error("🚨 **سيرفرات واتساب فرضت حظراً مؤقتاً (Rate Limit 429) لكثرة المحاولات!**")
    st.warning("""
    📌 **ماذا يجب أن تفعل الآن؟**
    * توقف عن الضغط على زر التحديث أو زر إعادة الضبط.
    * انتظر من **20 إلى 30 دقيقة** حتى يفك سيرفر واتساب الحظر التلقائي عن الرقم.
    * بعد انقضاء الوقت، اضغط على زر **`🔴 إعادة ضبط وبدء جلسة جديدة`** من القائمة الجانبية وسيُطلب الرمز بنجاح.
    """)

else:
    st.subheader("🔑 ربط الواتساب بـ رمز الهاتف (Pairing Code)")
    st.caption(f"الجلسة الحالية: `{SESSION_NAME}`")
    
    if os.path.exists(PAIR_CODE_FILE):
        with open(PAIR_CODE_FILE, "r") as f:
            pair_code = f.read().strip()
        
        if pair_code:
            st.success("🎉 **تم توليد رمز الربط بنجاح!**")
            st.markdown("انسخ الرمز الظاهر أدناه وافتحه بالواتساب فوراً:")
            st.code(pair_code, language="text")
            st.info("""
            📌 **طريقة الربط بالواتساب:**
            1. افتح الواتساب بتليفونك 📱.
            2. ادخل إلى **الأجهزة المرتبطة** 👈 **ربط جهاز**.
            3. اضغط على **الربط باستخدام رقم الهاتف بدلاً من ذلك**.
            4. اكتب الرمز المكتوب في الصندوق أعلاه.
            """)
    else:
        st.warning("⏳ جاري طلب رمز الربط من السيرفر... انتظر 6 ثوانٍ واضغط زر التحديث.")
        if st.button("🔄 تحديث الصفحة لرؤية الرمز"):
            st.rerun()
