# Administration et déploiement — O2switch

Adopta Me Playa gère ses fiches depuis **`/admin/`** : un formulaire qui reprend la
fiche du site (mêmes couleurs, même disposition). Il remplit en **espagnol
seulement** ; l'anglais est traduit automatiquement à la publication.

```
Panel /admin/ ──commit──▶ GitHub (main)
                              │  GitHub Actions : construit le site
                              ▼
                       branche « despliegue »
                              ▲
   O2switch ── cron toutes les 2 min : va la chercher et la copie ──┘
      │
      ├─ /api/auth, /api/callback   connexion GitHub (PHP)
      └─ /api/traducir              DeepL, clé côté serveur (PHP)
```

**Pourquoi le serveur va chercher le site, et GitHub ne l'envoie pas ?**
O2switch ne propose ni FTP chiffré (FTPS) ni SFTP aux adresses IP de GitHub, qui
changent sans arrêt (SFTP exige en plus le compte cPanel principal, jamais un
compte FTP restreint). Un FTP non chiffré ferait voyager le mot de passe en
clair, et comme l'hébergement porte aussi d'autres sites (wptonyoo.fr), ce mot
de passe donnerait accès à tout le compte. Ici **aucun mot de passe ne voyage** :
le dépôt est public, le serveur ne fait que le lire.

Chaque publication du panel est **un seul commit** (la fiche + ses photos).
Compter **3 à 4 minutes** entre le clic sur *Publicar* et le site à jour
(construction ≈ 1 min, puis le passage du cron, toutes les 2 min). Aucun quota :
GitHub Actions est gratuit sur un dépôt public.

> **Règle absolue :** le dépôt est public. Aucun mot de passe, jeton ou clé API
> n'y entre jamais. Le secret OAuth et la clé DeepL vivent dans un fichier sur le
> serveur. Tu les saisis toi-même, personne d'autre (moi compris) n'a à les voir.

> **À savoir :** le contenu de ce dépôt *devient* le site, PHP compris. Toute
> personne ayant l'accès en écriture peut donc faire exécuter du code sur le
> serveur. N'invite que des personnes de confiance, et fais-leur activer la
> **double authentification** GitHub.

---

## 1. Côté O2switch (cPanel)

> ⚠️ **Cet hébergement porte déjà d'autres sites** (wptonyoo.fr, dans `public_html`).
> Le site de Adopta Me Playa a **son propre dossier**, jamais `public_html`.

1. **Brancher le domaine** : cPanel → **Domaines** (« Domaines Configurés ») →
   *Configurer un nom de domaine* :
   - **Nom du nouveau domaine** : `adoptameplaya.org`
   - **Sous-domaine système** : un mot au choix (`adoptameplaya`)
   - **Racine du document** : `adoptameplaya.org` (un dossier à côté de `public_html`).
     **Jamais vide** (ce serait tout le répertoire personnel), **jamais `public_html`**
   - **Ne pas cocher** « Créez un compte FTP » : il ne sert à rien ici (voir plus haut).
     *(Si un compte FTP a déjà été créé : cPanel → Comptes FTP → **Supprimer**.)*

   Puis *Ajouter un domaine* et contrôler dans le tableau « Domaines supplémentaires »
   que la racine est `/adoptameplaya.org`. Les serveurs de noms sont déjà ceux
   d'o2switch : la zone DNS se crée toute seule.
2. **HTTPS** : attendre que le certificat **AutoSSL** du domaine soit actif (quelques
   heures). Le cookie de connexion de l'admin l'exige.
3. **PHP ≥ 7.4** pour ce domaine (8.x de préférence) : le *Sélecteur de version PHP*
   de cPanel. Vérification : après le déploiement, `https://adoptameplaya.org/api/traducir.php`
   doit afficher `{"ok":false,"error":"Método no permitido."}`. Si la page s'affiche
   comme du texte ou se télécharge, PHP n'est pas actif : **ne pas continuer**.

## 2. Côté GitHub (dépôt `adoptameplaya/site-adoption`)

