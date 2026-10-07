#!/usr/bin/env python3
"""Sert dist/preprod en local (http://127.0.0.1:8124) pour la vue d'ensemble avant publication.
Usage : python3 build-preprod.py && python3 herramientas/servir-vista-previa.py"""
import http.server, os, socketserver
RACINE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "dist", "preprod")

class Manejador(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **k): super().__init__(*a, directory=RACINE, **k)
    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()
    def log_message(self, *a): pass

socketserver.TCPServer.allow_reuse_address = True
with socketserver.TCPServer(("127.0.0.1", 8124), Manejador) as s:
    s.serve_forever()
