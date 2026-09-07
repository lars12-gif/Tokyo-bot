import streamlit as st
import subprocess
import sys
import os
import glob
import time

st.set_page_config(page_title="TOKYO Work System", page_icon="👑", layout="centered")
st.title("👑 TOKYO Work System - WhatsApp Bot")

LINKED_FLAG_FILE = "linked.flag"
PAIR_CODE_FILE = "pair_code.txt"

@st.cache_resource
def launch_background_engine():
    return subprocess.Popen([sys.executable, "bot_engine.py"])

launch_background_engine()

with st.sidebar:
    st.header("⚙️ لوحة التحكم")
    if st.button("🔴 مسح الجلسة وإعادة الربط"):
        for f in glob.glob("tokyo_fixed_session*") + [PAIR_CODE_FILE, LINKED_FLAG_FILE]:
            if os.path.exists(f):
                try: os.remove(f)
                except Exception: pass
        st.cache_resource.clear()
        st.success("تم مسح الجلسة! أعد تحميل الصفحة.")
        time.sleep(2)
        st.rerun()

if os.path.exists(LINKED_FLAG_FILE):
    st.success("🟢 **البوت مرتبط ومشغّل أونلاين بنجاح!**")
    st.info("الأوامر المتاحة بالواتساب: `$فحص` | `$انفو` | `$اوامر`")
else:
    st.subheader("🔑 ربط الواتساب")
    
    if os.path.exists(PAIR_CODE_FILE):
        with open(PAIR_CODE_FILE, "r") as f:
            pair_code = f.read().strip()
        
        if pair_code:
            st.success("🎉 **تم توليد رمز الربط بنجاح!**")
            st.code(pair_code, language="text")
            st.info("""
            📌 **طريقة الربط بالواتساب:**
            1. افتح الواتساب بتليفونك 📱.
            2. ادخل إلى **الأجهزة المرتبطة** 👈 **ربط جهاز**.
            3. اضغط على **الربط باستخدام رقم الهاتف بدلاً من ذلك**.
            4. اكتب الرمز الظاهر أعلاه.
            """)
    else:
        st.warning("⏳ جاري توليد الكود من السيرفر (انتظر 5 ثوانٍ ثم اضغط الزر أدناه)...")
        if st.button("🔄 تحديث لرؤية الرمز"):
            st.rerun()
