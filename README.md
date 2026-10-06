# Adopta Me Playa — site d'adoption

Site vitrine bilingue (ES-MX / EN) pour une association de protection animale de Playa del Carmen.
**HTML / CSS / JS statique, zéro build, zéro dépendance.** Les contenus éditables
par l'association vivent dans deux fichiers JSON.

---

## Administration et déploiement

Les fiches d'animaux se gèrent depuis `/admin/` (formulaire sur mesure, en
espagnol, traduction anglaise automatique). Le site est construit par
`build-preprod.py` puis publié sur O2switch par GitHub Actions
(`.github/workflows/desplegar.yml`, `deploy-ftp.py`).

- Mise en place complète : [ADMIN.md](ADMIN.md)
- Guide à remettre à l'association (espagnol) : [GUIA-ASOCIACION.md](GUIA-ASOCIACION.md)
- Tester le panel en local sans rien publier : `herramientas/servidor-prueba.py`

---

## Voir le site en local

Double-clic sur `servir.command`, ou :

```bash
python3 -m http.server 8123
```

Puis http://localhost:8123

> ⚠️ **Ne pas ouvrir `index.html` par double-clic.** Le site lit ses données via
> `fetch()` sur des fichiers JSON, ce que les navigateurs bloquent en `file://`.
> Le site affiche un message d'erreur explicite dans ce cas plutôt qu'une page vide.

---

## Arborescence

```
index.html                  Page unique
aviso-de-privacidad.html    Mention légale (LFPDPPP)
css/style.css               Design system complet
js/i18n.js                  Textes d'interface ES / EN
js/app.js                   Logique (filtres, fiche, formulaire, dons)
data/config.json            ← infos de l'association (à remplir)
data/animales.json          ← les animaux (à remplir)
img/animales/*.svg          Illustrations provisoires
img/ui/favicon.svg
servir.command              Lanceur local
```

---

## À remplacer avant mise en ligne

Tout est marqué `REEMPLAZAR` dans `data/config.json`.

| Champ | Où | Note |
|---|---|---|
| Nom de l'association | `refugio.nombre` | apparaît partout, y compris `<title>` |
| Adresse, CP, lien Maps | `refugio.direccion`, `mapa_url` | |
| **Numéro WhatsApp** | `contacto.whatsapp` | format international **sans `+` ni espaces** : `52` + `1` + indicatif + numéro → `5219841234567` |
| Téléphone, e-mail | `contacto.*` | |
| Facebook / Instagram | `redes.*` | laisser `""` masque l'icône |
| **CLABE** (18 chiffres), banque, titulaire | `donaciones.spei` | |
| Lien PayPal.me | `donaciones.paypal.url` | |
| Lien Mercado Pago | `donaciones.mercadopago.url` | |
| Chiffres de l'association | `cifras` | adoptions, stérilisations, animaux présents |
| Montants de parrainage | `padrinazgo` | |
| Liste de besoins | `lista_deseos` | |

`donaciones.*.activo: false` retire complètement un moyen de don de la page.

**Photos.** Les SVG de `img/animales/` portent la mention « foto pendiente » :
tant qu'elle apparaît, ce sont des placeholders. Remplacer par des JPG carrés
(1000×1000 suffit) et mettre à jour le champ `foto` de chaque animal.

Reste aussi à produire `img/ui/og.png` (1200×630) pour le partage sur les réseaux,
et à corriger l'URL `<link rel="canonical">` dans `index.html`.

---

## Ajouter un animal

Un objet de plus dans `data/animales.json`. Aucun autre fichier à toucher :
la grille, les filtres, la fiche, le menu déroulant du formulaire et le compteur
se mettent à jour tout seuls.

```json
{
  "id": "nina",                    // unique, sans espace ni accent
  "nombre": "Nina",
  "especie": "perro",              // "perro" | "gato"
  "sexo": "hembra",                // "macho" | "hembra"
  "edad_meses": 18,                // affiché en mois puis en années
  "peso_kg": 11,
  "tamano": "mediano",             // "chico" | "mediano" | "grande"
  "color": "turquesa",             // arena | lavanda | coral | turquesa | menta
  "foto": "img/animales/nina.jpg",
  "urgente": false,                // true = badge « lleva mucho esperando »
  "esterilizado": true,
  "vacunado": true,
  "desparasitado": true,
  "convive": { "ninos": true, "perros": true, "gatos": false },
  "cuota": 800,
  "es": { "resumen": "…", "historia": "…", "caracter": ["…", "…"] },
  "en": { "resumen": "…", "historia": "…", "caracter": ["…", "…"] }
}
```

