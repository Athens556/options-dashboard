"""Plotly figure builders. One shared dark layout, thin marks, one y-scale per panel."""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from modules.ml.tokens import ALL_TOKENS, SLOTS
from . import theme as t

PLOTLY_CONFIG = {"displayModeBar": False, "scrollZoom": False}
SPOT_INK = "#e8e7e1"


def _base(fig: go.Figure, height: int) -> go.Figure:
    fig.update_layout(
        height=height,
        margin=dict(l=8, r=8, t=28, b=8),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=t.TEXT_2, size=12),
        hoverlabel=dict(bgcolor=t.SURFACE, bordercolor=t.BORDER, font=dict(color=t.TEXT)),
        legend=dict(orientation="h", yanchor="bottom", y=1.0, x=0, bgcolor="rgba(0,0,0,0)"),
        hovermode="x unified",
    )
    fig.update_xaxes(showgrid=False, linecolor=t.BORDER, zeroline=False, showspikes=True,
                     spikecolor=t.MUTED, spikethickness=1, spikedash="dot", spikemode="across")
    fig.update_yaxes(gridcolor=t.GRID, zeroline=False, linecolor=t.BORDER)
    return fig


def _line(x, y, name, color, legend="legend", dash=None, width=2):
    return go.Scatter(x=x, y=y, name=name, mode="lines", legend=legend,
                      line=dict(color=color, width=width, dash=dash),
                      hovertemplate=f"{name}: %{{y:,.2f}}<extra></extra>")


def market_overview(f: pd.DataFrame, iv_is_proxy: bool) -> go.Figure:
    """Stacked small multiples sharing the time axis: price, vol, IV percentile, VIX."""
    has_vix = f["vix"].notna().any()
    rows = 4 if has_vix else 3
    heights = [0.46, 0.24, 0.15, 0.15] if has_vix else [0.52, 0.28, 0.20]
    titles = ["Price", "Implied vs realized vol (%)", "IV percentile"] + (["India VIX"] if has_vix else [])
    fig = make_subplots(rows=rows, cols=1, shared_xaxes=True, vertical_spacing=0.055,
                        row_heights=heights, subplot_titles=titles)
    x = f.index
    fig.add_trace(_line(x, f["close"], "Spot", SPOT_INK), 1, 1)
    fig.add_trace(_line(x, f["ma20"], "MA 20", t.SERIES[0], width=1.5), 1, 1)
    fig.add_trace(_line(x, f["ma50"], "MA 50", t.SERIES[1], width=1.5), 1, 1)

    iv_name = "IV (RV proxy)" if iv_is_proxy else "ATM IV"
    fig.add_trace(_line(x, f["iv"], iv_name, t.SERIES[0], legend="legend2"), 2, 1)
    fig.add_trace(_line(x, f["rv20"], "RV 20D", t.SERIES[1], legend="legend2"), 2, 1)

    fig.add_trace(go.Scatter(x=x, y=f["iv_pct"], name="IVP", mode="lines", showlegend=False,
                             line=dict(color=t.SERIES[6], width=2), fill="tozeroy",
                             fillcolor="rgba(144,133,233,0.12)",
                             hovertemplate="IV %ile: %{y:.0f}<extra></extra>"), 3, 1)
    for level in (20, 50, 80):
        fig.add_hline(y=level, line=dict(color=t.BORDER, width=1, dash="dot"), row=3, col=1)
    fig.update_yaxes(range=[0, 100], tickvals=[20, 50, 80], row=3, col=1)

    if has_vix:
        fig.add_trace(go.Scatter(x=x, y=f["vix"], name="VIX", mode="lines", showlegend=False,
                                 line=dict(color=t.SERIES[0], width=2),
                                 hovertemplate="VIX: %{y:.2f}<extra></extra>"), 4, 1)

    _base(fig, 720 if has_vix else 620)
    # One legend per panel, pinned to the panel's top-right
    y2_top = fig.layout.yaxis2.domain[1]
    fig.update_layout(
        legend=dict(orientation="h", x=1, xanchor="right", y=1.0, yanchor="bottom"),
        legend2=dict(orientation="h", x=1, xanchor="right", y=y2_top, yanchor="bottom", bgcolor="rgba(0,0,0,0)"),
    )
    fig.update_annotations(font=dict(size=12, color=t.MUTED), x=0, xanchor="left")
    fig.update_xaxes(rangeselector=dict(
        buttons=[dict(count=1, label="1M", step="month", stepmode="backward"),
                 dict(count=3, label="3M", step="month", stepmode="backward"),
                 dict(count=6, label="6M", step="month", stepmode="backward"),
                 dict(step="all", label="All")],
        bgcolor=t.SURFACE, activecolor=t.BORDER, font=dict(color=t.TEXT_2), y=1.04, x=0.06, xanchor="left"),
        row=1, col=1)
    return fig


