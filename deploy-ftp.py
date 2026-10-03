#!/usr/bin/env python3
"""
Publie un dossier sur l'hébergement par FTPS, en n'envoyant que ce qui a changé.

    python3 deploy-ftp.py dist/preprod                 # variables d'environnement
    python3 deploy-ftp.py dist/preprod --dry-run       # montre sans rien faire
    python3 deploy-ftp.py dist/preprod --local /tmp/x  # simule dans un dossier

Variables : FTP_HOST, FTP_USER, FTP_PASSWORD, FTP_DIR (dossier distant, facultatif),
            FTP_TLS=0 pour désactiver le chiffrement (déconseillé),
            FTP_VERIFY_TLS=0 si le certificat du serveur ne porte pas le nom de FTP_HOST.

Principe : le serveur garde un fichier `.deploy-manifest.json` (empreinte de
chaque fichier envoyé). Un envoi ne touche que les fichiers nouveaux ou modifiés,
et ne supprime QUE ceux qu'il avait lui-même envoyés. Tout ce qui a été posé à
la main sur le serveur — typiquement api/secrets.php — n'est jamais touché.

Garde-fou : au PREMIER envoi (pas de manifeste), si le dossier distant contient déjà
un site (index.html, index.php, WordPress…), le script s'arrête au lieu
de l'écraser. Utile sur un hébergement mutualisé qui porte plusieurs sites : une
erreur de dossier ne doit jamais détruire un autre site. FTP_ALLOW_OVERWRITE=1 le
désactive, à n'utiliser qu'en connaissance de cause.

Chaque fichier est envoyé sous un nom temporaire puis renommé : un visiteur ne
tombe jamais sur un fichier à moitié écrit. Le manifeste est écrit en dernier :
si l'envoi est interrompu, le suivant reprend là où il s'est arrêté.
"""
import argparse, hashlib, io, json, os, posixpath, shutil, ssl, sys
from pathlib import Path

MANIFESTE = ".deploy-manifest.json"
# Jamais envoyés ni supprimés, quoi qu'il arrive.
PROTEGES = {"api/secrets.php"}


def empreintes(racine: Path) -> dict:
    out = {}
    for p in sorted(racine.rglob("*")):
        if p.is_file() and p.name != ".DS_Store":
            rel = p.relative_to(racine).as_posix()
            if rel in PROTEGES:
                continue
            out[rel] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


def ordre_envoi(rel: str):
    """Ressources d'abord, pages et .htaccess en dernier : le site bascule d'un coup."""
    fin = rel.endswith(".html") or rel.endswith(".php") or rel.endswith(".htaccess")
    return (fin, rel)


# ---------------------------------------------------------------- cibles
class Local:
    """Cible dans un dossier local : sert aux essais, sans serveur."""
    def __init__(self, dossier): self.base = Path(dossier); self.base.mkdir(parents=True, exist_ok=True)
    def lire(self, rel):
        p = self.base / rel
        return p.read_bytes() if p.is_file() else None
    def envoyer(self, rel, donnees):
        p = self.base / rel; p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_name(p.name + ".deploy-tmp"); tmp.write_bytes(donnees); tmp.replace(p)
    def lister_racine(self):
        return sorted(p.name for p in self.base.iterdir())
    def supprimer(self, rel):
        p = self.base / rel
        if p.is_file(): p.unlink()
    def nettoyer(self, dossiers):
        for d in sorted(dossiers, key=len, reverse=True):
            p = self.base / d
            try: p.rmdir()
            except OSError: pass
    def fermer(self): pass


class Ftp:
    def __init__(self, hote, user, mdp, dossier, tls=True, verifier=True):
        import ftplib
        self.ftplib = ftplib
        if tls:
            ctx = ssl.create_default_context()
            if not verifier:
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
            self.ftp = ftplib.FTP_TLS(context=ctx, timeout=60)
        else:
            self.ftp = ftplib.FTP(timeout=60)
        self.tls = tls
        self.ftp.connect(hote, 21)
        self.ftp.login(user, mdp)
        if tls:
            self.ftp.prot_p()
        if dossier:
            self.ftp.cwd(dossier)
        self.connus = {""}

    def _dossier(self, chemin):
        if chemin in self.connus:
            return
        parent = posixpath.dirname(chemin)
        if parent: self._dossier(parent)
        try:
            self.ftp.mkd(chemin)
        except self.ftplib.error_perm:
            pass   # existe déjà
        self.connus.add(chemin)

    def lire(self, rel):
        tampon = io.BytesIO()
        try:
            self.ftp.retrbinary(f"RETR {rel}", tampon.write)
        except self.ftplib.error_perm:
            return None
        return tampon.getvalue()

    def envoyer(self, rel, donnees):
        self._dossier(posixpath.dirname(rel))
        tmp = rel + ".deploy-tmp"
        self.ftp.storbinary(f"STOR {tmp}", io.BytesIO(donnees))
        try:
            self.ftp.rename(tmp, rel)     # remplace d'un coup quand le serveur le permet
        except self.ftplib.error_perm:
            # d'autres refusent de renommer sur un fichier existant : on le retire d'abord
            try: self.ftp.delete(rel)
            except self.ftplib.error_perm: pass
            self.ftp.rename(tmp, rel)

    def lister_racine(self):
        try:
            return sorted(posixpath.basename(n.rstrip("/")) for n in self.ftp.nlst())
        except self.ftplib.error_perm:
            return []          # « 550 No files found » : dossier vide

    def supprimer(self, rel):
        try: self.ftp.delete(rel)
        except self.ftplib.error_perm: pass

    def nettoyer(self, dossiers):
        for d in sorted(dossiers, key=len, reverse=True):
            try: self.ftp.rmd(d)
            except self.ftplib.all_errors: pass

    def fermer(self):
        try: self.ftp.quit()
        except Exception: self.ftp.close()


