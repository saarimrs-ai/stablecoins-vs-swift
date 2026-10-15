"""Stablecoins vs SWIFT: reproducible analysis.
Run: python analysis.py   (needs pandas, matplotlib)
Every input is in data/ with its source. Assumptions are named constants below.
"""
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

ROOT = Path(__file__).parent
D, C = ROOT / "data", ROOT / "charts"
C.mkdir(exist_ok=True)

# ---------- Stablecoin rail cost assumptions (all-in, per transfer) ----------
# These are ASSUMPTIONS, not observed prices. Change them and everything re-runs.
RAIL = {  # (on-ramp %, off-ramp incl. FX %, fixed $ per transfer)
    "low":  (0.10, 0.30, 0.55),
    "base": (0.50, 1.00, 0.55),
    "high": (1.50, 3.00, 0.55),
}
TICKET = 200  # World Bank RPW benchmark transfer size (USD)
rail_cost = {k: on + off + fixed / TICKET * 100 for k, (on, off, fixed) in RAIL.items()}

# ---------- Load data ----------
sup = pd.read_csv(D / "stablecoin_supply_monthly.csv", parse_dates=["month"])
tb = pd.read_csv(D / "us_3m_tbill_monthly.csv", parse_dates=["month"])
iss = pd.read_csv(D / "stablecoin_issuers_2026-10.csv")
rpw = pd.read_csv(D / "rpw_corridor_costs_q3_2025.csv")
ctx = pd.read_csv(D / "remittance_context.csv").set_index("metric")["value"]

def supply_at(m):
    return sup.loc[sup.month == pd.Timestamp(m), "total_stablecoin_supply_usd_m"].iloc[0] / 1000

# ---------- Key metrics ----------
m = {}
m["supply_oct24_bn"] = supply_at("2024-10-01")
m["supply_oct25_bn"] = supply_at("2025-10-01")
m["supply_oct26_bn"] = supply_at("2026-10-01")
m["growth_oct24_oct25_pct"] = (m["supply_oct25_bn"] / m["supply_oct24_bn"] - 1) * 100
m["growth_oct25_oct26_pct"] = (m["supply_oct26_bn"] / m["supply_oct25_bn"] - 1) * 100
m["tbill_peak_pct"] = tb.tbill_3m_pct.max()
m["tbill_latest_pct"] = tb.tbill_3m_pct.iloc[-1]
tot = iss.loc[iss.symbol == "TOTAL", "supply_usd_m_oct2026"].iloc[0]
m["usdt_share_pct"] = iss.loc[iss.symbol == "USDT", "supply_usd_m_oct2026"].iloc[0] / tot * 100
m["usdc_share_pct"] = iss.loc[iss.symbol == "USDC", "supply_usd_m_oct2026"].iloc[0] / tot * 100
for k, v in rail_cost.items():
    m[f"rail_cost_{k}_pct"] = v

# Global fee pool (illustrative upper bound: $200 cost applied to all flows)
m["global_fee_pool_bn"] = ctx["Remittances to low/middle-income countries"] * ctx["Global average cost of sending $200"] / 100
m["gap_to_sdg_bn"] = ctx["Remittances to low/middle-income countries"] * (ctx["Global average cost of sending $200"] - 3) / 100

# Corridors where the base-case rail beats the incumbent average
m["corridors_tested"] = len(rpw)
m["offers_tested"] = int(rpw.n_offers.sum())
for bench in ["avg_total_cost_pct_usd200", "median_cost_pct", "min_cost_pct"]:
    m[f"corridors_beaten_vs_{bench}"] = int((rpw[bench] > rail_cost["base"]).sum())

# Pakistan: corridor-weighted saving vs PVARA's $400m claim
pk = pd.DataFrame({
    "corridor": ["Saudi Arabia → Pakistan", "UAE → Pakistan", "UK → Pakistan"],
    "flow_bn": [ctx["Pakistan remittances from Saudi Arabia"], ctx["Pakistan remittances from UAE"], ctx["Pakistan remittances from UK"]],
    "avg_pct": [5.02, 2.17, 2.39], "median_pct": [3.06, 0.63, 2.51], "min_pct": [1.44, -0.49, -1.44],
})
pk["incumbent_pct"] = pk.avg_pct
for k in ["low", "base", "high"]:
    pk[f"saving_{k}_m"] = (pk.flow_bn * 1000 * (pk.incumbent_pct - rail_cost[k]) / 100).clip(lower=0)
for b in ["avg", "median", "min"]:
    pk[f"saving_base_vs_{b}_m"] = (pk.flow_bn * 1000 * (pk[f"{b}_pct"] - rail_cost["base"]) / 100).clip(lower=0)
    m[f"pk_saving_base_vs_{b}_m"] = pk[f"saving_base_vs_{b}_m"].sum()
