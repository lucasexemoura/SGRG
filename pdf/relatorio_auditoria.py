"""Relatório de auditoria em A4, com gráfico vetorial para impressão."""

from datetime import date, datetime, timezone
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

import reportlab
from reportlab.graphics.shapes import Drawing, Line, Rect, String
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


AZUL = colors.HexColor("#0F4C81")
CINZA = colors.HexColor("#475569")
CLARO = colors.HexColor("#F1F5F9")
BORDA = colors.HexColor("#CBD5E1")

# Fontes distribuídas com o ReportLab: ficam incorporadas no PDF para impressão.
FONTES = Path(reportlab.__file__).parent / "fonts"
pdfmetrics.registerFont(TTFont("SGRGAuditoria", str(FONTES / "Vera.ttf")))
pdfmetrics.registerFont(TTFont("SGRGAuditoria-Bold", str(FONTES / "VeraBd.ttf")))
pdfmetrics.registerFontFamily("SGRGAuditoria", normal="SGRGAuditoria", bold="SGRGAuditoria-Bold")


def _texto(valor, padrao="-"):
    if valor is None or valor == "":
        valor = padrao
    return escape(str(valor)).replace("\r\n", "\n").replace("\r", "\n").replace("\n", "<br/>")


def _data(valor):
    if not valor:
        return "Não informado"
    try:
        return date.fromisoformat(str(valor)[:10]).strftime("%d/%m/%Y")
    except ValueError:
        return str(valor)


def _percentual(valor):
    return f"{valor:.1f}%".replace(".", ",") if valor is not None else "-"


def _grafico(resultados, largura):
    """Desenha uma barra por tópico no PDF, sem depender do navegador."""
    altura_linha = 22
    altura = len(resultados) * altura_linha + 35
    desenho = Drawing(largura, altura)
    inicio_x = 195
    largura_barras = largura - inicio_x - 43

    for marca in (0, 25, 50, 75, 100):
        x = inicio_x + largura_barras * marca / 100
        desenho.add(Line(x, 25, x, altura - 5, strokeColor=BORDA, strokeWidth=0.4))
        desenho.add(String(x, 10, f"{marca}%", fontName="SGRGAuditoria", fontSize=7,
                           fillColor=CINZA, textAnchor="middle"))

    for indice, resultado in enumerate(resultados):
        y = altura - 22 - indice * altura_linha
        percentual = resultado["percentual"]
        desenho.add(String(0, y + 1, resultado["titulo"], fontName="SGRGAuditoria",
                           fontSize=8, fillColor=CINZA))
        desenho.add(Rect(inicio_x, y - 2, largura_barras, 12,
                         fillColor=CLARO, strokeColor=None))
        if percentual is not None and percentual > 0:
            desenho.add(Rect(inicio_x, y - 2,
                             largura_barras * min(percentual, 100) / 100, 12,
                             fillColor=AZUL, strokeColor=None))
        desenho.add(String(inicio_x + largura_barras + 7, y,
                           _percentual(percentual), fontName="SGRGAuditoria-Bold",
                           fontSize=8, fillColor=AZUL))
    return desenho


