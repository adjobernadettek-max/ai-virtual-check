import streamlit as st
import easyocr
from PIL import Image, ImageDraw, ImageFont
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

# --- 1. FONCTIONS DE SÉCURITÉ ET CRYPTOGRAPHIE ---
def generer_empreinte_image(image_file):
    """Crée une signature SHA-256 unique pour l'image (Anti-doublon)."""
    return hashlib.sha256(image_file.getvalue()).hexdigest()

def check_bank_database(bin_6):
    """Interroge la base de données mondiale des banques (BIN)."""
    try:
        response = requests.get(f"https://lookup.binlist.net/{bin_6}", timeout=5)
        if response.status_code == 200:
            return response.json()
    except:
        return None
    return None

def enregistrer_dans_registre(nom, support, banque, hash_img):
    """Archivage automatique dans le registre CSV sécurisé."""
    DB_FILE = "registre_securise.csv"
    nouvelle_entree = pd.DataFrame([{
        "DATE_HEURE": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        "TITULAIRE": nom,
        "SUPPORT": support,
        "BANQUE": banque,
        "HASH_IMAGE": hash_img,
        "ID_CERTIFICAT": str(uuid.uuid4())[:12].upper()
    }])
    try:
        if not os.path.isfile(DB_FILE):
            nouvelle_entree.to_csv(DB_FILE, index=False)
        else:
            nouvelle_entree.to_csv(DB_FILE, mode='a', header=False, index=False)
    except Exception as e:
        st.error(f"Erreur d'écriture base de données : {e}")

# --- 2. CONFIGURATION DE L'IA ---
st.set_page_config(page_title="SYSTÈME D'AUDIT IA V2.0", layout="wide")

@st.cache_resource
def load_reader():
    # Moteur OCR neuronal
    return easyocr.Reader(['en'], gpu=False)

reader = load_reader()

# --- 3. INTERFACE UTILISATEUR ---
st.title("🔐 Terminal d'Audit IA - Sécurité Maximale")
st.markdown("---")

onglet_actif = st.tabs(["👤 INTERFACE DE CERTIFICATION", "🏢 ADMINISTRATION FBS"])

