import os
from datetime import date, timedelta

import pandas as pd
import streamlit as st

st.set_page_config(page_title="Options Terminal", page_icon="◈", layout="wide")

from modules.api import data_loader, news_loader  # noqa: E402  (after set_page_config)
from modules import utils  # noqa: E402
from modules.dashboard.backtest import BacktestEngine, strategy_stats  # noqa: E402
from modules.dashboard.db_manager import DBManager  # noqa: E402
from modules.dashboard.market_state import build_feature_frame, causality_audit  # noqa: E402
from modules.dashboard.strategy import STRATEGIES  # noqa: E402
from modules.ml.tokens import Tokenizer  # noqa: E402
from modules.ui import charts, theme  # noqa: E402

st.markdown(theme.CSS, unsafe_allow_html=True)

SLOW_SOURCES = {"Open Source (Bhavcopy)"}  # hundreds of NSE downloads on first load: gate behind a button
FALLBACK_SYMBOLS = ["NIFTY", "BANKNIFTY", "SBIN", "INFY", "RELIANCE", "TCS", "HDFCBANK", "ICICIBANK"]


class DataError(Exception):
    """Raised inside cached loaders so failures are not cached."""


# ---------------------------------------------------------------- cached data

@st.cache_data(ttl=86400, show_spinner=False)
def get_fo_symbols():
    symbols = data_loader.fetch_nifty_fo_symbols() or FALLBACK_SYMBOLS
    for idx in ("BANKNIFTY", "NIFTY"):
        if idx in symbols:
            symbols.remove(idx)
        symbols.insert(0, idx)
    return symbols


@st.cache_data(ttl=900, show_spinner=False)
def load_frame(source, symbol, start, end, indian_api_key=None):
    df, error = data_loader.load_market_frame(source, symbol, start, end, indian_api_key=indian_api_key)
    if error:
        raise DataError(error)
    return df


@st.cache_data(ttl=86400, show_spinner=False)
def kite_instruments(_kite, access_token):
    return _kite.instruments("NSE")


@st.cache_data(ttl=900, show_spinner=False)
def load_kite_frame(_kite, access_token, symbol, start, end):
    instruments = kite_instruments(_kite, access_token)
    names = {"NIFTY": "NIFTY 50", "BANKNIFTY": "NIFTY BANK"}
    token = (utils.get_instrument_token(_kite, symbol, instruments=instruments)
             or utils.get_instrument_token(_kite, names.get(symbol, symbol), instruments=instruments))
    if not token:
        raise DataError(f"Instrument token not found for {symbol}.")
    df, error = data_loader.load_market_frame("Zerodha Kite API", symbol, start, end, kite=_kite, kite_token=token)
    if error:
        raise DataError(error)
    return df


@st.cache_data(show_spinner=False)
def features_and_tokens(df):
    """Features on the full frame (incl. warm-up history); tokens for every day that has them."""
    features = build_feature_frame(df)
    return features, Tokenizer.tokenize_frame(features)


def in_range(frame):
    return frame[frame.index >= pd.Timestamp(start_date)]


@st.cache_data(ttl=1800, show_spinner=False)
def get_news(symbol):
    return news_loader.fetch_google_news(symbol, limit=8)


@st.cache_resource(show_spinner=False)
def get_encoder(model_mtime):
    """Loaded once per saved checkpoint (the mtime busts the cache after retraining)."""
    from modules.ml.context_encoder import ContextEncoder
    encoder = ContextEncoder()
    encoder.load()
    return encoder


def model_mtime():
    from modules.ml.context_encoder import MODEL_PATH
    return os.path.getmtime(MODEL_PATH) if os.path.exists(MODEL_PATH) else 0.0


def get_db():
    return DBManager()  # cheap (CREATE IF NOT EXISTS); not cached so a deleted DB file is recreated


# ---------------------------------------------------------------- sidebar

