#!/usr/bin/env python3
# coding: utf-8
"""
UTXO Bytes-CDF Facet Plot
Reads pre-computed category_id from JSON files and generates a cumulative distribution plot
for P2SH-P2WSH script types, grouped by smart contract categories.
"""

import os
import re
import json
import math
import multiprocessing as mp
from collections import defaultdict

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# ───────── Configuration ─────────────────────────────────────────────
ADDR = "P2SH-P2WSH"  # Target address type
INPUT_PATH = "P2SH-P2WSH_utxos.json"
OUTPUT_PATH = INPUT_PATH.replace(".json", "_cdf_plot.png")
CHUNK_SIZE = 20
DUST_TH = 546  # Dust threshold (in satoshis)
MIN_CNT = 1    # Minimum count to include in plot

# Y-axis configuration
Y_AXIS_MIN = 0
Y_AXIS_MAX = 250
Y_TICK_STEP = 100

# Font sizes
SUPTITLE_FONT_SIZE = 40
SUBPLOT_TITLE_FONT_SIZE = 18
AXIS_LABEL_FONT_SIZE = 14
TICK_LABEL_FONT_SIZE = 14
LEGEND_FONT_SIZE = 14
ANNOTATION_FONT_SIZE = 14

# Category labels
CATEGORY_NAME = {
    1: "Multi-Sig",
    2: "Timelock-CLTV",
    3: "Timelock-CSV",
    4: "Hashlock / HTLC",
    5: "Conditional (IF/ELSE)",
    6: "Custom",
    7: "Unknown",
    8: "Single-Sig",
}
EXCLUDE_CATS = {7}  # Exclude unknown category

# Signature regex for scriptSig fallback
_sig_re = re.compile(r"[0-9A-Fa-f]+\[ALL\]", re.I)

# ───────── JSON Parsing ──────────────────────────────────────────────
def parse_inputs(tx):
    if tx.get("scriptType") != ADDR:
        return
    byt = int(tx.get("bytes", 0))
    sat = int(float(tx.get("amount", 0)) * 1e8)
    cat = int(tx.get("category_id", 7))

    witness = tx.get("txinwitness") or []
    if isinstance(witness, list) and len(witness) > 0:
        n_sig = max(0, len(witness) - 1)
    else:
        asm = tx.get("scriptSig", {}).get("asm", "")
        n_sig = len(_sig_re.findall(asm))

    return byt, sat, cat, n_sig

# ───────── File Chunk Processing ─────────────────────────────────────
def process_chunk(files):
    out = defaultdict(list)
    for fp in files:
        try:
            with open(fp, "r", encoding="utf-8") as f:
                js = json.load(f)
        except Exception:
            continue
        js = js if isinstance(js, list) else [js]
        for tx in js:
            parsed = parse_inputs(tx)
            if parsed:
                byt, sat, cat, n_sig = parsed
                out[cat].append((byt, sat, n_sig))
    return out

def merge(dst, src):
    for k, v in src.items():
        dst[k].extend(v)

# ───────── ECDF Utility ──────────────────────────────────────────────
def ecdf(vals):
    y = np.sort(vals)
    x = np.arange(1, len(y) + 1) / len(y) * 100
    return np.insert(x, 0, 0.0), np.insert(y, 0, y[0] if len(y) > 0 else 0)

