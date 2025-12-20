

## The Executable Plan (For Your Coding Agents)

### **Project Structure**

```
finance-agent/
├── data/
│   ├── raw/              # PDFs go here
│   ├── processed/        # Extracted transactions (JSON)
│   └── database/         # SQLite DB
├── src/
│   ├── parser.py         # PDF → Raw transactions
│   ├── categorizer.py    # Transaction categorization
│   ├── analyzer.py       # Insights generation
│   ├── rag.py           # Merchant mappings RAG
│   ├── models.py        # LLM clients (Qwen, Phinance)
│   └── utils.py         # Logging, config
├── dashboard/
│   └── app.py           # Streamlit dashboard
├── prompts/
│   ├── extraction.txt   # PDF extraction prompt
│   ├── categorization.txt
│   └── analysis.txt
├── outputs/
│   ├── reports/         # Generated PDF reports
│   └── infographics/    # Images from z-image-turbo
├── tests/
│   └── test_parser.py
├── config.yaml
├── requirements.txt
└── README.md
```

---

## Phase-by-Phase Implementation

### **PHASE 1: PDF Parsing & Extraction (Days 1-2)**

**Goal**: Extract transactions from 16 PDFs (8 Apple Card + 8 Bank)

**File: `src/parser.py`**

```python
"""
PDF Parser for Apple Card and Bank Statements
Handles both regex patterns and LLM fallback
"""

import pdfplumber
import re
from datetime import datetime
from typing import List, Dict
import json

class StatementParser:
    def __init__(self, llm_client):
        self.llm = llm_client
        
        # Apple Card pattern: "01/15  AMAZON.COM  -$45.23"
        self.apple_card_pattern = r'(\d{2}/\d{2})\s+(.*?)\s+(-?\$[\d,]+\.\d{2})'
        
        # Common bank patterns (adjust based on actual format)
        self.bank_patterns = {
            'chase': r'(\d{2}/\d{2})\s+(.*?)\s+(-?[\d,]+\.\d{2})',
            'bofa': r'(\d{2}/\d{2})\s+(.*?)\s+(-?[\d,]+\.\d{2})',
        }
    
    def detect_statement_type(self, text: str) -> str:
        """Detect if Apple Card or Bank statement"""
        text_upper = text.upper()
        if 'APPLE CARD' in text_upper or 'GOLDMAN SACHS' in text_upper:
            return 'apple_card'
        elif 'CHASE' in text_upper:
            return 'chase'
        elif 'BANK OF AMERICA' in text_upper:
            return 'bofa'
        return 'unknown'
    
    def extract_text(self, pdf_path: str) -> str:
        """Extract all text from PDF"""
        with pdfplumber.open(pdf_path) as pdf:
            return '\n'.join(page.extract_text() or '' for page in pdf.pages)
    
    def parse_with_regex(self, text: str, statement_type: str) -> List[Dict]:
        """Try regex parsing first (fast)"""
        if statement_type == 'apple_card':
            pattern = self.apple_card_pattern
        else:
            pattern = self.bank_patterns.get(statement_type)
        
        if not pattern:
            return None
        
        transactions = []
        for match in re.finditer(pattern, text, re.MULTILINE):
            transactions.append({
                'date': match.group(1),
                'merchant': match.group(2).strip(),
                'amount': float(match.group(3).replace('$', '').replace(',', '')),
                'raw_text': match.group(0)
            })
        
        return transactions if transactions else None
    
    def parse_with_llm(self, text: str) -> List[Dict]:
        """Fallback to LLM extraction (accurate but slower)"""
        
        prompt = f"""Extract ALL transactions from this bank statement.

Return ONLY a JSON array with this exact structure:
[
  {{"date": "MM/DD", "merchant": "NAME", "amount": -45.23, "description": "full line"}},
  ...
]

Rules:
- Negative amounts for charges/debits
- Positive amounts for credits/refunds
- Use exact merchant names from statement
- Include ALL transactions, no truncation

Statement text:
{text[:4000]}  # Limit context for model
"""
        
        response = self.llm.generate(prompt, temperature=0.1)
        
        # Parse JSON from response
        try:
            # Extract JSON array (models sometimes add markdown)
            json_text = response.strip()
            if '```json' in json_text:
                json_text = json_text.split('```json')[1].split('```')[0]
            elif '```' in json_text:
                json_text = json_text.split('```')[1].split('```')[0]
            
            return json.loads(json_text)
        except Exception as e:
            print(f"LLM parsing failed: {e}")
            return []
    
    def parse_pdf(self, pdf_path: str) -> Dict:
        """Main entry point - parse PDF to transactions"""
        
        # Extract text
        text = self.extract_text(pdf_path)
        statement_type = self.detect_statement_type(text)
        
        # Try regex first (fast)
        transactions = self.parse_with_regex(text, statement_type)
        
        # Fallback to LLM if regex fails
        if not transactions:
            print(f"Regex failed for {pdf_path}, using LLM...")
            transactions = self.parse_with_llm(text)
        
        return {
            'source_file': pdf_path,
            'statement_type': statement_type,
            'num_transactions': len(transactions),
            'transactions': transactions,
            'parsing_method': 'regex' if transactions else 'llm'
        }
