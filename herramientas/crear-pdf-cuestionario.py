#!/usr/bin/env python3
"""Crea el cuestionario de adopción en PDF rellenable (formulario con campos).

Lee las preguntas de data/cuestionario.json (las mismas de la página web) y
dibuja el documento con la identidad de Adopta Me Playa : Letter, tipografía
Poppins, sello del logo, campos rellenables y casillas Sí / No.

Hace falta (no forman parte del sitio, se instalan solo para generar el PDF) :
  · ReportLab y Pillow  (pip install reportlab pillow, mejor en un entorno virtual)
  · el sello del logo : herramientas/sello-adopta-me.png
  · las fuentes Poppins-Regular/Medium/Bold.ttf (Google Fonts, licencia SIL OFL),
    ya incluidas en herramientas/fuentes/

Uso :
  python3 herramientas/crear-pdf-cuestionario.py --especie gato --lang es \
      --salida formularios/Cuestionario_Adopcion_Gato_ES.pdf
"""
import argparse
import io
import json
import sys
from pathlib import Path

from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

RAIZ = Path(__file__).resolve().parent.parent

# Paleta (la del PDF de los perros)
CREMA = (.964706, .933333, .890196)
TERRA = (.709804, .396078, .247059)
MARRON = (.290196, .14902, .117647)
GRIS = (.478431, .396078, .345098)
BORDE = (.85098, .776471, .690196)
CAMPO = (1, .992157, .976471)

ANCHO, ALTO = 612, 792
MARGEN = 50
DERECHA = ANCHO - MARGEN          # 562
INFERIOR = 50                      # nada se dibuja por debajo (el pie va a 38)

TEXTOS = {
    "es": {
        "titulo": "Cuestionario para Adoptantes",
        "nombre": {"perro": "NOMBRE DEL PERRO", "gato": "NOMBRE DEL GATO"},
        "fecha": "Fecha de solicitud",
        "comentario": "Comentario:",
        "si": "Sí", "no": "No",
        "pagina": "Página {n} de {total}",
        "firma_t": "FIRMA, FECHA Y LUGAR",
        "declaracion": "Declaro que la información proporcionada es verídica y acepto los compromisos descritos en este cuestionario.",
        "f_nombre": "Nombre completo", "f_firma": "Firma", "f_fecha": "Fecha", "f_lugar": "Lugar",
    },
    "en": {
        "titulo": "Adopter Questionnaire",
        "nombre": {"perro": "DOG'S NAME", "gato": "CAT'S NAME"},
        "fecha": "Application date",
        "comentario": "Comment:",
        "si": "Yes", "no": "No",
        "pagina": "Page {n} of {total}",
        "firma_t": "SIGNATURE, DATE AND PLACE",
        "declaracion": "I declare that the information provided is true and I accept the commitments described in this questionnaire.",
        "f_nombre": "Full name", "f_firma": "Signature", "f_fecha": "Date", "f_lugar": "Place",
    },
}


def registrar_fuentes(carpeta):
    for nombre, archivo in (("P-Regular", "Poppins-Regular.ttf"),
                            ("P-Medium", "Poppins-Medium.ttf"),
                            ("P-Bold", "Poppins-Bold.ttf")):
        ruta = Path(carpeta) / archivo
        if not ruta.exists():
            sys.exit(f"ERROR : falta la fuente {ruta}")
        pdfmetrics.registerFont(TTFont(nombre, str(ruta)))


def sello(ruta_logo):
    """Sello del logo : imagen de un solo color (#4A261E) con transparencia,
    extraída del PDF de los perros para que quede idéntico."""
    return ImageReader(ruta_logo)


def ancho(texto, fuente, tam):
    return pdfmetrics.stringWidth(texto, fuente, tam)


def partir(texto, fuente, tam, maximo):
    lineas, actual = [], ""
    for palabra in texto.split():
        prueba = (actual + " " + palabra).strip()
        if actual and ancho(prueba, fuente, tam) > maximo:
            lineas.append(actual)
            actual = palabra
        else:
            actual = prueba
    if actual:
        lineas.append(actual)
    return lineas


def etiqueta(texto):
    texto = texto.strip()
    return texto if texto[-1] in "?.:!" else texto + ":"


