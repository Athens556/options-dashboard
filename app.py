import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import date, timedelta
from modules.api import data_loader
from modules.api import news_loader
from modules import utils

# New Modules
from modules.dashboard.market_state import MarketStateBuilder
from modules.ml.tokens import Tokenizer
from modules.dashboard.db_manager import DBManager
from modules.dashboard.backtest import BacktestEngine
from modules.dashboard import strategy as strategies

st.set_page_config(page_title="Options Trading Dashboard", layout="wide")

st.title("Options Trading Dashboard")

# --- Sidebar Configuration ---
st.sidebar.header("Configuration")
app_mode = st.sidebar.selectbox("App Mode", ["Dashboard", "Market Gym (Research)"])
st.sidebar.markdown("---")
data_source_mode = st.sidebar.radio("Data Source", ["Sensibull (Unofficial)", "DhanHQ", "Open Source (Bhavcopy)", "Zerodha Kite API", "IndianAPI.in", "TradingView (Unofficial)"])

# Shared State
kite_instance = None
indian_api_key = None

if data_source_mode == "IndianAPI.in":
    st.sidebar.subheader("IndianAPI Credentials")
    indian_api_key = st.sidebar.text_input("API Key", type="password")

if data_source_mode == "Zerodha Kite API":
    st.sidebar.subheader("Kite Credentials")
    api_key = st.sidebar.text_input("API Key", type="password")
    query_params = st.experimental_get_query_params()
    request_token = query_params.get("request_token", [None])[0]
    
    if request_token and "kite_session" not in st.session_state:
        st.sidebar.info("Token received. Enter Secret to complete.")
        api_secret = st.sidebar.text_input("API Secret (Re-enter)", type="password")
        if st.sidebar.button("Complete Login"):
            if api_key and api_secret:
                try:
                    with st.spinner("Authenticating..."):
                        kite = data_loader.generate_kite_session(api_key, api_secret, request_token)
                        st.session_state["kite_session"] = kite
                        st.success("Logged in to Kite!")
                        st.experimental_set_query_params()
                        st.experimental_rerun()
                except Exception as e:
                    st.error(f"Login failed: {e}")
            else:
                st.error("API Secret required.")
    elif "kite_session" not in st.session_state:
        api_secret = st.sidebar.text_input("API Secret", type="password")
        if api_key:
            login_url = data_loader.get_kite_login_url(api_key)
            st.sidebar.markdown(f'<a href="{login_url}" target="_self">Login with Zerodha</a>', unsafe_allow_html=True)
            st.info("Click above to login.")
            
    if "kite_session" in st.session_state:
        kite_instance = st.session_state["kite_session"]
        st.sidebar.success("Session Active")
        if st.sidebar.button("Logout"):
            del st.session_state["kite_session"]
            st.experimental_rerun()

# Date Range
today = date.today()
start_date = st.sidebar.date_input("Start Date", value=today - timedelta(days=365))
end_date = st.sidebar.date_input("End Date", value=today)

# Common F&O Stocks
if hasattr(st, 'cache_data'):
    cache_decorator = st.cache_data
else:
    cache_decorator = st.cache

@cache_decorator
def get_fo_symbols():
    symbols = data_loader.fetch_nifty_fo_symbols()
    if not symbols:
        return ["SBIN", "INFY", "RELIANCE", "TCS", "HDFCBANK", "ICICIBANK", "NIFTY", "BANKNIFTY"]
    return symbols

COMMON_STOCKS = get_fo_symbols()
symbol = st.sidebar.selectbox("Select Symbol", options=COMMON_STOCKS, index=0)

if "Other" in COMMON_STOCKS and symbol == "Other":
    symbol = st.sidebar.text_input("Enter Symbol (e.g. TATAMOTORS)", value="TATAMOTORS")


# --- Main Application Logic ---

