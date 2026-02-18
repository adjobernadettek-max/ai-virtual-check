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

# --- FONCTIONS TECHNIQUES ---
def generer_empreinte(image_file):
    return hashlib.sha256(image_file.getvalue()).hexdigest()

def check_bank(bin_6):
    try:
        r = requests.get(f"https://lookup.binlist.net/{bin_6}", timeout=3)
        if r.status_code == 200: return r.json()
    except: return None
    return None

def save_csv(nom, support, banque, h):
    f = "registre_securise.csv"
    d = pd.DataFrame([{"DATE": datetime.now().strftime("%d/%m/%Y %H:%M"), "NOM": nom, "TYPE": support, "BANQUE": banque, "HASH": h}])
    try:
        if not os.path.isfile(f): d.to_csv(f, index=False)
        else: d.to_csv(f, mode='a', header=False, index=False)
    except: pass

# --- CONFIGURATION ---
st.set_page_config(page_title="IA AUDIT PRO", layout="wide")

@st.cache_resource
def load_ocr():
    return easyocr.Reader(['en'], gpu=False)
reader = load_ocr()

st.title("🔐 Terminal d'Audit Haute Sécurité")

tab1, tab2 = st.tabs(["👤 INTERFACE CLIENT", "🏢 ADMIN"])

with tab1:
    col1, col2 = st.columns([1, 1])
    with col1:
        st.subheader("📋 Formulaire")
        t_sup = st.selectbox("TYPE DE SUPPORT", ["Carte Physique", "Carte Virtuelle"])
        nom = st.text_input("NOM DU TITULAIRE", "").upper().strip()
        num = st.text_input("NUMÉRO DE CARTE", max_chars=19)
        last4 = num[-4:] if num else ""
        bin6 = num[:6] if num else ""

        fichiers = []
        if t_sup == "Carte Virtuelle":
            f = st.file_uploader("Screenshot", type=['png', 'jpg', 'jpeg'])
            if f: fichiers = [f]
        else:
            r = st.file_uploader("Recto", type=['png', 'jpg', 'jpeg'])
            v = st.file_uploader("Verso", type=['png', 'jpg', 'jpeg'])
            fichiers = [i for i in [r, v] if i]

    if st.button("🚀 LANCER LA VÉRIFICATION"):
        if fichiers and nom and last4:
            with st.status("Analyse en cours...") as status:
                h_img = generer_empreinte(fichiers[0])
                full_txt = ""
                ocr_ok = True
                for f in fichiers:
                    try:
                        img = Image.open(f).convert('RGB')
                        img.thumbnail((1000, 1000))
                        res = reader.readtext(np.array(img))
                        if not res: ocr_ok = False; break
                        full_txt += " " + " ".join([r[1].upper() for r in res])
                    except: ocr_ok = False; break
                
                if not ocr_ok or not full_txt.strip():
                    st.error("⚠️ Image illisible.")
                    st.stop()

                m_nom = nom in full_txt
                m_num = last4 in full_txt
                
                t_ok, h_cap = True, "N/A"
                if t_sup == "Carte Virtuelle":
                    motif = re.search(r'([0-1]?[0-9]|2[0-3])[:\.\sH]([0-5][0-9])', full_txt)
                    if motif:
                        hc, mc = int(motif.group(1)), int(motif.group(2))
                        h_cap = f"{hc:02d}:{mc:02d}"
                        diff = abs((datetime.now().hour * 60 + datetime.now().minute) - (hc * 60 + mc))
                        if diff > 10: t_ok = False
                    else: t_ok = False

                status.update(label="Vérification terminée", state="complete")

            if m_nom and m_num and t_ok:
                b_data = check_bank(bin6)
                n_b = b_data.get('bank', {}).get('name', 'INCONNUE') if b_data else "INCONNUE"
                st.balloons()
                st.success("✅ AUDIT VALIDÉ")
                save_csv(nom, t_sup, n_b, h_img)

                # --- GÉNÉRATION DU CERTIFICAT HAUTE LISIBILITÉ ---
                cert = Image.new('RGB', (1200, 800), color=(255, 255, 255))
                draw = ImageDraw.Draw(cert)
                
                # Cadre Vert Épais
                draw.rectangle([20, 20, 1180, 780], outline=(34, 139, 34), width=20)
                
                # Filigrane
                draw.text((300, 400), "AUDIT OFFICIEL FBS", fill=(240, 240, 240))

                # Titre et Textes en GRAS (via décalage de pixels)
                def draw_bold(d, pos, text, size_mult=1):
                    for off in range(3): # Épaisseur
                        d.text((pos[0]+off, pos[1]), text, fill=(0, 0, 0))

                draw_bold(draw, (350, 60), "--- CERTIFICAT D'AUTHENTICITÉ ---")
                
                y = 220
                infos = [
                    f"TITULAIRE : {nom}",
                    f"SUPPORT : {t_sup}",
                    f"BANQUE : {n_b}",
                    f"CARTE : **** **** **** {last4}",
                    f"CAPTURE : {h_cap}",
                    f"DATE : {datetime.now().strftime('%d/%m/%Y')}",
                    f"ID VERIF : {h_img[:18]}"
                ]
                for line in infos:
                    draw_bold(draw, (120, y), line)
                    y += 80

                # QR Code plus grand
                qr = qrcode.make(f"FBS-VERIF-{h_img[:15]}").resize((220, 220)).convert('RGB')
                cert.paste(qr, (900, 520))

                # Affichage
                st.image(cert, use_container_width=True)
                
                # Bouton de téléchargement
                buf = io.BytesIO()
                cert.save(buf, format="PNG")
                st.download_button(
                    label="📥 TÉLÉCHARGER LE CERTIFICAT (PNG)",
                    data=buf.getvalue(),
                    file_name=f"Certificat_{nom}.png",
                    mime="image/png"
                )
            else:
                st.error("❌ ÉCHEC : Les données ne correspondent pas.")
        else:
            st.warning("⚠️ Complétez tous les champs.")

with tab2:
    if st.text_input("CODE ADMIN", type="password") == "ADMIN123":
        if os.path.exists("registre_securise.csv"):
            st.dataframe(pd.read_csv("registre_securise.csv"))
