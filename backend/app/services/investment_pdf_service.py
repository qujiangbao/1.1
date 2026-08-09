"""Stable PDF rendering for an immutable investment scenario snapshot."""
from __future__ import annotations

from io import BytesIO
from xml.sax.saxutils import escape

from app.database.models.investment import InvestmentScenario
from app.schemas.investment_candidate import RecommendationCard


DIMENSION_LABELS = {
    "industry_fit": "产业匹配度",
    "technology": "技术能力",
    "growth": "成长潜力",
    "landing_intent": "落地意愿",
    "policy_fit": "政策适配度",
    "data_completeness": "数据完整度",
}
RISK_LABELS = {
    "HIGH": "高风险",
    "MEDIUM": "中风险",
    "LOW": "低风险",
    "UNKNOWN": "待核验",
}


def _text(value: object) -> str:
    return escape(str(value if value not in (None, "") else "—"))


def render_investment_scenario_pdf(scenario: InvestmentScenario) -> bytes:
    """Render from the persisted snapshot only; never rerun an Agent."""

    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    from reportlab.platypus import (
        HRFlowable,
        PageBreak,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=16 * mm,
        leftMargin=16 * mm,
        topMargin=18 * mm,
        bottomMargin=17 * mm,
        title=f"{scenario.name} - 招商研判报告",
        author="广州产业AI运营官",
    )
    base = getSampleStyleSheet()
    body = ParagraphStyle(
        "ChineseBody",
        parent=base["BodyText"],
        fontName="STSong-Light",
        fontSize=9,
        leading=14,
        textColor=colors.HexColor("#344054"),
    )
    small = ParagraphStyle(
        "ChineseSmall",
        parent=body,
        fontSize=7.5,
        leading=11,
        textColor=colors.HexColor("#667085"),
    )
    heading = ParagraphStyle(
        "ChineseHeading",
        parent=base["Heading2"],
        fontName="STSong-Light",
        fontSize=15,
        leading=21,
        textColor=colors.HexColor("#102A43"),
        spaceAfter=8,
    )
    title = ParagraphStyle(
        "ChineseTitle",
        parent=heading,
        fontSize=24,
        leading=32,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#0D47A1"),
        spaceAfter=10,
    )
    kicker = ParagraphStyle(
        "ChineseKicker",
        parent=body,
        fontSize=8,
        leading=12,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#1677FF"),
        spaceAfter=5,
    )
    card_heading = ParagraphStyle(
        "ChineseCardHeading",
        parent=heading,
        fontSize=13,
        leading=18,
    )

    metadata = scenario.snapshot_metadata or {}
    recommendations = [
        RecommendationCard.model_validate(item)
        for item in (scenario.recommendation_snapshot or [])
    ]
    generated_at = metadata.get("generated_at") or scenario.created_at.isoformat()
    story = [
        Paragraph("INDUSTRIAL AI DECISION REPORT", kicker),
        Paragraph(_text(scenario.name), title),
        Paragraph(
            "本报告基于已固化的招商场景快照生成，不会在导出时重新调用模型或修改评分。",
            ParagraphStyle(
                "ChineseSubtitle",
                parent=body,
                alignment=TA_CENTER,
                fontSize=10,
                leading=16,
            ),
        ),
        Spacer(1, 10 * mm),
    ]
    overview = [
        ["场景ID", scenario.id, "数据模式", scenario.data_mode],
        ["产业方向", scenario.industry, "候选企业", f"{len(recommendations)} 家"],
        [
            "目标环节",
            "、".join(scenario.target_chain_roles or []) or "—",
            "生成时间",
            str(generated_at),
        ],
        [
            "评分版本",
            str(metadata.get("version") or "—"),
            "编排版本",
            str(metadata.get("orchestration_version") or "—"),
        ],
    ]
    overview_table = Table(
        [[Paragraph(_text(cell), body) for cell in row] for row in overview],
        colWidths=[24 * mm, 58 * mm, 24 * mm, 62 * mm],
    )
    overview_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F0F7FF")),
                ("BACKGROUND", (2, 0), (2, -1), colors.HexColor("#F0F7FF")),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#D9E2EC")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.extend(
        [
            overview_table,
            Spacer(1, 7 * mm),
            Paragraph("决策边界", heading),
            Paragraph(
                "Agent 负责调查并返回带证据的结构化结果；确定性聚合器负责校验和计算。"
                "LLM 不能直接修改评分、风险等级或政策资格。缺失数据保持为空，不按0分处理。",
                body,
            ),
            Spacer(1, 5 * mm),
            HRFlowable(color=colors.HexColor("#D9E2EC"), thickness=0.7),
            Spacer(1, 5 * mm),
        ]
    )
    if recommendations:
        story.append(PageBreak())

    for index, card in enumerate(recommendations, start=1):
        if index > 1:
            story.append(PageBreak())
        score = "证据不足" if card.overall_score is None else f"{card.overall_score:.1f} 分"
        story.extend(
            [
                Paragraph(
                    f"{index:02d} · {_text(card.enterprise_name)}",
                    card_heading,
                ),
                Table(
                    [
                        [
                            Paragraph(f"<b>推荐分</b><br/>{_text(score)}", body),
                            Paragraph(
                                f"<b>数据置信度</b><br/>{round((card.confidence or 0) * 100)}%",
                                body,
                            ),
                            Paragraph(
                                f"<b>风险</b><br/>{_text(RISK_LABELS[card.risk.level])}",
                                body,
                            ),
                            Paragraph(
                                f"<b>证据</b><br/>{len(card.evidence)} 条",
                                body,
                            ),
                        ]
                    ],
                    colWidths=[42 * mm] * 4,
                    style=TableStyle(
                        [
                            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F6F8FB")),
                            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#D9E2EC")),
                            ("INNERGRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#E8EDF3")),
                            ("VALIGN", (0, 0), (-1, -1), "TOP"),
                            ("LEFTPADDING", (0, 0), (-1, -1), 8),
                            ("TOPPADDING", (0, 0), (-1, -1), 7),
                            ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                        ]
                    ),
                ),
                Spacer(1, 4 * mm),
                Paragraph(f"<b>建议：</b>{_text(card.recommendation)}", body),
                Paragraph(f"<b>下一步：</b>{_text(card.next_action)}", body),
                Spacer(1, 4 * mm),
                Paragraph("六维评分", heading),
            ]
        )
        dimension_rows = [["维度", "分数", "权重", "依据"]]
        for key, dimension in card.score_breakdown.items():
            dimension_rows.append(
                [
                    DIMENSION_LABELS.get(key, key),
                    "证据不足"
                    if dimension.score is None
                    else f"{dimension.score:.1f}",
                    f"{dimension.weight * 100:.0f}%",
                    dimension.reason,
                ]
            )
        dimension_table = Table(
            [
                [Paragraph(_text(cell), small) for cell in row]
                for row in dimension_rows
            ],
            colWidths=[25 * mm, 22 * mm, 18 * mm, 103 * mm],
            repeatRows=1,
        )
        dimension_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1677FF")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#D9E2EC")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ]
            )
        )
        story.extend([dimension_table, Spacer(1, 4 * mm)])
        policy_summary = "、".join(
            f"{match.title}（{match.match_type}）"
            for match in card.policy_matches
        ) or "尚无带结构化申报条件的政策核验结果"
        story.extend(
            [
                Paragraph(f"<b>风险核验：</b>{_text(card.risk.reason)}", body),
                Paragraph(f"<b>政策核验：</b>{_text(policy_summary)}", body),
                Paragraph(
                    f"<b>数据缺口：</b>{_text('、'.join(card.unknown_fields) or '暂无')}",
                    body,
                ),
                Spacer(1, 4 * mm),
                Paragraph("证据摘要", heading),
            ]
        )
        evidence_rows = [["字段", "主张", "来源", "置信度"]]
        for evidence in card.evidence[:12]:
            evidence_rows.append(
                [
                    evidence.field,
                    evidence.claim,
                    evidence.source_title,
                    f"{evidence.confidence * 100:.0f}%",
                ]
            )
        evidence_table = Table(
            [
                [Paragraph(_text(cell), small) for cell in row]
                for row in evidence_rows
            ],
            colWidths=[28 * mm, 65 * mm, 58 * mm, 17 * mm],
            repeatRows=1,
        )
        evidence_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EAF3FF")),
                    ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#D9E2EC")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 5),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        story.append(evidence_table)

    limitations = metadata.get("limitations") or []
    if limitations:
        story.extend(
            [
                PageBreak(),
                Paragraph("已知限制与人工复核要求", heading),
                *[
                    Paragraph(f"- {_text(item)}", body)
                    for item in limitations
                ],
            ]
        )

    def page_footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("STSong-Light", 7)
        canvas.setFillColor(colors.HexColor("#667085"))
        canvas.drawString(16 * mm, 9 * mm, f"场景快照：{scenario.id}")
        canvas.drawRightString(
            A4[0] - 16 * mm,
            9 * mm,
            f"第 {doc.page} 页",
        )
        canvas.restoreState()

    document.build(
        story,
        onFirstPage=page_footer,
        onLaterPages=page_footer,
    )
    return buffer.getvalue()