def render_dashboard():
    if st.sidebar.button("Fetch Data"):
        with st.spinner("Fetching and processing data..."):
            if data_source_mode == "IndianAPI.in":
                if not indian_api_key:
                    st.error("Please enter IndianAPI Key.")
                else:
                    spot_df = data_loader.fetch_indianapi_data(symbol, indian_api_key)
                    if spot_df.empty:
                        st.error("No data returned from IndianAPI.in")
                    else:
                        spot = spot_df['close']
                        spot = spot[(spot.index >= start_date) & (spot.index <= end_date)]
                        st.success(f"Fetched Spot Data from IndianAPI.in! ({len(spot)} records)")
                        st.subheader(f"{symbol} Spot Price (IndianAPI)")
                        fig_spot = go.Figure()
                        fig_spot.add_trace(go.Scatter(x=spot.index, y=spot.values, mode='lines', name='Spot Price'))
                        st.plotly_chart(fig_spot, use_container_width=True)
                        rv = utils.calculate_rv(spot)
                        st.subheader("Realized Volatility (20D)")
                        fig_rv = go.Figure()
                        fig_rv.add_trace(go.Scatter(x=rv.index, y=rv.values, mode='lines', name='RV', line=dict(color='blue')))
                        st.plotly_chart(fig_rv, use_container_width=True)
                        st.info("Note: IV calculation requires Options Chain data which is not yet integrated for IndianAPI.in.")

            elif data_source_mode == "TradingView (Unofficial)":
                spot_df = data_loader.fetch_tv_data(symbol)
                if spot_df.empty:
                    st.error("No data returned from TradingView.")
                else:
                    spot = spot_df['close']
                    spot = spot[(spot.index >= start_date) & (spot.index <= end_date)]
                    st.success(f"Fetched Spot Data from TradingView! ({len(spot)} records)")
                    st.subheader(f"{symbol} Spot Price (TradingView)")
                    fig_spot = go.Figure()
                    fig_spot.add_trace(go.Scatter(x=spot.index, y=spot.values, mode='lines', name='Spot Price'))
                    st.plotly_chart(fig_spot, use_container_width=True)
                    rv = utils.calculate_rv(spot)
                    st.subheader("Realized Volatility (20D)")
                    fig_rv = go.Figure()
                    fig_rv.add_trace(go.Scatter(x=rv.index, y=rv.values, mode='lines', name='RV', line=dict(color='blue')))
                    st.plotly_chart(fig_rv, use_container_width=True)
                    st.info("Note: IV calculation requires Options Chain data.")

            elif data_source_mode == "Sensibull (Unofficial)":
                df = data_loader.fetch_sensibull_data(symbol)
                if df.empty:
                    st.error("No data returned from Sensibull.")
                else:
                    df = df[(df.index >= start_date) & (df.index <= end_date)]
                    st.success(f"Fetched Data from Sensibull! ({len(df)} records)")
                    spot = df['close'] if 'close' in df.columns else pd.Series()
                    iv = df['iv'] if 'iv' in df.columns else pd.Series()
                    vix = df['vix'] if 'vix' in df.columns else pd.Series()
                    if not spot.empty:
                        st.subheader(f"{symbol} Spot Price (Sensibull)")
                        fig_spot = go.Figure()
                        fig_spot.add_trace(go.Scatter(x=spot.index, y=spot.values, mode='lines', name='Spot Price'))
                        st.plotly_chart(fig_spot, use_container_width=True)
                        rv = utils.calculate_rv(spot)
                    if not iv.empty:
                        st.subheader("Implied Volatility (ATM)")
                        fig_iv = go.Figure()
                        fig_iv.add_trace(go.Scatter(x=iv.index, y=iv.values, mode='lines', name='IV', line=dict(color='orange')))
                        st.plotly_chart(fig_iv, use_container_width=True)
                    if not iv.empty and not spot.empty:
                        st.subheader("IV vs RV")
                        fig_iv_rv = go.Figure()
                        fig_iv_rv.add_trace(go.Scatter(x=iv.index, y=iv.values, mode='lines', name='IV', line=dict(color='orange')))
                        fig_iv_rv.add_trace(go.Scatter(x=rv.index, y=rv.values, mode='lines', name='RV (20D)', line=dict(color='blue')))
                        st.plotly_chart(fig_iv_rv, use_container_width=True)
                    if not vix.empty:
                        st.subheader("India VIX")
                        fig_vix = go.Figure()
                        fig_vix.add_trace(go.Scatter(x=vix.index, y=vix.values, mode='lines', name='India VIX', line=dict(color='red')))
                        st.plotly_chart(fig_vix, use_container_width=True)
                    ivp = df['ivp'] if 'ivp' in df.columns else pd.Series()
                    if ivp.empty and not iv.empty: ivp = utils.calculate_iv_percentile(iv)
                    if not ivp.empty:
                        st.subheader("IV Percentile")
                        fig_ivp = go.Figure()
                        fig_ivp.add_trace(go.Scatter(x=ivp.index, y=ivp.values, mode='lines', name='IVP', line=dict(color='purple')))
                        fig_ivp.add_hline(y=20, line_dash="dash", line_color="green", annotation_text="Low IV (20)")
                        fig_ivp.add_hline(y=50, line_dash="dash", line_color="gray", annotation_text="Median (50)")
                        fig_ivp.add_hline(y=80, line_dash="dash", line_color="red", annotation_text="High IV (80)")
                        fig_ivp.update_layout(yaxis_range=[0, 100])
                        st.plotly_chart(fig_ivp, use_container_width=True)

            elif data_source_mode == "DhanHQ":
                spot_df = data_loader.fetch_dhan_data(symbol, start_date, end_date)
                if spot_df.empty:
                    st.error("No data returned from DhanHQ. Check symbol or credentials.")
                else:
                    st.success(f"Fetched Data from DhanHQ! ({len(spot_df)} records)")
                    spot = spot_df['close']
                    st.subheader(f"{symbol} Spot Price (DhanHQ)")
                    fig_spot = go.Figure()
                    fig_spot.add_trace(go.Scatter(x=spot.index, y=spot.values, mode='lines', name='Spot Price'))
                    st.plotly_chart(fig_spot, use_container_width=True)
                    rv = utils.calculate_rv(spot)
                    st.subheader("Realized Volatility (20D)")
                    fig_rv = go.Figure()
                    fig_rv.add_trace(go.Scatter(x=rv.index, y=rv.values, mode='lines', name='RV', line=dict(color='blue')))
                    st.plotly_chart(fig_rv, use_container_width=True)
                    st.info("Note: Showing Spot and RV. IV requires options chain data not yet implemented for Dhan.")

            elif data_source_mode == "Zerodha Kite API" and kite_instance:
                try:
                    token = utils.get_instrument_token(kite_instance, symbol)
                    if not token:
                        search_symbol = symbol
                        if symbol == "NIFTY": search_symbol = "NIFTY 50"
                        if symbol == "BANKNIFTY": search_symbol = "NIFTY BANK"
                        token = utils.get_instrument_token(kite_instance, search_symbol)
                    if not token:
                        st.error(f"Instrument token not found for {symbol}")
                    else:
                        spot_df = data_loader.fetch_kite_historical_data(kite_instance, token, start_date, end_date)
                        if spot_df.empty:
                            st.error("No data returned from Kite.")
                        else:
                            spot = spot_df['close']
                            st.success(f"Fetched Spot Data from Kite! ({len(spot)} records)")
                            st.subheader(f"{symbol} Spot Price (Kite)")
                            fig_spot = go.Figure()
                            fig_spot.add_trace(go.Scatter(x=spot.index, y=spot.values, mode='lines', name='Spot Price'))
                            st.plotly_chart(fig_spot, use_container_width=True)
                            rv = utils.calculate_rv(spot)
                            st.subheader("Realized Volatility (20D)")
                            fig_rv = go.Figure()
                            fig_rv.add_trace(go.Scatter(x=rv.index, y=rv.values, mode='lines', name='RV', line=dict(color='blue')))
                            st.plotly_chart(fig_rv, use_container_width=True)
                            st.info("Note: IV calculation using Kite data requires fetching options chain history.")
                except Exception as e:
                    st.error(f"Kite Error: {e}")
            elif data_source_mode == "Zerodha Kite API" and not kite_instance:
                st.error("Please login to Kite first.")

            else:
                data, error = data_loader.process_market_data(symbol, start_date, end_date)
                if error:
                    st.error(f"Error: {error}")
                else:
                    spot = data['spot']
                    vix = data['vix']
                    rv = data['rv']
                    iv = data['iv']
                    source = data.get('source', 'Unknown')
                    st.success(f"Data fetched successfully! Spot Price Source: **{source}**")
                    st.subheader(f"{symbol} Spot Price")
                    fig_spot = go.Figure()
                    fig_spot.add_trace(go.Scatter(x=spot.index, y=spot.values, mode='lines', name='Spot Price'))
                    st.plotly_chart(fig_spot, use_container_width=True)
                    st.subheader("Implied Volatility (ATM)")
                    if not iv.empty:
                        fig_iv = go.Figure()
                        fig_iv.add_trace(go.Scatter(x=iv.index, y=iv.values, mode='lines', name='IV', line=dict(color='orange')))
                        st.plotly_chart(fig_iv, use_container_width=True)
                    st.subheader("IV vs RV")
                    if not iv.empty and not rv.empty:
                        fig_iv_rv = go.Figure()
                        fig_iv_rv.add_trace(go.Scatter(x=iv.index, y=iv.values, mode='lines', name='IV', line=dict(color='orange')))
                        fig_iv_rv.add_trace(go.Scatter(x=rv.index, y=rv.values, mode='lines', name='RV (20D)', line=dict(color='blue')))
                        st.plotly_chart(fig_iv_rv, use_container_width=True)
                    st.subheader("India VIX")
                    if not vix.empty:
                        fig_vix = go.Figure()
                        fig_vix.add_trace(go.Scatter(x=vix.index, y=vix.values, mode='lines', name='India VIX', line=dict(color='red')))
                        st.plotly_chart(fig_vix, use_container_width=True)
                    st.subheader("IV Percentile")
                    if not iv.empty:
                        ivp = utils.calculate_iv_percentile(iv)
                        fig_ivp = go.Figure()
                        fig_ivp.add_trace(go.Scatter(x=ivp.index, y=ivp.values, mode='lines', name='IVP', line=dict(color='purple')))
                        fig_ivp.add_hline(y=20, line_dash="dash", line_color="green", annotation_text="Low IV (20)")
                        fig_ivp.add_hline(y=50, line_dash="dash", line_color="gray", annotation_text="Median (50)")
                        fig_ivp.add_hline(y=80, line_dash="dash", line_color="red", annotation_text="High IV (80)")
                        fig_ivp.update_layout(yaxis_range=[0, 100])
                        st.plotly_chart(fig_ivp, use_container_width=True)
                    st.markdown("---")
        st.markdown("---")
        st.header(f"News & Trends: {symbol}")
        tab1, tab2 = st.tabs(["Latest News", "Google Trends"])
        with tab1:
            with st.spinner("Fetching News..."):
                news_items = news_loader.fetch_google_news(symbol)
                if news_items:
                    for item in news_items:
                        st.markdown(f"**[{item['title']}]({item['link']})**")
                        st.caption(f"{item['source']} - {item['published']}")
                        st.markdown("---")
                else:
                    st.info("No recent news found.")
        with tab2:
            with st.spinner("Fetching Trends..."):
                # trends_df = news_loader.fetch_google_trends(symbol)
                # if not trends_df.empty:
                #     fig_trends = go.Figure()
                #     fig_trends.add_trace(go.Scatter(x=trends_df.index, y=trends_df[symbol], mode='lines', name='Interest', line=dict(color='blue')))
                #     st.plotly_chart(fig_trends, use_container_width=True)
                # else:
                #     st.warning("Could not fetch Google Trends data (likely rate limited).")
                st.info("Google Trends disabled by user request.")
    st.sidebar.markdown("---")
    st.sidebar.info("Note: Historical IV is calculated using Black-Scholes on ATM options from NSE Bhavcopy.")

