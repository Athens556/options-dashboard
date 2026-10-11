"""Colors, CSS and small HTML components for the dark terminal look."""
import html

from modules.ml.tokens import SLOTS, TOKEN_SLOT, VOCAB_BY_SLOT, Tokenizer

# Surfaces & ink
BG = "#111110"
SURFACE = "#1a1a19"
BORDER = "#2e2e2b"
GRID = "#262624"
TEXT = "#ffffff"
TEXT_2 = "#c3c2b7"
MUTED = "#8a897f"
ACCENT = "#9085e9"

# Categorical slots (dark mode), assigned in fixed order — never cycled.
SERIES = ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#008300", "#9085e9", "#e66767"]
STRATEGY_COLORS = {
    "Iron Condor": SERIES[0],
    "Long Straddle": SERIES[1],
    "Bull Call Spread": SERIES[2],
    "Bear Put Spread": SERIES[3],
}
SLOT_COLORS = dict(zip(SLOTS, SERIES))

# Diverging (blue <-> red, gray midpoint) for polarity: win-rate vs 50%, impact +/-.
DIV_POS, DIV_MID, DIV_NEG = "#3987e5", "#383835", "#e66767"
GOOD, CRITICAL = "#0ca30c", "#d03b3b"

CSS = f"""
<style>
.block-container {{padding-top: 1.6rem; padding-bottom: 3rem; max-width: 1500px;}}
[data-testid="stSidebar"] {{border-right: 1px solid {BORDER};}}
h1, h2, h3 {{letter-spacing: -0.02em;}}
.hero {{display:flex; align-items:flex-end; justify-content:space-between; gap:1rem; flex-wrap:wrap;
        padding: 0.2rem 0 0.9rem; border-bottom: 1px solid {BORDER}; margin-bottom: 1rem;}}
.hero .sym {{font-size: 2.3rem; font-weight: 800; line-height: 1; color:{TEXT};}}
.hero .sub {{color:{MUTED}; font-size: 0.85rem; margin-top: 0.35rem;}}
.hero .px {{font-size: 2rem; font-weight: 700; font-variant-numeric: tabular-nums; color:{TEXT}; text-align:right;}}
.hero .chg {{font-size: 0.95rem; font-weight: 600; text-align:right; font-variant-numeric: tabular-nums;}}
.chips {{display:flex; flex-wrap:wrap; gap:0.45rem; margin: 0.2rem 0 0.6rem;}}
.chip {{display:inline-flex; flex-direction:column; padding: 0.35rem 0.7rem 0.4rem; border-radius: 10px;
        background:{SURFACE}; border:1px solid {BORDER}; border-left: 3px solid var(--c); cursor: help;}}
.chip .slot {{font-size:0.62rem; letter-spacing:0.08em; color:{MUTED}; text-transform:uppercase;}}
.chip .tok {{font-size:0.85rem; font-weight:650; color:{TEXT}; font-family: ui-monospace, SFMono-Regular, Menlo, monospace;}}
.card {{background:{SURFACE}; border:1px solid {BORDER}; border-radius: 14px; padding: 0.9rem 1rem; height: 100%;}}
.card .name {{font-weight:700; font-size:1rem; color:{TEXT}; display:flex; align-items:center; gap:0.5rem;}}
.card .dot {{width:10px; height:10px; border-radius:50%; background: var(--c); display:inline-block;}}
.card .thesis {{color:{MUTED}; font-size:0.78rem; margin: 0.2rem 0 0.7rem; min-height: 2.2em;}}
.card .score {{font-size:2.1rem; font-weight:800; font-variant-numeric: tabular-nums; color:{TEXT}; line-height:1;}}
.card .score small {{font-size:0.8rem; color:{MUTED}; font-weight:500; margin-left:0.3rem;}}
.card .bar {{height:6px; border-radius:3px; background:{GRID}; margin: 0.6rem 0 0.7rem; overflow:hidden;}}
.card .bar > div {{height:100%; background: var(--c); border-radius:3px;}}
.card .row {{display:flex; justify-content:space-between; color:{TEXT_2}; font-size:0.78rem; margin-top:0.15rem;
            font-variant-numeric: tabular-nums;}}
.badge {{font-size:0.66rem; font-weight:700; letter-spacing:0.06em; padding: 0.12rem 0.45rem; border-radius: 999px;
         border:1px solid {BORDER}; color:{MUTED};}}
.badge.on {{color:{TEXT}; border-color:{GOOD}; background: rgba(12,163,12,0.18);}}
.rank {{color:{MUTED}; font-size:0.72rem; font-weight:700; margin-left:auto;}}
.section {{font-size:0.72rem; letter-spacing:0.12em; text-transform:uppercase; color:{MUTED}; font-weight:700;
           margin: 1.4rem 0 0.5rem;}}
</style>
"""


def token_chips(tokens):
    parts = []
    for tok in tokens:
        slot = TOKEN_SLOT.get(tok, "")
        tip = html.escape(Tokenizer.explain_token(tok))
        parts.append(
            f'<div class="chip" style="--c:{SLOT_COLORS.get(slot, MUTED)}" title="{tip}">'
            f'<span class="slot">{slot.replace("_", " ")}</span><span class="tok">{html.escape(tok)}</span></div>')
    return f'<div class="chips">{"".join(parts)}</div>'


def strategy_card(rank, rec):
    color = STRATEGY_COLORS.get(rec["strategy"], ACCENT)
    signal = '<span class="badge on">RULE FIRING</span>' if rec["signal"] else '<span class="badge">NO SIGNAL</span>'
    model = f'{rec["p_model"]:.0%}' if rec["p_model"] is not None else "—"
    return f"""
<div class="card" style="--c:{color}">
  <div class="name"><span class="dot"></span>{html.escape(rec["strategy"])}<span class="rank">#{rank}</span></div>
  <div class="thesis">{html.escape(rec["thesis"])}</div>
  <div class="score">{rec["score"]:.0%}<small>P(win) blended</small></div>
  <div class="bar"><div style="width:{rec["score"] * 100:.0f}%"></div></div>
  <div class="row"><span>Model</span><span>{model}</span></div>
  <div class="row"><span>History in this regime</span><span>{rec["wins"]}W / {rec["losses"]}L</span></div>
  <div class="row" style="margin-top:0.55rem">{signal}</div>
</div>"""


def token_level(token: str) -> float:
    """Ordinal position of a token within its slot, scaled to [-1, 1] (for regime heat strips)."""
    slot = TOKEN_SLOT.get(token)
    if slot is None or token.endswith("_NA"):
        return float("nan")
    levels = [t for t in VOCAB_BY_SLOT[slot] if not t.endswith("_NA")]
    return -1 + 2 * levels.index(token) / (len(levels) - 1)
