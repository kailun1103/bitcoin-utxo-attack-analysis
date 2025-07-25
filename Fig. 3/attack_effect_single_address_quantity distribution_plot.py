#!/usr/bin/env python3
# coding: utf-8
"""
Dust UTXO Attack Effects – Single-Sig Address Distribution (Facet-Scatter)
• Logarithmic Y-axis (1 to 1,000,000); bottom label displays '0' instead of 10⁰.
• Each subplot includes: black ROI trend line and purple ROI ≥100% threshold line.
• Each facet displays only one address type (with dot density and label).
• Bottom area shows global legend: ROI line, ROI≥100% threshold, and reference line.
"""
import os, orjson, numpy as np
from collections import defaultdict
from multiprocessing import Pool, cpu_count
from tqdm import tqdm
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from matplotlib.lines import Line2D

# Configurable Parameters
FOLDER = "2024_utxo"
SCRIPT_TYPES = ["P2TR_key_path", "P2WPKH", "P2PKH", "P2SH-P2WPKH"]

FACET_LAYOUT = (4, 1)  # rows, cols
FIG_WIDTH, FIG_HEIGHT = 12, 10
POINT_SIZE = 10

Z_RANGE = (1, 1_000_000)
LOG_TICKS = [10**i for i in range(0, 7)]
PLANE_Z = 100
X_TICK_M = 1
X_MARGIN_RATIO = 0.05

TITLE_FONTSIZE, LABEL_FONTSIZE = 24, 14
TICK_FONTSIZE, LEGEND_FONTSIZE = 12, 12

COLOR_MAP = {
    "P2PKH": "#0012D7",
    "P2SH-P2WPKH": "#E62DC7",
    "P2WPKH": "#01936B",
    "P2TR_key_path": "#FF8400",
}
LEGEND_MAP = {
    "P2TR_key_path": "P2TR (Key Path)",
    "P2WPKH": "P2WPKH",
    "P2SH-P2WPKH": "P2SH-P2WPKH",
    "P2PKH": "P2PKH",
}

def scan_file(path):
    pairs, dots = [], []
    try:
        data = orjson.loads(open(path, "rb").read())
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
        except (ValueError, TypeError):
            continue
        pairs.append((ae, key))

        utd = tx.get("Txn Input UTXO Details", [])
        if isinstance(utd, str):
            try:
                utd = orjson.loads(utd.encode())
            except Exception:
                continue
        for inp in utd:
            st = inp.get("scriptType")
            vr = inp.get("victim_attack_ratio", "").replace("%", "")
            if st in SCRIPT_TYPES and vr:
                try:
                    dots.append((key, float(vr), st))
                except (ValueError, TypeError):
                    pass
    return pairs, dots