# ---------------------------------------------------------------- principal
# Présence d'un de ces noms à la racine = « il y a déjà un site ici ».
# (.htaccess seul ne compte pas : cPanel en crée un dès qu'on choisit la version de PHP.)
SIGNES_D_UN_SITE = {"index.html", "index.htm", "index.php", "wp-config.php",
                    "wp-content", "wp-admin", "wp-includes"}


def verifier_dossier_vierge(cible):
    """Premier envoi : refuse d'écraser un site qui n'est pas le nôtre."""
    if os.environ.get("FTP_ALLOW_OVERWRITE") == "1":
        print("⚠ FTP_ALLOW_OVERWRITE=1 : contrôle du dossier distant désactivé")
        return
    presents = sorted(SIGNES_D_UN_SITE & set(cible.lister_racine()))
    if presents:
        sys.exit(
            "ARRÊT : le dossier distant contient déjà un site (" + ", ".join(presents) + ") "
            "et n'a jamais été déployé par ce script.\n"
            "Rien n'a été modifié. Vérifie FTP_DIR et le dossier du compte FTP : sur un hébergement "
            "qui porte plusieurs sites, ce dossier doit être celui du domaine du refuge, "
            "jamais public_html s'il sert un autre site.\n"
            "Si c'est bien le bon dossier et que tu acceptes d'écraser son contenu : "
            "variable FTP_ALLOW_OVERWRITE=1.")


def deployer(racine: Path, cible, dry_run=False):
    local = empreintes(racine)

    brut = cible.lire(MANIFESTE)
    premier = brut is None
    anciens = json.loads(brut) if brut else {}
    if premier:
        print("aucun manifeste distant : premier envoi, tout sera déposé")
        verifier_dossier_vierge(cible)
    else:
        print(f"manifeste distant : {len(anciens)} fichiers connus")

    a_envoyer = [r for r in sorted(local, key=ordre_envoi) if anciens.get(r) != local[r]]
    a_supprimer = [r for r in anciens if r not in local and r not in PROTEGES]

    print(f"{len(a_envoyer)} à envoyer, {len(a_supprimer)} à supprimer, "
          f"{len(local) - len(a_envoyer)} inchangés")
    if dry_run:
        for r in a_envoyer: print("  + ", r)
        for r in a_supprimer: print("  - ", r)
        return

    if premier:
        # Marque le dossier comme géré par ce script : si cet envoi est interrompu,
        # le suivant reprendra sans que le garde-fou ne prenne nos fichiers pour un autre site.
        cible.envoyer(MANIFESTE, b"{}")

    for i, rel in enumerate(a_envoyer, 1):
        cible.envoyer(rel, (racine / rel).read_bytes())
        print(f"  [{i}/{len(a_envoyer)}] {rel}")
    for rel in a_supprimer:
        cible.supprimer(rel)
        print(f"  supprimé {rel}")
    cible.nettoyer({posixpath.dirname(r) for r in a_supprimer if posixpath.dirname(r)})

    cible.envoyer(MANIFESTE, json.dumps(local, indent=1, sort_keys=True).encode())
    print("✓ publication terminée")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dossier", help="dossier à publier (ex. dist/preprod)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--local", metavar="DOSSIER", help="publier dans un dossier local (essai)")
    a = ap.parse_args()

    racine = Path(a.dossier).resolve()
    if not (racine / "index.html").is_file():
        sys.exit(f"ERREUR : {racine} ne contient pas index.html — rien n'est publié.")

    if a.local:
        cible = Local(a.local)
    else:
        env = os.environ
        manque = [k for k in ("FTP_HOST", "FTP_USER", "FTP_PASSWORD") if not env.get(k)]
        if manque:
            sys.exit("ERREUR : variables manquantes : " + ", ".join(manque))
        tls = env.get("FTP_TLS", "1") != "0"
        if not tls:
            print("⚠ FTP sans chiffrement : le mot de passe circule en clair.")
        cible = Ftp(env["FTP_HOST"], env["FTP_USER"], env["FTP_PASSWORD"],
                    env.get("FTP_DIR", "").strip("/"), tls=tls,
                    verifier=env.get("FTP_VERIFY_TLS", "1") != "0")
    try:
        deployer(racine, cible, a.dry_run)
    finally:
        cible.fermer()


if __name__ == "__main__":
    main()
