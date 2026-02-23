import streamlit as st
import easyocr
from PIL import Image, ImageDraw, ImageFont, ImageStat, ImageChops
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

# --- 1. SÉCURITÉS (Luhn, Bank, Forensic) ---
def check_luhn(n):
    r = [int(d) for d in str(n) if d.isdigit()]
    if not r: return False
    return sum(r[-1::-2] + [sum(divmod(d * 2, 10)) for d in r[-2::-2]]) % 10 == 0

def check_bank_database(bin_6):
    try:
        response = requests.get(f"https://lookup.binlist.net/{bin_6}", timeout=5)
        if response.status_code == 200:
            data = response.json()
            return True, f"{data.get('bank', {}).get('name', 'Banque')} ({data.get('country', {}).get('name', 'ID')})"
        return False, "Banque Inconnue"
    except: return True, "Mode Offline"

def detecter_retouche(file):
    try:
        img = Image.open(file)
        logiciels = ["photoshop", "gimp", "canva", "picsart", "adobe", "editor", "paint"]
        for key, value in img.info.items():
            if any(l in str(value).lower() for l in logiciels): return False
        return True
    except: return True

def verifier_doublon(hash_actuel):
    DB_FILE = "registre_securise.csv"
    if os.path.exists(DB_FILE):
        df = pd.read_csv(DB_FILE)
        if "HASH_IMAGE" in df.columns and hash_actuel in df["HASH_IMAGE"].values: return False
    return True

# --- 2. GESTION DES REGISTRES ---
def enregistrer_fraude(session_id, motif, nom_suspect):
    FRAUDE_FILE = "blacklist_fraudeurs.csv"
    infractions = pd.DataFrame([{"DATE": datetime.now().strftime("%d/%m/%Y %H:%M"), "SESSION": session_id, "NOM": nom_suspect, "MOTIF": motif}])
    if not os.path.isfile(FRAUDE_FILE): infractions.to_csv(FRAUDE_FILE, index=False)
    else: infractions.to_csv(FRAUDE_FILE, mode='a', header=False, index=False)

def enregistrer_dans_registre(nom, support, banque, hash_img, session_id):
    DB_FILE = "registre_securise.csv"
    entree = pd.DataFrame([{"DATE_HEURE": datetime.now().strftime("%d/%m/%Y %H:%M"), "SESSION_ID": session_id, "TITULAIRE": nom, "SUPPORT": support, "BANQUE": banque, "HASH_IMAGE": hash_img, "ID_CERT": str(uuid.uuid4())[:12].upper()}])
    if not os.path.isfile(DB_FILE): entree.to_csv(DB_FILE, index=False)
    else: entree.to_csv(DB_FILE, mode='a', header=False, index=False)

# --- 3. INTERFACE PRINCIPALE ---
st.set_page_config(page_title="FBS AUDIT V11.2", layout="wide")

if 'user_session_id' not in st.session_state:
    st.session_state['user_session_id'] = str(uuid.uuid4())[:8].upper()

@st.cache_resource
def load_ocr(): return easyocr.Reader(['en'], gpu=False)
lecteur = load_ocr()

st.title("🔐 Terminal d'Audit IA - FBS Forensic V11.2")
st.write(f"🆔 **ID Session : {st.session_state['user_session_id']}**")

tab1, tab2 = st.tabs(["👤 CERTIFICATION", "🏢 CENTRE DE SÉCURITÉ"])

