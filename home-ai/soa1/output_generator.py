import json
from typing import Dict, Any, Optional, List


class OutputGenerator:
    async def generate_dashboard_json(
        self, analysis: Dict[str, Any], batch_id: Optional[str] = None
    ) -> Dict[str, Any]:
        if analysis is None:
            analysis = {}

        transactions: List[Dict[str, Any]] = []
        if batch_id:
            try:
                from home_ai.finance_agent.src import storage as fa_storage

                transactions = fa_storage.get_transactions_for_batch(batch_id)
            except Exception:
                pass

        dashboard = {
            "total_spent": analysis.get("total_spent") or analysis.get("total") or 0,
            "total_income": analysis.get("total_income") or 0,
            "transaction_count": analysis.get("transaction_count") or len(transactions),
            "categories": analysis.get("categories")
            or analysis.get("by_category")
            or {},
            "insights": analysis.get("insights") or [],
            "recommendations": analysis.get("recommendations") or [],
            "hidden_drains": analysis.get("hidden_drains") or [],
            "top_merchants": analysis.get("top_merchants") or [],
            "date_range": analysis.get("date_range") or {},
            "transactions": transactions,
        }
        return dashboard

    async def build_pdf_command(self, analysis: Dict[str, Any]) -> str:
        if not analysis:
            return ""

        # Placeholder for actual PDF generation command
        return f"generate_pdf --data '{json.dumps(analysis)}' --output report.pdf"

    async def build_infographic_prompt(self, analysis: Dict[str, Any]) -> str:
        if not analysis:
            return ""

        total = analysis.get("total_spent", 0)
        top_cats = list(analysis.get("categories", {}).keys())[:3]

        prompt = f"""
        Brutalist infographic design.
        Central Metric: ${total:,.2f}
        Key Categories: {", ".join(top_cats)}
        Style: Neon orange on black background, futuristic, terminal aesthetic.
        """
        return prompt.strip()

    async def generate_text_summary(self, analysis: Dict[str, Any]) -> str:
        if not analysis:
            return "No analysis available."

        total = analysis.get("total_spent", 0)
        tx_count = analysis.get("transaction_count", 0)
        summary = f"I've analyzed your spending. Total spent: ${total:,.2f} across {tx_count} transactions."
        return summary


output_generator = OutputGenerator()
