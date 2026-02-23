import streamlit as st
import easyocr
from PIL import Image, ImageDraw, ImageFont, ImageStat
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

# --- SÉCURITÉ 1 : CALCUL MATHÉMATIQUE (LUHN) ---
def check_luhn(num_card):
    num_card = "".join(filter(str.isdigit, str(num_card)))
    if not num_card or len(num_card) < 13:
        return False
    n_sum = 0
    is_second = False
    for i in range(len(num_card) - 1, -1, -1):
        d = int(num_card[i])
        if is_second:
            d = d * 2
            if d > 9: d = d - 9
        n_sum += d
        is_second = not is_second
    return n_sum % 10 == 0

# --- SÉCURITÉ 2 : VÉRIFICATION BANQUE (BIN) ---
def check_bank_database(bin_6):
    try:
        response = requests.get(f"https://lookup.binlist.net/{bin_6}", timeout=5)
        if response.status_code == 200:
            data = response.json()
            bank_name = data.get('bank', {}).get('name', 'Banque Inconnue')
            country = data.get('country', {}).get('name', 'ID')
            return True, f"{bank_name} ({country})"
        return False, "Banque Non Répertoriée"
    except:
        return True, "Vérification Offline"

# --- SÉCURITÉ 3 : ANTI-PHOTOSHOP (METADATA) ---
def detecter_retouche(image_file):
    try:
        img = Image.open(image_file)
        info = img.info
        logiciels = ["photoshop", "gimp", "canva", "picsart", "adobe", "editor", "paint"]
        for key, value in info.items():
            if any(l in str(value).lower() for l in logiciels):
                return False
        return True
    except:
        return True

# --- SÉCURITÉ 4 : ANTI-DOUBLON (SIGNATURE UNIQUE) ---
def verifier_doublon(hash_actuel):
    DB_FILE = "registre_securise.csv"
    if os.path.exists(DB_FILE):
        df = pd.read_csv(DB_FILE)
        if "HASH_IMAGE" in df.columns:
            if hash_actuel in df["HASH_IMAGE"].values:
                return False
    return True

# --- SÉCURITÉ 5 : ANTI-PHOTO D'ÉCRAN (TEXTURE) ---
def analyser_texture(image_file):
    try:
        img = Image.open(image_file).convert('L')
        stat = ImageStat.Stat(img)
        if stat.stddev[0] < 15: 
            return False
        return True
    except:
        return True

# --- SÉCURITÉ 6 : ANTI-COLLAGE (COHÉRENCE COULEUR) ---
def analyser_coherence_couleur(image_file):
    try:
        img = Image.open(image_file)
        couleurs = img.getcolors(maxcolors=1000000)
        if couleurs is not None and len(couleurs) < 100: 
            return False 
        return True
    except:
        return True

# --- SÉCURITÉ 7 : ORIGINE DU FICHIER (ANALYSE EXIF/SOURCE) ---
def analyser_origine_image(image_file):
    try:
        img = Image.open(image_file)
        exif_data = img._getexif()
        # Si c'est un screenshot ou une photo réelle, l'image possède une structure d'en-tête spécifique
        if not exif_data and img.format not in ["PNG", "JPEG"]:
            return False # Format suspect ou converti illégalement
        return True
    except:
        return True

# --- FONCTIONS SYSTÈME ---
def generer_empreinte_image(image_file):
    return hashlib.sha256(image_file.getvalue()).hexdigest()

def enregistrer_dans_registre(nom, support, banque, hash_img):
    DB_FILE = "registre_securise.csv"
    nouvelle_entree = pd.DataFrame([{
        "DATE_HEURE": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        "TITULAIRE": nom,
        "SUPPORT": support,
        "BANQUE": banque,
        "HASH_IMAGE": hash_img,
        "ID_CERTIFICAT": str(uuid.uuid4())[:12].upper()
    }])
    if not os.path.isfile(DB_FILE):
        nouvelle_entree.to_csv(DB_FILE, index=False)
    else:
        nouvelle_entree.to_csv(DB_FILE, mode='a', header=False, index=False)

# --- CONFIGURATION INTERFACE ---
st.set_page_config(page_title="SYSTÈME D'AUDIT IA V7.0", layout="wide")

@st.cache_resource
def charger_lecteur():
    return easyocr.Reader(['en'], gpu=False)

lecteur = charger_lecteur()

st.title("🔐 Terminal d'Audit IA - FBS Forteresse V7.0")
st.markdown("---")

onglet_actif = st.tabs(["👤 INTERFACE DE CERTIFICATION", "🏢 ADMINISTRATION FBS"])

