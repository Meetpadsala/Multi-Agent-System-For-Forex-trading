# TODO: Include All Trading Currencies

## Task: Ensure all 23 currency pairs are fully supported throughout the system

### Currency Pairs to Include:
EURUSD, GBPUSD, USDJPY, USDCHF, AUDUSD, USDCAD, NZDUSD, USDINR, EURGBP, EURJPY, GBPJPY, AUDJPY, CADJPY, CHFJPY, EURCHF, GBPCHF, AUDCHF, EURNZD, GBPNZD, AUDNZD, USDMXN, USDZAR, USDTRY

---

## Implementation Plan:

### Step 1: Update trading/views.py
- [ ] 1.1 Update _generate_mock_data() method with base prices for all 23 pairs
- [ ] 1.2 Update _generate_mock_historical_data() method with base prices for all 23 pairs

### Step 2: Update trading/agents.py
- [ ] 2.1 Update DataAgent._generate_mock_historical_data() with all 23 pairs
- [ ] 2.2 Update SentimentAgent.analyze_sentiment() with sentiments for all 23 pairs

### Step 3: Verify Changes
- [ ] 3.1 Check that all pairs work in dashboard
- [ ] 3.2 Confirm no syntax errors

---

## Base Prices (Approximate current market rates):

| Pair | Rate | Pair | Rate |
|------|------|------|------|
| EURUSD | 1.08 | EURCHF | 0.95 |
| GBPUSD | 1.27 | GBPCHF | 1.12 |
| USDJPY | 150.0 | AUDCHF | 0.58 |
| USDCHF | 0.88 | EURNZD | 1.75 |
| AUDUSD | 0.65 | GBPNZD | 2.05 |
| USDCAD | 1.36 | AUDNZD | 1.08 |
| NZDUSD | 0.61 | USDMXN | 18.5 |
| USDINR | 83.0 | USDZAR | 18.2 |
| EURGBP | 0.85 | USDTRY | 32.0 |
| EURJPY | 162.0 | | |
| GBPJPY | 190.0 | | |
| AUDJPY | 98.0 | | |
| CADJPY | 110.0 | | |
| CHFJPY | 165.0 | | |

---

## Sentiment Mapping (for SentimentAgent):
- Major Pairs (EURUSD, GBPUSD, USDJPY): NEUTRAL to POSITIVE
- Commodity Currencies (AUDUSD, USDCAD, NZDUSD): NEUTRAL
- Emerging Market Pairs (USDINR, USDMXN, USDZAR, USDTRY): MIXED (volatile)
- Cross Pairs (EURGBP, EURJPY, etc.): NEUTRAL