**Aucun secret.** Seulement deux variables : *Settings → Secrets and variables →
Actions → onglet **Variables***.

| Nom | Valeur |
|---|---|
| `SITE_URL` | `https://adoptameplaya.org` (sans `/` final) |
| `MODO` | `preprod` jusqu'au lancement, puis `produccion` |

## 3. Application OAuth GitHub (connexion à l'admin)

*GitHub → Settings → Developer settings → OAuth Apps* : modifier l'application
existante (ou en créer une) :

| Champ | Valeur |
|---|---|
| Homepage URL | `https://adoptameplaya.org` |
| Authorization callback URL | `https://adoptameplaya.org/api/callback` |

Garder le **Client ID** et générer un **Client secret**.

## 4. Les secrets du serveur

Un fichier à créer une fois, à la main, **hors du dossier web** :

1. cPanel → **Gestionnaire de fichiers**. Il s'ouvre dans ton répertoire personnel
   (`/home/cupa8096/`), **au-dessus** du dossier du site.
2. Y créer **`secrets-adoptameplaya.php`**, coller le contenu de
   `api/secrets.example.php` (visible sur GitHub) et remplir les valeurs.

Hors du dossier web, aucune adresse ne peut le servir, même si la configuration du
serveur échouait un jour. Le script le cherche là d'abord ; à défaut `api/secrets.php`
(dans le dossier web, protégé par `api/.htaccess`). Le déploiement ne les touche jamais.

```php
<?php
return [
    'github_client_id'     => '…',   // Client ID de l'étape 3
    'github_client_secret' => '…',   // Client secret de l'étape 3
    'github_repo'          => 'adoptameplaya/site-adoption',
    'site_url'             => 'https://adoptameplaya.org',
    'deepl_key'            => '…',   // clé DeepL, voir ci-dessous
];
```

**Comment remplir ce fichier sans jamais le coller dans un éditeur web** (l'éditeur de cPanel traduit
et abîme le code, et les secrets ne doivent traverser aucun chat ni capture) : lancer
`herramientas/rellenar-secretos.command` (ou `python3 herramientas/rellenar-secretos.py`). L'outil ne demande
qu'**un collage, masqué** — le secret client GitHub — le vérifie auprès de GitHub, écrit le fichier sur le
Bureau (`~/Desktop/Claude/secrets-adoptameplaya.php`, droits 600), qu'on **téléverse** ensuite dans
`/home/cupa8096` (*Gestionnaire de fichiers → Téléverser*, en vérifiant que le titre de la page dit bien
`/home/cupa8096` et **pas** un sous-dossier), puis qu'on **supprime du Mac** : `rm -P ~/Desktop/Claude/secrets-adoptameplaya.php`.

**Traduction anglaise.** Tant qu'il n'y a pas de clé DeepL, `admin/config.js` garde `traduccionAuto: false` :
l'anglais s'écrit **à la main** dans la section « Versión en inglés » de chaque fiche (avec le texte espagnol
rappelé sous chaque champ) ; s'il est vide, la version anglaise du site affiche l'espagnol. Quand la clé DeepL
sera dans le fichier de secrets, passer `traduccionAuto` à `true`.

**Clé DeepL** : compte sur deepl.com → *DeepL API Free* → copier la clé (elle se termine
par `:fx`). Le plan gratuit offre 500 000 caractères par mois ; une fiche en pèse
environ 600. Une carte bancaire est demandée à l'inscription pour vérification : à
confirmer au moment de la créer. **Sans clé**, l'admin fonctionne quand même : la fiche
est publiée et le site affiche l'espagnol dans la version anglaise.

## 5. Premier déploiement

**a. Construire la branche `despliegue`.** GitHub → onglet **Actions** → *Construir el
sitio* → **Run workflow** (ou simplement pousser sur `main`). Quand le job est vert,
la branche `despliegue` existe sur le dépôt.

