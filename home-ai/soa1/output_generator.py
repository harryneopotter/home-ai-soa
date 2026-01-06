import json
from typing import Dict, Any, Optional, List

EXPENSE_ONLY_ACCOUNT = "credit_card"
INCOME_EXPENSE_ACCOUNT = "bank"
UNKNOWN_ACCOUNT = "unknown"


def _determine_account_type(files: Optional[List[Dict]] = None) -> str:
    if not files:
        return UNKNOWN_ACCOUNT

    doc_types = [f.get("inferred_type", "") for f in files]

    if any("credit_card" in t for t in doc_types):
        return EXPENSE_ONLY_ACCOUNT
    if any("apple" in t.lower() for t in doc_types):
        return EXPENSE_ONLY_ACCOUNT
    if any(f.get("is_apple_card") for f in files):
        return EXPENSE_ONLY_ACCOUNT
    if any("bank_statement" in t for t in doc_types):
        return INCOME_EXPENSE_ACCOUNT

    return UNKNOWN_ACCOUNT


class OutputGenerator:
    async def generate_dashboard_json(
        self,
        analysis: Dict[str, Any],
        batch_id: Optional[str] = None,
        files: Optional[List[Dict]] = None,
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

        account_type = _determine_account_type(files)

        total_income = analysis.get("total_income") or 0
        if account_type == EXPENSE_ONLY_ACCOUNT:
            total_income = 0

        # Compute categories from live transactions if not in analysis
        categories = analysis.get("categories") or analysis.get("by_category")
        if not categories and transactions:
            categories = {}
            for t in transactions:
                cat = t.get("category", "Other")
                amt = float(t.get("amount", 0))
                if amt > 0:  # Only count spending (positive amounts)
                    categories[cat] = categories.get(cat, 0) + amt

        # Compute total_spent from transactions if not in analysis
        total_spent = analysis.get("total_spent") or analysis.get("total")
        if not total_spent and transactions:
            total_spent = sum(
                float(t.get("amount", 0))
                for t in transactions
                if float(t.get("amount", 0)) > 0
            )

        dashboard = {
            "total_spent": total_spent or 0,
            "total_income": total_income,
            "transaction_count": analysis.get("transaction_count") or len(transactions),
            "categories": categories or {},
            "insights": analysis.get("insights") or [],
            "recommendations": analysis.get("recommendations") or [],
            "hidden_drains": analysis.get("hidden_drains") or [],
            "top_merchants": analysis.get("top_merchants") or [],
            "date_range": analysis.get("date_range") or {},
            "transactions": transactions,
            "account_type": account_type,
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
