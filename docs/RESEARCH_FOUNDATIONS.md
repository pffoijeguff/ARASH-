# ARASH Research Foundations

This document records the research ideas informing the ARASH engineering roadmap. It is a design reference, not a claim that every method cited is already implemented or that a profitable edge has been demonstrated.

## Findings that materially affect system design

### 1. Backtest overfitting and multiple testing are central risks

Bailey, Borwein, López de Prado and Zhu describe how repeatedly selecting among backtested alternatives can produce apparently strong results that do not generalize. Their Probability of Backtest Overfitting framework is designed to quantify this risk. The Deflated Sharpe Ratio literature addresses selection bias from multiple trials and non-normal return distributions.

**ARASH implication:** track the entire candidate family; keep the final holdout untouched; report the research search process; use appropriate PBO/DSR diagnostics; do not advertise the best grid result as evidence of a durable edge. The development branch now includes a CSCV-based PBO diagnostic and CLI entry point; it remains subject to verification.

References:
- Bailey et al., *The Probability of Backtest Overfitting*, Journal of Computational Finance (2015): https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2326253
- Bailey & López de Prado, *The Deflated Sharpe Ratio: Correcting for Selection Bias, Backtest Overfitting, and Non-Normality*, The Journal of Portfolio Management (2014): https://doi.org/10.3905/jpm.2014.40.5.094

### 2. Validation choice changes the apparent strength of a strategy

A 2024 study compared out-of-sample techniques in controlled environments that included non-stationarity, autocorrelation and regime changes. It reported that Combinatorial Purged Cross-Validation (CPCV) reduced overfitting risk in its evaluated settings and performed better than a basic walk-forward approach on the study's PBO/DSR criteria. That result is not a universal theorem that CPCV is always superior; applicability depends on the target, sampling design and data.

**ARASH implication:** retain true chronological holdouts and walk-forward studies; add purge/embargo and CPCV as complementary diagnostics where appropriate; report assumptions and avoid treating any single split method as proof.

Reference:
- Arian, Mobarekeh & Seco, *Backtest overfitting in the machine learning era: A comparison of out-of-sample testing methods in a synthetic controlled environment*, Knowledge-Based Systems (published 3 Dec 2024): https://doi.org/10.1016/j.knosys.2024.112477

### 3. Crypto microstructure features may be informative but economically insufficient

A 2026 *Frontiers in Blockchain* study evaluated microstructure signals using more than three million minute-level observations across major cryptocurrencies and exchange venues. Its pipeline included leakage controls and purged walk-forward validation. The paper reports that learned models overfit under proper controls and that the tested short-horizon strategies did not survive standard exchange fees and slippage; transfer across different cryptocurrencies was limited.

**ARASH implication:** prediction metrics must be separated from tradable net edge. Cost-aware validation, turnover control, cross-asset transfer tests and venue-specific execution assumptions are essential. A sophisticated ML model is not automatically better than a simple baseline.

Reference:
- Pindza, *Microstructure alpha: hierarchical learning and cross-asset transfer in cryptocurrency markets*, Frontiers in Blockchain (published 11 Jun 2026): https://doi.org/10.3389/fbloc.2026.1811716

### 4. Liquidity is dynamic and shared across crypto markets

A 2025 study of cryptocurrency liquidity reports weekly patterns in bid-ask spreads, trading volume and volatility, alongside commonality in liquidity across assets. Another 2026 paper studies changes in Bitcoin market microstructure over 2012–2025 and reports structural changes in volatility, volume and transaction costs over time.

**ARASH implication:** static slippage assumptions can be misleading. Execution scenarios should vary costs and capacity by venue, asset, liquidity state and time; a model calibrated on one asset or period should not be presumed to generalize.

References:
- *Liquidity commonality in cryptocurrencies*, Finance Research Letters (2025): https://doi.org/10.1016/j.frl.2025.108187
- *Maturation of Bitcoin market microstructure: Evidence of institutional-grade liquidity and efficiency (2012–2025)*, Borsa Istanbul Review (2026): https://doi.org/10.1016/j.bir.2026.100869

### 5. Statistical evidence and economic relevance are separate gates

A 2026 SSRN preprint proposes a 12-item validation checklist for machine-learning research in cryptocurrency markets. Its experiments report that statistical significance under one procedure can coexist with failure under combinatorial purged validation or after transaction costs. As an SSRN preprint, it should be treated as emerging research rather than settled consensus; its core engineering lesson is nevertheless directly relevant: forecast fit, statistical evidence, and net economic value answer different questions.

**ARASH implication:** report uncertainty around return statistics, control repeated strategy selection, reserve untouched chronological evaluation, and model realistic costs as separate checks. ARASH now includes two complementary research diagnostics: a CSCV/PBO selection-instability estimate and a circular moving-block bootstrap for mean-return and Sharpe-like intervals. Neither diagnostic establishes an investable edge, and neither replaces the other.

Reference:
- Kim, *Beyond Accuracy: A Validation Framework for Machine Learning in Cryptocurrency Trading*, SSRN preprint (posted 28 Apr 2026; revised 3 Aug 2026): https://doi.org/10.2139/ssrn.6508779

### 6. Risk must be enforced in the order path and operations

Regulatory guidance for market access emphasizes controls intended to limit financial exposure, with documented controls and supervisory procedures. Although scope differs by venue, jurisdiction and participant type, the engineering principles are broadly relevant to robust automated systems.

**ARASH implication:** risk checks should be independent from signal generation, with order bounds, price collars, rate controls, durable kill switches, monitoring and recovery procedures. Risk controls reduce specified failure modes; they do not eliminate market risk.

Reference:
- U.S. Securities and Exchange Commission, *Responses to Frequently Asked Questions Concerning Risk Management Controls for Brokers or Dealers with Market Access*: https://www.sec.gov/rules-regulations/staff-guidance/trading-markets-frequently-asked-questions/divisionsmarketregfaq-0

## Design priorities derived from the evidence

1. **Net edge, not gross signal quality:** evaluate realistic fees, spread, slippage, funding/borrow where relevant, market impact and turnover.
2. **Leakage resistance by construction:** point-in-time features, separated training/validation/holdout windows, purge/embargo where appropriate, and explicit handling of revised or missing data.
3. **Selection-bias transparency:** maintain an immutable record of candidate configurations and report PBO/DSR or equivalent diagnostics when statistically appropriate.
4. **Regime and liquidity robustness:** evaluate different volatility, liquidity and market-state conditions; do not assume yesterday's microstructure persists.
5. **Operational resilience:** event timestamps, stale-data gates, idempotency, bounded queues, reconnect/reconciliation logic, order-rate limits and independent emergency stops.
6. **Complexity must earn its place:** keep interpretable baselines, evaluate models on the same splits and costs, measure drift and retain simpler methods when they generalize better.

## Evidence status

These papers inform the research direction, not a performance claim for ARASH. The current development branch has not been independently verified as implementing every target practice described here, and no profitability or global-ranking claim is made.