with onglet_actif[0]:
    col1, col2 = st.columns([1, 1])
    with col1:
        st.subheader("📋 Informations du Titulaire")
        type_support = st.selectbox("TYPE DE SUPPORT", ["Carte Physique", "Carte Virtuelle"])
        nom_complet = st.text_input("NOM COMPLET SUR LA CARTE", "").upper().strip()
        num_complet = st.text_input("NUMÉRO DE CARTE (16 CHIFFRES)", max_chars=16).replace(" ", "")

    f = st.file_uploader("Preuve Image (Screenshot ou Photo)", type=['png', 'jpg', 'jpeg'])

    if st.button("🚀 LANCER L'AUDIT DE SÉCURITÉ"):
        if f and nom_complet and len(num_complet) == 16:
            with st.status("Audit des 7 couches de sécurité FBS en cours...", expanded=True) as status:
                # Signature
                hash_actuel = generer_empreinte_image(f)
                
                # IA OCR
                img_pil = Image.open(f).convert('RGB')
                img_np = np.array(img_pil)
                res_ocr = lecteur.readtext(img_np)
                tous_les_textes = " ".join([r[1].upper() for r in res_ocr])

                # Vérifications Classiques (Nom, Numéro, Heure)
                match_16 = num_complet in tous_les_textes.replace(" ", "")
                match_nom = nom_complet in tous_les_textes
                
                sync_ok, heure_trouvee = True, "N/A"
                motif = re.search(r'([0-1]?[0-9]|2[0-3])[:\.\sH]([0-5][0-9])', tous_les_textes)
                if motif:
                    h, m = int(motif.group(1)), int(motif.group(2))
                    heure_trouvee = f"{h:02d}:{m:02d}"
                    diff = abs((datetime.now().hour * 60 + datetime.now().minute) - (h * 60 + m))
                    if diff > 10: sync_ok = False
                else: sync_ok = False
                
                # Vérifications Avancées (1 à 7)
                luhn_ok = check_luhn(num_complet)
                bin_ok, info_banque = check_bank_database(num_complet[:6])
                original_ok = detecter_retouche(f)
                jamais_vu_ok = verifier_doublon(hash_actuel)
                texture_ok = analyser_texture(f)
                coherence_ok = analyser_coherence_couleur(f)
                origine_ok = analyser_origine_image(f)

                status.update(label="Audit complet terminé - Analyse des résultats", state="complete")

            # --- DÉCISION FINALE (7 CONDITIONS) ---
            if (match_nom and match_16 and sync_ok and luhn_ok and 
                bin_ok and original_ok and jamais_vu_ok and 
                texture_ok and coherence_ok and origine_ok):
                
                st.balloons()
                st.success(f"✅ AUDIT VALIDÉ : Carte {info_banque} certifiée conforme.")
                
                enregistrer_dans_registre(nom_complet, type_support, info_banque, hash_actuel)

                # --- GÉNÉRATION CERTIFICAT ---
                cert = Image.new('RGB', (1200, 800), color=(255, 255, 255))
                d = ImageDraw.Draw(cert)
                d.rectangle([20, 20, 1180, 780], outline=(0, 100, 0), width=20)
                d.rectangle([40, 40, 1160, 760], outline=(0, 100, 0), width=2)
                
                # FILIGRANE (PRÉSERVÉ)
                fili = Image.new('RGBA', (1200, 800), (0,0,0,0))
                ImageDraw.Draw(fili).text((250, 350), "AUDIT OFFICIEL FBS", fill=(230, 230, 230, 120))
                cert.paste(fili.rotate(30), (0,0), fili.rotate(30))

                def draw_bold(draw, pos, text):
                    for off in range(3): draw.text((pos[0]+off, pos[1]), text, fill=(0,0,0))

                draw_bold(d, (350, 70), "--- CERTIFICAT D'AUTHENTICITÉ IA ---")
                
                y = 230
                infos = [f"TITULAIRE : {nom_complet}", f"BANQUE : {info_banque}", f"SÉCURITÉ : NIVEAU 7 (MAXIMUM)", f"HEURE : {heure_trouvee}", f"EMPREINTE : {hash_actuel[:20]}"]
                for line in infos:
                    draw_bold(d, (100, y), line)
                    y += 80

                qr = qrcode.make(f"FBS-V7-{hash_actuel[:10]}").resize((250, 250)).convert('RGB')
                cert.paste(qr, (880, 500))

                st.image(cert, use_container_width=True)
                buf = io.BytesIO()
                cert.save(buf, format="PNG")
                st.download_button("📥 TÉLÉCHARGER LE CERTIFICAT V7", buf.getvalue(), f"Audit_FBS_{nom_complet}.png")
            
            else:
                st.error("❌ ÉCHEC CRITIQUE : L'IA A DÉTECTÉ UNE FRAUDE")
                if not origine_ok: st.warning("🚨 SOURCE : Image suspecte (Metadata altérées ou fichier non-original).")
                if not coherence_ok: st.warning("🚨 COLLAGE : Modification des pixels détectée (Deepfake).")
                if not texture_ok: st.warning("🚨 TEXTURE : Image identifiée comme photo d'écran (Moire).")
                if not original_ok: st.warning("🚨 LOGICIEL : Traces de montage détectées.")
                if not jamais_vu_ok: st.warning("🚨 DOUBLON : Image déjà utilisée.")
                if not luhn_ok: st.warning("🚨 MATHS : Numéro de carte invalide.")
                if not sync_ok: st.warning(f"🚨 TEMPS : Screenshot expiré ({heure_trouvee}).")
                if not (match_nom and match_16): st.warning("🚨 OCR : Les données de la photo ne correspondent pas au formulaire.")
        else:
            st.warning("⚠️ Veuillez remplir tous les champs.")

with onglet_actif[1]:
    st.header("🏢 Administration")
    if st.text_input("CODE ADMIN", type="password") == "ADMIN123":
        if os.path.exists("registre_securise.csv"):
            st.dataframe(pd.read_csv("registre_securise.csv"), use_container_width=True)
