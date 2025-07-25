import os
import json
import numpy as np
import matplotlib.pyplot as plt
import statistics
from concurrent.futures import ProcessPoolExecutor
import matplotlib.ticker as ticker
from matplotlib.collections import LineCollection

def read_attack_effects(file_path):
    """Read attack_effect values from JSON files where dust_attacker == '1'"""
    effects = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            print(f"Processing file: {file_path}")
            data = json.load(f)
            if not isinstance(data, list):
                data = [data]
            for tx in data:
                if tx.get("dust_attacker") != "1":
                    continue
                if "attack_effect" in tx:
                    try:
                        effects.append(float(tx["attack_effect"]))
                    except Exception as e:
                        print(f"Failed to convert attack_effect: {e}")
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
    return effects

def map_to_visual_space(y, tick_positions, visual_positions):
    """Map y values to visual positions"""
    return np.interp(y, tick_positions, visual_positions)

def main():
    folder_path = "2024_utxo"
    all_json_files = [
        os.path.join(root, file)
        for root, _, files in os.walk(folder_path)
        for file in files if file.lower().endswith(".json")
    ]

    with ProcessPoolExecutor() as executor:
        all_attack_effects = [v for sub in executor.map(read_attack_effects, all_json_files) for v in sub]

    if not all_attack_effects:
        print("No attack_effect values found with dust_attacker == '1'")
        return

    y = sorted(max(float(v), 0) for v in all_attack_effects)
    x = np.arange(1, len(y) + 1)

    tick_positions = [0, 10, 100, 1000, 10000, 100000, 1000000, 10000000]
    visual_positions = list(range(len(tick_positions)))
    tick_labels = [r'$0$', r'$10^1$', r'$10^2$', r'$10^3$', r'$10^4$', r'$10^5$', r'$10^6$', '']

    visual_y = map_to_visual_space(y, tick_positions, visual_positions)

    plt.figure(figsize=(10, 6))
    ax = plt.gca()

    line, = ax.plot(
        x, visual_y,
        color='black', 
        linewidth=5,
        label='_nolegend_',
    )

    # ROI ≥ 100%
    idx_100 = next((i for i, v in enumerate(y) if v >= 100), None)
    count_100 = sum(v >= 100 for v in y)
    percent_100 = count_100 / len(y) * 100

    handles = []
    if idx_100 is not None:
        x_threshold = idx_100 + 1
        vline = plt.axvline(
            x=x_threshold, color='purple', linestyle='--',
            linewidth=3, alpha=0.9,
            label=f'{count_100} Txns ({percent_100:.2f}%) ≥ ROI (100%)',
            zorder=3
        )
        handles.append(vline)

        hline = plt.axhline(
            y=np.interp(100, tick_positions, visual_positions),
            color='red', linestyle='-.',
            linewidth=3, alpha=1,
            label='Attack Effect ROI = 100%', zorder=3
        )
        handles.append(hline)

    legend_proxy = plt.Line2D([], [], color='black', linewidth=3,
                              label='Attack Effect ROI Curve')
    handles.append(legend_proxy)

    plt.legend(handles=handles, loc='upper left', bbox_to_anchor=(0.25, 0.99), fontsize=14)

    ax.margins(x=0.05)
    ax.set_ylim(0, visual_positions[-1])
    ax.set_yticks(visual_positions)
    ax.set_yticklabels(tick_labels, fontsize=16)

    ax.xaxis.set_major_locator(ticker.MultipleLocator(1_000_000))
    ax.xaxis.set_major_formatter(ticker.FuncFormatter(lambda v, _: f'{int(v/1_000_000)}M'))
    ax.tick_params(axis='both', which='major', labelsize=16)

    plt.xlabel('Transactions (By Attack Effect ROI, Ascending)', fontsize=18)
    plt.ylabel('Attack Effect ROI (%)', fontsize=18)
    plt.title('Dust UTXO Attack Effect Distribution', fontsize=20, pad=15)

    # Statistics
    positive_y = [v for v in y if v > 0]
    stats = (
        f"Min: {min(positive_y):.2f}%\n"
        f"Max: {max(y):.2f}%\n"
        f"Mean: {statistics.mean(y):.2f}%\n"
        f"Median: {statistics.median(y):.2f}%"
    )
    plt.text(
        0.02, 0.95, stats, transform=ax.transAxes,
        fontsize=14, verticalalignment='top',
        bbox=dict(facecolor='white', alpha=0.6)
    )

    ax.grid(True, which='major', linestyle='--', alpha=0.9, zorder=0)
    plt.tight_layout()
    plt.savefig('attack_effect_roi_plot.png', dpi=600)
    print("Saved: attack_effect_roi_plot.png")

if __name__ == "__main__":
    main()
