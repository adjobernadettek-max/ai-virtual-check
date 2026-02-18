importer streamlit comme st
importer easyocr
from PIL import Image, ImageDraw
importer le code QR
from datetime import datetime
import numpy as np
importer pandas comme pd
importer os
importer la bibliothèque de hachage
importation io
importer re
demandes d'importation
importer uuid

# --- FONCTIONS DE SÉCURITÉ ET REGISTRE ---

def generer_empreinte_image(image_file) :
renvoie hashlib.sha256(image_file.getvalue()).hexdigest()

def check_bank_database(bin_6):
essayer:
réponse = requests.get(f" https://lookup.binlist.net/{bin_6} ", timeout=5)
si response.status_code == 200 : retourner response.json()
sauf : retourner None
renvoyer Aucun

def enregistrer_dans_registre(nom, support, banque, hash_img):
FICHIER_DB = "registre_securise.csv"
nouvelle_entree = pd.DataFrame([{
"DATE_HEURE" : datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
"TITULAIRE": nom,
"SUPPORT" : support,
"BANQUE": banque,
"HASH_IMAGE" : hash_img,
"ID_CERTIFICAT": str(uuid.uuid4())[:8]
}])
essayer:
si os.path.isfile(DB_FILE) n'est pas :
nouvelle_entree.to_csv(DB_FILE, index=False)
autre:
nouvelle_entree.to_csv(DB_FILE, mode='a', header=False, index=False)
sauf:
st.warning("⚠️ Sauvegarde locale impossible sur ce serveur Cloud.")

# --- INTERFACE DE CONFIGURATION ---
st.set_page_config(page_title="IA SÉCURITÉ MAXIMALE", layout="wide")

@st.cache_resource
def charger_lecteur():
# gpu=False est VITAL pour éviter le crash "Oh no" sur Streamlit Cloud
renvoie easyocr.Reader(['en'], gpu=False)
lecteur = charger_lecteur()

st.title("🔐 Terminal d'Audit Haute Sécurité")

onglet_actif = st.tabs(["👤 INTERFACE CLIENT", "🏢 ESPACE ENTREPRISE"])

# ==========================================
# 1. INTERFACE CLIENT
# ==========================================
avec onglet_actif[0] :
col1, col2 = st.columns([1, 1])
avec col1 :
st.subheader("📋 Formulaire de Certification")
type_support = st.selectbox("TYPE DE SUPPORT", ["Carte Physique", "Carte Virtuelle"])
nom_complet = st.text_input("NOM COMPLET DU TITULAIRE", "").upper().strip()
num_complet = st.text_input("NUMÉRO DE CARTE (16 CHIFFRES)", max_chars=19)
bin_6 = num_complet[:6] si num_complet sinon ""
last_4 = num_complet[-4:] si num_complet sinon ""

fichiers_a_analyser = []
if type_support == "Carte Virtuelle" :
fichier_v = st.file_uploader("Télécharger une capture d'écran", type=['png', 'jpg', 'jpeg'])
si fichier_v : fichiers_a_analyser = [fichier_v]
autre:
recto = st.file_uploader("Côté Face (Recto)", type=['png', 'jpg', 'jpeg'])
verso = st.file_uploader("Côté Pile (Verso)", type=['png', 'jpg', 'jpeg'])
fichiers_a_analyser = [f pour f dans [recto, verso] si f n'est pas None]

if st.button("🚀 LANCER LA VÉRIFICATION") :
si len(fichiers_à_analyser) > 0 et nom_complet et last_4 :
avec st.status("Analyse OCR et Sécurité...", expand=True) comme statut :
hash_actuel = generer_empreinte_image(fichiers_a_analyser[0])
tous_les_textes = ""
lecture_reussie = Vrai
pour f dans fichiers_a_analyser :
essayer:
img = Image.open(f).convert('RGB')
img.thumbnail((1000, 1000)) # Protection mémoire
img_np = np.array(img)
res_ocr = lecteur.liretexte(img_np)
si ce n'est pas res_ocr :
lecture_reussie = Faux
casser
tous_les_textes += " " + " ".join([r[1].upper() for r in res_ocr])
sauf:
lecture_reussie = Faux
casser

sinon lecture_reussie ou pas tous_les_textes.strip() :
st.error("⚠️ Impossible de lire les données (Photo trop floue).")
st.stop()

match_nom = nom_complet dans tous_les_textes
match_chiffres = last_4 dans tous_les_textes
sync_ok, heure_trouvee = Vrai, "N/A"
if type_support == "Carte Virtuelle" :
motif = re.search(r'([0-1]?[0-9]|2[0-3])[:\.\sH]([0-5][0-9])', tous_les_textes)
si motif :
h, m = int(motif.group(1)), int(motif.group(2))
heure_trouvee = f"{h:02d}:{m:02d}"
diff = abs((datetime.now().hour * 60 + datetime.now().minute) - (h * 60 + m))
si diff > 10 : sync_ok = False
sinon : sync_ok = Faux

status.update(label="Analyse terminée", state="complete")

si match_nom et match_chiffres et sync_ok :
banque_info = check_bank_database(bin_6)
nom_b = banque_info.get('bank', {}).get('name', 'INCONNUE') si banque_info sinon "INCONNUE"
st.ballons()
st.success("✅AUDIT VALIDÉ")
enregistrer_dans_registre(nom_complet, type_support, nom_b, hash_actuel)
# GÉNÉRATION DU CERTIFICAT COMPLET
cert = Image.new('RGB', (1000, 600), color=(255, 255, 255))
d = ImageDraw.Draw(cert)
d.rectangle([10, 10, 990, 590], contour=(0, 128, 0), largeur=15)

essayer:
w_txt = "AUDIT OFFICIEL"
txt_img = Image.new('RGBA', (900, 300), (255, 255, 255, 0))
d_w = ImageDraw.Draw(txt_img)
d_w.text((50, 100), w_txt, fill=(235, 235, 235, 150))
cert.paste(txt_img.rotate(20, expand=1), (100, 100), txt_img.rotate(20, expand=1))
sauf : passer

def dessiner_grand(dessiner, pos, texte):
pour o dans la plage(3) : dessiner.texte((pos[0]+o, pos[1]), texte, remplissage=(0, 0, 0))

draw_big(d, (250, 40), "CERTIFICAT D'AUTHENTICITÉ")
y_p = 180
lignes = [f"TITULAIRE : {nom_complet}", f"SUPPORT : {type_support}", f"BANQUE : {nom_b}", f"CARTE : **** {last_4}", f"HEURE : {heure_trouvee}"]
pour ligne en lignes :
dessiner_grand(d, (80, y_p), ligne)
y_p += 85
qr = qrcode.make(f"SECURE-{hash_actuel[:15]}").resize((180, 180))
cert.paste(qr, (780, 380))
st.image(cert)
autre:
st.error("❌ ÉCHEC : Les données ne correspondent pas ou l'heure est expirée.")
autre:
st.warning("⚠️ Remplissez tous les champs.")

# ==========================================
# 2. ESPACE ENTREPRISE
# ==========================================
avec onglet_actif[1] :
st.header("🏢 Admin")
si st.text_input("CODE D'ACCÈS", type="password") == "ADMIN123":
si os.path.exists("registre_securise.csv"):
df = pd.read_csv("registre_securise.csv")
st.dataframe(df, use_container_width=True)