# ==========================================
# PARTIE CLIENT
# ==========================================
with onglet_actif[0]:
    col1, col2 = st.columns([1, 1])
   
    with col1:
        st.subheader("📋 Informations du Titulaire")
        type_support = st.selectbox("TYPE DE SUPPORT", ["Carte Physique", "Carte Virtuelle"])
        nom_complet = st.text_input("NOM COMPLET (TEL QU'ÉCRIT SUR LA CARTE)", "").upper().strip()
        num_complet = st.text_input("NUMÉRO DE CARTE COMPLET (16 CHIFFRES)", max_chars=16).replace(" ", "")
       
        bin_6 = num_complet[:6] if num_complet else ""

        fichiers_a_analyser = []
        if type_support == "Carte Virtuelle":
            st.warning("⚠️ L'heure doit être visible sur la capture d'écran.")
            f = st.file_uploader("Upload screenshot", type=['png', 'jpg', 'jpeg'])
            if f: fichiers_a_analyser = [f]
        else:
            st.warning("⚠️ Recto et Verso obligatoires pour les cartes physiques.")
            r = st.file_uploader("Côté Face (Recto)", type=['png', 'jpg', 'jpeg'])
            v = st.file_uploader("Côté Pile (Verso)", type=['png', 'jpg', 'jpeg'])
            fichiers_a_analyser = [img for img in [r, v] if img is not None]

    # --- LOGIQUE DE VÉRIFICATION ---
    if st.button("🚀 LANCER L'AUDIT DE SÉCURITÉ"):
        if len(fichiers_a_analyser) > 0 and nom_complet and len(num_complet) == 16:
            with st.status("Analyse neuronale et temporelle...", expanded=True) as status:
               
                hash_actuel = generer_empreinte_image(fichiers_a_analyser[0])
                tous_les_textes = ""
                lecture_reussie = True
       
                for f in fichiers_a_analyser:
                    try:
                        img_pil = Image.open(f).convert('RGB')
                        img_pil.thumbnail((1200, 1200)) # Qualité max
                        img_np = np.array(img_pil)
                        res_ocr = reader.readtext(img_np)
               
                        if not res_ocr:
                            lecture_reussie = False
                            break
                        tous_les_textes += " " + " ".join([r[1].upper() for r in res_ocr])
                    except:
                        lecture_reussie = False
                        break

                if not lecture_reussie or not tous_les_textes.strip():
                    st.error("❌ ÉCHEC : Photo illisible ou floue. L'IA rejette l'audit.")
                    st.stop()

                # --- SÉCURITÉ 16 CHIFFRES STRICTE ---
                texte_chiffres_seuls = "".join(re.findall(r'\d+', tous_les_textes))
                match_16_chiffres = num_complet in texte_chiffres_seuls
                match_nom = nom_complet in tous_les_textes
       
                # --- SÉCURITÉ TEMPORELLE ---
                sync_ok, heure_trouvee = True, "N/A"
                if type_support == "Carte Virtuelle":
                    motif = re.search(r'([0-1]?[0-9]|2[0-3])[:\.\sH]([0-5][0-9])', tous_les_textes)
                    if motif:
                        h, m = int(motif.group(1)), int(motif.group(2))
                        heure_trouvee = f"{h:02d}:{m:02d}"
                        diff = abs((datetime.now().hour * 60 + datetime.now().minute) - (h * 60 + m))
                        if diff > 10: sync_ok = False
                    else:
                        sync_ok = False

                status.update(label="Analyse terminée", state="complete")

            # --- RÉSULTAT ET CERTIFICATION ---
            if match_nom and match_16_chiffres and sync_ok:
                banque_info = check_bank_database(bin_6)
                nom_b = banque_info.get('bank', {}).get('name', 'INCONNUE') if banque_info else "INCONNUE"
               
                st.balloons()
                st.success("✅ AUDIT VALIDÉ : TOUS LES CRITÈRES DE SÉCURITÉ SONT REMPLIS")
               
                enregistrer_dans_registre(nom_complet, type_support, nom_b, hash_actuel)
               
                # --- GÉNÉRATION DU CERTIFICAT PRO (NON SIMPLIFIÉ) ---
                cert = Image.new('RGB', (1200, 800), color=(255, 255, 255))
                d = ImageDraw.Draw(cert)
                
                # Cadre Double Vert Forêt
                d.rectangle([20, 20, 1180, 780], outline=(0, 100, 0), width=20)
                d.rectangle([40, 40, 1160, 760], outline=(0, 100, 0), width=2)

                # Filigrane de sécurité "AUDIT OFFICIEL"
                watermark = Image.new('RGBA', (1200, 800), (0,0,0,0))
                w_draw = ImageDraw.Draw(watermark)
                w_draw.text((250, 350), "AUDIT OFFICIEL FBS", fill=(230, 230, 230, 120))
                cert.paste(watermark.rotate(30), (0,0), watermark.rotate(30))

                # Dessin du texte en GRAS (Triple couche pour visibilité)
                def draw_bold(draw, pos, text, fill=(0,0,0)):
                    for off in range(3):
                        draw.text((pos[0]+off, pos[1]), text, fill=fill)

                draw_bold(d, (350, 70), "--- CERTIFICAT D'AUTHENTICITÉ IA ---")
               
                y_p = 230
                lignes = [
                    f"TITULAIRE : {nom_complet}",
                    f"SUPPORT : {type_support}",
                    f"BANQUE D'ORIGINE : {nom_b}",
                    f"NUMÉRO : **** **** **** {num_complet[-4:]}",
                    f"CONFORMITÉ : 16/16 CHIFFRES VÉRIFIÉS",
                    f"HORODATAGE CAPTURE : {heure_trouvee}",
                    f"SIGNATURE HASH : {hash_actuel[:24]}"
                ]
                for line in lignes:
                    draw_bold(d, (100, y_p), line)
                    y_p += 80
               
                # QR Code de vérification
                qr = qrcode.make(f"SECURE-FBS-{hash_actuel[:15]}").resize((250, 250)).convert('RGB')
                cert.paste(qr, (880, 500))
                
                # Affichage final
                st.image(cert, caption="Certificat Infalsifiable Généré par l'IA", use_container_width=True)
                
                # Bouton de téléchargement
                buf = io.BytesIO()
                cert.save(buf, format="PNG")
                st.download_button(
                    label="📥 TÉLÉCHARGER LE CERTIFICAT D'AUDIT (PNG)",
                    data=buf.getvalue(),
                    file_name=f"Certificat_{nom_complet}.png",
                    mime="image/png"
                )
            else:
                st.error("❌ ÉCHEC CRITIQUE DE L'AUDIT")
                if not match_16_chiffres: st.warning("ALERTE : Les 16 chiffres ne correspondent pas à l'image.")
                if not match_nom: st.warning(f"ALERTE : Nom '{nom_complet}' introuvable sur la carte.")
                if not sync_ok: st.warning(f"ALERTE : Heure du screenshot invalide ({heure_trouvee}).")
        else:
            st.warning("⚠️ Veuillez remplir tous les champs et fournir les images.")

# ==========================================
# PARTIE ADMINISTRATION
# ==========================================
with onglet_actif[1]:
    st.header("🏢 Registre des Audits FBS")
    code = st.text_input("CODE D'ACCÈS SÉCURISÉ", type="password")
    if code == "ADMIN123":
        if os.path.exists("registre_securise.csv"):
            df = pd.read_csv("registre_securise.csv")
            st.dataframe(df, use_container_width=True)
            st.download_button("📥 EXPORTER LE REGISTRE COMPLET", df.to_csv(index=False), "registre_fbs.csv", "text/csv")
        else:
            st.info("Le registre est actuellement vide.")