def main():
    files = [os.path.join(r, f)
             for r, _, fs in os.walk(FOLDER)
             for f in fs if f.lower().endswith(".json")]
    if not files:
        print("No JSON data found.")
        return

    pairs, dots = [], []
    with Pool(cpu_count() or 4) as p:
        for ap, dp in tqdm(p.imap_unordered(scan_file, files),
                           total=len(files), desc="Scanning JSON", unit="file"):
            pairs.extend(ap)
            dots.extend(dp)

    if not pairs or not dots:
        print("Insufficient data for plotting.")
        return

    pairs.sort(key=lambda x: x[0])
    ae_idx = {k: i + 1 for i, (_, k) in enumerate(pairs)}
    total = len(pairs)

    ae_curve = [max(ae, 1) for ae, _ in pairs]
    idx_100 = next((i for i, v in enumerate(ae_curve) if v >= 100), None)
    x_thresh = idx_100 + 1 if idx_100 is not None else None

    counts = defaultdict(int)
    for _, _, st in dots:
        counts[st] += 1

    rows, cols = FACET_LAYOUT
    fig, axes = plt.subplots(rows, cols, sharex=True, sharey=True,
                             figsize=(FIG_WIDTH, FIG_HEIGHT))
    axes = axes.flatten()

    for i, st in enumerate(SCRIPT_TYPES):
        ax = axes[i]
        ax.plot(range(1, total + 1), ae_curve,
                color='black', linewidth=3,
                label='_nolegend_', zorder=2)

        if x_thresh:
            ax.axvline(x_thresh, color='purple', linestyle='--',
                       linewidth=3, alpha=0.9, zorder=2)

        pts = [(ae_idx[k], vr) for k, vr, t in dots if t == st and k in ae_idx]
        if pts:
            xs, ys = map(np.array, zip(*pts))
            ax.scatter(xs, ys, s=POINT_SIZE,
                       color=COLOR_MAP[st], alpha=0.1,
                       label='_nolegend_', zorder=1)
            proxy = Line2D([], [], marker='o',
                           color=COLOR_MAP[st], markersize=np.sqrt(POINT_SIZE),
                           linestyle='None', alpha=1,
                           label=f"{LEGEND_MAP[st]} (n={counts[st]})")
            ax.legend(handles=[proxy],
                      loc='upper left',
                      fontsize=LEGEND_FONTSIZE,
                      framealpha=0.5)

        ax.axhline(PLANE_Z, color='red', linestyle='-.',
                   linewidth=3, alpha=0.9, zorder=1)

        ax.set_yscale('log', base=10)
        ax.set_ylim(Z_RANGE)
        ax.set_yticks(LOG_TICKS)
        ytick_labels = ['0'] + [f'$10^{{{i}}}$' for i in range(1, 7)]
        ax.set_yticklabels(ytick_labels, fontsize=TICK_FONTSIZE)

        ax.grid(which='major', axis='both',
                linestyle='--', linewidth=0.7,
                color='#A0A0A0', alpha=0.6, zorder=0)

        ax.xaxis.set_minor_locator(ticker.NullLocator())
        ax.yaxis.set_minor_locator(ticker.NullLocator())

    for j in range(len(SCRIPT_TYPES), len(axes)):
        axes[j].set_visible(False)

    for idx, ax in enumerate(axes):
        ax.set_xlim(1 - X_MARGIN_RATIO * total,
                    total + X_MARGIN_RATIO * total)
        ax.tick_params(axis='x',
                       labelbottom=(idx == len(axes) - 1),
                       labelsize=TICK_FONTSIZE)
        ax.xaxis.set_major_locator(
            ticker.MultipleLocator(X_TICK_M * 1_000_000))
        ax.xaxis.set_major_formatter(
            ticker.FuncFormatter(lambda x, _: f'{int(x / 1_000_000)}M'))

    fig.suptitle('Dust UTXO Attack Effects - Single-sig Address Attack Distribution',
                 y=0.95, fontsize=18)
    fig.text(0.5, 0.0765,
             'Transactions (By Attack Effect ROI, Ascending)',
             ha='center', fontsize=LABEL_FONTSIZE)
    fig.text(0.04, 0.5, 'Attack Effect ROI (%)',
             va='center', rotation='vertical',
             fontsize=LABEL_FONTSIZE)

    plt.subplots_adjust(hspace=0.15, wspace=0.05,
                        top=0.90, bottom=0.15,
                        left=0.10, right=0.98)

    count_100 = sum(v >= 100 for v in ae_curve)
    percent_100 = count_100 / len(ae_curve) * 100
    legend_handles = [
        Line2D([], [], color='black', linewidth=3, linestyle='-',
               label='Attack Effect ROI Curve'),
        Line2D([], [], color='purple', linewidth=3, linestyle='--',
               label=f'{count_100} Txns ({percent_100:.2f}%) ≥ ROI (100%)'),
        Line2D([], [], color='red', linewidth=3, linestyle='-.',
               label='Attack Effect ROI = 100%'),
    ]
    fig.legend(handles=legend_handles,
               loc='lower center', ncol=3,
               fontsize=LEGEND_FONTSIZE,
               framealpha=0.5,
               bbox_to_anchor=(0.5, 0.025),
               handletextpad=1.5)

    out = 'attack_effect_single_address_quantity distribution_plot.png'
    plt.savefig(out, dpi=600)
    print(f"➡ Image saved: {out}")

if __name__ == '__main__':
    main()