`convive` pilote les filtres du catalogue **et** la section « Convive con » de la fiche.
Un animal adopté : le retirer du fichier (ou le déplacer dans un fichier d'archive).

---

## Le formulaire

Pas de backend. À la soumission, le JS valide les champs, assemble un message
structuré et ouvre `wa.me` avec le texte pré-rempli. **Rien n'est stocké** :
c'est ce que dit l'avis de confidentialité, ne pas ajouter de tracker sans le
mettre à jour.

Si l'association préfère un jour recevoir les demandes par e-mail, la bascule est
localisée : la fonction `conectarFormulario()` dans `js/app.js`, dernière ligne
(`window.open(enlaceWA(...))`).

---

## i18n

Textes d'interface dans `js/i18n.js` (`TEXTOS.es` / `TEXTOS.en`, mêmes clés des
deux côtés). Contenus des animaux dans `animales.json`, sous les clés `es` / `en`.
La langue choisie est mémorisée dans `localStorage`; au premier passage elle est
déduite de `navigator.language`.

---

## Cache

Les assets sont appelés avec `?v=1`. **Après une mise à jour, incrémenter ce
numéro** dans `index.html` (CSS + 2 scripts) et dans les deux `fetch()` de
`js/app.js`, sinon les visiteurs déjà venus garderont l'ancienne version.

---

## Déploiement

Glisser-déposer le dossier sur Netlify. Aucune commande de build, dossier de
publication = la racine. Prévoir un domaine et un certificat HTTPS.

---

## Points vérifiés

- Filtres espèce / taille / cohabitation + recherche, avec état vide.
- Fiche animale : ouverture, fermeture (bouton, clic en dehors, `Échap`), pré-sélection de l'animal dans le formulaire.
- Formulaire : blocage sur champs manquants, génération du message WhatsApp complet.
- Bascule ES/EN sur toute la page, y compris contenus JSON et liens WhatsApp.
- Copie de la CLABE dans le presse-papier.
- Responsive 375 / 768 / 1360 px, focus clavier visible, `prefers-reduced-motion` respecté.

**À valider dans un vrai navigateur** : le navigateur intégré à l'outil de
développement n'exécute pas `requestAnimationFrame`, donc les transitions et le
défilement doux n'y sont pas observables.

---

## Version de préprod (Netlify)

```bash
python3 build-preprod.py
```

Produit `dist/refugio-preprod.zip` — c'est **ce zip** qu'on dépose sur Netlify,
pas le dossier de travail. Il diffère du site final sur trois points :

- **`noindex` triple** : `robots.txt`, en-tête `X-Robots-Tag` via `netlify.toml`,
  et balise `<meta name="robots">` sur les deux pages. Indispensable tant que la
  page affiche une CLABE fictive au nom d'une association qui existe vraiment.
- **Bandeau « sitio de demostración »** en haut de page, bilingue, injecté par
  `js/demo.js`. Ce fichier n'existe que dans le build.
- **Fichiers de travail exclus** : les `.md`, `servir.command` et le script de
  build lui-même ne partent pas en ligne.

Les fichiers source ne sont jamais modifiés par le script : le bandeau et le
`noindex` n'existent que dans `dist/`.

**Pour la mise en production**, quand les vraies données seront là : retirer
l'appel à `bandeau()` et à `noindex()` dans `build-preprod.py`, et vider le
`robots.txt`.

---

## Fiche type d'un animal (`data/animales.json`)

Le bloc vert « Sale en adopción con » n'affiche **que ce qui est explicitement
`true`**. Un champ absent ou `false` ne s'affiche pas — on n'invente jamais
l'état sanitaire d'un animal réel.

**Les quatre lignes standard**, à mettre sur chaque fiche :

```json
"esterilizado": true,
"vacunado": true,
"desparasitado": true,
"cartilla": true
```

`"esterilizado": false` est un cas particulier utile : au lieu de masquer la
ligne, la fiche affiche « Esterilización incluida, se agenda por edad ». C'est
le cas de Tuna (4 mois) et Frida (6 mois).

**Le microchip s'ajoute au cas par cas**, seulement sur les animaux qui en ont
un. Sans la ligne, rien ne s'affiche :

```json
"microchip": true
```

**Champs optionnels** utilisés par Sheruk et disponibles pour les autres :

| Champ | Effet |
|---|---|
| `raza` | sous-titre en italique sous le nom (`{"es": "...", "en": "..."}`) |
| `edad_texto` | remplace l'âge calculé, pour une approximation (`"6-7 años"`) |
| `fotos` | tableau d'images : fait apparaître les miniatures cliquables |
| `es.aviso` / `en.aviso` | encadré rouge d'avertissement, placé avant le bloc santé |
| `urgente` | badge « Lleva mucho esperando » sur la carte et la fiche |
