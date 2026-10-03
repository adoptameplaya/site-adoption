import json, subprocess, time, sys, urllib.request, urllib.error, os, re
PHP = os.environ["PHP_BIN"]
ROOT = sys.argv[1]; PORT = 8771
srv = subprocess.Popen([PHP, "-d", "display_errors=0", "-S", f"127.0.0.1:{PORT}", "-t", ROOT], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(0.8)
def cfg(**k): open(f"{ROOT}/stub.cfg", "w").write(json.dumps(k))
def secrets(deepl=""):
    open(f"{ROOT}/secrets.php", "w").write(f"<?php return ['github_client_id'=>'CID','github_client_secret'=>'SEC','github_repo'=>'o/r','site_url'=>'https://x.org','deepl_key'=>'{deepl}'];")
def call(path, method="GET", headers=None, body=None):
    req = urllib.request.Request(f"http://127.0.0.1:{PORT}{path}", method=method, headers=headers or {}, data=body.encode() if body is not None else None)
    class SinRedireccion(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *a, **k): return None     # se lee la redirección, no se sigue
    try:
        r = urllib.request.build_opener(SinRedireccion).open(req, timeout=20); return r.status, dict(r.headers), r.read().decode()
    except urllib.error.HTTPError as e: return e.code, dict(e.headers), e.read().decode()
def log(): 
    try: return [json.loads(l) for l in open(f"{ROOT}/stub.log")]
    except FileNotFoundError: return []
def reset_log():
    try: os.remove(f"{ROOT}/stub.log")
    except FileNotFoundError: pass
ok = fail = 0
def check(n, c, d=""):
    global ok, fail
    if c: ok += 1; print("  ✓", n)
    else: fail += 1; print("  ✗", n, "→", d)
J = {"Content-Type": "application/json"}
def tr(textos, token="good", extra=None):
    h = dict(J); 
    if token: h["X-Token-GitHub"] = token
    return call("/traducir.php", "POST", h, json.dumps({"textos": textos} if extra is None else extra, ensure_ascii=False))
try:
    print("— callback.php : succès, token hostile pour tester l'échappement")
    secrets(); hostile = "gho_A</script><script>alert(1)</script>\"'&\\"
    cfg(token_body=json.dumps({"access_token": hostile, "token_type": "bearer"}))
    reset_log()
    s, h, b = call("/callback.php?code=C0DE&state=ST", headers={"Cookie": "oauth_state=ST"})
    check("200 HTML", s == 200 and "text/html" in h.get("Content-Type", ""), (s, b[:100]))
    check("un seul </script> (celui de la page)", b.count("</script>") == 1, b.count("</script>"))
    check("pas de <script> injecté", b.count("<script>") == 1)
    m = re.search(r"var mensaje = (\".*?\");\n", b, re.S)
    msg = json.loads(m.group(1)) if m else ""
    pref = "authorization:github:success:"
    check("message = préfixe Decap + JSON", msg.startswith(pref), msg[:60])
    data = json.loads(msg[len(pref):]) if msg.startswith(pref) else {}
    check("le token arrive intact (aller-retour exact)", data.get("token") == hostile and data.get("provider") == "github", data)
    check("cookie d'état effacé", "oauth_state=" in h.get("Set-Cookie", "") and ("1970" in h.get("Set-Cookie", "") or "Max-Age=0" in h.get("Set-Cookie", "") or "expires" in h.get("Set-Cookie", "").lower()), h.get("Set-Cookie"))
    check("no-store", "no-store" in h.get("Cache-Control", ""))
    L = log()
    sent = json.loads(L[0]["b"]) if L else {}
    check("échange envoyé avec client_id, secret, code", sent == {"client_id": "CID", "client_secret": "SEC", "code": "C0DE"}, sent)
    check("le secret n'est jamais dans la page", "SEC" not in b.replace("SECURE", ""))
    cfg(token_body=json.dumps({"error": "bad_verification_code", "error_description": "The code passed is incorrect or expired."}))
    s, h, b = call("/callback.php?code=C0DE&state=ST", headers={"Cookie": "oauth_state=ST"})
    check("erreur GitHub → 401 avec motif", s == 401 and "incorrect or expired" in b, (s, b))
    cfg(token_body="")
    s, h, b = call("/callback.php?code=C0DE&state=ST", headers={"Cookie": "oauth_state=ST"})
    check("réponse vide → 401 « respuesta vacía »", s == 401 and "vacía" in b, (s, b))

    print("— traducir.php : succès")
    secrets("CLAVE-GRATIS:fx"); cfg(); reset_log()
    s, h, b = tr(["Hola, soy Ñoño", "Cariñosa y juguetona"])
    d = json.loads(b)
    check("200 ok + traductions dans l'ordre", s == 200 and d == {"ok": True, "textos": ["EN: Hola, soy Ñoño", "EN: Cariñosa y juguetona"]}, (s, b))
    check("accents non échappés en \\uXXXX", "Ñoño" in b)
    L = log(); dl = [x for x in L if "deepl" in x["u"]][0]
    check("clé :fx → api-free.deepl.com", dl["u"] == "https://api-free.deepl.com/v2/translate", dl["u"])
    check("en-tête DeepL-Auth-Key", "Authorization: DeepL-Auth-Key CLAVE-GRATIS:fx" in dl["h"], dl["h"])
    body = json.loads(dl["b"])
    check("ES → EN-US, textes transmis", body["source_lang"] == "ES" and body["target_lang"] == "EN-US" and body["text"] == ["Hola, soy Ñoño", "Cariñosa y juguetona"], body)
    gh = [x for x in L if "api.github.com" in x["u"]][0]
    check("permission vérifiée sur le bon dépôt", gh["u"] == "https://api.github.com/repos/o/r", gh["u"])
    secrets("CLAVE-PAYANTE"); reset_log(); tr(["hola"])
    check("clé sans :fx → api.deepl.com", [x for x in log() if "deepl" in x["u"]][0]["u"] == "https://api.deepl.com/v2/translate")

    print("— traducir.php : refus et erreurs")
    secrets("K:fx")
    s, h, b = tr(["hola"], token="ro"); check("compte lecture seule → 403", s == 403, (s, b))
    reset_log(); s, h, b = tr(["hola"], token="ro")
    check("…et DeepL n'est jamais appelé", not [x for x in log() if "deepl" in x["u"]])
    secrets(""); s, h, b = tr(["hola"]); check("sans clé DeepL → 503 message clair", s == 503 and "configurada" in json.loads(b)["error"], (s, b))
    secrets("K:fx")
    cfg(deepl_status=456); s, h, b = tr(["hola"]); check("quota DeepL (456) → 429", s == 429 and "cuota" in json.loads(b)["error"], (s, b))
    cfg(deepl_status=500); s, h, b = tr(["hola"]); check("DeepL en panne → 502", s == 502, (s, b))
    cfg(deepl_count=1); s, h, b = tr(["a", "b"]); check("réponse incomplète → 502 (jamais de décalage de textes)", s == 502, (s, b))
    cfg()
    s, h, b = tr([]); check("liste vide → 400", s == 400, (s, b))
    s, h, b = tr(["x"] * 21); check("21 textes → 400", s == 400, (s, b))
    s, h, b = tr(["ok", ""]); check("texte vide → 400", s == 400, (s, b))
    s, h, b = tr(["ok", 5]); check("non-chaîne → 400", s == 400, (s, b))
    s, h, b = tr(["a" * 6001, "b" * 6001]); check("trop de texte → 413", s == 413, (s, b))
    s, h, b = call("/traducir.php", "POST", {"X-Token-GitHub": "good"}, "pas du json"); check("JSON invalide → 400", s == 400, (s, b))
    s, h, b = tr(["hola"], token="malo"); check("token refusé par GitHub → 403", s == 403, (s, b))
    print("— secrets hors du dossier web (recommandé)")
    secrets("K:fx")
    dehors = os.path.join(os.path.dirname(ROOT.rstrip("/")), "secrets-adoptameplaya.php")
    open(dehors, "w").write("<?php return ['github_client_id'=>'DEHORS','github_client_secret'=>'S','site_url'=>'https://x.org'];")
    try:
        s, h, b = call("/auth.php")
        check("le fichier hors dossier web a la priorité", "client_id=DEHORS" in h.get("Location", ""), h.get("Location"))
    finally:
        os.remove(dehors)
    s, h, b = call("/auth.php")
    check("sans lui, retombe sur api/secrets.php", "client_id=CID" in h.get("Location", ""), h.get("Location"))
finally:
    srv.terminate()
print(f"\n{ok} réussis, {fail} échoués"); sys.exit(1 if fail else 0)