def render_market_gym():
    st.subheader("Adaptive Market Research (Alpha)")
    st.markdown("Visualize market regimes, test strategies conditionally, and update beliefs.")
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.info("Current State Analysis")
        # Placeholder for 'As of Date' analysis
        # We need to fetch data first
        pass
        
    db = DBManager()
    
    if st.button("Analyze Current State & Run Backtest"):
        with st.spinner("Building Context & Simulating Strategies..."):
            # 1. Fetch Data (Sensibull)
            # Use fetch_sensibull_data directly
            df = data_loader.fetch_sensibull_data(symbol)
            
            if df.empty:
                st.error("No data returned from Sensibull.")
                return
            
            # Filter by date
            df = df[(df.index >= start_date) & (df.index <= end_date)]
            
            if df.empty:
                st.error("No data in selected date range.")
                return
                
            spot_series = df['close']
            iv_series = df['iv'] if 'iv' in df.columns else pd.Series()
            # Calculate RV dynamically
            rv_series = utils.calculate_rv(spot_series)
            
            if spot_series.empty:
                st.error("No spot data available.")
                return
            
            # 2. Build State for latest date
            builder = MarketStateBuilder()
            latest_date = spot_series.index[-1]
            state = builder.build_daily_state(symbol, latest_date, spot_series, iv_series, rv_series)
            
            if state:
                tokens = Tokenizer.get_tokens(state)
                
                # Display State
                st.success(f"Market State for {latest_date}")
                c1, c2, c3 = st.columns(3)
                c1.metric("Trend Score", f"{state.trend_score:.2%}", f"{state.regime_label}")
                c2.metric("Volatility Regime", state.volatility_regime, f"IVP: {state.iv_percentile:.0f}")
                c3.metric("VRP", f"{state.vrp:.1f}")
                
                # Phase 4.5: Narrative Context
                # Extract Narrative token if present
                narrative_status = "ABSENT"
                narrative_color = "gray"
                for t in tokens:
                    if "NARRATIVE_PRESENT" in t:
                        narrative_status = "PRESENT"
                        narrative_color = "red"
                    elif "NARRATIVE_UNCERTAIN" in t:
                        narrative_status = "UNCERTAIN"
                        narrative_color = "orange"
                
                st.markdown(f"**Narrative Context:** :{narrative_color}[{narrative_status}]")
                if narrative_status == "PRESENT":
                    # Explain why? (Tokenizer doesn't return description, only token)
                    # Ideally we would get the full NarrativeState object here.
                    # For now, just show the token.
                    st.caption("Active Drivers: High Trends Velocity / News Volume")
                
                st.subheader("Active Tokens")
                st.write(tokens)
                
                # RECOMMENDED STRATEGIES
                st.subheader("Recommended Strategies (Bayesian Allocator)")
                recs = db.get_recommended_strategies(tokens)
                if recs:
                    for rec in recs:
                        with st.expander(f"{rec['strategy']} | Score: {rec['score']:.2f} | Conf: {rec['confidence']:.1f}"):
                            st.write(f"Observations: {rec['obs']}")
                            
                            # Phase 4: Model Attention
                            if 'attention' in rec and rec['attention']:
                                st.caption("Context Attention (Learned Importance):")
                                attn = rec['attention']
                                # Sort by weight
                                sorted_attn = sorted(attn.items(), key=lambda x: x[1], reverse=True)
                                attn_df = pd.DataFrame(sorted_attn, columns=["Token", "Weight"])
                                st.dataframe(attn_df)
                                
                                # Highlight Top Token
                                top_token = sorted_attn[0][0]
                                st.info(f"Model focuses on **{top_token}** as key signal.")
                else:
                    st.info("No sufficient belief data yet. Run backtest to learn.")
                    
            # 3. RUN BACKTEST
            st.markdown("---")
            st.write(f"Running Conditional Backtest ({start_date} to {end_date})...")
            engine = BacktestEngine(symbol, start_date, end_date)
            output = engine.run(strategies.get_all_strategies())
            
            trades = output['trades']
            history = output['history']
            
            if trades:
                df = pd.DataFrame(trades)
                st.subheader(f"Trade Log ({len(df)} trades)")
                st.dataframe(df)
                
                win_rate = df[df['result'].apply(lambda x: x['win'])] 
                st.metric("Total Trades", len(df), f"Win Rate: {len(win_rate)/len(df):.1%}")
                
                # Visualize PnL
                # Extract pnl from result dict
                df['pnl'] = df['result'].apply(lambda x: x['pnl'])
                df['cum_pnl'] = df['pnl'].cumsum()
                
                fig_pnl = go.Figure()
                fig_pnl.add_trace(go.Bar(x=df['date'], y=df['pnl'], name='Trade PnL'))
                fig_pnl.add_trace(go.Scatter(x=df['date'], y=df['cum_pnl'], name='Cumulative PnL', yaxis='y2'))
                fig_pnl.update_layout(title="Backtest Performance", yaxis2=dict(overlaying='y', side='right'))
                st.plotly_chart(fig_pnl, use_container_width=True)
            else:
                st.warning("No TRADES generated in this period.")
                
            # Always show History Debug if requested or if no trades
            if history:
                with st.expander("See Market Regime History (Debug)", expanded=not trades):
                    hist_df = pd.DataFrame(history)
                    st.dataframe(hist_df)
                    st.caption("This log shows the Market Regimes and Tokens generated for each day. If 'Tokens' don't match Strategy logic, no trades occur.")
            
            # 4. TRAINING (Auto-Learn)
            if trades:
                st.markdown("---")
                st.write("🧠 **Active Learning System**")
                with st.spinner("Training Context Transformer on new data..."):
                    try:
                        from modules.ml.trainer import Trainer
                        # Initialize Trainer
                        t = Trainer()
                        # Train on the trades we just simulated
                        logs = t.train_from_trades(trades, epochs=5)
                        
                        # Show logs
                        with st.expander("Training Logs", expanded=True):
                            for log in logs:
                                st.code(log, language="text")
                        
                        st.success(f"Context Encoder Updated! Loss reduced (See logs).")
                    except Exception as e:
                        st.error(f"Training Failed: {e}")
                
if app_mode == "Dashboard":
    render_dashboard()
else:
    render_market_gym()
