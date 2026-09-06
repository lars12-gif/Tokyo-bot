import re
import difflib
import os
from supabase import create_client, Client
from neonize.client import NewClient
from neonize.events import MessageEv, ConnectedEv

# ---------------------------------------------------------
# 1. إعدادات قاعدة البيانات (TOKYO Work System)
# ---------------------------------------------------------
SUPABASE_URL = "https://igskxyazuomofeqvkwcy.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imlnc2t4eWF6dW9tb2ZlcXZrd2N5Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODYxNTkyNTksImV4cCI6MjEwMTczNTI1OX0.HadeqymBYWETFaauKYFNtlD-ahg3GfoOGoH0XKu_mWg"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# زخرفة الحقوق الرسمية
FOOTER_CREDITS = "\n\n👑 *TOKYO Work System © 2026*\n⚡ *Developed By Aurther*"

# ---------------------------------------------------------
# 2. دوال المعالجة وتطبيع النصوص والأوامر
# ---------------------------------------------------------
def normalize_arabic(text: str) -> str:
    """تطبيع النص العربي لتجاهل الهمزات والفرق بين الأحرف المتشابهة"""
    if not text:
        return ""
    text = re.sub(r"[أإآ]", "ا", text)
    text = re.sub(r"ى", "ي", text)
    text = re.sub(r"ة", "ه", text)
    text = re.sub(r"[\u064B-\u0652]", "", text)  # إزالة التشكيل
    return text.strip().lower()

def fetch_all_members():
    """جلب قائمة الأعضاء من جدول work_members"""
    try:
        res = supabase.table("work_members").select("*").execute()
        return res.data if res.data else []
    except Exception as e:
        print(f"❌ خطأ في الاتصال بقاعدة البيانات: {e}")
        return []

def cmd_check(query_nick: str) -> str:
    """معالجة أمر .فحص مع خاصية كشف التشابه الإملائي"""
    if not query_nick:
        return "⚠️ *يرجى كتابة اللقب بعد الأمر.* \nمثال: `.فحص ارين`"
    
    members = fetch_all_members()
    if not members:
        return "⚠️ *تعذر جلب البيانات من الداتا بيس حالياً.*"

    normalized_query = normalize_arabic(query_nick)
    exact_match = None
    similar_nicks = []

    registered_nicks = [m.get("nickname", "") for m in members]

    # 1. مطابقة تامة
    for member in members:
        orig = member.get("nickname", "")
        if query_nick.strip().lower() == orig.lower() or normalized_query == normalize_arabic(orig):
            exact_match = member
            break

    # 2. مطابقة تقريبية (Fuzzy Matching للتشابه)
    if not exact_match:
        for orig in registered_nicks:
            norm_orig = normalize_arabic(orig)
            similarity = difflib.SequenceMatcher(None, normalized_query, norm_orig).ratio()
            if similarity >= 0.68:  # نسبة تشابه قريبة جداً
                similar_nicks.append(orig)

    # 3. صياغة الرد
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
    """معالجة أمر .انفو لعرض معلومات العضو بالكامل"""
    if not query_text:
        return "⚠️ *يرجى كتابة اللقب أو الرقم بعد الأمر.* \nمثال: `.انفو ارين`"

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
# 3. إعداد واستقبال رسائل الواتساب (Neonize Engine)
# ---------------------------------------------------------
client = NewClient("tokyo_bot_session")

@client.event(ConnectedEv)
def on_connected(_: NewClient, __: ConnectedEv):
    print("🟢 تم الاتصال بالواتساب بنجاح! بوت TOKYO شغال وجاهز لاستلام الأوامر.")

@client.event(MessageEv)
def on_message(client: NewClient, message: MessageEv):
    # استخراج نص الرسالة
    msg_text = message.message.conversation or message.message.extendedTextMessage.text or ""
    msg_text = msg_text.strip()

    # التفاعل فقط مع الرسائل التي تبدأ بنقطة
    if not msg_text.startswith("."):
        return

    parts = msg_text.split(" ", 1)
    command = parts[0].lower()
    args = parts[1].strip() if len(parts) > 1 else ""

    if command == ".فحص":
        reply = cmd_check(args)
        client.reply_message(reply, message)
        
    elif command == ".انفو":
        reply = cmd_info(args)
        client.reply_message(reply, message)

    elif command in [".الاوامر", ".اوامر"]:
        reply = (
            f"👑 *قائمة أوامر بوت TOKYO Work System*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🔹 `.فحص [اللقب]` : تفحص توفر اللقب وتمنع التكرار والتشابه.\n"
            f"🔹 `.انفو [اللقب أو الرقم]` : تعطي كافة معلومات العضو.\n"
            f"🔹 `.اوامر` : لعرض هذه القائمة.\n"
            f"━━━━━━━━━━━━━━━━━━━━━━"
            f"{FOOTER_CREDITS}"
        )
        client.reply_message(reply, message)

print("🚀 جاري بدء بوت TOKYO... امسح رمز الـ QR Code الذي سيظهر بالأسفل بواتسابك:")
client.connect()