with st.sidebar:
    st.markdown("### ◈ Options Terminal")
    app_mode = st.segmented_control("Mode", ["Dashboard", "Market Gym"], default="Dashboard",
                                    label_visibility="collapsed") or "Dashboard"
    source = st.selectbox("Data source", data_loader.SOURCES)

    kite_instance = indian_api_key = None
    if source == "IndianAPI.in":
        indian_api_key = st.text_input("IndianAPI key", type="password")

    if source == "Zerodha Kite API":
        api_key = st.text_input("Kite API key", type="password")
        request_token = st.query_params.get("request_token")
        if "kite_session" in st.session_state:
            kite_instance = st.session_state["kite_session"]
            st.success("Kite session active")
            if st.button("Log out"):
                del st.session_state["kite_session"]
                st.rerun()
        elif request_token:
            api_secret = st.text_input("Kite API secret", type="password")
            if st.button("Complete login", type="primary") and api_key and api_secret:
                try:
                    st.session_state["kite_session"] = data_loader.generate_kite_session(
                        api_key, api_secret, request_token)
                    st.query_params.clear()
                    st.rerun()
                except Exception as e:
                    st.error(f"Login failed: {e}")
        elif api_key:
            st.link_button("Log in with Zerodha", data_loader.get_kite_login_url(api_key))

    symbols = get_fo_symbols()
    symbol = st.selectbox("Symbol", symbols, index=0)
    custom = st.text_input("…or type any symbol", placeholder="e.g. TATAMOTORS").strip().upper()
    symbol = custom or symbol

    today = date.today()
    picked = st.date_input("Date range", value=(today - timedelta(days=365), today), max_value=today)
    start_date, end_date = picked if isinstance(picked, tuple) and len(picked) == 2 else (today - timedelta(days=365), today)

    st.caption("Sensibull and TradingView use unofficial APIs and can break without notice. Not financial advice.")


# ---------------------------------------------------------------- data

def load_current_frame():
    key = (source, symbol, start_date, end_date)
    if source in SLOW_SOURCES and st.session_state.get("loaded_key") != key:
        st.info("Bhavcopy downloads a file per trading day on first load (cached on disk afterwards).")
        if not st.button("Load Bhavcopy data", type="primary"):
            st.stop()
        st.session_state["loaded_key"] = key
    try:
        with st.spinner(f"Loading {symbol} from {source}…"):
            if source == "Zerodha Kite API":
                if kite_instance is None:
                    raise DataError("Log in to Kite in the sidebar first.")
                return load_kite_frame(kite_instance, kite_instance.access_token, symbol, start_date, end_date)
            return load_frame(source, symbol, start_date, end_date, indian_api_key)
    except DataError as e:
        st.error(str(e))
        st.stop()


def hero(features):
    last, prev = features["close"].iloc[-1], features["close"].iloc[-2] if len(features) > 1 else features["close"].iloc[-1]
    change = last - prev
    pct = change / prev * 100 if prev else 0
    color = theme.GOOD if change >= 0 else theme.CRITICAL
    arrow = "▲" if change >= 0 else "▼"
    st.markdown(f"""
<div class="hero">
  <div><div class="sym">{symbol}</div>
       <div class="sub">{source} · {len(features):,} sessions · last close {features.index[-1]:%d %b %Y}</div></div>
  <div><div class="px">{last:,.2f}</div>
       <div class="chg" style="color:{color}">{arrow} {change:+,.2f} ({pct:+.2f}%)</div></div>
</div>""", unsafe_allow_html=True)


def fmt(v, spec, suffix=""):
    return "—" if v is None or pd.isna(v) else f"{v:{spec}}{suffix}"


