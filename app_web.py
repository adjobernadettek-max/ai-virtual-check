import streamlit as st
import easyocr
from PIL import Image, ImageDraw
import qrcode
from datetime import datetime
import numpy as np
import time
import uuid
import re
import requests
import pandas as pd
import os
import hashlib
import io

# --- FONCTIONS DE SÉCURITÉ ET REGISTRE ---

def generer_empreinte_image(image_file):
    """Crée une signature unique pour bloquer les doublons"""
    return hashlib.sha256(image_file.getvalue()).hexdigest()

def check_bank_database(bin_6):
    """Vérification de l'émetteur via API"""
    try:
        response = requests.get(f"https://lookup.binlist.net/{bin_6}", timeout=5)
        if response.status_code == 200: return response.json()
    except: return None
    return None

def enregistrer_dans_registre(nom, support, banque, hash_img):
    """Sauvegarde dans le fichier CSV pour l'entreprise"""
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
st.set_page_config(page_title="IA SÉCURITÉ MAXIMALE", layout="wide")

@st.cache_resource
def load_reader():
    return easyocr.Reader(['en'])
reader = load_reader()

st.title("🔐 Terminal d'Audit Haute Sécurité")

# CRÉATION DES DEUX INTERFACES SÉPARÉES
onglet_actif = st.tabs(["👤 INTERFACE CLIENT", "🏢 ESPACE ENTREPRISE"])

