# Options Trading Dashboard (Demo)

A comprehensive, modular dashboard for analyzing options market data, identifying regimes, and generating strategy recommendations using a hybrid approach of classical technical analysis and novel "Narrative" context.

## Screenshots

| Dashboard View | Market Gym View |
|:---:|:---:|
| ![Dashboard](screenshots/Screenshot_22-12-2025_214054_localhost.jpeg) | ![Market Gym](screenshots/Screenshot_22-12-2025_214125_localhost.jpeg) |

## Features

- **Fast, cached data layer**: Sensibull, DhanHQ, NSE Bhavcopy (UDiFF & legacy), Zerodha Kite, IndianAPI, TradingView and an offline **Demo** source, all behind one loader that returns the same frame. Results are cached, so moving a slider doesn't re-download anything. Heavy SDKs load only when their source is picked.
- **Dashboard**: price with 20/50-day moving averages, implied vs realized vol, IV percentile and India VIX in one linked chart; KPI tiles; a **regime map** of the tokenizer over time; news.
- **Mini tokenizer**: each day becomes a 7-token "market sentence", one token per slot: `TREND · MOMENTUM · IV_LEVEL · IV_FLOW · VRP · RV_REGIME · VIX` (e.g. `TREND_UP · MOM_FLAT · IV_HIGH · IV_FALLING · VRP_RICH · RV_STEADY · VIX_MID`). Trend and momentum are measured in units of the stock's own volatility, so NIFTY and a high-beta stock read on the same scale.
- **Market Gym**
    - **Vectorized options backtest**: Iron Condor, Long Straddle, Bull Call and Bear Put spreads, with strikes set in σ-units of the expected move and every leg priced with Black-Scholes at entry IV. Every strategy is simulated on *every* day (shadow trades), and the rule-based entries are flagged.
    - **Context micro-transformer**: `[CLS, STRAT, 7 tokens]` → P(win). It trains on actual trade outcomes, with a chronological, purged validation split (AUC and accuracy vs baseline are reported honestly). It explains itself two ways: attention (what it looks at) and masking impact (which way each token pushes the odds).
    - **Bayesian ranking**: today's win rate in the same core regime (TREND + IV_LEVEL + VRP), with the model's prediction as the prior.
    - **Causality audit**: features are recomputed on truncated history to prove there is no look-ahead.

> [!WARNING]
> **API Disclaimer**: Some data sources included (e.g., Sensibull, TradingView) effectively use unofficial APIs. They are provided for demonstration purposes and may break at any time or violate Terms of Service. Use official APIs (DhanHQ, Kite) for reliability.

> [!NOTE]
> **IV Data Availability**: Sensibull provides ATM IV directly. For Bhavcopy, IV is solved from the near-expiry ATM call with a vectorized Black-Scholes solver. Sources without options data (IndianAPI, Dhan, Kite, TradingView) fall back to 20-day realized vol as an IV proxy, and the app flags it.

## Installation

1.  **Clone the repository**:
    ```bash
    git clone https://github.com/athens556/options-dashboard.git
    cd options-dashboard
    ```

2.  **Install Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

3.  **Environment Setup**:
    - Copy `.env.example` to `.env`:
        ```bash
        cp .env.example .env
        ```
    - Fill in your API keys (DhanHQ, etc.) in the `.env` file.

## Usage

Run the Streamlit application:

```bash
streamlit run app.py
```

Pick **Demo (synthetic)** as the data source to try everything offline. In **Market Gym**, hit *Run gym*: the backtest takes milliseconds, and training the transformer takes a few seconds (toggle *Retrain model*). Trades are stored in `market_research.db` (upserted, so re-runs never double-count) and model weights in `data/models/`. Training on several symbols makes the model generalise better.

Tests (offline, synthetic data):

```bash
python -m pytest tests/test_core.py -q
```

## Project Structure

- **`modules/api`**: Data adapters (`load_market_frame` is the single entry point).
- **`modules/dashboard`**: Features (`market_state`), strategies, vectorized backtest, SQLite store.
- **`modules/ml`**: Tokenizer, context micro-transformer, trainer.
- **`modules/ui`**: Theme and Plotly chart builders.
- **`tests`**: `test_core.py` (offline pipeline tests) plus ad-hoc API probe scripts.

## Disclaimer

This project is a **DEMO** and is intended for educational and research purposes only. It is **not** financial advice. Trading options involves significant risk.

## License

MIT
