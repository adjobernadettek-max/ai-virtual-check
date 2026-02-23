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

# --- 1. FONCTIONS DE SÉCURITÉ MATHÉMATIQUE ---
def check_luhn(n):
    r = [int(d) for d in str(n) if d.isdigit()]
    if not r: return False
    return sum(r[-1::-2] + [sum(divmod(d * 2, 10)) for d in r[-2::-2]]) % 10 == 0

def check_bank_database(bin_6):
    try:
        response = requests.get(f"https://lookup.binlist.net/{bin_6}", timeout=5)
        if response.status_code == 200:
            data = response.json()
            bank = data.get('bank', {}).get('name', 'Banque Inconnue')
            country = data.get('country', {}).get('name', 'ID')
            return True, f"{bank} ({country})"
        return False, "Banque Non Répertoriée"
    except: return True, "Vérification Offline"

# --- 2. ANALYSE D'IMAGE AVANCÉE ---
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
        if hash_actuel in df["HASH_IMAGE"].values: return False
    return True

def analyser_texture(file):
    try:
        img = Image.open(file).convert('L')
        if ImageStat.Stat(img).stddev[0] < 15: return False
        return True
    except: return True

def analyser_bruit_compression(file):
    try:
        img = Image.open(file).convert('RGB')
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=90)
        buf.seek(0)
        img_comp = Image.open(buf)
        diff = ImageChops.difference(img, img_comp)
        if ImageStat.Stat(diff).mean[0] > 10: return False
        return True
    except: return True

def analyser_origine_image(file):
    try:
        img = Image.open(file)
        return True if (img._getexif() or img.format in ["PNG", "JPEG"]) else False
    except: return True

# --- 3. SYSTÈME ET REGISTRE ---
def generer_empreinte_image(file):
    return hashlib.sha256(file.getvalue()).hexdigest()

def enregistrer_dans_registre(nom, support, banque, hash_img):
    DB_FILE = "registre_securise.csv"
    entree = pd.DataFrame([{"DATE": datetime.now().strftime("%d/%m/%Y %H:%M"), "TITULAIRE": nom, "SUPPORT": support, "BANQUE": banque, "HASH_IMAGE": hash_img, "ID_CERT": str(uuid.uuid4())[:8].upper()}])
    if not os.path.isfile(DB_FILE): entree.to_csv(DB_FILE, index=False)
    else: entree.to_csv(DB_FILE, mode='a', header=False, index=False)

# --- 4. INTERFACE STREAMLIT ---
st.set_page_config(page_title="FBS AUDIT IA V9.0", layout="wide")
@st.cache_resource
def load_ocr(): return easyocr.Reader(['en'], gpu=False)
lecteur = load_ocr()

st.title("🔐 Terminal d'Audit IA - FBS Forteresse V9.0")
st.markdown("---")

tab1, tab2 = st.tabs(["👤 CERTIFICATION", "🏢 ADMIN"])