```

**Coding Agent Instructions:**
1. Create `src/parser.py` with above code
2. Test on 2 PDFs (1 Apple Card, 1 Bank)
3. Adjust regex patterns based on actual format
4. Log parsing success rate (regex vs LLM)
5. Save extracted transactions as JSON in `data/processed/`

---

### **PHASE 2: Categorization (Two-Stage Pipeline) (Days 3-4)**

**File: `src/categorizer.py`**

```python
"""
Two-Stage Transaction Categorization:
1. Qwen 7B: Normalize merchants + initial categorization
2. Phinance 3.8B: Detailed financial analysis
"""

import json
from typing import List, Dict
import sqlite3

class TransactionCategorizer:
    
    CATEGORIES = [
        'Groceries', 'Dining', 'Transportation', 'Housing', 
        'Utilities', 'Healthcare', 'Entertainment', 'Shopping',
        'Travel', 'Insurance', 'Taxes', 'Subscriptions',
        'Income', 'Transfers', 'Fees', 'Other'
    ]
    
    def __init__(self, qwen_client, phinance_client, db_path):
        self.qwen = qwen_client
        self.phinance = phinance_client
        self.db = sqlite3.connect(db_path)
        self.init_db()
        self.merchant_cache = self.load_merchant_cache()
    
    def init_db(self):
        """Initialize merchant mappings database"""
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS merchant_mappings (
                merchant_raw TEXT PRIMARY KEY,
                merchant_normalized TEXT,
                category TEXT,
                confidence REAL,
                learned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self.db.commit()
    
    def load_merchant_cache(self) -> Dict:
        """Load known merchant→category mappings"""
        cursor = self.db.execute("SELECT merchant_raw, category FROM merchant_mappings")
        return {row[0]: row[1] for row in cursor.fetchall()}
    
    def stage1_normalize(self, merchant: str) -> Dict:
        """Stage 1: Qwen normalizes merchant name"""
        
        # Check cache first
        if merchant in self.merchant_cache:
            return {
                'normalized': merchant,
                'category': self.merchant_cache[merchant],
                'confidence': 0.95,
                'source': 'cache'
            }
        
        prompt = f"""Normalize this merchant name and suggest a category.

Merchant: "{merchant}"

Return JSON:
{{
  "normalized": "Clean name (e.g., 'AMZN MKTP' → 'Amazon')",
  "category": "One of: {', '.join(self.CATEGORIES)}",
  "confidence": 0.X
}}
"""
        
        response = self.qwen.generate(prompt, temperature=0.0)
        result = self._parse_json(response)
        result['source'] = 'qwen'
        return result
    
    def stage2_analyze(self, transaction: Dict, normalized: Dict) -> Dict:
        """Stage 2: Phinance does detailed financial classification"""
        
        # Only use Phinance for low-confidence or complex cases
        if normalized['confidence'] > 0.85:
            return normalized
        
        prompt = f"""Classify this financial transaction with high precision.

Transaction:
- Date: {transaction['date']}
- Merchant: {normalized['normalized']}
- Amount: ${transaction['amount']:.2f}

Provide:
1. Most accurate category from: {', '.join(self.CATEGORIES)}
2. Subcategory (e.g., "Fast Food" under "Dining")
3. Confidence score
4. Reasoning

Return JSON:
{{
  "category": "...",
  "subcategory": "...",
  "confidence": 0.X,
  "reasoning": "..."
}}
"""
        
        response = self.phinance.generate(prompt, temperature=0.0)
        result = self._parse_json(response)
        result['source'] = 'phinance'
        return result
    
    def categorize_batch(self, transactions: List[Dict]) -> List[Dict]:
        """Categorize all transactions using two-stage pipeline"""
        
        categorized = []
        
        for txn in transactions:
            # Stage 1: Normalize with Qwen
            norm = self.stage1_normalize(txn['merchant'])
            
            # Stage 2: Refine with Phinance if needed
            final = self.stage2_analyze(txn, norm)
            
            # Update transaction with category
            txn['merchant_normalized'] = norm['normalized']
            txn['category'] = final['category']
            txn['confidence'] = final['confidence']
            
            # Learn for future (if high confidence)
            if final['confidence'] > 0.85:
                self._save_to_cache(txn['merchant'], final['category'])
            
            categorized.append(txn)
        
        return categorized
    
    def _save_to_cache(self, merchant: str, category: str):
        """Save merchant→category mapping for future use"""
        self.db.execute("""
            INSERT OR REPLACE INTO merchant_mappings (merchant_raw, category)
            VALUES (?, ?)
        """, (merchant, category))
        self.db.commit()
        self.merchant_cache[merchant] = category
    
    def _parse_json(self, response: str) -> Dict:
        """Parse JSON from LLM response"""
        try:
            text = response.strip()
            if '```json' in text:
                text = text.split('```json')[1].split('```')[0]
            return json.loads(text)
        except:
            return {'category': 'Other', 'confidence': 0.5, 'error': 'parse_failed'}
```

**Coding Agent Instructions:**
1. Create `src/categorizer.py`
2. Initialize SQLite DB for merchant mappings
3. Test categorization on 50 transactions
4. Measure Stage 1 vs Stage 2 usage (should be 80% Stage 1)
5. Log confidence scores distribution

---

### **PHASE 3: Analysis Engine (Days 5-6)**

**File: `src/analyzer.py`**

```python
"""
Financial Analysis Engine
Generates insights using Qwen 14B
"""

import pandas as pd
from typing import Dict, List
from datetime import datetime

class FinancialAnalyzer:
    
    def __init__(self, qwen_14b_client):
        self.model = qwen_14b_client
    
    def prepare_dataframe(self, transactions: List[Dict]) -> pd.DataFrame:
        """Convert transactions to pandas for analysis"""
        df = pd.DataFrame(transactions)
        df['date'] = pd.to_datetime(df['date'], format='%m/%d')
        df['month'] = df['date'].dt.month
        df['amount'] = df['amount'].astype(float)
        return df
    
    def calculate_summary(self, df: pd.DataFrame) -> Dict:
        """Basic financial summary statistics"""
        return {
            'total_income': float(df[df['amount'] > 0]['amount'].sum()),
            'total_spending': float(abs(df[df['amount'] < 0]['amount'].sum())),
            'net_savings': float(df['amount'].sum()),
            'num_transactions': len(df),
            'avg_transaction': float(df[df['amount'] < 0]['amount'].mean()),
            'num_months': df['month'].nunique()
        }
    
    def category_breakdown(self, df: pd.DataFrame) -> Dict:
        """Spending by category"""
        spending = df[df['amount'] < 0].copy()
        spending['amount'] = spending['amount'].abs()
        
        by_category = spending.groupby('category')['amount'].agg(['sum', 'count', 'mean'])
        by_category = by_category.sort_values('sum', ascending=False)
        
        return by_category.to_dict('index')
    
    def detect_hidden_drains(self, df: pd.DataFrame) -> List[Dict]:
        """Find small recurring charges that add up"""
        
        # Find recurring merchants (appear 3+ times)
        merchant_counts = df['merchant_normalized'].value_counts()
        recurring = merchant_counts[merchant_counts >= 3]
        
        # Filter for small charges (<$50)
        drains = []
        for merchant in recurring.index:
            merchant_txns = df[df['merchant_normalized'] == merchant]
            avg_amount = abs(merchant_txns['amount'].mean())
            
            if avg_amount < 50:
                drains.append({
                    'merchant': merchant,
                    'frequency': len(merchant_txns),
                    'avg_amount': avg_amount,
                    'annual_cost': avg_amount * len(merchant_txns),
                    'category': merchant_txns['category'].iloc[0]
                })
        
        return sorted(drains, key=lambda x: x['annual_cost'], reverse=True)
    
    def detect_taxes(self, df: pd.DataFrame) -> Dict:
        """Identify tax payments"""
        tax_keywords = ['IRS', 'TAX', 'TREASURY', 'STATE TAX', 'PROPERTY TAX']
        
        tax_txns = df[df['merchant_normalized'].str.contains('|'.join(tax_keywords), case=False, na=False)]
        
        return {
            'total_taxes': float(abs(tax_txns['amount'].sum())),
            'num_payments': len(tax_txns),
            'breakdown': tax_txns[['date', 'merchant_normalized', 'amount']].to_dict('records')
        }
    
    def generate_insights(self, df: pd.DataFrame) -> Dict:
        """Generate AI-powered insights using Qwen 14B"""
        
        summary = self.calculate_summary(df)
        categories = self.category_breakdown(df)
        hidden_drains = self.detect_hidden_drains(df)
        taxes = self.detect_taxes(df)
        
        # Create context for LLM
        context = f"""Analyze this person's financial data for 12 months:

SUMMARY:
- Total Income: ${summary['total_income']:,.2f}
- Total Spending: ${summary['total_spending']:,.2f}
- Net Savings: ${summary['net_savings']:,.2f}
- Savings Rate: {(summary['net_savings'] / summary['total_income'] * 100):.1f}%

TOP 5 SPENDING CATEGORIES:
{self._format_categories(categories, top_n=5)}

HIDDEN DRAINS (Small recurring charges):
{self._format_hidden_drains(hidden_drains[:5])}

TAX PAYMENTS:
- Total Taxes Paid: ${taxes['total_taxes']:,.2f}

TASK: Provide:
1. 3-5 KEY BEHAVIORAL INSIGHTS (surprising patterns, trends)
2. COMPARISON to typical American spending (use your knowledge)
3. 3 ACTIONABLE RECOMMENDATIONS to save money (specific, measurable)
4. HIGHLIGHT any concerning patterns (overspending, lifestyle creep, etc.)

Be direct, specific, and use actual numbers from the data.
"""
        
        insights_text = self.model.generate(context, temperature=0.3, max_tokens=1000)
        
        return {
            'summary': summary,
            'categories': categories,
            'hidden_drains': hidden_drains,
            'taxes': taxes,
            'ai_insights': insights_text,
            'generated_at': datetime.now().isoformat()
        }
    
    def _format_categories(self, categories: Dict, top_n: int = 5) -> str:
        """Format category data for prompt"""
        lines = []
        for i, (cat, data) in enumerate(list(categories.items())[:top_n], 1):
            lines.append(f"{i}. {cat}: ${data['sum']:,.2f} ({data['count']} transactions)")
        return '\n'.join(lines)
    
    def _format_hidden_drains(self, drains: List[Dict]) -> str:
        """Format hidden drains for prompt"""
        if not drains:
            return "None detected"
        
        lines = []
        for drain in drains:
            lines.append(f"- {drain['merchant']}: ${drain['avg_amount']:.2f} × {drain['frequency']} = ${drain['annual_cost']:.2f}/year")
        return '\n'.join(lines)
```

**Coding Agent Instructions:**
1. Create `src/analyzer.py`
2. Test with sample transaction data
3. Verify all calculations (use test data with known results)
4. Test Qwen 14B prompt with real data subset
5. Save analysis results as JSON

---

### **PHASE 4: Infographic Generation (Day 7)**

**File: `src/infographic.py`**

```python
"""
Generate infographic using Z-Image-Turbo
(After Phinance finishes, use idle GPU for image generation)
"""

class InfographicGenerator:
    
    def __init__(self, z_image_client):
        self.model = z_image_client
    
    def create_prompt(self, analysis: Dict) -> str:
        """Create infographic prompt from analysis data"""
        
        summary = analysis['summary']
        top_categories = list(analysis['categories'].items())[:5]
        
        prompt = f"""Create a clean, professional financial infographic with these elements:

TITLE: "Your 2024 Financial Overview"

SECTION 1: Key Numbers (large, bold)
- Total Income: ${summary['total_income']:,.0f}
- Total Spending: ${summary['total_spending']:,.0f}
- Net Savings: ${summary['net_savings']:,.0f}
- Savings Rate: {(summary['net_savings']/summary['total_income']*100):.1f}%

SECTION 2: Top 5 Spending Categories (pie or bar chart)
{self._format_for_viz(top_categories)}

SECTION 3: Key Insight (highlighted box)
"{analysis['ai_insights'][:200]}..."

Style: Modern, clean, use green for savings, red for spending, blue for income.
Layout: Vertical, mobile-friendly, professional.
"""
        return prompt
    
    def generate(self, analysis: Dict, output_path: str):
        """Generate and save infographic"""
        prompt = self.create_prompt(analysis)
        
        image = self.model.generate(
            prompt=prompt,
            width=1080,
            height=1920,  # Vertical for mobile
            steps=20,
            guidance_scale=7.5
        )
        
        image.save(output_path)
        return output_path
```

**Coding Agent Instructions:**
1. Create `src/infographic.py`
2. Test prompt with Z-Image-Turbo
3. Iterate on prompt for best visual output
4. Save infographics to `outputs/infographics/`

---

### **PHASE 5: Dashboard (Days 8-9)**

**File: `dashboard/app.py`**

```python
"""
Streamlit Dashboard for Financial Analysis
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import json
from pathlib import Path

st.set_page_config(page_title="Financial Intelligence", layout="wide")

# Load analysis results
@st.cache_data
def load_analysis():
    with open('outputs/analysis_results.json') as f:
        return json.load(f)

@st.cache_data
def load_transactions():
    return pd.read_json('data/processed/all_transactions.json')

# Main dashboard
st.title("💰 Personal Financial Intelligence")

analysis = load_analysis()
df = load_transactions()

# Sidebar
st.sidebar.header("Controls")
date_range = st.sidebar.date_input("Date Range", value=(df['date'].min(), df['date'].max()))

# Summary Cards
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Total Income", f"${analysis['summary']['total_income']:,.0f}")
with col2:
    st.metric("Total Spending", f"${analysis['summary']['total_spending']:,.0f}")
with col3:
    st.metric("Net Savings", f"${analysis['summary']['net_savings']:,.0f}")
with col4:
    savings_rate = (analysis['summary']['net_savings'] / analysis['summary']['total_income']) * 100
    st.metric("Savings Rate", f"{savings_rate:.1f}%")

# Category Breakdown
st.header("📊 Spending by Category")
cat_df = pd.DataFrame(analysis['categories']).T.reset_index()
cat_df.columns = ['Category', 'Total', 'Count', 'Average']

fig = px.pie(cat_df, values='Total', names='Category', title='Spending Distribution')
st.plotly_chart(fig, use_container_width=True)

# Monthly Trend
st.header("📈 Monthly Spending Trend")
monthly = df.groupby(df['date'].dt.to_period('M'))['amount'].sum().abs()
fig = px.line(x=monthly.index.astype(str), y=monthly.values, title='Monthly Spending')
st.plotly_chart(fig, use_container_width=True)

# Hidden Drains
st.header("💸 Hidden Drains (Small Recurring Charges)")
drains_df = pd.DataFrame(analysis['hidden_drains'])
st.dataframe(drains_df, use_container_width=True)
st.info(f"Total annual cost: ${drains_df['annual_cost'].sum():,.0f}")

# AI Insights
st.header("🤖 AI-Generated Insights")
st.write(analysis['ai_insights'])

# Infographic
st.header("📄 Shareable Infographic")
infographic_path = 'outputs/infographics/financial_overview.png'
if Path(infographic_path).exists():
    st.image(infographic_path, use_column_width=True)

# Export
st.header("📥 Export")
if st.button("Generate PDF Report"):
    st.info("Generating PDF report... (implement with ReportLab)")
```

**Coding Agent Instructions:**
1. Create `dashboard/app.py`
2. Test with sample data
3. Add more visualizations (optional)
4. Test PDF export (use ReportLab or weasyprint)

---

### **PHASE 6: Integration & Testing (Day 10)**

**File: `main.py` (Orchestrator)**

```python
"""
Main orchestrator - runs entire pipeline
"""

import sys
from pathlib import Path
from src.parser import StatementParser
from src.categorizer import TransactionCategorizer
from src.analyzer import FinancialAnalyzer
from src.infographic import InfographicGenerator
from src.models import QwenClient, PhinanceClient, ZImageClient
import json

def main():
    print("🚀 Starting Financial Intelligence Pipeline...")
    
    # Initialize models
    qwen_7b = QwenClient(model="qwen2.5:7b", base_url="http://localhost:11434")
    phinance = PhinanceClient(model="phinance:3.8b", base_url="http://localhost:11434")
    qwen_14b = QwenClient(model="qwen2.5:14b", base_url="http://localhost:11434")
    z_image = ZImageClient(model="z-image-turbo", base_url="http://localhost:11434")
    
    # Step 1: Parse all PDFs
    print("\n📄 Step 1: Parsing PDFs...")
    parser = StatementParser(qwen_7b)
    
    pdf_dir = Path("data/raw")
    all_transactions = []
    
    for pdf_file in pdf_dir.glob("*.pdf"):
        print(f"  Processing {pdf_file.name}...")
        result = parser.parse_pdf(str(pdf_file))
        all_transactions.extend(result['transactions'])
    
    print(f"✅ Extracted {len(all_transactions)} transactions")
    
    # Save intermediate results
    with open('data/processed/raw_transactions.json', 'w') as f:
        json.dump(all_transactions, f, indent=2)
    
    # Step 2: Categorize transactions
    print("\n🏷️  Step 2: Categorizing transactions...")
    categorizer = TransactionCategorizer(qwen_7b, phinance, 'data/database/finance.db')
    categorized = categorizer.categorize_batch(all_transactions)
    
    print(f"✅ Categorized {len(categorized)} transactions")
    
    with open('data/processed/categorized_transactions.json', 'w') as f:
        json.dump(categorized, f, indent=2)
    
    # Step 3: Generate insights
    print("\n🧠 Step 3: Generating insights with Qwen 14B...")
    analyzer = FinancialAnalyzer(qwen_14b)
    df = analyzer.prepare_dataframe(categorized)
    analysis = analyzer.generate_insights(df)
    
    print("✅ Insights generated")
    
    with open('outputs/analysis_results.json', 'w') as f:
        json.dump(analysis, f, indent=2)
    
    # Step 4: Generate infographic
    print("\n🎨 Step 4: Creating infographic...")
    infographic_gen = InfographicGenerator(z_image)
    infographic_path = infographic_gen.generate(analysis, 'outputs/infographics/overview.png')
    
    print(f"✅ Infographic saved to {infographic_path}")
    
    # Done
    print("\n✨ Pipeline complete! Run dashboard with: streamlit run dashboard/app.py")

if __name__ == "__main__":
    main()
```

**Coding Agent Instructions:**
1. Create `main.py`
2. Test end-to-end with 2-3 PDFs
3. Fix any bugs in pipeline
4. Add error handling and logging
5. Test with full 16 PDFs
6. Launch dashboard and verify all data

---

## Timeline & Deliverables

| Day | Phase | Deliverable | Coding Agent Task |
|-----|-------|-------------|-------------------|
| 1-2 | Parsing | Extract transactions from PDFs | `parser.py` + tests |
| 3-4 | Categorization | Two-stage categorization working | `categorizer.py` + RAG DB |
| 5-6 | Analysis | Insights from Qwen 14B | `analyzer.py` + prompts |
| 7 | Infographic | Z-Image-Turbo generates visuals | `infographic.py` |
| 8-9 | Dashboard | Streamlit UI working | `app.py` |
| 10 | Integration | End-to-end pipeline tested | `main.py` + bug fixes |

---

## What You Need to Give Your Coding Agents

**Prompt Template for Each Phase:**

```
You are building a financial intelligence system. 

TASK: Implement [PHASE NAME]

REQUIREMENTS:
[Paste specific requirements from plan]

FILES TO CREATE:
[List files]

ACCEPTANCE CRITERIA:
- Code runs without errors
- Passes test cases
- Logs progress
- Saves outputs to correct locations

CONTEXT:
- Using Ollama for local LLMs
- Models: qwen2.5:7b, phinance:3.8b, qwen2.5:14b, z-image-turbo
- Data: 16 PDFs (8 Apple Card + 8 Bank statements)
- Stack: Python, pandas, streamlit, sqlite3

START WITH: [Paste code from plan]
```

---
