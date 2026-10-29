"""Geração do relatório HTML (e, opcionalmente, PDF)."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .metricas import Metricas
from .validacao import Diagnostico

_TEMPLATES = Path(__file__).resolve().parent / "templates"
_env = Environment(loader=FileSystemLoader(_TEMPLATES), autoescape=select_autoescape(["html", "j2"]))
_CHARTJS = (_TEMPLATES / "vendor" / "chart.umd.min.js").read_text(encoding="utf-8")


def _fmt(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def _dec(valor: float, casas: int = 1, sinal: bool = False) -> str:
    """Decimal no padrão brasileiro: 11.0 -> '11,0' (ou '+11,0' com sinal=True)."""
    return f"{valor:{'+' if sinal else ''}.{casas}f}".replace(".", ",")


def gerar_html(m: Metricas, diag: Diagnostico, serie: list[dict], destino: Path,
               idade_critica: int = 30) -> Path:
    dados = {
        "canais": [{"canal": l.canal, "entradas": l.entradas, "fechados": l.fechados} for l in m.canais],
        "serie": serie,
        "idade": m.faixas_idade,
        "assuntos": m.top_assuntos,
    }
    html = _env.get_template("relatorio.html.j2").render(
        m=m, diag=diag, serie=serie, fmt=_fmt, dec=_dec, idade_critica=idade_critica, chartjs=_CHARTJS,
        gerado_em=datetime.now().strftime("%d/%m/%Y às %H:%M"),
        dados_js=json.dumps(dados, ensure_ascii=False).replace("</", "<\\/"),
    )
    destino.write_text(html, encoding="utf-8")
    return destino


def gerar_pdf(html: Path) -> Path:  # pragma: no cover - depende de um navegador instalado
    """Converte o HTML em PDF com um navegador headless (requer: pip install playwright && playwright install chromium)."""
    from playwright.sync_api import sync_playwright

    pdf = html.with_suffix(".pdf")
    with sync_playwright() as p:
        navegador = p.chromium.launch()
        pagina = navegador.new_page(viewport={"width": 1240, "height": 1600})
        pagina.goto(html.resolve().as_uri(), wait_until="networkidle")
        pagina.emulate_media(media="print", color_scheme="light")
        pagina.pdf(path=str(pdf), format="A4", print_background=True,
                   margin={"top": "12mm", "bottom": "12mm", "left": "10mm", "right": "10mm"})
        navegador.close()
    return pdf