class Documento:
    def __init__(self, c, datos, especie, lang, logo, total):
        self.c, self.especie, self.lang, self.logo, self.total = c, especie, lang, logo, total
        self.t = TEXTOS[lang]
        self.bloque = datos[especie]
        self.pagina = 1

    # ---------- piezas sueltas ----------
    def color(self, rgb, trazo=False):
        (self.c.setStrokeColorRGB if trazo else self.c.setFillColorRGB)(*rgb)

    def texto(self, x, y, s, fuente, tam, rgb, derecha=False):
        self.color(rgb)
        self.c.setFont(fuente, tam)
        (self.c.drawRightString if derecha else self.c.drawString)(x, y, s)

    def pie(self):
        c = self.c
        self.color(BORDE, True)
        c.setLineWidth(.6)
        c.line(MARGEN, 38, DERECHA, 38)
        self.texto(MARGEN, 26, self.t["titulo"], "P-Regular", 7.5, GRIS)
        self.texto(DERECHA, 26, self.t["pagina"].format(n=self.pagina, total=self.total),
                   "P-Regular", 7.5, GRIS, derecha=True)

    def nueva_pagina(self):
        self.pie()
        self.c.showPage()
        self.pagina += 1
        self.cabecera_corta()

    def cabecera_corta(self):
        c = self.c
        c.drawImage(self.logo, MARGEN, 730, 30, 30, mask="auto")
        self.texto(90, 742, self.t["titulo"], "P-Medium", 10, MARRON)
        self.color(BORDE, True)
        c.setLineWidth(.6)
        c.line(MARGEN, 720, DERECHA, 720)

    def portada(self):
        c = self.c
        self.color(CREMA)
        c.rect(0, 592, ANCHO, 200, stroke=0, fill=1)
        self.color(TERRA)
        c.rect(0, 592, ANCHO, 3, stroke=0, fill=1)
        c.drawImage(self.logo, MARGEN, 622, 130, 130, mask="auto")
        self.texto(200, 710, self.t["titulo"], "P-Bold", 24, MARRON)
        intro = self.bloque.get("intro_pdf", self.bloque["intro"])[self.lang]
        y = 690
        for linea in partir(intro, "P-Regular", 9, DERECHA - 200):
            self.texto(200, y, linea, "P-Regular", 9, GRIS)
            y -= 12.5
        # tarjeta con el nombre del animal
        self.color((1, 1, 1))
        self.color(TERRA, True)
        c.setLineWidth(1.2)
        c.roundRect(MARGEN, 508, DERECHA - MARGEN, 62, 8, stroke=1, fill=1)
        self.texto(66, 548, self.t["nombre"][self.especie], "P-Bold", 10.5, TERRA)
        self.texto(383.44, 548, self.t["fecha"], "P-Medium", 8.5, GRIS)
        self.campo("nombre_" + self.especie, 66.4, 518.4, 296.16, 21.2, borde=TERRA, tam=13)
        self.campo("fecha_solicitud", 383.84, 518.4, 161.76, 21.2)
        return 478                       # arriba de la primera franja

    # ---------- campos ----------
    def campo(self, nombre, x, y, w, h, borde=BORDE, tam=10, multilinea=False):
        """(x, y, w, h) es el rectángulo dibujado ; el campo del formulario lo
        envuelve con medio trazo de margen, como en los PDF de los perros."""
        self.c.acroForm.textfield(
            name=nombre, x=x - .4, y=y - .4, width=w + .8, height=h + .8,
            borderColor=_color(borde), fillColor=_color(CAMPO), textColor=_color(MARRON),
            borderWidth=.8, borderStyle="solid", forceBorder=True,
            fontName="Helvetica", fontSize=0 if multilinea else tam, maxlen=0,
            fieldFlags="multiline" if multilinea else "")

    def casilla(self, nombre, valor, x, y):
        self.c.acroForm.radio(
            name=nombre, value=valor, selected=False, buttonStyle="check", shape="square",
            x=x, y=y, size=12, borderColor=_color(TERRA), fillColor=_color(CAMPO),
            textColor=_color(MARRON), borderWidth=1, borderStyle="solid", forceBorder=True)

    # ---------- bloques ----------
    def franja(self, titulo, arriba):
        self.color(MARRON)
        self.c.roundRect(MARGEN, arriba - 24, DERECHA - MARGEN, 24, 5, stroke=0, fill=1)
        self.texto(62, arriba - 24 + 7, titulo.upper(), "P-Bold", 11, (1, 1, 1))

    def altura(self, q):
        return 47.2 if q["tipo"] == "largo" else 19.2

    def lineas_pregunta(self, q):
        return partir(etiqueta(q[self.lang]), "P-Medium", 9.5, DERECHA - 72)

    def fondo_pregunta(self, L, q):
        n = len(self.lineas_pregunta(q))
        return L - 12.5 * (n - 1) - 10.4 - self.altura(q)

    def pregunta(self, L, q):
        c = self.c
        n = q["n"]
        nombre = f"q{n:02d}"
        lineas = self.lineas_pregunta(q)
        self.color(TERRA)
        c.circle(58, L + 3.5, 8, stroke=0, fill=1)
        s = str(n)
        self.texto(58 - ancho(s, "P-Bold", 7.5) / 2, L + .8, s, "P-Bold", 7.5, (1, 1, 1))
        for i, linea in enumerate(lineas):
            self.texto(72, L - 12.5 * i, linea, "P-Medium", 9.5, MARRON)
        ult = L - 12.5 * (len(lineas) - 1)
        if q["tipo"] == "sino":
            self.casilla(nombre, "si", 72, ult - 26)
            self.texto(88, ult - 23, self.t["si"], "P-Regular", 9, MARRON)
            self.casilla(nombre, "no", 130, ult - 26)
            self.texto(146, ult - 23, self.t["no"], "P-Regular", 9, MARRON)
            self.texto(192, ult - 23, self.t["comentario"], "P-Regular", 8, GRIS)
            x = 192 + ancho(self.t["comentario"], "P-Regular", 8) + 6
            self.campo(nombre + "_comentario", x, ult - 29.6, 561.6 - x, 19.2, tam=9)
        else:
            h = self.altura(q)
            self.campo(nombre, 72.4, ult - 10.4 - h, 489.2, h, multilinea=q["tipo"] == "largo")

    def firma(self, arriba):
        c = self.c
        self.franja(self.t["firma_t"], arriba)
        self.texto(MARGEN, arriba - 40, self.t["declaracion"], "P-Regular", 9, GRIS)
        self.texto(MARGEN, arriba - 60.5, self.t["f_nombre"], "P-Medium", 9.5, MARRON)
        self.campo("firma_nombre", 50.4, arriba - 88.1, 511.2, 21.2)
        self.texto(MARGEN, arriba - 106.5, self.t["f_firma"], "P-Medium", 9.5, MARRON)
        self.campo("firma", 50.4, arriba - 154.1, 511.2, 41.2, tam=14)
        self.texto(MARGEN, arriba - 172.5, self.t["f_fecha"], "P-Medium", 9.5, MARRON)
        self.texto(314, arriba - 172.5, self.t["f_lugar"], "P-Medium", 9.5, MARRON)
        self.campo("firma_fecha", 50.4, arriba - 200.1, 247.2, 21.2)
        self.campo("firma_lugar", 314.4, arriba - 200.1, 247.2, 21.2)

    # ---------- recorrido ----------
    def construir(self):
        arriba = self.portada()
        fondo = 0
        for sec in self.bloque["secciones"]:
            primera = sec["preguntas"][0]
            L0 = arriba - 24 - 20
            if self.fondo_pregunta(L0, primera) < INFERIOR:
                self.nueva_pagina()
                arriba = 696
                L0 = arriba - 24 - 20
            self.franja(sec[self.lang], arriba)
            L = L0
            for q in sec["preguntas"]:
                fondo = self.fondo_pregunta(L, q)
                if fondo < INFERIOR:
                    self.nueva_pagina()
                    L = 692
                    fondo = self.fondo_pregunta(L, q)
                self.pregunta(L, q)
                L = fondo - 22.4
            arriba = fondo - 18.4
        if arriba - 200.1 < INFERIOR:
            self.nueva_pagina()
            arriba = 696
        self.firma(arriba)
        self.pie()
        self.c.showPage()