# ==========================================
# 1. INTERFACE CLIENT
# ==========================================
with onglet_actif[0]:
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.subheader("📋 Formulaire de Certification")
        type_support = st.selectbox("TYPE DE SUPPORT", ["Carte Virtuelle", "Carte Physique"])
        nom_complet = st.text_input("NOM COMPLET DU TITULAIRE", "").upper().strip()
        num_complet = st.text_input("NUMÉRO DE CARTE (16 CHIFFRES)", max_chars=19)
        
        bin_6 = num_complet[:6] if num_complet else ""
        last_4 = num_complet[-4:] if num_complet else ""

        fichiers_a_analyser = []
        if type_support == "Carte Virtuelle":
            st.info("💡 **Condition :** Capture d'écran avec heure visible (Max 10 min).")
            fichier_v = st.file_uploader("Upload screenshot", type=['png', 'jpg', 'jpeg'], key="cl_v")
            if fichier_v: fichiers_a_analyser = [fichier_v]
        else:
            st.info("💡 **Condition :** Recto et Verso obligatoires.")
            recto = st.file_uploader("Côté Face (Recto)", type=['png', 'jpg', 'jpeg'], key="cl_r")
            verso = st.file_uploader("Côté Pile (Verso)", type=['png', 'jpg', 'jpeg'], key="cl_p")
            fichiers_a_analyser = [f for f in [recto, verso] if f is not None]

    if st.button("🚀 LANCER LA VÉRIFICATION"):
        if len(fichiers_a_analyser) > 0 and nom_complet and last_4:
            with st.status("Analyse OCR et Sécurité temporelle...", expanded=True) as status:
                
                # 1. Signature de l'image
                hash_actuel = generer_empreinte_image(fichiers_a_analyser[0])
                
                # 2. Analyse OCR
                tous_les_textes = ""
                for f in fichiers_a_analyser:
                    img_np = np.array(Image.open(f))
                    res_ocr = reader.readtext(img_np)
                    tous_les_textes += " " + " ".join([r[1].upper() for r in res_ocr])
                
                # 3. Validation Nom et Chiffres
                match_nom = nom_complet in tous_les_textes
                match_chiffres = last_4 in tous_les_textes
                
                # 4. SÉCURITÉ TEMPORELLE (STRICTE 10 MIN)
                sync_ok, heure_trouvee = True, "N/A"
                if type_support == "Carte Virtuelle":
                    motif = re.search(r'([0-1]?[0-9]|2[0-3])[:\.\sH]([0-5][0-9])', tous_les_textes)
                    if motif:
                        h, m = int(motif.group(1)), int(motif.group(2))
                        heure_trouvee = f"{h:02d}:{m:02d}"
                        maintenant = datetime.now()
                        diff = abs((maintenant.hour * 60 + maintenant.minute) - (h * 60 + m))
                        if diff > 10: sync_ok = False
                    else:
                        sync_ok = False

                status.update(label="Analyse terminée", state="complete")

            if match_nom and match_chiffres and sync_ok:
                # RÉCUPÉRATION BANQUE
                banque_info = check_bank_database(bin_6)
                nom_b = banque_info.get('bank', {}).get('name', 'INCONNUE') if banque_info else "INCONNUE"
                
                st.balloons()
                st.success("✅ AUDIT VALIDÉ : CARTE AUTHENTIQUE")
                
                # Enregistrement registre
                enregistrer_dans_registre(nom_complet, type_support, nom_b, hash_actuel)
                
                # GÉNÉRATION DU CERTIFICAT (FILIGRANE + TEXTE GRAS)
                cert = Image.new('RGB', (1000, 600), color=(255, 255, 255))
                d = ImageDraw.Draw(cert)
                d.rectangle([10, 10, 990, 590], outline=(0, 128, 0), width=15)

                # Filigrane diagonal
                try:
                    w_txt = "AUDIT OFFICIEL"
                    txt_img = Image.new('RGBA', (900, 300), (255, 255, 255, 0))
                    d_w = ImageDraw.Draw(txt_img)
                    d_w.text((50, 100), w_txt, fill=(235, 235, 235, 150))
                    cert.paste(txt_img.rotate(20, expand=1), (100, 100), txt_img.rotate(20, expand=1))
                except: pass

                def draw_big(draw, pos, text):
                    for o in range(3): draw.text((pos[0]+o, pos[1]), text, fill=(0, 0, 0))

                draw_big(d, (250, 40), "CERTIFICAT D'AUTHENTICITÉ")
                
                y_p = 180
                lignes = [
                    f"TITULAIRE : {nom_complet}",
                    f"SUPPORT : {type_support}",
                    f"BANQUE : {nom_b}",
                    f"CARTE : **** **** **** {last_4}",
                    f"HEURE CAP : {heure_trouvee}"
                ]
                for line in lignes:
                    draw_big(d, (80, y_p), line)
                    y_p += 85
                
                qr = qrcode.make(f"SECURE-{hash_actuel[:15]}").resize((180, 180))
                cert.paste(qr, (780, 380))
                st.image(cert)

                buf = io.BytesIO()
                cert.save(buf, format="PNG")
                st.download_button("📥 TÉLÉCHARGER LE CERTIFICAT (PNG)", buf.getvalue(), f"Certif_{nom_complet}.png", "image/png")
            else:
                st.error("❌ ÉCHEC DE L'AUDIT")
                if not match_nom: st.warning(f"Le nom '{nom_complet}' n'a pas été détecté.")
                if not match_chiffres: st.warning(f"Les chiffres '{last_4}' sont absents.")
                if not sync_ok: st.warning(f"Heure invalide ou trop ancienne ({heure_trouvee}). Max 10 min.")
        else:
            st.warning("⚠️ Veuillez remplir tous les champs et ajouter les images.")

# ==========================================
# 2. ESPACE ENTREPRISE
# ==========================================
with onglet_actif[1]:
    st.header("🏢 Accès Administrateur")
    code = st.text_input("ENTREZ LE CODE D'ACCÈS", type="password")
    
    if code == "ADMIN123":
        if os.path.exists("registre_securise.csv"):
            st.subheader("📜 Registre des Audits")
            df = pd.read_csv("registre_securise.csv")
            st.dataframe(df, use_container_width=True)
            
            st.download_button("📥 EXPORTER LE REGISTRE (CSV)", df.to_csv(index=False), "registre.csv", "text/csv")
        else:
            st.info("Le registre est actuellement vide.")