from __future__ import annotations

from html import escape
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer

from libs.models.run import WorkflowRun
from libs.models.workflow import Workflow


CORAL = colors.HexColor("#FF6D5A")
INK = colors.HexColor("#29262D")
MUTED = colors.HexColor("#756F79")
LINE = colors.HexColor("#DDD8D3")
SOFT = colors.HexColor("#FFF0ED")


def _text(value: str | None, fallback: str = "Not available") -> str:
    return escape(value.strip()) if value and value.strip() else fallback


def _date(value) -> str:
    if not value:
        return "Not finished"
    return value.strftime("%d %b %Y, %H:%M UTC")


def _page(canvas, document) -> None:
    canvas.saveState()
    canvas.setStrokeColor(LINE)
    canvas.line(18 * mm, 14 * mm, A4[0] - 18 * mm, 14 * mm)
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(MUTED)
    canvas.drawString(18 * mm, 9 * mm, "Nodara workflow run report")
    canvas.drawRightString(A4[0] - 18 * mm, 9 * mm, f"Page {document.page}")
    canvas.restoreState()


def build_run_report_pdf(workflow: Workflow, runs: list[WorkflowRun]) -> bytes:
    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=20 * mm,
        title=f"{workflow.name} - Run report",
        author="Nodara",
    )
    base = getSampleStyleSheet()
    styles = {
        "title": ParagraphStyle("Title", parent=base["Title"], fontName="Helvetica-Bold", fontSize=24, leading=29, textColor=INK, alignment=TA_CENTER, spaceAfter=8),
        "subtitle": ParagraphStyle("Subtitle", parent=base["BodyText"], fontSize=10, leading=15, textColor=MUTED, alignment=TA_CENTER, spaceAfter=20),
        "run": ParagraphStyle("Run", parent=base["Heading2"], fontName="Helvetica-Bold", fontSize=16, leading=20, textColor=INK, spaceAfter=5),
        "meta": ParagraphStyle("Meta", parent=base["BodyText"], fontSize=9, leading=13, textColor=MUTED, spaceAfter=12),
        "label": ParagraphStyle("Label", parent=base["Heading3"], fontName="Helvetica-Bold", fontSize=10, leading=13, textColor=INK, spaceBefore=8, spaceAfter=4),
        "body": ParagraphStyle("Body", parent=base["BodyText"], fontSize=10, leading=15, textColor=INK, backColor=colors.white, borderColor=LINE, borderWidth=0.5, borderPadding=8, spaceAfter=8),
        "node": ParagraphStyle("Node", parent=base["BodyText"], fontSize=9, leading=13, textColor=INK, backColor=SOFT, borderPadding=7, spaceAfter=5),
    }
    story = [
        Paragraph(_text(workflow.name, "Workflow report"), styles["title"]),
        Paragraph(
            f"{len(runs)} run{'s' if len(runs) != 1 else ''} - Generated from saved execution history",
            styles["subtitle"],
        ),
    ]

    if not runs:
        story.append(Paragraph("This workflow has no saved runs yet.", styles["body"]))

    for index, run in enumerate(runs):
        if index:
            story.append(PageBreak())
        story.extend([
            Paragraph(f"Run {index + 1}", styles["run"]),
            Paragraph(
                f"Status: <b>{escape(run.status.title())}</b> &nbsp;&nbsp; Started: {_date(run.created_at)} &nbsp;&nbsp; Finished: {_date(run.finished_at)}",
                styles["meta"],
            ),
            Paragraph("Input", styles["label"]),
            Paragraph(_text(run.input), styles["body"]),
            Paragraph("Final output", styles["label"]),
            Paragraph(_text(run.final_output, run.error or "No final output was produced."), styles["body"]),
            Paragraph("Agent results", styles["label"]),
        ])
        for node in run.nodes:
            node_content = (
                f"<b>{escape(node.node_name or node.node_id)}</b> - {escape(node.status.title())}<br/>"
                f"<font color='#756F79'>Input:</font> {_text(node.input)}<br/>"
                f"<font color='#756F79'>Output:</font> {_text(node.output, node.error or 'Not available')}"
            )
            story.append(KeepTogether([Paragraph(node_content, styles["node"]), Spacer(1, 1 * mm)]))

    document.build(story, onFirstPage=_page, onLaterPages=_page)
    return buffer.getvalue()