with tab1:
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("📋 Informations")
        type_s = st.selectbox("TYPE DE SUPPORT", ["Carte Physique", "Carte Virtuelle"])
        nom_c = st.text_input("NOM COMPLET SUR LA CARTE").upper().strip()
        num_c = st.text_input("NUMÉRO DE CARTE (16 CHIFFRES)", max_chars=16).replace(" ", "")

    st.subheader("📸 Preuves Numériques")
    if type_s == "Carte Physique":
        c_r, c_v = st.columns(2)
        f_recto = c_r.file_uploader("PHOTO RECTO", type=['png', 'jpg', 'jpeg'])
        f_verso = c_v.file_uploader("PHOTO VERSO", type=['png', 'jpg', 'jpeg'])
        f_list = [f_recto, f_verso] if (f_recto and f_verso) else []
    else:
        f_virt = st.file_uploader("SCREENSHOT CARTE VIRTUELLE", type=['png', 'jpg', 'jpeg'])
        f_list = [f_virt] if f_virt else []

    if st.button("🚀 LANCER L'AUDIT DE SÉCURITÉ"):
        if f_list and nom_c and len(num_c) == 16:
            with st.status("Analyse des 9 couches de sécurité...", expanded=True) as status:
                tout_texte = ""
                img_checks = True
                h_img = generer_empreinte_image(f_list[0])
                
                for f in f_list:
                    img_p = Image.open(f).convert('RGB')
                    res = lecteur.readtext(np.array(img_p))
                    tout_texte += " " + " ".join([r[1].upper() for r in res])
                    if not (detecter_retouche(f) and analyser_texture(f) and analyser_bruit_compression(f) and analyser_origine_image(f)):
                        img_checks = False

                # Validations logiques
                luhn_ok = check_luhn(num_c)
                bin_ok, info_b = check_bank_database(num_c[:6])
                doublon_ok = verifier_doublon(h_img)
                match_data = (nom_c in tout_texte) and (num_c in tout_texte.replace(" ", ""))
                
                # Heure < 10min
                sync_ok, h_trouvee = False, "N/A"
                motif = re.search(r'([0-1]?[0-9]|2[0-3])[:\.\sH]([0-5][0-9])', tout_texte)
                if motif:
                    h, m = int(motif.group(1)), int(motif.group(2))
                    h_trouvee = f"{h:02d}:{m:02d}"
                    if abs((datetime.now().hour * 60 + datetime.now().minute) - (h * 60 + m)) <= 10: sync_ok = True

                status.update(label="Audit terminé", state="complete")

            if match_data and sync_ok and luhn_ok and bin_ok and img_checks and doublon_ok:
                st.balloons()
                st.success(f"✅ AUDIT VALIDÉ : {info_b}")
                enregistrer_dans_registre(nom_c, type_s, info_b, h_img)

                # CERTIFICAT DESIGN
                cert = Image.new('RGB', (1200, 800), (255, 255, 255))
                d = ImageDraw.Draw(cert)
                d.rectangle([20, 20, 1180, 780], outline=(0, 100, 0), width=20)
                
                # FILIGRANE
                fili = Image.new('RGBA', (1200, 800), (0,0,0,0))
                ImageDraw.Draw(fili).text((250, 350), "AUDIT OFFICIEL FBS", fill=(230, 230, 230, 120))
                cert.paste(fili.rotate(30), (0,0), fili.rotate(30))

                y = 200
                for line in [f"TITULAIRE : {nom_c}", f"BANQUE : {info_b}", "SÉCURITÉ : V9.0 (STRICT)", f"HEURE : {h_trouvee}"]:
                    d.text((100, y), line, fill=(0,0,0))
                    y += 80

                qr = qrcode.make(f"FBS-V9-{h_img[:10]}").resize((200, 200)).convert('RGB')
                cert.paste(qr, (900, 550))
                st.image(cert, use_container_width=True)
                
                buf = io.BytesIO()
                cert.save(buf, format="PNG")
                st.download_button("📥 TÉLÉCHARGER LE CERTIFICAT", buf.getvalue(), f"Audit_{nom_c}.png")
            else:
                st.error("❌ ÉCHEC DE L'AUDIT")
                if not doublon_ok: st.warning("🚨 DOUBLE USAGE : Cette image est déjà enregistrée.")
                if not sync_ok: st.warning(f"🚨 HEURE : Screenshot expiré ou non détecté ({h_trouvee}).")
                if not match_data: st.warning("🚨 OCR : Les données de la carte ne correspondent pas au formulaire.")
                if not img_checks: st.warning("🚨 FRAUDE IMAGE : Texture ou compression suspecte.")
        else:
            st.warning("⚠️ Données ou images manquantes (Recto/Verso obligatoires pour Physique).")

with tab2:
    if st.text_input("CODE ADMIN", type="password") == "ADMIN123":
        if os.path.exists("registre_securise.csv"): st.dataframe(pd.read_csv("registre_securise.csv"))
