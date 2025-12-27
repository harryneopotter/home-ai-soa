# Multi-PDF Integration Test Results
**Date**: December 26, 2025
**Time**: 15:57 - 16:00 CST

---

## Test Environment
- **Base URL**: http://localhost:8080
- **SOA1 API**: http://localhost:8001
- **GPU Setup**: 2x RTX 5060 Ti (NemoAgent on GPU 0, phinance-json on GPU 1)

---

## Test 1: 3 PDFs

### Summary
| Metric | Value |
|--------|-------|
| **Total Time** | 66.54s |
| **Average per Document** | 22.18s |
| **Success Rate** | 3/3 (100%) |
| **Total Transactions** | 220 |

### PDFs Processed
1. Apple Card Statement - September 2025 (83 transactions)
2. Apple Card Statement - October 2025 (52 transactions)
3. Apple Card Statement - November 2025 (85 transactions)

### Timing Breakdown
| Doc | PDF | Upload | Stage-AB | Consent | Analysis | Total |
|-----|-----|--------|----------|---------|----------|-------|
| 1 | September 2025 | 0.00s | 9.76s | 0.00s | 11.54s | 21.30s |
| 2 | October 2025 | 0.02s | 9.31s | 0.00s | 13.48s | 22.81s |
| 3 | November 2025 | 0.02s | 8.82s | 0.00s | 13.57s | 22.41s |

### Aggregate Timing
- **Avg Upload**: 0.01s
- **Avg Stage-AB**: 9.30s
- **Avg Analysis**: 12.86s

---

## Test 2: 6 PDFs

### Summary
| Metric | Value |
|--------|-------|
| **Total Time** | 139.52s |
| **Average per Document** | 23.25s |
| **Success Rate** | 6/6 (100%) |
| **Total Transactions** | 430 |

### PDFs Processed
1. Apple Card Statement - September 2025 (83 transactions)
2. Apple Card Statement - October 2025 (52 transactions)
3. Apple Card Statement - November 2025 (85 transactions)
4. Apple Card Statement - May 2025 (66 transactions)
5. Apple Card Statement - March 2025 (59 transactions)
6. Apple Card Statement - November 2025 (85 transactions) - duplicate month

### Timing Breakdown
| Doc | PDF | Upload | Stage-AB | Consent | Analysis | Total |
|-----|-----|--------|----------|---------|----------|-------|
| 1 | September 2025 | 0.00s | 8.90s | 0.00s | 12.53s | 21.44s |
| 2 | October 2025 | 0.01s | 10.70s | 0.00s | 13.47s | 24.18s |
| 3 | November 2025 | 0.01s | 9.88s | 0.00s | 13.58s | 23.47s |
| 4 | May 2025 | 0.01s | 8.84s | 0.00s | 11.51s | 20.36s |
| 5 | March 2025 | 0.02s | 7.39s | 0.00s | 16.48s | 23.89s |
| 6 | November 2025 | 0.02s | 9.53s | 0.00s | 16.57s | 26.12s |

### Aggregate Timing
- **Avg Upload**: 0.01s
- **Avg Stage-AB**: 9.21s
- **Avg Analysis**: 14.02s

---

## Pipeline Step Timing (Sample: Last Document)

From `/analysis-timing/finance-20251226-220020-27cabe`:

| Step | Duration |
|------|----------|
| metadata_extraction | 0.003ms (cached) |
| transaction_extraction | 1,446ms (~1.4s) |
| insights_generation | 0.002ms (cached) |
| anomaly_check | 14,628ms (~14.6s) |
| **Total Pipeline** | 16,075ms (~16s) |

### Anomalies Detected
- **Type**: category_mismatch
- **Description**: Calculated total of $6792.50 does not match reported total of $7453.35 (difference of $660.85)
- **Severity**: high

---

## Observations

### Performance
- **Upload time**: Negligible (<0.02s) - file copying is fast
- **Stage-AB time**: ~8-11s - NemoAgent header parsing + PDF processing
- **Analysis time**: ~11-17s - Transaction extraction + NemoAgent anomaly check
- **Total per doc**: ~20-26s average

### Bottlenecks
1. **Anomaly check** (~14-15s) - NemoAgent reasoning about data quality
2. **Stage-AB** (~8-11s) - NemoAgent header parsing
3. **Transaction extraction** (~1.4s) - Regex extraction is fast when cached

### Scaling
- 3 PDFs: 66.54s (22.18s/doc)
- 6 PDFs: 139.52s (23.25s/doc)
- Linear scaling confirmed (no degradation with more documents)

---

## Reports Generated

All reports saved to `/home/ryzen/projects/home-ai/finance-agent/data/reports/`:
- 3 reports from Test 1 (15:57)
- 6 reports from Test 2 (15:58-16:00)

Each report contains:
- `transactions.json` - Raw transaction data
- `analysis.json` - Aggregated insights, categories, top merchants
- `dashboard/` - Dashboard-compatible format
