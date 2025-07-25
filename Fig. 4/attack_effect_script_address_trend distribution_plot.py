#!/usr/bin/env python3
# coding: utf-8
"""
Dust UTXO Attack Effects – Script Address Attack Trend Line Plot
• Main plot uses a logarithmic Y-axis (10⁰–10⁷), with a red dashed line at ROI = 100%.
• Inset highlights the last 0.5% segment with a linear Y-axis and percentage labels.
• X-axis ticks every 1M transactions, labeled with 'M'.
• Axis tick labels use 18 pt font.
• Hides the tick label for 10⁷.
"""
import math
import os
import orjson
import numpy as np
from multiprocessing import Pool, cpu_count
from tqdm import tqdm
import matplotlib.pyplot as plt
from mpl_toolkits.axes_grid1.inset_locator import inset_axes
from matplotlib.patches import Rectangle, ConnectionPatch
import matplotlib.ticker as mticker

# Configurable parameters
FOLDER = "2024_utxo"
SCRIPT_TYPES = ["P2WSH", "P2TR_script_path", "P2SH", "P2SH-P2WSH"]
FIG_WIDTH, FIG_HEIGHT = 10, 8
EMA_SPLIT_FRAC = 0.00001
SMOOTH_ALPHA_MAIN = 1e-6
SMOOTH_ALPHA_LAST = 0.1
MAX_PTS_MAIN = 2000
MAX_PTS_INSET = 500

COLOR_MAP = {
    "P2WSH": "#1f77b4",
    "P2TR_script_path": "#2ca02c",
    "P2SH": "#d62728",
    "P2SH-P2WSH": "#9467bd",
}
LEGEND_MAP = {
    "P2WSH": "P2WSH",
    "P2TR_script_path": "P2TR (Script Path)",
    "P2SH": "P2SH",
    "P2SH-P2WSH": "P2SH-P2WSH",
}

def scan_file(path: str):
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
        except Exception:
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
                except Exception:
                    pass
    return pairs, dots

def fill_nan(a: np.ndarray):
    mask = np.isnan(a)
    if mask.all():
        return a
    x = np.arange(a.size)
    a[mask] = np.interp(x[mask], x[~mask], a[~mask])
    return a

def ema_segmented(y, a_main, a_last, split):
    ema = np.empty_like(y)
    ema[0] = y[0]
    for i in range(1, len(y)):
        a = a_main if i < split else a_last
        ema[i] = a * y[i] + (1 - a) * ema[i - 1]
    return ema

def downsample(x, y, limit):
    if len(x) <= limit:
        return x, y
    idx = np.linspace(0, len(x) - 1, limit, dtype=int)
    return x[idx], y[idx]

