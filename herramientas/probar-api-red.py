import json, subprocess, time, sys, urllib.request, urllib.error, os
PHP = os.environ["PHP_BIN"]
ROOT = sys.argv[1]; PORT = 8770
def serve():
    p = subprocess.Popen([PHP, "-d", "display_errors=0", "-S", f"127.0.0.1:{PORT}", "-t", ROOT],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(0.8); return p
def call(path, method="GET", headers=None, body=None, follow=False):
    req = urllib.request.Request(f"http://127.0.0.1:{PORT}{path}", method=method, headers=headers or {},
                                 data=body.encode() if isinstance(body, str) else body)
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *a, **k): return None
    op = urllib.request.build_opener(NoRedirect)
    try:
        r = op.open(req, timeout=20); return r.status, dict(r.headers), r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read().decode()
ok = fail = 0
def check(nom, cond, detalle=""):
    global ok, fail
    if cond: ok += 1; print("  ✓", nom)
    else: fail += 1; print("  ✗", nom, "→", detalle)

srv = serve()
try:
    print("— auth.php sans secrets.php")
    s, h, b = call("/auth.php"); check("500 + message clair", s == 500 and "github_client_id" in b, (s, b))

    open(f"{ROOT}/secrets.php", "w").write("<?php return ['github_client_id'=>'CLIENT123','github_client_secret'=>'SECRETXYZ','site_url'=>'https://adoptameplaya.org','deepl_key'=>''];")
    print("— auth.php avec secrets de test")
    s, h, b = call("/auth.php")
    loc = h.get("Location", ""); ck = h.get("Set-Cookie", "")
    check("302 vers GitHub", s == 302 and loc.startswith("https://github.com/login/oauth/authorize?"), (s, loc))
    check("client_id", "client_id=CLIENT123" in loc)
    check("redirect_uri = site_url + /api/callback", "redirect_uri=https%3A%2F%2Fadoptameplaya.org%2Fapi%2Fcallback" in loc, loc)
    check("scope public_repo (moindre privilège)", "scope=public_repo" in loc, loc)
    check("le secret n'apparaît jamais", "SECRETXYZ" not in loc + ck + b)
    state = loc.split("state=")[1].split("&")[0]
    check("state aléatoire de 32 car. hex", len(state) == 32 and all(c in "0123456789abcdef" for c in state), state)
    check("cookie oauth_state = state", f"oauth_state={state}" in ck, ck)
    check("cookie HttpOnly + Secure + SameSite=Lax", all(x in ck for x in ("HttpOnly", "secure", "SameSite=Lax")) or all(x.lower() in ck.lower() for x in ("httponly", "secure", "samesite=lax")), ck)
    check("no-store", "no-store" in h.get("Cache-Control", ""))
    s2, h2, _ = call("/auth.php"); st2 = h2["Location"].split("state=")[1].split("&")[0]
    check("state différent à chaque appel", st2 != state)

    print("— callback.php : refus")
    s, h, b = call("/callback.php"); check("sans code → 400", s == 400, (s, b))
    s, h, b = call("/callback.php?code=abc&state=zzz"); check("sans cookie → 400", s == 400 and "Estado" in b, (s, b))
    s, h, b = call("/callback.php?code=abc&state=zzz", headers={"Cookie": "oauth_state=otro"}); check("state ≠ cookie → 400", s == 400, (s, b))

    print("— callback.php : vrai GitHub, faux identifiants (doit refuser proprement)")
    s, h, b = call("/callback.php?code=abc&state=zzz", headers={"Cookie": "oauth_state=zzz"})
    check("401 « GitHub no devolvió un token »", s == 401 and "GitHub no devolvió un token" in b, (s, b[:200]))
    check("le message n'expose pas le secret", "SECRETXYZ" not in b)

    print("— traducir.php : refus")
    s, h, b = call("/traducir.php"); check("GET → 405 JSON", s == 405 and json.loads(b)["ok"] is False, (s, b))
    s, h, b = call("/traducir.php", "POST", {"Content-Type": "application/json"}, "{}"); check("sans token → 401", s == 401, (s, b))
    s, h, b = call("/traducir.php", "POST", {"Content-Type": "application/json", "X-Token-GitHub": "x" * 300}, "{}"); check("token démesuré → 401", s == 401, (s, b))
    s, h, b = call("/traducir.php", "POST", {"Content-Type": "application/json", "X-Token-GitHub": "ghp_faux_token"}, '{"textos":["hola"]}')
    check("faux token → vrai GitHub refuse → 403", s == 403 and json.loads(b)["ok"] is False, (s, b))
    check("JSON + no-store", "application/json" in h.get("Content-Type", "") and "no-store" in h.get("Cache-Control", ""))

    print("— protection des fichiers internes (serveur PHP intégré : informatif)")
    s, h, b = call("/secrets.php"); check("secrets.php n'affiche rien", b.strip() == "", (s, b[:80]))
    s, h, b = call("/_comun.php"); check("_comun.php n'affiche rien", b.strip() == "", (s, b[:80]))
finally:
    srv.terminate()
print(f"\n{ok} réussis, {fail} échoués"); sys.exit(1 if fail else 0)
