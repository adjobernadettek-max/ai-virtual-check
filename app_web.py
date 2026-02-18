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

# --- FONCTIONS DE BASE STABLES ---

def generer_empreinte_image(image_file):
    return hashlib.sha256(image_file.getvalue()).hexdigest()

def enregistrer_dans_registre(nom, support, banque, hash_img):
    """Sauvegarde locale uniquement (CSV) - Zéro risque de bug cloud"""
    DB_FILE = "registre_securise.csv"
    nouvelle_entree = pd.DataFrame([{
        "DATE_HEURE": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        "TITULAIRE": nom,
        "SUPPORT": support,
        "BANQUE": banque,
        "HASH_IMAGE": hash_img,
        "ID_CERTIFICAT": str(uuid.uuid4())[:8]
    }])
    if not os.path.isfile(DB_FILE):
        nouvelle_entree.to_csv(DB_FILE, index=False)
    else:
        nouvelle_entree.to_csv(DB_FILE, mode='a', header=False, index=False)

# --- CONFIGURATION INTERFACE ---
st.set_page_config(page_title="IA SÉCURITÉ", layout="wide")

@st.cache_resource
def load_reader():
    return easyocr.Reader(['en'])
reader = load_reader()

st.title("🔐 Terminal d'Audit Stable")

onglet_actif = st.tabs(["👤 INTERFACE CLIENT", "🏢 ESPACE ENTREPRISE"])

# ==========================================
# 1. INTERFACE CLIENT
# ==========================================
with onglet_actif[0]:
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.subheader("📋 Formulaire")
        type_support = st.selectbox("TYPE DE SUPPORT", ["Carte Physique", "Carte Virtuelle"])
        nom_complet = st.text_input("NOM COMPLET", "").upper().strip()
        num_complet = st.text_input("NUMÉRO DE CARTE (16 CHIFFRES)", max_chars=19)
        
        last_4 = num_complet[-4:] if num_complet else ""

        fichiers_a_analyser = []
        if type_support == "Carte Virtuelle":
            fichier_v = st.file_uploader("Upload screenshot", type=['png', 'jpg', 'jpeg'])
            if fichier_v: fichiers_a_analyser = [fichier_v]
        else:
            recto = st.file_uploader("Recto", type=['png', 'jpg', 'jpeg'])
            verso = st.file_uploader("Verso", type=['png', 'jpg', 'jpeg'])
            fichiers_a_analyser = [f for f in [recto, verso] if f is not None]

    if st.button("🚀 LANCER LA VÉRIFICATION"):
        if len(fichiers_a_analyser) > 0 and nom_complet and last_4:
            with st.status("Analyse en cours...", expanded=True) as status:
                
                hash_actuel = generer_empreinte_image(fichiers_a_analyser[0])
                tous_les_textes = ""
                lecture_reussie = True
                
                for f in fichiers_a_analyser:
                    try:
                        img_np = np.array(Image.open(f))
                        res_ocr = reader.readtext(img_np)
                        if not res_ocr:
                            lecture_reussie = False
                            break
                        tous_les_textes += " " + " ".join([r[1].upper() for r in res_ocr])
                    except:
                        lecture_reussie = False
                        break

                if not lecture_reussie or not tous_les_textes.strip():
                    st.error("⚠️ Photo illisible ou trop floue.")
                    st.stop()

                # Validation
                match_nom = nom_complet in tous_les_textes
                match_chiffres = last_4 in tous_les_textes
                
                # Sécurité 10 min (Uniquement pour Virtuelle)
                sync_ok, heure_trouvee = True, "N/A"
                if type_support == "Carte Virtuelle":
                    motif = re.search(r'([0-1]?[0-9]|2[0-3])[:\.\sH]([0-5][0-9])', tous_les_textes)
                    if motif:
                        h, m = int(motif.group(1)), int(motif.group(2))
                        heure_trouvee = f"{h:02d}:{m:02d}"
                        diff = abs((datetime.now().hour * 60 + datetime.now().minute) - (h * 60 + m))
                        if diff > 10: sync_ok = False
                    else: sync_ok = False

                status.update(label="Analyse terminée", state="complete")

            if match_nom and match_chiffres and sync_ok:
                st.balloons()
                st.success("✅ AUDIT VALIDÉ")
                enregistrer_dans_registre(nom_complet, type_support, "VÉRIFIÉ", hash_actuel)
                
                # Certificat simplifié (Plus robuste)
                cert = Image.new('RGB', (800, 400), color=(255, 255, 255))
                d = ImageDraw.Draw(cert)
                d.text((50, 50), f"CERTIFICAT POUR : {nom_complet}", fill=(0,0,0))
                d.text((50, 100), f"SUPPORT : {type_support}", fill=(0,0,0))
                d.text((50, 150), f"CARTE : **** {last_4}", fill=(0,0,0))
                
                qr = qrcode.make(f"ID-{hash_actuel[:10]}").resize((100, 100))
                cert.paste(qr, (650, 250))
                st.image(cert)
            else:
                st.error("❌ ÉCHEC : Les données ne correspondent pas ou l'heure est expirée.")
        else:
            st.warning("⚠️ Remplissez tous les champs.")

# ==========================================
# 2. ESPACE ENTREPRISE
# ==========================================
with onglet_actif[1]:
    st.header("🏢 Admin")
    if st.text_input("CODE", type="password") == "ADMIN123":
        if os.path.exists("registre_securise.csv"):
            df = pd.read_csv("registre_securise.csv")
            st.dataframe(df)