def gerar_relatorio_auditoria_pdf(auditoria, resultados, planos, conformidade_geral):
    """Retorna um PDF em memória com os dados salvos de uma auditoria."""
    arquivo = BytesIO()
    documento = SimpleDocTemplate(
        arquivo, pagesize=A4, leftMargin=1.5 * cm, rightMargin=1.5 * cm,
        topMargin=1.6 * cm, bottomMargin=1.8 * cm,
        title=f"Relatório - {auditoria['nome']}", author="SGRG",
    )
    normal = ParagraphStyle(
        "TextoAuditoria", fontName="SGRGAuditoria", fontSize=9, leading=13,
        textColor=CINZA, spaceAfter=6, splitLongWords=True,
    )
    titulo = ParagraphStyle(
        "TituloAuditoria", parent=normal, fontName="SGRGAuditoria-Bold", fontSize=19,
        leading=23, textColor=AZUL, spaceAfter=6, keepWithNext=True,
    )
    pequeno = ParagraphStyle("PequenoAuditoria", parent=normal, fontSize=8, leading=11)
    secao = ParagraphStyle(
        "SecaoAuditoria", parent=normal, fontName="SGRGAuditoria-Bold", fontSize=11,
        leading=15, textColor=AZUL, spaceBefore=9, spaceAfter=7, keepWithNext=True,
    )
    rotulo = ParagraphStyle(
        "RotuloAuditoria", parent=pequeno, fontName="SGRGAuditoria-Bold",
        spaceAfter=3, keepWithNext=True,
    )
    celula = ParagraphStyle("CelulaAuditoria", parent=pequeno, spaceAfter=0)
    cabecalho = ParagraphStyle(
        "CabecalhoAuditoria", parent=celula, fontName="SGRGAuditoria-Bold",
        textColor=colors.white,
    )

    def paragrafo(valor, estilo=normal, padrao="-"):
        return Paragraph(_texto(valor, padrao), estilo)

    elementos = [
        paragrafo("RELATÓRIO DE AUDITORIA", pequeno),
        paragrafo(auditoria["nome"], titulo),
        paragrafo("HOSPITAL DA MULHER E DA CRIANÇA DO VALE DO JURUÁ", pequeno),
        paragrafo("Sistema de Gestão de Rondas Gerenciais - SGRG", pequeno),
        Spacer(1, 5),
    ]
    identificacao = Table([
        [paragrafo("Data", rotulo), paragrafo(_data(auditoria["data"]), celula),
         paragrafo("Setor", rotulo), paragrafo(auditoria["setor"], celula)],
        [paragrafo("Responsável", rotulo), paragrafo(auditoria["responsavel"], celula), "", ""],
        [paragrafo("Itens avaliados", rotulo),
         paragrafo(auditoria["total_avaliado"], celula),
         paragrafo("Conformidade geral", rotulo),
         paragrafo(_percentual(conformidade_geral), celula)],
    ], colWidths=[documento.width * parte for parte in (0.17, 0.18, 0.20, 0.45)],
       hAlign="LEFT")
    identificacao.setStyle(TableStyle([
        ("SPAN", (1, 1), (3, 1)),
        ("BACKGROUND", (0, 0), (-1, -1), CLARO),
        ("BOX", (0, 0), (-1, -1), 0.5, BORDA),
        ("LINEBELOW", (0, 0), (-1, -1), 0.3, BORDA),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    elementos.extend([identificacao, paragrafo("Resultado do checklist", secao)])

    linhas = [[paragrafo(texto, cabecalho) for texto in
               ("Tópico", "Total avaliado", "Conformes", "Não conformes", "Conformidade")]]
    for resultado in resultados:
        linhas.append([
            paragrafo(resultado["titulo"], celula),
            paragrafo(resultado["total"], celula),
            paragrafo(resultado["conformes"], celula),
            paragrafo(resultado["nao_conformes"], celula),
            paragrafo(_percentual(resultado["percentual"]), celula),
        ])
    tabela = Table(linhas, colWidths=[documento.width * parte for parte in
                                     (0.40, 0.13, 0.14, 0.18, 0.15)],
                   repeatRows=1, hAlign="LEFT")
    tabela.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), AZUL),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, CLARO]),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, BORDA),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    elementos.extend([
        tabela,
        Spacer(1, 6),
        paragrafo("Cada tópico tem seu próprio total (conformes + não conformes). A conformidade geral considera a soma dos itens conformes dividida pelo total dos tópicos avaliados. Tópicos sem avaliação não entram no cálculo.", pequeno),
    ])
    if auditoria.get("prontuarios_revisados") is None:
        elementos.append(paragrafo("Neste registro, foi informada apenas a quantidade de prontuários. A conformidade desse tópico não foi registrada.", pequeno))
    elementos.extend([
        paragrafo("Gráfico de conformidade", secao),
        _grafico(resultados, documento.width),
        paragrafo("Observações do checklist", secao),
    ])
    observacoes = [item for item in resultados if item["observacao"]]
    if not observacoes:
        elementos.append(paragrafo("Nenhuma observação registrada."))
    for resultado in observacoes:
        elementos.extend([paragrafo(resultado["titulo"], rotulo),
                          paragrafo(resultado["observacao"])])

    quantidade_acoes = f"{len(planos)} ação" if len(planos) == 1 else f"{len(planos)} ações"
    elementos.append(paragrafo(f"Plano de ação ({quantidade_acoes})", secao))
    if not planos:
        elementos.append(paragrafo("Nenhuma ação cadastrada para esta auditoria."))
    for indice, plano in enumerate(planos, start=1):
        elementos.append(paragrafo(f"Ação {indice}", rotulo))
        elementos.append(Paragraph(
            f"<b>Responsável:</b> {_texto(plano['responsavel'], 'Não informado')}<br/>"
            f"<b>Prazo:</b> {_texto(_data(plano['prazo']))}"
            f"{' - Atrasado' if plano['atrasado'] else ''}"
            f" | <b>Prioridade:</b> {_texto(plano['prioridade'])}"
            f" | <b>Status:</b> {_texto(plano['status'])}", normal))
        if plano["data_conclusao"]:
            elementos.append(paragrafo(f"Concluída em: {_data(plano['data_conclusao'])}", pequeno))
        elementos.extend([
            Paragraph(f"<b>Problema identificado:</b><br/>{_texto(plano['problema'])}", normal),
            Paragraph(f"<b>Ação corretiva:</b><br/>{_texto(plano['acao'])}", normal),
            Spacer(1, 5),
        ])

    elementos.extend([
        paragrafo("Conclusão", secao),
        paragrafo(auditoria["conclusao"], padrao="Conclusão não registrada."),
    ])
    emissao = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")

    def pagina(canvas, doc):
        canvas.saveState()
        canvas.setFont("SGRGAuditoria", 8)
        canvas.setFillColor(CINZA)
        canvas.drawRightString(A4[0] - doc.rightMargin, A4[1] - 25,
                               "SGRG")
        canvas.setStrokeColor(BORDA)
        canvas.line(doc.leftMargin, 36, A4[0] - doc.rightMargin, 36)
        canvas.drawString(doc.leftMargin, 24, f"SGRG - Emitido em {emissao}")
        canvas.drawRightString(A4[0] - doc.rightMargin, 24, f"Página {doc.page}")
        canvas.restoreState()

    documento.build(elementos, onFirstPage=pagina, onLaterPages=pagina)
    arquivo.seek(0)
    return arquivo