def main():
    files = [
        os.path.join(r, f)
        for r, _, fs in os.walk(FOLDER)
        for f in fs if f.lower().endswith(".json")
    ]
    if not files:
        print("No JSON data found.")
        return

    pairs, dots = [], []
    with Pool(cpu_count() or 4) as pool:
        for p, d in tqdm(pool.imap_unordered(scan_file, files), total=len(files), desc="Scanning JSON"):
            pairs.extend(p)
            dots.extend(d)
    if not pairs or not dots:
        print("Insufficient data for plotting.")
        return

    pairs.sort(key=lambda t: t[0])
    total = len(pairs)
    ae_idx = {k: i for i, (_, k) in enumerate(pairs)}
    x_all = np.arange(1, total + 1)
    split_idx = int(total * (1 - EMA_SPLIT_FRAC))

    y_vals = {st: np.full(total, np.nan) for st in SCRIPT_TYPES}
    for key, vr, st in dots:
        idx = ae_idx.get(key)
        if idx is not None:
            y_vals[st][idx] = vr
    y_smooth = {
        st: ema_segmented(fill_nan(y_vals[st]), SMOOTH_ALPHA_MAIN, SMOOTH_ALPHA_LAST, split_idx)
        for st in SCRIPT_TYPES
    }

    fig, ax = plt.subplots(figsize=(FIG_WIDTH, FIG_HEIGHT))

    for st in SCRIPT_TYPES:
        xs, ys = downsample(x_all, y_smooth[st], MAX_PTS_MAIN)
        ax.plot(xs, ys, color=COLOR_MAP[st], lw=1.5, label=LEGEND_MAP[st])

    ae_val = [max(a, 1) for a, _ in pairs]
    idx100 = next((i for i, v in enumerate(ae_val) if v >= 100), None)
    if idx100 is not None:
        cnt = sum(v >= 100 for v in ae_val)
        pct = cnt / total * 100
        ax.axvline(
            idx100 + 1,
            color="purple",
            ls="--",
            lw=3,
            alpha=0.8,
            label=f'{cnt} Txns ({pct:.2f}%) ≥ ROI (100%)',
        )

    ax.axhline(100, color="red", ls="-.", lw=3, alpha=0.9, label="Attack Effect ROI = 100%")

    seg = np.concatenate([y_smooth[st][split_idx:] for st in SCRIPT_TYPES])
    y_min, y_max = np.nanmin(seg), np.nanmax(seg)
    ax.add_patch(Rectangle((split_idx, y_min), total - split_idx, y_max - y_min, ec="gray", ls="--", fc="none"))

    axins = inset_axes(ax, width="30%", height="30%", bbox_to_anchor=(0.56, 0.62, 1, 1), bbox_transform=ax.transAxes, loc="lower left")
    for st in SCRIPT_TYPES:
        xs_i, ys_i = downsample(x_all[split_idx:], y_smooth[st][split_idx:], MAX_PTS_INSET)
        axins.plot(xs_i, ys_i, color=COLOR_MAP[st], lw=1)
    axins.set_xlim(split_idx, total)
    axins.set_ylim(y_min, y_max)
    axins.yaxis.set_major_locator(mticker.MaxNLocator(4))
    axins.yaxis.set_major_formatter(mticker.FuncFormatter(lambda y, _: f"{int(y)}%"))
    axins.tick_params(axis="both", labelsize=12)
    axins.set_xticks([])

    ax.add_artist(ConnectionPatch(xyA=(split_idx, y_max), xyB=(0, 1), coordsA=ax.transData, coordsB=axins.transAxes, color="gray"))
    ax.add_artist(ConnectionPatch(xyA=(total, y_min), xyB=(1, 0), coordsA=ax.transData, coordsB=axins.transAxes, color="gray"))

    ax.set_yscale("log", base=10)
    ax.set_ylim(1, 10 ** 7)
    yticks = [10 ** i for i in range(0, 8)]
    ax.set_yticks(yticks)

    def y_fmt(y, _):
        if y == 1:
            return "0"
        exp = int(np.log10(y))
        return "" if exp == 7 else f"$10^{{{exp}}}$"
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(y_fmt))
    ax.yaxis.set_minor_locator(mticker.NullLocator())

    xtick_max = math.ceil(total / 1_000_000) * 1_000_000
    ax.set_xticks(np.arange(0, xtick_max + 1, 1_000_000))
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{int(v/1_000_000)}M"))
    pad = 0.05 * xtick_max
    ax.set_xlim(-pad, xtick_max + pad)

    ax.tick_params(axis="both", labelsize=18)
    ax.set_xlabel("Transactions (By Attack Effect ROI, Ascending)", fontsize=18)
    ax.set_ylabel("Attack Effect ROI (%)", fontsize=18)
    ax.set_title('Dust UTXO Attack Effects - Script Address Attack Trend', fontsize=20, pad=15)
    ax.grid(which="major", ls="--", lw=0.7, alpha=0.6)
    ax.legend(fontsize=12, framealpha=0.5, loc="upper left")

    plt.tight_layout()
    outfile = "attack_effect_script_address_quantity distribution_plot.png"
    plt.savefig(outfile, dpi=600)
    print(f"➡ Image saved: {outfile} ({total} transactions)")

if __name__ == "__main__":
    main()
