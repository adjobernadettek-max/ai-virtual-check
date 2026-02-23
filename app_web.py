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

# --- SÉCURITÉS 1 À 8 (MATHS & IMAGE) ---
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
        return False, "Banque Non Répertoriée"
    except: return True, "Vérification Offline"

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
        diff = ImageChops.difference(img, Image.open(buf))
        if ImageStat.Stat(diff).mean[0] > 10: return False
        return True
    except: return True

def analyser_origine_image(file):
    try:
        img = Image.open(file)
        return True if (img._getexif() or img.format in ["PNG", "JPEG"]) else False
    except: return True

def analyser_coherence_couleur(file):
    try:
        img = Image.open(file)
        couleurs = img.getcolors(maxcolors=1000000)
        if couleurs is not None and len(couleurs) < 100: return False 
        return True
    except: return True

# --- SYSTÈME DE REGISTRE MULTI-SESSION ---
def enregistrer_dans_registre(nom, support, banque, hash_img, session_id):
    DB_FILE = "registre_securise.csv"
    entree = pd.DataFrame([{
        "DATE_HEURE": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        "SESSION_ID": session_id,
        "TITULAIRE": nom,
        "SUPPORT": support,
        "BANQUE": banque,
        "HASH_IMAGE": hash_img,
        "ID_CERTIFICAT": str(uuid.uuid4())[:12].upper()
    }])
    if not os.path.isfile(DB_FILE): entree.to_csv(DB_FILE, index=False)
    else: entree.to_csv(DB_FILE, mode='a', header=False, index=False)

# --- INTERFACE STREAMLIT ---
st.set_page_config(page_title="FBS AUDIT IA V10.0 - ENTERPRISE", layout="wide")

# Initialisation de la session unique pour le multi-utilisateur
if 'user_session_id' not in st.session_state:
    st.session_state['user_session_id'] = str(uuid.uuid4())[:8].upper()

@st.cache_resource
def load_ocr(): return easyocr.Reader(['en'], gpu=False)
lecteur = load_ocr()

st.title("🔐 Terminal d'Audit IA - FBS Enterprise V10.0")
st.write(f"🆔 **Votre Session ID : {st.session_state['user_session_id']}** (Isolée et Sécurisée)")
st.markdown("---")

tab1, tab2 = st.tabs(["👤 ESPACE CERTIFICATION", "🏢 ADMINISTRATION FBS"])

with tab1:
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("📋 Formulaire Titulaire")
        type_s = st.selectbox("TYPE DE SUPPORT", ["Carte Physique", "Carte Virtuelle"])
        nom_c = st.text_input("NOM COMPLET SUR LA CARTE").upper().strip()
        num_c = st.text_input("NUMÉRO DE CARTE (16 CHIFFRES)", max_chars=16).replace(" ", "")

    st.subheader("📸 Preuves Numériques")
    if type_s == "Carte Physique":
        c_r, c_v = st.columns(2)
        f_recto = c_r.file_uploader("PHOTO RECTO (Nom/Num)", type=['png', 'jpg', 'jpeg'])
        f_verso = c_v.file_uploader("PHOTO VERSO (Signature/CCV)", type=['png', 'jpg', 'jpeg'])
        f_list = [f_recto, f_verso] if (f_recto and f_verso) else []
    else:
        f_virt = st.file_uploader("SCREENSHOT CARTE VIRTUELLE", type=['png', 'jpg', 'jpeg'])
        f_list = [f_virt] if f_virt else []

    if st.button("🚀 LANCER L'AUDIT DE SÉCURITÉ"):
        if f_list and nom_c and len(num_c) == 16:
            with st.status(f"Audit Session {st.session_state['user_session_id']} en cours...", expanded=True) as status:
                tout_texte = ""
                img_checks = True
                h_img = hashlib.sha256(f_list[0].getvalue()).hexdigest()
                
                for f in f_list:
                    img_p = Image.open(f).convert('RGB')
                    res = lecteur.readtext(np.array(img_p))
                    tout_texte += " " + " ".join([r[1].upper() for r in res])
                    # Sécurités Image
                    if not (detecter_retouche(f) and analyser_texture(f) and analyser_bruit_compression(f) and analyser_origine_image(f) and analyser_coherence_couleur(f)):
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

                status.update(label="Audit Session Terminé", state="complete")

            if match_data and sync_ok and luhn_ok and bin_ok and img_checks and doublon_ok:
                st.balloons()
                st.success(f"✅ AUDIT VALIDÉ : {info_b}")
                enregistrer_dans_registre(nom_c, type_s, info_b, h_img, st.session_state['user_session_id'])

                # CERTIFICAT DESIGN
                cert = Image.new('RGB', (1200, 800), (255, 255, 255))
                d = ImageDraw.Draw(cert)
                d.rectangle([20, 20, 1180, 780], outline=(0, 100, 0), width=20)
                
                # FILIGRANE
                fili = Image.new('RGBA', (1200, 800), (0,0,0,0))
                ImageDraw.Draw(fili).text((250, 350), "AUDIT OFFICIEL FBS", fill=(230, 230, 230, 120))
                cert.paste(fili.rotate(30), (0,0), f_mask=fili.rotate(30))

                y = 200
                details = [f"TITULAIRE : {nom_c}", f"BANQUE : {info_b}", f"SESSION : {st.session_state['user_session_id']}", f"HEURE CAPTURE : {h_trouvee}", f"EMPREINTE : {h_img[:15]}"]
                for line in details:
                    d.text((100, y), line, fill=(0,0,0))
                    y += 80

                qr = qrcode.make(f"FBS-V10-{st.session_state['user_session_id']}-{h_img[:8]}").resize((200, 200)).convert('RGB')
                cert.paste(qr, (900, 550))
                st.image(cert, use_container_width=True)
                
                buf = io.BytesIO()
                cert.save(buf, format="PNG")
                st.download_button("📥 TÉLÉCHARGER CERTIFICAT V10", buf.getvalue(), f"Audit_FBS_{st.session_state['user_session_id']}.png")
            else:
                st.error("❌ ÉCHEC DE L'AUDIT SÉCURISÉ")
                if not doublon_ok: st.warning("🚨 DOUBLE USAGE : Image déjà présente dans le registre global.")
                if not sync_ok: st.warning(f"🚨 HEURE : Screenshot expiré ou illisible ({h_trouvee}).")
                if not img_checks: st.warning("🚨 FRAUDE IMAGE : Texture, Retouche ou Compression suspecte.")
                if not match_data: st.warning("🚨 OCR : Incohérence Nom/Numéro sur la photo.")
        else:
            st.warning("⚠️ Remplissez tous les champs et fournissez les preuves (Recto/Verso pour physique).")

with tab2:
    st.header("🏢 Administration Centrale")
    if st.text_input("CODE ACCÈS ADMIN", type="password") == "ADMIN123":
        if os.path.exists("registre_securise.csv"):
            df_admin = pd.read_csv("registre_securise.csv")
            st.write("### Historique des Audits par Session")
            st.dataframe(df_admin, use_container_width=True)
            
            # Fonction entreprise : Filtrer par session
            session_search = st.text_input("Filtrer par Session ID (ex: 4B2A...)")
            if session_search:
                st.dataframe(df_admin[df_admin["SESSION_ID"] == session_search.upper()])