**b. Installer le script de mise à jour sur le serveur.** cPanel → Gestionnaire de
fichiers → répertoire personnel → *Nouveau fichier* `actualizar-adoptameplaya.sh` →
coller le contenu de [`herramientas/actualizar-servidor.sh`](herramientas/actualizar-servidor.sh).
Par défaut il copie vers `~/adoptameplaya.org` : à modifier (ligne `DEST=`) si la racine
du document n'est pas celle-là.

**c. Le lancer une première fois.** cPanel → **Tâches cron** → ajouter une tâche
temporaire (ou la tâche définitive ci-dessous) et regarder le fichier
`actualizar-adoptameplaya.log` apparaître dans le répertoire personnel : il doit dire
`clonado …` puis `publicado …`.

**d. La tâche cron définitive.** cPanel → **Tâches cron** → *Ajouter une nouvelle tâche* :

| Minute | Heure | Jour | Mois | Jour de la semaine | Commande |
|---|---|---|---|---|---|
| `*/2` | `*` | `*` | `*` | `*` | `/bin/sh /home/cupa8096/actualizar-adoptameplaya.sh` |

Quand il n'y a rien de nouveau, le script ne fait rien et n'écrit rien.

**e. Vérifier :**
- `https://adoptameplaya.org/version.txt` → commit, mode, destination
- `https://adoptameplaya.org/admin/` → écran de connexion

