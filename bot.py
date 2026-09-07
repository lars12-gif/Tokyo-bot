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
SESSION_PREFIX = "tokyo_bot_session"

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
# 3. إعداد الكلاينت وتشغيل البوت بـ Singleton عبر Cache
# ---------------------------------------------------------
@st.cache_resource
def start_bot_singleton():
    client = NewClient(SESSION_PREFIX)

    @client.event(ConnectedEv)
    def on_connected(_: NewClient, __: ConnectedEv):
        print("\n🟢 تم الاتصال بنجاح! البوت أونلاين الآن وشغال بالجروب.")

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
        # الانتظار 5 ثوانٍ لضمان تجهيز محرك الاتصال
        time.sleep(5)
        has_session = any(os.path.exists(f) for f in glob.glob(f"{SESSION_PREFIX}.sqlite*"))
        if not has_session:
            phone = os.getenv("PHONE_NUMBER", "").replace("+", "").replace(" ", "").replace("-", "")
            if phone:
                try:
                    print(f"⏳ جاري طلب رمز الربط للرقم: {phone}")
                    code = client.PairPhone(phone, True)
                    with open(PAIR_CODE_FILE, "w") as f:
                        f.write(code)
                    print(f"🔑 تم توليد الرمز بنجاح: {code}")
                except Exception as e:
                    print(f"❌ خطأ أثناء طلب رمز الربط: {e}")

    def runner():
        threading.Thread(target=pairing_worker, daemon=True).start()
        try:
            client.connect()
        except Exception as e:
            print(f"❌ خطأ الاتصال: {e}")

    thread = threading.Thread(target=runner, daemon=True)
    thread.start()
    return True

# تشغيل البوت مرة واحدة فقط
start_bot_singleton()

# ---------------------------------------------------------
# 4. واجهة التحكم بالصفحة
# ---------------------------------------------------------
has_active_session = any(os.path.exists(f) for f in glob.glob(f"{SESSION_PREFIX}.sqlite*"))

if has_active_session:
    st.success("🟢 **البوت مرتبط ومشغّل أونلاين بنجاح!**")
    st.info("⚡ البوت جاهز ويستقبل الأوامر حالياً في الواتساب ($فحص ، $انفو ، $اوامر).")
    
    st.divider()
    st.caption("⚠️ إذا سجلت خروج وتريد ربط حساب جديد أو إعادة الربط، اضغط الزر أدناه:")
    if st.button("🔴 إزالة الجلسة القديمة وإعادة الربط"):
        for f in glob.glob(f"{SESSION_PREFIX}.sqlite*") + [PAIR_CODE_FILE]:
            if os.path.exists(f):
                try:
                    os.remove(f)
                except Exception:
                    pass
        st.cache_resource.clear()
        st.success("تم مسح الجلسة القديمة! جاري إعادة التشغيل...")
        time.sleep(2)
        st.rerun()

else:
    st.subheader("🔑 ربط الواتساب بـ رمز الهاتف (Pairing Code)")
    
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
        st.warning("⏳ جاري طلب رمز الربط من السيرفر... انتظر 5 ثوانٍ واضغط زر التحديث.")
        if st.button("🔄 تحديث الصفحة لرؤية الرمز"):
            st.rerun()