def kpis(features):
    row = features.iloc[-1]
    prev = features.iloc[-6] if len(features) > 5 else row
    iv_label = "IV (RV proxy)" if row["iv_is_proxy"] else "ATM IV"
    cols = st.columns(6)
    cols[0].metric(iv_label, fmt(row["iv"], ".1f", "%"), fmt(row["iv"] - prev["iv"], "+.1f", " 5d"),
                   delta_color="off", border=True)
    cols[1].metric("IV percentile", fmt(row["iv_pct"], ".0f"), border=True)
    cols[2].metric("RV 20D", fmt(row["rv20"], ".1f", "%"), fmt(row["rv20"] - prev["rv20"], "+.1f", " 5d"),
                   delta_color="off", border=True)
    cols[3].metric("VRP (IV − RV)", fmt(row["vrp"], "+.1f"), border=True,
                   help="Positive: options priced above realized movement (premium sellers' edge).")
    cols[4].metric("Trend z", fmt(row["trend_z"], "+.2f"), border=True,
                   help="(MA20 / MA50 − 1) in units of 20-day expected move.")
    cols[5].metric("India VIX", fmt(row["vix"], ".2f"), fmt(row["vix"] - prev["vix"], "+.2f", " 5d"),
                   delta_color="off", border=True)


def section(title):
    st.markdown(f'<div class="section">{title}</div>', unsafe_allow_html=True)


# ---------------------------------------------------------------- dashboard

def render_dashboard(df):
    all_features, all_tokens = features_and_tokens(df)
    features, tokens = in_range(all_features), in_range(all_tokens)
    hero(features)
    kpis(features)

    if not tokens.empty:
        section(f"Market sentence · {tokens.index[-1]:%d %b %Y}")
        st.markdown(theme.token_chips(Tokenizer.get_tokens(tokens.iloc[-1])), unsafe_allow_html=True)
    else:
        st.caption("Need ~50 sessions of history before the tokenizer can read the market.")

    if features["iv_is_proxy"].all():
        st.caption(f"{source} has no options data, so realized volatility stands in for IV.")
    st.plotly_chart(charts.market_overview(features, features["iv_is_proxy"].all()),
                    width="stretch", config=charts.PLOTLY_CONFIG)

    view = st.segmented_control("View", ["Regime map", "News"], default="Regime map",
                                label_visibility="collapsed")
    if view == "Regime map" and not tokens.empty:
        st.caption("Each row is one tokenizer slot. Red = down / low / cheap / falling · "
                   "gray = neutral · blue = up / high / rich / rising. Hover for the exact token.")
        st.plotly_chart(charts.regime_strip(tokens), width="stretch", config=charts.PLOTLY_CONFIG)
    elif view == "News":
        with st.spinner("Fetching headlines…"):
            items = get_news(symbol)
        if not items:
            st.info("No recent news found.")
        for item in items:
            st.markdown(f"**[{item['title']}]({item['link']})**  \n"
                        f"<span style='color:{theme.MUTED};font-size:0.8rem'>{item['source']} · {item['published']}</span>",
                        unsafe_allow_html=True)


# ---------------------------------------------------------------- market gym

def recommend(encoder, db, tokens, prior_strength=6):
    """Posterior P(win) per strategy: history in this core regime, with the model's prediction as the prior."""
    beliefs = db.beliefs(symbol, Tokenizer.signature(tokens))
    probs = (encoder.predict_proba([tokens] * len(STRATEGIES), [s.name for s in STRATEGIES])
             if encoder.trained else [None] * len(STRATEGIES))
    recs = []
    for strat, p in zip(STRATEGIES, probs):
        wins, losses = beliefs.get(strat.name, (0, 0))
        prior = 0.5 if p is None else float(p)
        recs.append({
            "strategy": strat.name, "thesis": strat.thesis, "p_model": None if p is None else float(p),
            "wins": wins, "losses": losses, "signal": strat.should_enter(tokens),
            "score": (wins + prior_strength * prior) / (wins + losses + prior_strength),
        })
    return sorted(recs, key=lambda r: r["score"], reverse=True)


def run_gym(df, retrain, all_symbols):
    db = get_db()
    result = BacktestEngine(symbol, df).run()
    if result.trades.empty:
        return {"result": result, "report": None, "audit": causality_audit(df)}
    db.upsert_trades(result.trades)
    report = None
    if retrain:
        from modules.ml.trainer import Trainer
        report = Trainer().fit(db.load_trades(None if all_symbols else symbol))
    return {"result": result, "report": report, "audit": causality_audit(df)}


