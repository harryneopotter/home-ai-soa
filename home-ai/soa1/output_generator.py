import json
from typing import Dict, Any, Optional


class OutputGenerator:
    async def generate_dashboard_json(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        if not analysis:
            return {}

        dashboard = {
            "summary": analysis.get("summary", {}),
            "charts": {
                "by_category": analysis.get("by_category", {}),
                "by_month": analysis.get("by_month", {}),
                "by_merchant": analysis.get("by_merchant", {}),
            },
            "metrics": {
                "total_spent": analysis.get("total_spent", 0),
                "transaction_count": analysis.get("transaction_count", 0),
                "top_category": analysis.get("top_category", ""),
            },
        }
        return dashboard

    async def build_pdf_prompt(self, analysis: Dict[str, Any]) -> str:
        if not analysis:
            return ""

        prompt = f"""
        Generate a professional financial report based on the following analysis:
        {json.dumps(analysis, indent=2)}
        
        Include sections for:
        - Executive Summary
        - Category Breakdown
        - Monthly Trends
        - Key Recommendations
        """
        return prompt.strip()

    async def build_infographic_prompt(self, analysis: Dict[str, Any]) -> str:
        if not analysis:
            return ""

        prompt = f"""
        Create a visual infographic summary showing:
        - Total Spending: ${analysis.get("total_spent", 0)}
        - Top 5 Categories: {analysis.get("top_categories", [])}
        - Spending Trend: {analysis.get("trend", "stable")}
        """
        return prompt.strip()

    async def generate_text_summary(self, analysis: Dict[str, Any]) -> str:
        if not analysis:
            return "No analysis available."

        summary = f"I've analyzed your spending. Total spent: ${analysis.get('total_spent', 0)}. "
        summary += f"Your top category was {analysis.get('top_category', 'unknown')}."
        return summary


output_generator = OutputGenerator()