m["pk_saving_base_m"] = pk.saving_base_m.sum()
m["pk_saving_low_m"] = pk.saving_low_m.sum()
m["pk_saving_high_m"] = pk.saving_high_m.sum()
m["pk_saudi_share_of_base_saving_pct"] = pk.saving_base_m.iloc[0] / pk.saving_base_m.sum() * 100

# Issuer rate squeeze (Circle-like): what 100bp of rate cuts costs and what replaces it
USDC_AVG_BN, DIST_SHARE = 73.0, 1662 / 2747  # distribution costs as share of revenue, FY2025
lost_reserve = USDC_AVG_BN * 0.01 * 1000  # $m lost per 100bp
lost_rldc = lost_reserve * (1 - DIST_SHARE)
m["issuer_reserve_loss_per_100bp_m"] = lost_reserve
m["issuer_rldc_loss_per_100bp_m"] = lost_rldc
m["payment_volume_to_replace_100bp_bn_at_10bp"] = lost_rldc / 0.001 / 1000

pd.Series(m).round(2).to_csv(ROOT / "key_metrics.csv", header=["value"])
pk.round(1).to_csv(D / "derived_pakistan_corridor_savings.csv", index=False)

# ---------- Charts (palette: dataviz reference instance) ----------
INK, INK2, MUTED, GRID, BASE = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
plt.rcParams.update({"text.parse_math": False, 
    "font.size": 10, "axes.edgecolor": BASE, "axes.labelcolor": INK2, "xtick.color": MUTED,
    "ytick.color": MUTED, "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6, "axes.axisbelow": True,
    "figure.facecolor": "#fcfcfb", "axes.facecolor": "#fcfcfb", "text.color": INK,
})

def src(fig, txt):
    fig.text(0.01, 0.01, txt, fontsize=7.5, color=MUTED)

# 1. Supply vs rates (two panels, one axis each)
fig, (a1, a2) = plt.subplots(2, 1, figsize=(8, 5.6), sharex=True, gridspec_kw={"height_ratios": [3, 2]})
s = sup[sup.month >= "2021-01-01"]
a1.plot(s.month, s.total_stablecoin_supply_usd_m / 1000, color=BLUE, lw=2)
a1.set_ylabel("Stablecoin supply ($bn)")
a1.set_title("Stablecoin supply grew 77% in a year, then flatlined after the GENIUS Act", loc="left", fontsize=11, color=INK)
for d, lab in [("2025-07-18", "GENIUS Act signed\n18 Jul 2025")]:
    a1.axvline(pd.Timestamp(d), color=MUTED, lw=1, ls="--")
    a1.text(pd.Timestamp(d), 100, " " + lab, fontsize=8, color=INK2, va="bottom")
a1.annotate(f"+{m['growth_oct24_oct25_pct']:.0f}% in 12 months", xy=(pd.Timestamp("2025-01-15"), 270), fontsize=8.5, color=INK2, ha="right")
a1.annotate(f"+{m['growth_oct25_oct26_pct']:.1f}% in 12 months", xy=(pd.Timestamp("2026-04-01"), 322), fontsize=8.5, color=INK2, ha="center")
t = tb[tb.month >= "2021-01-01"]
a2.plot(t.month, t.tbill_3m_pct, color=ORANGE, lw=2)
a2.set_ylabel("3-month T-bill (%)")
a2.xaxis.set_major_locator(mdates.YearLocator())
a2.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
src(fig, "Source: DefiLlama stablecoin API (monthly, to Oct 2026); FRED TB3MS (to Sep 2026).")
fig.tight_layout(rect=(0, 0.03, 1, 1)); fig.savefig(C / "1_supply_vs_rates.png", dpi=170); plt.close(fig)

# 2. Corridor map: cheapest vs typical offer, against the stablecoin rail band
r = rpw[~rpw.corridor.isin(["TZ/KE", "ZA/MW"])].copy()
r["label"] = r["from"] + " → " + r["to"]
r = r.sort_values("min_cost_pct")
fig, ax = plt.subplots(figsize=(8.4, 8.6))
y = range(len(r))
ax.axvspan(rail_cost["low"], rail_cost["high"], color=AQUA, alpha=0.12, lw=0)
ax.axvline(rail_cost["base"], color=AQUA, lw=2)
ax.hlines(list(y), r.min_cost_pct, r.median_cost_pct, color="#c3c2b7", lw=2)
ax.scatter(r.median_cost_pct, list(y), s=34, color="#86b6ef", zorder=3, label="Typical offer (median)")
ax.scatter(r.min_cost_pct, list(y), s=40, color=BLUE, zorder=4, label="Cheapest offer")
ax.set_yticks(list(y)); ax.set_yticklabels(r.label, fontsize=8.5)
for yy, lo, lab in zip(y, r.min_cost_pct, r.label):
    if lo > rail_cost["base"]:
        ax.text(r.loc[r.label == lab, "median_cost_pct"].iloc[0] + 0.25, yy, "rail beats every offer", fontsize=7, color="#0f7a55", va="center")
