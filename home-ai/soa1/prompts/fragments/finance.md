You may invoke the finance specialist using [INVOKE:finance] when:
- The user has uploaded financial documents (bank/credit-card statements)
- The user explicitly requests spending analysis, breakdown, or insights
- The batch stage is READY and invoke_specialist is in allowed_actions
- The user has granted ANALYZE_DETERMINISTIC capability (implicit on upload)
- The user has granted per-batch invocation approval (if required by ConsentManager)

The specialist will return structured JSON insights including:
- spending_by_category
- merchant_breakdown
- monthly_trends
- top_expenses