**Filet de sécurité :** au premier passage, si le dossier visé contient déjà un site
(`index.php`, WordPress, un `index.html` qui n'est pas le nôtre), ou si c'est
`public_html`, le script **s'arrête sans rien modifier** et l'écrit dans le journal.

Dès lors, **chaque push sur `main`** (y compris ceux du panel) se retrouve en ligne.

## 6. Donner l'accès à Adopta Me Playa

Chaque personne a besoin d'un **compte GitHub gratuit** (avec double authentification),
puis : dépôt → *Settings → Collaborators → Add people* (accès en écriture). Elle se
connecte sur `/admin/` avec **Entrer avec GitHub**. Le panel vérifie qu'elle a bien le
droit d'écrire ; le script de traduction fait la même vérification, donc personne
d'extérieur ne peut consommer le quota DeepL.

Le guide à lui remettre : [GUIA-PANEL.md](GUIA-PANEL.md).

---

## Passer en production

Quand les fiches d'exemple (Coco, Rocky, Canela, Bruno, Frida) sont remplacées par de
vrais animaux : variable GitHub `MODO` = `produccion`, puis *Run workflow*. Cela retire
le bandeau « sitio de demostración » et le `noindex`. `/admin/` reste exclu des moteurs
de recherche.

## HSTS (sécurité HTTPS)

`.htaccess` envoie `Strict-Transport-Security`. **Mise en place progressive**, parce qu'on ne peut pas
l'annuler vite : une fois reçu, le navigateur refuse tout accès non sécurisé pendant `max-age`.

| Étape | Valeur | Quand |
|---|---|---|
| 1 | `max-age=604800` (1 semaine) | mis en place le 12/10/2026 |
| 2 | `max-age=15552000` (6 mois) | après 2–3 semaines sans souci (vers le 02/11/2026) |

Pas de `includeSubDomains` (le site n'a pas besoin d'imposer HTTPS aux sous-domaines) ni de `preload`
(liste intégrée aux navigateurs, quasi irréversible). Avant de monter la durée : certificat valide
(AutoSSL), `http://` et `www.` redirigent bien vers `https://adoptameplaya.org` — `auditar-sitio.py` le vérifie.
**Pour l'annuler** : servir `max-age=0` en HTTPS ; chaque navigateur oublie la règle à sa prochaine visite.

## Fichiers

| Chemin | Rôle |
|---|---|
| `.github/workflows/desplegar.yml` | construit le site, le publie dans la branche `despliegue` |
| `herramientas/actualizar-servidor.sh` | **sur le serveur**, via cron : récupère `despliegue` et la copie |
| `api/auth.php`, `api/callback.php` | connexion GitHub (le secret OAuth ne sort jamais du serveur) |
| `api/traducir.php` | traduction ES → EN ; n'obéit qu'à un compte ayant le droit d'écriture |
| `/home/cupa8096/secrets-adoptameplaya.php` | **créé à la main**, hors dépôt et hors dossier web |
| `.htaccess` | HTTPS forcé, adresses `/api/…`, cache (les JSON ne sont jamais mis en cache) |
| `admin/.htaccess` | en-têtes de sécurité du panel : seuls ses propres scripts peuvent s'y exécuter |
| `data/cuestionario.json` | questions d'adoption **chiens (44) et chats (36)** et questionnaire de **famille d'accueil « hogar » (34, 9 sections)**, ES et EN. Pas modifiable depuis le panel : se change dans ce fichier. Le build refuse un numéro en double ou une traduction manquante. Types : `texto`, `largo`, `sino` (Sí/No + commentaire, `ph` = texte du champ commentaire), `multi` (cases à cocher : `opciones` [{es,en}], `opcional`: true si on peut n'en cocher aucune) |
| `formularios/*.pdf` | les 4 PDF remplissables (chien/chat × ES/EN) joints à l'e-mail automatique. Ceux des chats sont **générés** depuis `data/cuestionario.json` (voir ci-dessous) |
| `herramientas/crear-pdf-cuestionario.py`, `herramientas/fuentes/`, `herramientas/sello-adopta-me.png` | générateur de ces PDF, polices Poppins (licence SIL OFL) et sello du logo |
| `herramientas/servir-vista-previa.py` | sert `dist/preprod` sur http://127.0.0.1:8124 pour vérifier le site avant publication |
| `.sitio-adoptameplaya` (dans le dossier web) | marque « ce dossier est géré par le script » |

## Régénérer les PDF du questionnaire

Si une question change dans `data/cuestionario.json`, les PDF ne se mettent pas à jour tout seuls. Il faut
[ReportLab](https://pypi.org/project/reportlab/) et Pillow, **dans un environnement temporaire** (rien d'autre
dans le projet n'en dépend ; versions testées : ReportLab 5.0.1, Pillow 11.3.0) :

```bash
python3 -m venv /tmp/pdf && /tmp/pdf/bin/pip install reportlab pillow
for l in es en; do /tmp/pdf/bin/python herramientas/crear-pdf-cuestionario.py --especie gato --lang $l \
  --salida formularios/$([ $l = es ] && echo Cuestionario_Adopcion_Gato_ES || echo Adoption_Questionnaire_Cat_EN).pdf; done
```

Pour la **famille d'accueil** : `--especie hogar` (`formularios/Cuestionario_Hogar_Temporal_ES.pdf` et `formularios/Foster_Home_Questionnaire_EN.pdf`, 6 pages, 37 champs texte + cases à cocher et Sí/No) ; la couverture n'a pas de nom d'animal et son titre passe sur deux lignes s'il est trop long. Les PDF « hogar » ont été générés le 19/10/2026 avec ReportLab 5.0.1 et Pillow 11.3.0 ; l'extension du générateur (type `multi`, `hogar`) donne des fichiers identiques octet pour octet à l'ancienne version pour les chiens et les chats.

Le même outil, lancé avec `--especie perro`, retrouve **à l'identique** (au pixel près) les PDF des chiens.
La sortie est reproductible : sans changement de questions, le fichier généré est identique octet pour octet.

## Vitesse et référencement (build)

- **Prérendu** : `build-preprod.py` écrit dans `index.html`, en espagnol, ce que le JavaScript écrirait (textes, bande des animaux, cartes,
  compteur, JSON-LD). Les robots voient donc une vraie page et la bande a sa hauteur dès le départ (plus de saut de mise en page). Le JS ne
  repeint pas la bande et la grille quand la langue est l'espagnol (attribut `data-pre`) ; en anglais il repeint comme avant, et le `<head>`
  masque le texte espagnol le temps de la traduction (classe `pre-en`). Source des textes : `js/i18n.js` (même dictionnaire).
- **Miniatures** : chaque photo `x.jpg` a une petite `x-m.jpg` (**480 px, ≈ 25-30 Ko**) créée par le panneau (canvas, qualité 0,62) ; le build
  l'ajoute en `miniatura` quand elle existe (jamais de 404). Les 357 vignettes d'avant (560 px, 53 Ko) ont été régénérées le 14/10/2026
  depuis les photos complètes (31 Ko en moyenne, −40 %) avec ImageIO (Swift, qualité 0,38 ≈ canvas 0,62). Une vignette seule : `swift` + `CGImageDestination`
  (le `sips` classique donne un fichier plus lourd à qualité égale).
- **Photo du haut de l'accueil** : `img/ui/familia.webp` (273 Ko, repli) + `familia-960.avif` (64 Ko) et `familia-1344.avif` (108 Ko) dans un `<picture>` ;
  l'AVIF garde la transparence. `.htaccess` déclare `image/avif` et le cache 30 jours.
- **Accueil : 12 cartes puis « Ver más »** (12 de plus à chaque clic ; filtres et recherche remettent à 12 et portent sur toutes les fiches). Les autres cartes
  sont dans le HTML avec l'attribut `hidden` (`POR_PAGINA = 12` dans `build-preprod.py` ET `js/app.js`, à garder identique).
- **Plafond de 4 photos** par fiche dans le panneau (`MAX_FOTOS`) ; les fiches qui en avaient plus gardent les leurs (avertissement à l'ouverture).
- **Polices hébergées sur le site** (`css/fonts/` : Baloo 2 et Nunito, polices variables, alphabet latin, licence SIL OFL jointe) : plus de Google Fonts, donc pas de requête externe ni d'adresse IP envoyée à Google. `@font-face` est en tête de `css/style.css` ; préchargées dans le `<head>` ; cache d'un an dans `.htaccess`. Si on remplace un fichier, **changer son nom** (cache « immutable »). Un caractère hors alphabet latin prend la police de secours.
- Mesure : https://pagespeed.web.dev (mobile) — avant : Performances 57, CLS 0,513 ; l'audit local contrôle aussi photos et miniatures.

## Ordre des fiches (aléatoire, change chaque semaine)

- **Panel** : liste alphabétique (`localeCompare('es', {sensitivity:'base'})`), groupes Borradores / En el sitio.
  L'ancien écran glisser-déposer et le bouton « Mostrarlo el primero » sont supprimés ; le champ `orden`
  des JSON n'a plus d'effet (les nouvelles fiches reçoivent 999).
- **Site** : `ordenar_semanal()` (`build-preprod.py`) et `ordenSemanal()` (`js/app.js`) — **mêmes calculs, à ne
  modifier qu'ensemble**. Clé = (urgent disponible d'abord, `hash32("<lundi>|<id>")`, id) ; la « semaine » est le
  lundi 00:00–dimanche, heure de Quintana Roo (UTC−5 toute l'année). Les adoptés sont mélangés aux autres ;
  la bande du haut = les 5 premiers disponibles. Ajouter/retirer une fiche ne remélange pas les autres.
- Le build écrit l'ordre de la semaine dans `index.html` (prérendu). Le navigateur recalcule et **ne repeint que si
  la page date d'une autre semaine** (garde-fou : sans reconstruction hebdomadaire, ça marche mais la page peut
  se réordonner au chargement).
- **Reconstruction hebdomadaire** : `schedule: - cron: '10 5 * * 1'` dans `.github/workflows/desplegar.yml`
  (lundi 05:10 UTC = 00:10 Quintana Roo). Ce fichier ne peut être modifié que sur le site de GitHub
  (le jeton du panel/des pushs n'a pas le droit « workflow »).
- `auditar-sitio.py` vérifie que l'ordre servi correspond à la semaine en cours.

## Brouillons (mode « en attente »)

Une fiche avec `"borrador": true` dans son JSON est un **brouillon** : `build-preprod.py` ne la met
pas dans `data/animales.json` et **retire du site publié** ses photos et miniatures (celles qu'aucune
fiche publiée n'utilise). Le panel enregistre un brouillon avec seulement le nom, sans traduction ;
« Publier les N à la fois » = **un seul commit** (donc un seul build), avec la même validation que la
publication d'une fiche seule (l'ordre sur le site ne dépend plus de la publication : voir plus haut). Le brouillon est partagé entre appareils et personnes (c'est le JSON
du dépôt). **Attention : le dépôt est public**, donc un brouillon n'est pas visible sur le site mais
l'est sur GitHub. `herramientas/auditar-sitio.py` vérifie qu'aucun `borrador` n'est dans le JSON public
et (avec `--repo`) que les photos des brouillons répondent 404.

## Demande de formulaire : page de remerciement et e-mail

- **Voie principale (depuis le 19/10/2026)** : la section « Rellena tu formulario de adopción » de l'accueil demande seulement chien/chat (et l'animal, facultatif), puis deux boutons :
  « Rellenar el formulario en línea » (`cuestionario.html?especie=..&lang=..&animal=..`) et « Descargar el formulario en PDF » (`app.js` → `actualizarEnlacesAdopcion()`).
  Sans espèce choisie, le clic affiche « Elige perro o gato ». L'ancien envoi par e-mail (nom, prénom, e-mail → FormSubmit → page de remerciement) est resté en **option repliée**
  « ¿Prefieres recibirlo por correo? » (`<details class="solicitud__correo">`) ; pour la supprimer, retirer ce bloc dans `index.html`.
- **Voie par e-mail (ancienne voie principale)** :
- Le mini-formulaire de l'accueil poste vers FormSubmit (natif, avec reCAPTCHA) puis revient sur `gracias.html?lang=..&especie=..&animal=..`
  (jamais de nom ni d'e-mail dans l'adresse). **Cette page affiche le logo, le remerciement et DEUX boutons** : « Rellenar el formulario en línea »
  (`cuestionario.html?especie=..`) et « Descargar el formulario en PDF » (lien `download`, chemin pris dans `data/config.json` → `solicitud.formularios`).
  Sans `especie` dans l'adresse, elle propose les deux espèces. Depuis le questionnaire complet (`&de=cuestionario`), elle garde son comportement (bouton WhatsApp).
- **L'e-mail automatique reste du TEXTE BRUT** : test réel du 16/10/2026 — FormSubmit affiche le HTML tel quel, impose l'expéditeur « FormSubmit »,
  l'objet « We have received your submission on <site> » (anglais) et ajoute « Here's what we have received ». Textes dans `js/i18n.js`
  (`sol.auto_con` / `sol.auto_web` / `sol.auto_sin`, ES et EN selon la langue du visiteur). Pour un vrai e-mail HTML avec logo et boutons,
  il faudrait l'envoyer depuis le serveur (PHP + expéditeur + anti-abus) : non fait, au choix de Yohan.

## Questionnaire « hogar temporal » (famille d'accueil)

- Page : `cuestionario.html?especie=hogar` (même page que l'adoption, pilotée par le bloc `hogar` de `data/cuestionario.json`) ; pas de champ « ¿Para qué peludo? ».
  Mêmes pied de page, déclaration, lieu, e-mail et envoi (FormSubmit, tout dans un seul champ texte « Cuestionario ») ; objet « Cuestionario de hogar temporal — Nom ».
  Les cases à cocher (questions 16 et 22) sont recopiées dans le texte de l'e-mail (« > [x] option »).
- Accès : carte « Hogar temporal » de l'accueil (bouton « Rellenar el cuestionario de hogar temporal », bouton PDF dès que `solicitud.formularios.hogar` existe
  dans `data/config.json`, et lien WhatsApp). Source : Word « Cuestionario_Hogar_Temporal_Foster_last.docx » (34 questions) ; la question 23 fusionne « flexibilité » et
  « date limite » (le commentaire reçoit la date) ; textes ES repris du Word (fautes corrigées : « situation » → « situación », « tomarnos fotos » → « tomar y enviarnos fotos ») ;
  l'anglais est une traduction à faire relire.
- L'avis de confidentialité mentionne ce questionnaire (données, finalité, conservation).

## Texte « en attente » (case « Aún no tengo esta información »)

Sous le résumé et l'histoire, la case remplit `es.resumen` / `es.historia` avec **« Pronto más información »**
et l'anglais avec **« More information coming soon »** (sans appeler la traduction : `enBase` = espagnol, donc
rien à retraduire). Décocher vide le champ ; le vrai texte est ensuite traduit comme d'habitude. La liste du
panel affiche « Info pendiente » ; `auditar-sitio.py` les compte en *info* (plus d'avertissement « résumé
très court / même histoire ») et reconnaît aussi l'ancienne formule « información pendiente » (31 fiches
au 12/10/2026, saisie à la main, **non modifiées**).

## Tester sans rien publier

```bash
python3 herramientas/probar-api.py          # scripts PHP : 56 contrôles (PHP ≥ 8.0 avec curl)
python3 herramientas/probar-servidor.py     # script de mise à jour du serveur : 23 contrôles
```

`herramientas/servidor-prueba.py` simule l'API GitHub et la traduction, sur une **copie**
du projet (jamais le dépôt réel), pour essayer le panel :

```bash
cp -R . /tmp/copia && rm -rf /tmp/copia/.git
python3 herramientas/servidor-prueba.py --raiz /tmp/copia --puerto 8765
# puis http://localhost:8765/admin/?dev
```

`?dev` ne fonctionne que sur `localhost`. Options : `--sin-traduccion`, `--solo-lectura`, `--lento`.

Ce que ces tests ne couvrent pas : `.htaccess` (pas d'Apache en local), le vrai flux OAuth
dans la fenêtre GitHub, le vrai DeepL, et le cron réel d'o2switch.

---

## Si quelque chose casse

Le journal du serveur est le fichier **`actualizar-adoptameplaya.log`** (répertoire
personnel). Les erreurs y sont écrites avec l'heure.

| Symptôme | Cause probable |
|---|---|
| La fiche est enregistrée mais le site ne change pas | 1) onglet *Actions* du dépôt : la construction a-t-elle échoué ? 2) le journal du serveur : le cron tourne-t-il ? |
| Journal : `no se pudo clonar … rama despliegue` | la première construction GitHub n'a pas eu lieu : lancer *Construir el sitio* |
| Journal : `ya contiene un sitio` ou `public_html … se niega` | **le garde-fou a fait son travail** : le dossier visé n'est pas celui de Adopta Me Playa. Vérifier `DEST=` dans le script. Rien n'a été modifié |
| Journal : `git no está disponible` / `rsync no está disponible` | outil absent du serveur : le signaler au support o2switch |
| `/api/auth.php` s'affiche comme du texte ou se télécharge | PHP n'est pas actif pour ce domaine (étape 1.3). **Ne pas continuer** |
| `/api/auth` renvoie 404 | `.htaccess` absent du dossier web, ou `mod_rewrite` inactif |
| La fenêtre de connexion affiche « Falta github_client_id » | fichier de secrets absent, mal placé ou incomplet (étape 4) |
| La fenêtre de connexion se ferme sans rien faire | callback URL de l'OAuth App ≠ `https://DOMAINE/api/callback` |
| « Estado no válido » | cookies bloqués, ou HTTP au lieu de HTTPS |
| « La cuenta … no tiene permiso » | la personne n'est pas collaboratrice du dépôt |
| « Traducción no disponible » à la publication | clé DeepL absente/erronée, ou quota du mois épuisé. La fiche est publiée quand même |
| Le `.htaccess` perd sa configuration PHP après une mise à jour | cPanel y avait écrit la version de PHP et le script l'a remplacé : la choisir à nouveau dans le *Sélecteur de version PHP* |