def regime_strip(tokens: pd.DataFrame) -> go.Figure:
    """Tokenizer output over time: one row per slot, colored by the token's position in its slot scale."""
    z = np.vectorize(t.token_level, otypes=[float])(tokens[SLOTS].to_numpy()).T
    fig = go.Figure(go.Heatmap(
        z=z, x=tokens.index, y=[s.replace("_", " ") for s in SLOTS], customdata=tokens[SLOTS].to_numpy().T,
        colorscale=[[0, t.DIV_NEG], [0.5, t.DIV_MID], [1, t.DIV_POS]], zmin=-1, zmax=1, showscale=False,
        xgap=0, ygap=2, hovertemplate="%{x|%d %b %Y}<br>%{customdata}<extra></extra>"))
    _base(fig, 300)
    fig.update_layout(hovermode="closest")
    fig.update_yaxes(autorange="reversed", gridcolor="rgba(0,0,0,0)")
    fig.update_xaxes(showspikes=False)
    return fig


def equity_curves(signals: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    for name, color in t.STRATEGY_COLORS.items():
        g = signals[signals["strategy"] == name].sort_values("date")
        if g.empty:
            continue
        fig.add_trace(go.Scatter(
            x=g["date"], y=g["roi"].cumsum(), name=name, mode="lines", line=dict(color=color, width=2),
            customdata=np.stack([g["roi"], g["tokens"].map(" · ".join)], axis=-1),
            hovertemplate=f"{name}: %{{y:,.0f}}% cum · trade %{{customdata[0]:+.0f}}%<extra></extra>"))
    fig.add_hline(y=0, line=dict(color=t.BORDER, width=1))
    _base(fig, 360)
    fig.update_yaxes(ticksuffix="%", title=None)
    return fig


def explain_bars(explanation: dict) -> go.Figure:
    """Attention (what the model looks at) beside masking impact (which way each token pushes P(win))."""
    tokens = list(explanation["attention"])
    attn = [explanation["attention"][k] * 100 for k in tokens]
    impact = [explanation["impact"][k] * 100 for k in tokens]
    fig = make_subplots(rows=1, cols=2, shared_yaxes=True, horizontal_spacing=0.04,
                        subplot_titles=["Attention (%)", "Impact on P(win) (pts)"])
    fig.add_trace(go.Bar(y=tokens, x=attn, orientation="h", marker=dict(color=t.ACCENT, cornerradius=4),
                         showlegend=False, hovertemplate="%{y}: %{x:.1f}% attention<extra></extra>"), 1, 1)
    fig.add_trace(go.Bar(y=tokens, x=impact, orientation="h", showlegend=False,
                         marker=dict(color=[t.DIV_POS if v >= 0 else t.DIV_NEG for v in impact], cornerradius=4),
                         hovertemplate="%{y}: %{x:+.1f} pts<extra></extra>"), 1, 2)
    _base(fig, 300)
    fig.update_layout(hovermode="closest", bargap=0.35)
    fig.update_yaxes(autorange="reversed", gridcolor="rgba(0,0,0,0)")
    fig.update_xaxes(gridcolor=t.GRID, showspikes=False)
    fig.update_annotations(font=dict(size=12, color=t.MUTED), x=None)
    for i, ann in enumerate(fig.layout.annotations):
        ann.update(x=[0, 0.52][i], xanchor="left")
    return fig


def winrate_heatmap(trades: pd.DataFrame) -> go.Figure:
    """Win rate of every strategy conditioned on each token — the tokenizer's raw explanatory power."""
    exploded = trades[["strategy", "tokens", "win"]].explode("tokens")
    pivot = exploded.pivot_table(index="tokens", columns="strategy", values="win", aggfunc=["mean", "count"])
    order = [tok for tok in ALL_TOKENS if tok in pivot.index]
    cols = [s for s in t.STRATEGY_COLORS if s in pivot["mean"].columns]
    rate = pivot["mean"].loc[order, cols] * 100
    count = pivot["count"].loc[order, cols]
    text = rate.round(0).astype("Int64").astype(str) + "%"
    fig = go.Figure(go.Heatmap(
        z=rate.to_numpy(), x=cols, y=order, text=text.to_numpy(), texttemplate="%{text}",
        customdata=count.to_numpy(), zmid=50, zmin=0, zmax=100, xgap=2, ygap=2,
        colorscale=[[0, t.DIV_NEG], [0.5, t.DIV_MID], [1, t.DIV_POS]],
        colorbar=dict(title="Win %", thickness=10, outlinewidth=0, ticksuffix="%"),
        hovertemplate="%{y} × %{x}<br>Win rate %{z:.0f}% over %{customdata} trades<extra></extra>"))
    _base(fig, 34 * len(order) + 80)
    fig.update_layout(hovermode="closest")
    fig.update_yaxes(autorange="reversed", gridcolor="rgba(0,0,0,0)")
    fig.update_xaxes(side="top", showspikes=False)
    return fig


def loss_curves(train_curve, val_curve) -> go.Figure:
    fig = go.Figure()
    epochs = np.arange(1, len(train_curve) + 1)
    fig.add_trace(_line(epochs, train_curve, "Train loss", t.SERIES[0]))
    if val_curve:
        fig.add_trace(_line(np.arange(1, len(val_curve) + 1), val_curve, "Validation loss", t.SERIES[1]))
    _base(fig, 260)
    fig.update_xaxes(title="Epoch", showspikes=False)
    return fig