def _color(rgb):
    from reportlab.lib.colors import Color
    return Color(*rgb)


def generar(datos, especie, lang, logo, salida):
    """Dos pasadas : la primera cuenta las páginas (para «Página n de N»)."""
    total = 0
    for paso in (1, 2):
        buf = io.BytesIO() if paso == 1 else None
        c = canvas.Canvas(buf if buf else str(salida), pagesize=(ANCHO, ALTO), invariant=1, pageCompression=1)
        t = TEXTOS[lang]
        c.setTitle(f'{t["titulo"]} · {"Gatos" if especie == "gato" else "Perros"} · Adopta Me Playa'
                   if lang == "es" else
                   f'{t["titulo"]} · {"Cats" if especie == "gato" else "Dogs"} · Adopta Me Playa')
        c.setAuthor("Adopta Me Playa")
        doc = Documento(c, datos, especie, lang, logo, total or 1)
        doc.construir()
        c.save()
        total = doc.pagina
    return total


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--especie", choices=("perro", "gato"), required=True)
    ap.add_argument("--lang", choices=("es", "en"), required=True)
    ap.add_argument("--fuentes", default=str(RAIZ / "herramientas" / "fuentes"), help="carpeta con Poppins-Regular/Medium/Bold.ttf")
    ap.add_argument("--salida", required=True)
    ap.add_argument("--datos", default=str(RAIZ / "data" / "cuestionario.json"))
    ap.add_argument("--logo", default=str(RAIZ / "herramientas" / "sello-adopta-me.png"))
    a = ap.parse_args()

    registrar_fuentes(a.fuentes)
    datos = json.load(open(a.datos, encoding="utf-8"))
    if not datos.get(a.especie, {}).get("secciones"):
        sys.exit(f"ERROR : no hay preguntas para «{a.especie}» en {a.datos}")
    paginas = generar(datos, a.especie, a.lang, sello(a.logo), a.salida)
    print(f"{a.salida} : {paginas} páginas")


if __name__ == "__main__":
    main()
