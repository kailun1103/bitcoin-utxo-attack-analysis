#!/usr/bin/env python3
# coding: utf-8
"""
Dust UTXO Attack Effects – Script-Based Address Distribution (Facet-Scatter View)
• Manual legend counts specified in MANUAL_COUNTS.
• Uniform legend styling and alignment across facets.
• Retains original plotting logic; non-essential font dependencies removed.
"""
import os
import json
import re
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
import numpy as np
from tqdm import tqdm
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from matplotlib.lines import Line2D

# ───────── Manual Legend Counts ────────────────────────────────────
MANUAL_COUNTS = {
    "P2WSH": {1: 39829, 3: 31075, 2: 6596, 8: 600},
    "P2TR_script_path": {10: 329369, 9: 108499},
    "P2SH": {1: 742, 2: 90, 3: 12, 8: 8, 4: 8, 5: 6},
    "P2SH-P2WSH": {1: 239, 2: 10, 3: 10, 4: 4}
}

# ───────── Configuration ─────────────────────────────────────────
FOLDER = "2024_utxo"
SCRIPT_TYPES = ["P2TR_script_path", "P2WSH", "P2SH", "P2SH-P2WSH"]
FACET_LAYOUT = (4, 1)
FIG_SIZE = (12, 10)
POINT_SIZE = 10

CATEGORY_ORDER_MAP = {
    "P2WSH": [1, 3, 2, 8],
    "P2TR_script_path": [10, 9],
    "P2SH": [1, 2, 3, 8, 4, 5],
    "P2SH-P2WSH": [1, 2, 3, 4],
}
EXCLUDE_CATS = {6, 7}

CATEGORY_NAME = {
    1: "Multi-Sig", 2: "Timelock-CLTV", 3: "Timelock-CSV", 4: "Hashlock/HTLC",
    5: "Conditional(IF/ELSE)", 6: "Custom", 7: "Unknown", 8: "Single-Sig",
    9: "BRC-20", 10: "Ordinals",
}
COLOR_LIST = [
    "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728",
    "#9467bd", "#8c564b", "#e377c2", "#17becf",
    "#bcbd22", "#7f7f7f"
]
CATEGORY_COLORS = {cat: COLOR_LIST[i] for i, cat in enumerate(sorted(CATEGORY_NAME))}

# Plot parameters
Z_RANGE = (1, 1_000_000)
LOG_TICKS = [10**i for i in range(7)]
PLANE_Z = 100
SCRIPT_ROI_COLOR = "black"
THRESH_COLOR = "purple"
PLANE_COLOR = "red"
X_TICK_M = 1
X_MARGIN_RATIO = 0.05

LABEL_FONTSIZE = 14
TICK_FONTSIZE = 12
LEGEND_FONTSIZE = 10
COMMON_LEGEND_KW = dict(
    loc="upper left",
    bbox_to_anchor=(0.012, 0.84, 0.4, 0.1),
    borderaxespad=0,
    handlelength=0.8,
    handletextpad=0.4,
    alignment="left",
    mode="expand",
    fontsize=LEGEND_FONTSIZE,
    frameon=True
)

# ───────── JSON Loader ─────────────────────────────────────────────
try:
    import orjson as _oj
    jloads = _oj.loads
except ImportError:
    jloads = json.loads

# ───────── File Processor ─────────────────────────────────────────
def process_file(path):
    """Scan a JSON file for dust_attacker transactions and extract ROI data."""
    pairs, dots = [], []
    try:
        data = jloads(open(path, "rb").read())
    except Exception:
        return pairs, dots
    if not isinstance(data, list):
        data = [data]

    for idx, tx in enumerate(data):
        if tx.get("dust_attacker") != "1":
            continue
        key = (path, idx)
        try:
            ae = float(tx.get("attack_effect", 0))
        except ValueError:
            continue
        pairs.append((ae, key))

        utd = tx.get("Txn Input UTXO Details", [])
        if isinstance(utd, str):
            try:
                utd = jloads(utd)
            except Exception:
                continue

        for inp in utd:
            st = inp.get("scriptType")
            vr_s = str(inp.get("victim_attack_ratio", "")).replace("%", "")
            if st not in SCRIPT_TYPES or not vr_s:
                continue
            try:
                vr = float(vr_s)
            except ValueError:
                continue

            cat_val = inp.get("category_id")
            if cat_val is None:
                continue
            try:
                cat = int(cat_val)
            except (ValueError, TypeError):
                continue
            if cat in EXCLUDE_CATS:
                continue

            dots.append((key, vr, st, cat))
    return pairs, dots