ax.text(rail_cost["base"] + 0.1, len(r) - 0.3, f"Stablecoin rail ≈ {rail_cost['base']:.1f}% (base)", fontsize=8, color=INK2, va="bottom")
ax.axvline(0, color=BASE, lw=0.8)
ax.set_xlabel("All-in cost of sending $200 (%)")
ax.set_title(f"Against the cheapest provider, stablecoins win in only {m['corridors_beaten_vs_min_cost_pct']} of {m['corridors_tested']} corridors", loc="left", fontsize=11)
ax.legend(loc="lower right", frameon=False, fontsize=8)
ax.grid(axis="y", visible=False)
src(fig, f"World Bank Remittance Prices Worldwide, Q3 2025 (latest published), {m['offers_tested']} priced offers. \nRail cost = on-ramp + off-ramp + $0.55 fixed (assumptions; shaded band = low–high case). Not shown: Tanzania→Kenya, South Africa→Malawi (median 84% and 33%).")
fig.tight_layout(rect=(0, 0.045, 1, 1)); fig.savefig(C / "2_corridor_breakeven.png", dpi=170); plt.close(fig)

# 3. Pakistan: PVARA's $400m depends entirely on the benchmark
bench = pd.DataFrame({
    "label": ["vs. the AVERAGE offer\n(what the $400m implicitly assumes)", "vs. the TYPICAL offer\n(median)", "vs. the CHEAPEST offer\nalready on the market"],
    "val": [m["pk_saving_base_vs_avg_m"], m["pk_saving_base_vs_median_m"], m["pk_saving_base_vs_min_m"]],
})
fig, ax = plt.subplots(figsize=(9, 3.8))
ax.barh(bench.label[::-1], bench.val[::-1], color=[BLUE, "#86b6ef", "#cde2fb"][::-1], height=0.55)
for yy, v in enumerate(bench.val[::-1]):
    ax.text(v + 6, yy, f"${v:,.0f}m / yr", va="center", fontsize=9, color=INK2)
ax.axvline(400, color=MUTED, lw=1, ls="--"); ax.text(404, 2.35, "PVARA claim: $400m", fontsize=8, color=INK2)
ax.set_xlim(0, 520)
ax.set_xlabel("Annual saving, Saudi + UAE + UK → Pakistan flows ($m)")
ax.set_title("Pakistan's $400m stablecoin saving vanishes against the cheapest provider", loc="left", fontsize=11)
ax.grid(axis="y", visible=False)
src(fig, "Flows: SBP FY26 (Saudi $9.78bn, UAE $8.81bn, UK $6.33bn). Costs: World Bank RPW Q3 2025. Upper bounds: 100% switching, $200-ticket pricing.")
fig.tight_layout(rect=(0, 0.04, 1, 1)); fig.savefig(C / "3_pakistan_savings.png", dpi=170); plt.close(fig)

# 4. Concentration
top = iss[~iss.symbol.isin(["TOTAL"])].copy()
top["share"] = top.supply_usd_m_oct2026 / tot * 100
fig, ax = plt.subplots(figsize=(8, 3.8))
lab = top.symbol.where(top.symbol != "ALL_OTHERS", "407 others")
ax.barh(lab[::-1], top.share[::-1], color=[BLUE if s in ("USDT", "USDC") else "#86b6ef" for s in top.symbol[::-1]], height=0.6)
for y, v in enumerate(top.share[::-1]):
    ax.text(v + 0.5, y, f"{v:.1f}%", va="center", fontsize=8, color=INK2)
ax.set_xlabel("Share of $309bn stablecoin supply (%)")
ax.set_title(f"Two issuers hold {m['usdt_share_pct'] + m['usdc_share_pct']:.0f}% of all stablecoins", loc="left", fontsize=11)
ax.grid(axis="y", visible=False)
src(fig, "Source: DefiLlama stablecoin API, Oct 2026.")
fig.tight_layout(rect=(0, 0.04, 1, 1)); fig.savefig(C / "4_issuer_concentration.png", dpi=170); plt.close(fig)

for k, v in m.items():
    print(f"{k:48s} {v:,.2f}")