# ───────── Plotting ──────────────────────────────────────────────────
def plot_and_stats(cat_map):
    print("[STATS] Category summary:")
    for cat in sorted(cat_map):
        data = cat_map[cat]
        total = len(data)
        dust = sum(1 for b, s, _ in data if s <= DUST_TH)
        norm = total - dust
        print(f" - {CATEGORY_NAME.get(cat, cat)}: total={total}, normal={norm}, dust={dust}")

    cats = [c for c in cat_map if c not in EXCLUDE_CATS]
    if not cats:
        print("No data to plot.")
        return

    all_bytes = [b for c in cats for b, _, _ in cat_map[c]]
    auto_max = math.ceil(max(all_bytes, default=0) / 50) * 50
    y_min = Y_AXIS_MIN
    y_max = Y_AXIS_MAX if Y_AXIS_MAX is not None else auto_max

    cols = 3 if len(cats) > 2 else len(cats)
    rows = math.ceil(len(cats) / cols)

    fig, axes = plt.subplots(rows, cols, figsize=(5.5 * cols, 4.3 * rows), sharey=True)
    axes = np.atleast_1d(axes).flatten()

    for idx, cat in enumerate(cats):
        ax = axes[idx]
        data = cat_map[cat]
        ax.set_axisbelow(True)

        dust_vals = [b for b, s, _ in data if s <= DUST_TH]
        norm_vals = [b for b, s, _ in data if s > DUST_TH]

        if len(norm_vals) >= MIN_CNT:
            x_n, y_n = ecdf(norm_vals)
            ax.plot(x_n, y_n, lw=2, drawstyle="steps-post",
                    label="Unlocked Non-Dust UTXO", zorder=2, alpha=0.7)
        if len(dust_vals) >= MIN_CNT:
            x_d, y_d = ecdf(dust_vals)
            ax.plot(x_d, y_d, lw=2, color="red", drawstyle="steps-post",
                    label="Unlocked Dust UTXO", zorder=2, alpha=0.7)

        ax.axhline(y=32, color="green", linestyle="-.", linewidth=2,
                   label="Locked UTXO (32 bytes)", zorder=3)

        # Median line for each signature count (Multi-Sig only)
        if cat == 1:
            from collections import defaultdict as dd
            sigs_map = dd(list)
            for b, _, n in data:
                if n >= 2:
                    sigs_map[n].append(b)
            for n, blist in sorted(sigs_map.items()):
                if blist:
                    y_med = np.median(blist)
                    ax.axhline(y=y_med, color="black", linestyle="--",
                               linewidth=2, alpha=0.5,
                               label=f"{n} sigs median", zorder=4)
                    ax.text(50, y_med, f"{n} sigs", va="center", ha="left",
                            fontsize=ANNOTATION_FONT_SIZE,
                            bbox=dict(facecolor="white", alpha=0.6, edgecolor="none"),
                            zorder=5)

        total = len(data)
        dust_count = len(dust_vals) if len(dust_vals) >= MIN_CNT else 0
        norm_count = len(norm_vals) if len(norm_vals) >= MIN_CNT else 0
        ax.set_title(f"{CATEGORY_NAME[cat]}\n(Dust={dust_count}, Non-Dust={norm_count})",
                     fontsize=SUBPLOT_TITLE_FONT_SIZE)

        ax.set_ylim(y_min, y_max)
        if Y_TICK_STEP:
            ax.set_yticks(np.arange(y_min, y_max + 1, Y_TICK_STEP))
        ax.set_xlim(0, 100)
        ax.grid(alpha=0.3, ls="--", zorder=1)
        ax.set_xlabel("UTXOs % (Ascending)", fontsize=AXIS_LABEL_FONT_SIZE)
        if idx % cols == 0:
            ax.set_ylabel("bytes", fontsize=AXIS_LABEL_FONT_SIZE)
        ax.tick_params(axis="both", labelsize=TICK_LABEL_FONT_SIZE)

    # Turn off unused subplots
    for ax in axes[len(cats):]:
        ax.axis("off")

    # Global legend at bottom
    handles, labels = [], []
    for ax in axes[:len(cats)]:
        h, l = ax.get_legend_handles_labels()
        for hi, li in zip(h, l):
            if li not in labels:
                handles.append(hi)
                labels.append(li)
    fig.legend(handles, labels, loc="lower center", ncol=len(labels),
               frameon=False, fontsize=LEGEND_FONT_SIZE,
               bbox_to_anchor=(0.5, 0.00), bbox_transform=fig.transFigure)

    fig.suptitle(f"UTXO Byte Cumulative Distribution – {ADDR}",
                 y=0.95, fontsize=SUPTITLE_FONT_SIZE)
    fig.tight_layout(rect=[0, 0.05, 1, 0.95])
    fig.savefig(OUTPUT_PATH)
    plt.close(fig)
    print(f"Saved: {OUTPUT_PATH}")

# ───────── Entry Point ───────────────────────────────────────────────
def main():
    if os.path.isfile(INPUT_PATH) and INPUT_PATH.lower().endswith(".json"):
        files = [INPUT_PATH]
    else:
        files = [os.path.join(r, f)
                 for r, _, fs in os.walk(INPUT_PATH)
                 for f in fs if f.lower().endswith(".json")]

    if not files:
        print(f"No JSON under {INPUT_PATH}")
        return

    chunks = [files[i:i + CHUNK_SIZE] for i in range(0, len(files), CHUNK_SIZE)]
    cat_map = defaultdict(list)

    with mp.get_context("spawn").Pool(min(len(chunks), mp.cpu_count())) as pool:
        for part in pool.map(process_chunk, chunks):
            merge(cat_map, part)

    plot_and_stats(cat_map)

if __name__ == "__main__":
    mp.freeze_support()
    main()
