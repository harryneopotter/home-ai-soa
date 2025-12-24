"""Report payload builders for Web, PDF, and Infographic output formats."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Dict, List, Optional


@dataclass
class ReportBase:
    title: str
    generated_at: str
    analysis_summary: str


@dataclass
class WebReportPayload(ReportBase):
    format: str = "web"
    html_sections: List[Dict] = None

    def __post_init__(self):
        if self.html_sections is None:
            self.html_sections = []


@dataclass
class PDFReportPayload(ReportBase):
    format: str = "pdf"
    pages: List[Dict] = None

    def __post_init__(self):
        if self.pages is None:
            self.pages = []


@dataclass
class InfographicPayload(ReportBase):
    format: str = "infographic"
    visual_elements: List[Dict] = None

    def __post_init__(self):
        if self.visual_elements is None:
            self.visual_elements = []


def build_web_report_payload(analysis_json: Dict) -> Dict:
    """Build JSON payload for Web report generation (requires user consent)."""

    if not isinstance(analysis_json, dict):
        raise TypeError("analysis_json must be a dictionary")

    payload = WebReportPayload(
        title=analysis_json.get("title", "Financial Analysis Report"),
        generated_at=analysis_json.get("timestamp", ""),
        analysis_summary=analysis_json.get("summary", ""),
        html_sections=[
            {
                "section": "overview",
                "content": analysis_json.get("overview", {}),
            },
            {
                "section": "details",
                "content": analysis_json.get("details", {}),
            },
        ],
    )
    return asdict(payload)


def build_pdf_report_payload(analysis_json: Dict) -> Dict:
    """Build JSON payload for PDF report generation (requires user consent)."""

    if not isinstance(analysis_json, dict):
        raise TypeError("analysis_json must be a dictionary")

    payload = PDFReportPayload(
        title=analysis_json.get("title", "Financial Analysis Report"),
        generated_at=analysis_json.get("timestamp", ""),
        analysis_summary=analysis_json.get("summary", ""),
        pages=[
            {
                "page_num": 1,
                "section": "summary",
                "content": analysis_json.get("summary", ""),
            },
            {
                "page_num": 2,
                "section": "breakdown",
                "content": analysis_json.get("breakdown", {}),
            },
        ],
    )
    return asdict(payload)


def build_infographic_payload(analysis_json: Dict) -> Dict:
    """Build JSON payload for Infographic generation (requires user consent)."""

    if not isinstance(analysis_json, dict):
        raise TypeError("analysis_json must be a dictionary")

    payload = InfographicPayload(
        title=analysis_json.get("title", "Financial Analysis"),
        generated_at=analysis_json.get("timestamp", ""),
        analysis_summary=analysis_json.get("summary", ""),
        visual_elements=[
            {
                "type": "pie_chart",
                "data": analysis_json.get("categories", {}),
                "label": "Spending by Category",
            },
            {
                "type": "bar_chart",
                "data": analysis_json.get("trends", {}),
                "label": "Monthly Trends",
            },
        ],
    )
    return asdict(payload)