# ───────── Main Entry ─────────────────────────────────────────────
def main():
    files = [os.path.join(r, f)
             for r, _, fs in os.walk(FOLDER)
             for f in fs if f.lower().endswith(".json")]
    if not files:
        print("No JSON data found.")
        return

    pairs, dots = [], []
    with ProcessPoolExecutor(max_workers=os.cpu_count() or 4) as exe:
        for p, d in tqdm(exe.map(process_file, files, chunksize=10),
                         total=len(files), desc="Scanning JSON"):
            pairs.extend(p)
            dots.extend(d)

    if not pairs or not dots:
        print("Insufficient data for plotting.")
        return

    # Sort ROI curve globally
    pairs.sort(key=lambda x: x[0])
    ae_idx = {k: i+1 for i, (_, k) in enumerate(pairs)}
    total = len(pairs)
    ae_curve = [max(ae, 1) for ae, _ in pairs]
    idx_100 = next((i for i, v in enumerate(ae_curve) if v >= 100), None)
    x_thresh = idx_100 + 1 if idx_100 is not None else None

    fig, axes = plt.subplots(FACET_LAYOUT[0], FACET_LAYOUT[1],
                             sharex=True, sharey=True, figsize=FIG_SIZE)
    axes = axes.flatten()

    # Generate each facet
    for ax, st in zip(axes, SCRIPT_TYPES):
        ax.plot(range(1, total+1), ae_curve,
                color=SCRIPT_ROI_COLOR, linewidth=2, zorder=2)
        if x_thresh:
            ax.axvline(x_thresh, color=THRESH_COLOR,
                       linestyle='--', linewidth=2, zorder=2)

        handles = []
        for cat in CATEGORY_ORDER_MAP.get(st, []):
            pts = [(ae_idx[k], vr) for k, vr, s, c in dots
                   if s == st and c == cat and k in ae_idx]
            if not pts:
                continue
            xs, ys = map(np.array, zip(*pts))
            ax.scatter(xs, ys, s=POINT_SIZE,
                       color=CATEGORY_COLORS[cat], zorder=1)
            count = MANUAL_COUNTS.get(st, {}).get(cat, len(pts))
            handles.append(Line2D([], [], marker='o', linestyle='None',
                                  color=CATEGORY_COLORS[cat], markersize=6,
                                  label=f"{CATEGORY_NAME[cat]} ({count})"))

        # Facet legend
        total_count = sum(MANUAL_COUNTS.get(st, {}).values())
        title_label = f"{st} (n={total_count})"
        ncol = 1 if len(handles) <= 3 else 2
        ax.legend(handles=handles, title=title_label,
                  ncol=ncol, **COMMON_LEGEND_KW)

        # Reference line and log scale
        ax.axhline(PLANE_Z, color=PLANE_COLOR,
                   linestyle='-.', linewidth=2, zorder=1)
        ax.set_yscale('log', base=10)
        ax.set_ylim(Z_RANGE)
        ax.set_yticks(LOG_TICKS)
        ylabels = ['0'] + [f'$10^{{{i}}}$' for i in range(1, 7)]
        ax.set_yticklabels(ylabels, fontsize=TICK_FONTSIZE)
        ax.grid(True, which='major', linestyle='--',
                linewidth=0.7, alpha=0.6, zorder=0)

    # Hide unused facets
    for ax in axes[len(SCRIPT_TYPES):]:
        ax.set_visible(False)

    # X-axis formatting
    for idx, ax in enumerate(axes):
        ax.set_xlim(1 - X_MARGIN_RATIO*total, total + X_MARGIN_RATIO*total)
        ax.tick_params(axis='x', labelbottom=(idx == len(axes)-1),
                       labelsize=TICK_FONTSIZE)
        ax.xaxis.set_major_locator(ticker.MultipleLocator(X_TICK_M*1_000_000))
        ax.xaxis.set_major_formatter(
            ticker.FuncFormatter(lambda x, _: f'{int(x/1_000_000)}M'))

    # Global title and labels
    fig.suptitle(
        'Dust UTXO Attack Effects - Script Address Attack Distribution',
        fontsize=18, y=0.95)
    fig.text(0.5, 0.08,
             'Transactions (By Attack Effect ROI, Ascending)',
             ha='center', fontsize=LABEL_FONTSIZE)
    fig.text(0.08, 0.5,
             'Attack Effect ROI (%)', va='center',
             rotation='vertical', fontsize=LABEL_FONTSIZE)

    # Global legend
    c100 = sum(v >= 100 for v in ae_curve)
    pct100 = c100 / len(ae_curve) * 100
    global_handles = [
        Line2D([], [], color=SCRIPT_ROI_COLOR,
               linewidth=3, linestyle='-',
               label='Attack Effect ROI Curve'),
        Line2D([], [], color=THRESH_COLOR,
               linewidth=3, linestyle='--',
               label=f'{c100} Txns ({pct100:.2f}%) ≥ ROI (100%)'),
        Line2D([], [], color=PLANE_COLOR,
               linewidth=3, linestyle='-.',
               label='Reference Z = 100%')
    ]
    fig.legend(handles=global_handles,
               loc='lower center', ncol=3,
               fontsize=LEGEND_FONTSIZE,
               framealpha=0.5,
               bbox_to_anchor=(0.5, 0.03),
               handletextpad=1.5)

    plt.tight_layout(rect=[0, 0.03, 1, 0.90])
    out = 'attack_effect_script_address_quantity distribution_plot.png'
    plt.savefig(out, dpi=600)
    print(f"Image saved to {out}")

if __name__ == '__main__':
    main()