with tab1:
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("📋 Formulaire")
        type_s = st.selectbox("SUPPORT", ["Carte Physique", "Carte Virtuelle"])
        nom_c = st.text_input("NOM SUR LA CARTE").upper().strip()
        num_c = st.text_input("NUMÉRO (16 CHIFFRES)", max_chars=16).replace(" ", "")

    st.subheader("📸 Preuves")
    if type_s == "Carte Physique":
        c_r, c_v = st.columns(2)
        f_recto = c_r.file_uploader("RECTO", type=['png', 'jpg', 'jpeg'])
        f_verso = c_v.file_uploader("VERSO", type=['png', 'jpg', 'jpeg'])
        f_list = [f_recto, f_verso] if (f_recto and f_verso) else []
    else:
        f_virt = st.file_uploader("SCREENSHOT", type=['png', 'jpg', 'jpeg'])
        f_list = [f_virt] if f_virt else []

    if st.button("🚀 LANCER L'AUDIT SÉCURISÉ"):
        if f_list and nom_c and len(num_c) == 16:
            with st.status("Audit Forensic en cours...", expanded=True) as status:
                tout_texte, img_checks = "", True
                h_img = hashlib.sha256(f_list[0].getvalue()).hexdigest()
                
                try:
                    for f in f_list:
                        img_p = Image.open(f).convert('RGB')
                        res = lecteur.readtext(np.array(img_p))
                        tout_texte += " " + " ".join([r[1].upper() for r in res])
                        if not detecter_retouche(f): img_checks = False
                except Exception as e:
                    st.error(f"Erreur de lecture image : {e}")
                    img_checks = False

                luhn_ok = check_luhn(num_c)
                bin_ok, info_b = check_bank_database(num_c[:6])
                doublon_ok = verifier_doublon(h_img)
                match_data = (nom_c in tout_texte) and (num_c in tout_texte.replace(" ", ""))
                
                sync_ok = False
                motif_h = re.search(r'([0-1]?[0-9]|2[0-3])[:\.\sH]([0-5][0-9])', tout_texte)
                if motif_h:
                    h, m = int(motif_h.group(1)), int(motif_h.group(2))
                    if abs((datetime.now().hour * 60 + datetime.now().minute) - (h * 60 + m)) <= 15: sync_ok = True
                
                status.update(label="Audit Terminé", state="complete")

            if match_data and sync_ok and luhn_ok and bin_ok and img_checks and doublon_ok:
                st.balloons()
                enregistrer_dans_registre(nom_c, type_s, info_b, h_img, st.session_state['user_session_id'])
                
                # --- GÉNÉRATION CERTIFICAT HD ---
                cert = Image.new('RGB', (1200, 900), (255, 255, 255))
                draw = ImageDraw.Draw(cert)
                draw.rectangle([20, 20, 1180, 880], outline=(0, 100, 0), width=25)
                
                # Filigrane
                fili = Image.new('RGBA', (1200, 900), (0,0,0,0))
                ImageDraw.Draw(fili).text((150, 400), "AUDIT FBS SÉCURISÉ", fill=(230, 230, 230, 120))
                f_rot = fili.rotate(30); cert.paste(f_rot, (0,0), mask=f_rot)

                # Titre et Détails
                draw.text((400, 80), "CERTIFICAT D'AUDIT OFFICIEL", fill=(0, 100, 0))
                y_pos = 200
                details = [
                    f"STATUT : VALIDÉ ET CERTIFIÉ",
                    f"TITULAIRE : {nom_c}",
                    f"BANQUE : {info_b[:35]}", # Limite pour éviter dépassement
                    f"SESSION ID : {st.session_state['user_session_id']}",
                    f"EMPREINTE : {h_img[:20].upper()}",
                    f"DATE : {datetime.now().strftime('%d/%m/%Y %H:%M')}"
                ]
                for line in details:
                    for offset in range(2): # Effet gras
                        draw.text((80 + offset, y_pos), line, fill=(0,0,0))
                    y_pos += 95 

                qr = qrcode.make(f"FBS-V11-{h_img[:12]}").resize((280, 280)).convert('RGB')
                cert.paste(qr, (850, 550))
                
                st.image(cert, use_container_width=True)
                buf = io.BytesIO()
                cert.save(buf, format="PNG")
                st.download_button("📥 TÉLÉCHARGER LE CERTIFICAT HD", buf.getvalue(), f"Audit_{nom_c}.png")
            else:
                st.error("❌ ÉCHEC DE L'AUDIT SÉCURISÉ")
                enregistrer_fraude(st.session_state['user_session_id'], "Incohérence ou Fraude", nom_c)
                if not match_data: st.warning("Le nom ou numéro ne correspond pas à l'image.")
                if not sync_ok: st.warning("L'heure de la capture est invalide ou trop ancienne.")

with tab2:
    if st.text_input("ADMIN ACCÈS", type="password") == "ADMIN123":
        if os.path.exists("registre_securise.csv"): 
            st.write("### ✅ Audits")
            st.dataframe(pd.read_csv("registre_securise.csv"), use_container_width=True)
        if os.path.exists("blacklist_fraudeurs.csv"): 
            st.write("### 🚨 Fraudes")
            st.dataframe(pd.read_csv("blacklist_fraudeurs.csv"), use_container_width=True)
