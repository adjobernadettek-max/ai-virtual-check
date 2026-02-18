import streamlit as st
import easyocr
from PIL import Image, ImageDraw
import qrcode
from datetime import datetime
import numpy as np
import pandas as pd
import os
import hashlib
import io
import re
import requests
import uuid

# --- FONCTIONS DE BASE ---
def generer_empreinte(image_file):
    return hashlib.sha256(image_file.getvalue()).hexdigest()

def enregistrer_csv(nom, support, banque, hash_img):
    f = "registre.csv"
    data = pd.DataFrame([{"DATE": datetime.now(), "NOM": nom, "TYPE": support, "BANQUE": banque, "HASH": hash_img}])
    if not os.path.isfile(f):
        data.to_csv(f, index=False)
    else:
        data.to_csv(f, mode='a', header=False, index=False)

# --- CONFIGURATION ---
st.set_page_config(page_title="IA Audit", layout="wide")

@st.cache_resource
def load_ocr():
    return easyocr.Reader(['en'], gpu=False)
reader = load_ocr()

st.title("🔐 Terminal d'Audit Sécurisé")

tab1, tab2 = st.tabs(["👤 CLIENT", "🏢 ADMIN"])

with tab1:
    type_s = st.selectbox("SUPPORT", ["Carte Physique", "Carte Virtuelle"])
    nom = st.text_input("NOM COMPLET").upper().strip()
    num = st.text_input("16 CHIFFRES", max_chars=19)
    last4 = num[-4:] if num else ""

    files = []
    if type_s == "Carte Virtuelle":
        up = st.file_uploader("Screenshot")
        if up: files = [up]
    else:
        r = st.file_uploader("Recto")
        v = st.file_uploader("Verso")
        files = [x for x in [r, v] if x]

    if st.button("🚀 VÉRIFIER"):
        if files and nom and last4:
            with st.status("Analyse...") as status:
                h = generer_empreinte(files[0])
                txt = ""
                ok = True
                for f in files:
                    try:
                        img = Image.open(f).convert('RGB')
                        img.thumbnail((800, 800))
                        res = reader.readtext(np.array(img))
                        if not res: 
                            ok = False
                            break
                        txt += " " + " ".join([r[1].upper() for r in res])
                    except:
                        ok = False
                        break
                
                if not ok or not txt.strip():
                    st.error("Photo illisible.")
                    st.stop()

                m_nom = nom in txt
                m_num = last4 in txt
                
                time_ok = True
                if type_s == "Carte Virtuelle":
                    motif = re.search(r'([0-1]?[0-9]|2[0-3])[:\.\sH]([0-5][0-9])', txt)
                    if motif:
                        h_c, m_c = int(motif.group(1)), int(motif.group(2))
                        diff = abs((datetime.now().hour * 60 + datetime.now().minute) - (h_c * 60 + m_c))
                        if diff > 10: time_ok = False
                    else: time_ok = False

                if m_nom and m_num and time_ok:
                    st.success("✅ AUTHENTIQUE")
                    enregistrer_csv(nom, type_s, "VÉRIFIÉ", h)
                    # Certificat simple
                    c = Image.new('RGB', (600, 300), (255, 255, 255))
                    d = ImageDraw.Draw(c)
                    d.text((20, 20), f"CERTIFIE: {nom}", fill=(0,0,0))
                    st.image(c)
                else:
                    st.error("❌ ÉCHEC : Données non trouvées ou heure expirée.")
        else:
            st.warning("Champs manquants.")

with tab2:
    if st.text_input("PASS", type="password") == "ADMIN123":
        if os.path.exists("registre.csv"):
            st.dataframe(pd.read_csv("registre.csv"))