def model_vs_rules(val: pd.DataFrame) -> pd.DataFrame:
    groups = {
        "Every day (no filter)": val,
        "Rule signals": val[val["is_signal"]],
        "Model picks (P > 55%)": val[val["p_win"] > 0.55],
        "Rules ∧ model agree": val[val["is_signal"] & (val["p_win"] > 0.55)],
    }
    return pd.DataFrame([{"Filter": k, "Trades": len(g),
                          "Win rate": g["win"].mean() * 100 if len(g) else None,
                          "Avg ROI %": g["roi"].mean() if len(g) else None} for k, g in groups.items()])


def render_gym(df):
    features, tokens = features_and_tokens(df)  # the gym backtests all available history
    hero(in_range(features))
    if tokens.empty:
        st.warning("Not enough history to tokenize (need ~50+ sessions). Widen the date range.")
        return
    if features["iv_is_proxy"].mean() > 0.5:
        st.warning(f"{source} has no IV for most days. Options are priced off realized vol, "
                   "so volatility-premium effects will be muted. Sensibull or Bhavcopy give real IV.")

    db = get_db()
    has_model = model_mtime() > 0
    c1, c2, c3 = st.columns([1.2, 1.4, 3])
    run = c1.button("▶  Run gym", type="primary", width="stretch")
    retrain = c2.toggle("Retrain model", value=not has_model,
                        help="Backtesting takes milliseconds; training the transformer takes a few seconds.")
    all_symbols = c3.toggle("Train on every symbol in the DB", value=True,
                            help=f"{db.trade_count():,} stored trades. More symbols → better generalisation.")

    gym_key = (source, symbol, start_date, end_date)
    if run:
        with st.spinner("Simulating every strategy on every day, then training…" if retrain else "Simulating…"):
            st.session_state["gym"] = {"key": gym_key, **run_gym(df, retrain, all_symbols)}
    gym = st.session_state.get("gym")
    if not gym or gym["key"] != gym_key:
        st.markdown(theme.token_chips(Tokenizer.get_tokens(tokens.iloc[-1])), unsafe_allow_html=True)
        st.info("Hit **Run gym**. Four option strategies are priced with Black-Scholes on every day and "
                "settled at expiry, a micro-transformer learns which market sentences they win in, "
                "and the result is today's ranking.")
        return

    result, report = gym["result"], gym["report"]
    encoder = get_encoder(model_mtime())
    latest = Tokenizer.get_tokens(tokens.iloc[-1])

    # --- today's read
    section(f"Today's read · {tokens.index[-1]:%d %b %Y}")
    st.markdown(theme.token_chips(latest), unsafe_allow_html=True)
    recs = recommend(encoder, db, latest)
    for col, (i, rec) in zip(st.columns(len(recs)), enumerate(recs, 1)):
        col.markdown(theme.strategy_card(i, rec), unsafe_allow_html=True)
    if not encoder.trained:
        st.caption("No trained model yet. Scores use regime history only. Turn on **Retrain model** and run.")
    else:
        explain_panel(encoder, latest, recs[0]["strategy"])

    trades = result.trades
    if trades.empty:
        st.warning("No completed trades in this window (each needs its full holding period of future data).")
        return
    signals = trades[trades["is_signal"]]

    # --- backtest
    section(f"Rule-based backtest · {trades['date'].min():%b %Y} – {trades['exit_date'].max():%b %Y} · "
            "cumulative ROI per trade, fixed risk")
    st.plotly_chart(charts.equity_curves(signals), width="stretch", config=charts.PLOTLY_CONFIG)
    left, right = st.columns([3, 2])
    stats = strategy_stats(signals) if not signals.empty else pd.DataFrame()
    left.dataframe(stats, hide_index=True, width="stretch", column_config={
        "Win rate": st.column_config.ProgressColumn("Win rate", format="%.0f%%", min_value=0, max_value=100),
        "Avg ROI %": st.column_config.NumberColumn(format="%+.1f%%"),
        "Total ROI %": st.column_config.NumberColumn(format="%+.0f%%"),
        "Max DD %": st.column_config.NumberColumn(format="%.0f%%"),
    })
    audit = "✅ Causality audit passed: features recomputed on truncated history match exactly." if gym["audit"] \
        else "⚠️ Causality audit failed: a feature is using future data."
    right.caption(f"{audit}  \nOptions priced at entry IV (Black-Scholes), settled at intrinsic after the holding "
                  f"period, {int(0.03 * 100)}% of premium lost to slippage.")

    # --- model
    if report is None and encoder.trained:
        section("Context model")
        meta = encoder.meta
        auc = f"validation AUC {meta['val_auc']:.3f}" if pd.notna(meta.get("val_auc")) else "no validation split"
        st.caption(f"Using the saved model: trained on {meta.get('n_trades', 0):,} trades, {auc}. "
                   "Turn on **Retrain model** to learn from the latest trades.")
    if report is not None:
        section("Context model · out-of-sample")
        for line in report.logs:
            st.caption(line)
        if report.val_predictions is not None:
            m1, m2, m3 = st.columns([1, 1, 2])
            m1.metric("Validation AUC", f"{report.val_auc:.3f}", border=True,
                      help="0.5 = coin flip. Chronological split with purged overlap.")
            m2.metric("Accuracy vs baseline", f"{report.val_acc:.1%}",
                      f"{(report.val_acc - report.val_base_rate) * 100:+.1f} pts", border=True)
            m3.dataframe(model_vs_rules(report.val_predictions), hide_index=True, width="stretch",
                         column_config={"Win rate": st.column_config.NumberColumn(format="%.0f%%"),
                                        "Avg ROI %": st.column_config.NumberColumn(format="%+.1f%%")})
        with st.expander("Training curve"):
            st.plotly_chart(charts.loss_curves(report.train_curve, report.val_curve),
                            width="stretch", config=charts.PLOTLY_CONFIG)

    # --- tokenizer power
    section("What each token says · win rate of every strategy on days carrying that token")
    st.plotly_chart(charts.winrate_heatmap(trades), width="stretch", config=charts.PLOTLY_CONFIG)

    with st.expander(f"Trade log · {len(signals):,} rule signals ({len(trades):,} shadow trades simulated)"):
        log = signals.assign(tokens=signals["tokens"].map(" · ".join)).sort_values("date", ascending=False)
        st.dataframe(log[["date", "strategy", "spot", "exit_spot", "iv", "roi", "win", "tokens"]],
                     hide_index=True, width="stretch", column_config={
                         "date": st.column_config.DateColumn("Entry", format="DD MMM YY"),
                         "spot": st.column_config.NumberColumn("Entry", format="%.2f"),
                         "exit_spot": st.column_config.NumberColumn("Exit", format="%.2f"),
                         "iv": st.column_config.NumberColumn("IV", format="%.1f"),
                         "roi": st.column_config.NumberColumn("ROI", format="%+.1f%%"),
                         "tokens": st.column_config.TextColumn("Market sentence", width="large")})


@st.fragment
def explain_panel(encoder, tokens, default_strategy):
    """Fragment: switching strategy re-renders only this panel, not the page."""
    names = [s.name for s in STRATEGIES]
    pick = st.segmented_control("Why? Explain the model's read for", names, default=default_strategy, key="explain_pick") or default_strategy
    exp = encoder.explain(tokens, pick)
    st.plotly_chart(charts.explain_bars(exp), width="stretch", config=charts.PLOTLY_CONFIG)
    top = max(exp["impact"], key=lambda k: abs(exp["impact"][k]))
    direction = "raises" if exp["impact"][top] >= 0 else "lowers"
    st.caption(f"For **{pick}** the model reads P(win) = {exp['p']:.0%}. **{top}** moves it most: "
               f"it {direction} the odds by {abs(exp['impact'][top]) * 100:.1f} pts "
               f"({Tokenizer.explain_token(top).lower()}).")


# ---------------------------------------------------------------- main

frame = load_current_frame()
if len(frame) < 2:
    st.warning("Not enough data points in this range.")
    st.stop()
if app_mode == "Dashboard":
    render_dashboard(frame)
else:
    render_gym(frame)
