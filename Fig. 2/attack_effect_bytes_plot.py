import os
import time
import json
import numpy as np
import statistics
import matplotlib.pyplot as plt
from concurrent.futures import ProcessPoolExecutor
from matplotlib.ticker import MultipleLocator, FuncFormatter
from tqdm import tqdm

# Optional: use orjson if available for faster parsing
try:
    import orjson
    def load_json(fp):
        return orjson.loads(fp.read())
except ImportError:
    def load_json(fp):
        return json.load(fp)

# ───────── Plot Settings ─────────────────────────────────────────────
LABEL_FONTSIZE  = 18
TICK_FONTSIZE   = 16
LEGEND_FONTSIZE = 14
STATS_FONTSIZE  = 14
GRID_LINEWIDTH  = 1.5

# Y-axis configuration
Y_MIN   = 0
Y_MAX   = 600
Y_STEP  = 100

# ───────── JSON Parsing ──────────────────────────────────────────────
def read_txn_data(path):
    """Parse a JSON file and extract attack_effect, victim size, and attack size."""
    results = []
    try:
        with open(path, 'rb') as f:
            data = load_json(f)
    except:
        return results

    recs = data if isinstance(data, list) else [data]
    for tx in recs:
        if tx.get("dust_attacker") != "1":
            continue
        try:
            ae = float(tx["attack_effect"])
            input_details = json.loads(tx.get("Txn Input UTXO Details", "[]"))
            victim_size = sum(item.get("bytes", 0) for item in input_details)

            total_attack_bytes = 0
            for sub in tx.get("sent_utxo_uxns", []):
                det_str = sub.get("Txn Output UTXO Details", "")
                if not det_str:
                    continue
                det = json.loads(det_str)
                total_attack_bytes += det.get("bytes", 0)

            results.append((ae, victim_size, total_attack_bytes))
        except:
            continue
    return results

# ───────── Smoothing Function ────────────────────────────────────────
def smooth_data(data, group_size=100):
    return [np.mean(data[i:i+group_size]) for i in range(0, len(data), group_size)]

# ───────── Main Routine ──────────────────────────────────────────────
def main():
    folder = "2024_utxo"

    paths = [
        os.path.join(dp, fn)
        for dp, _, fns in os.walk(folder)
        for fn in fns if fn.lower().endswith('.json')
    ]
    if not paths:
        print("No JSON files found.")
        return

    all_data = []
    t0 = time.time()
    with ProcessPoolExecutor() as exe:
        for part in tqdm(exe.map(read_txn_data, paths),
                         total=len(paths), desc="Processing"):
            all_data.extend(part)
    print(f"\nTotal {len(all_data)} records loaded in {time.time() - t0:.1f}s")

    if not all_data:
        print("No qualifying records found.")
        return

    all_data.sort(key=lambda x: x[0])
    attack_effects = [d[0] for d in all_data]
    victim_sizes   = [d[1] for d in all_data]
    attack_sizes   = [d[2] for d in all_data]

    group = 19000
    sm_victim = smooth_data(victim_sizes, group)
    sm_attack = smooth_data(attack_sizes, group)

    x_victim = np.linspace(1, len(victim_sizes), len(sm_victim))
    x_attack = np.linspace(1, len(victim_sizes), len(sm_attack))

    idx100 = next((i for i, v in enumerate(attack_effects) if v >= 100), None)
    count_100   = sum(1 for v in attack_effects if v >= 100)
    percent_100 = count_100 / len(attack_effects) * 100

    plt.figure(figsize=(10, 6))
    plt.plot(x_victim, sm_victim, '-', lw=2, label='Victim bytes')
    if sm_attack:
        plt.plot(x_attack, sm_attack, '-', lw=2, label='Attack bytes')

    if idx100 is not None:
        x_th = idx100 + 1
        label_vs = f'{count_100} Txns ({percent_100:.2f}%) ≥ ROI (100%)'
        plt.axvline(x=x_th, color='purple', linestyle='--', linewidth=3,
                    alpha=0.9, label=label_vs, zorder=3)

    ax = plt.gca()
    ax.legend(loc='upper left', fontsize=LEGEND_FONTSIZE,
              bbox_to_anchor=(0.255, 0.987), bbox_transform=ax.transAxes)

    ax.set_ylim(Y_MIN, Y_MAX)
    ax.yaxis.set_major_locator(MultipleLocator(Y_STEP))
    ax.xaxis.set_major_locator(MultipleLocator(1_000_000))
    ax.xaxis.set_major_formatter(FuncFormatter(lambda x, _: f'{int(x/1_000_000)}M'))
    ax.tick_params(axis='both', labelsize=TICK_FONTSIZE)

    plt.xlabel('Transactions (By Attack Effect ROI, Ascending)', fontsize=LABEL_FONTSIZE)
    plt.ylabel('bytes', fontsize=LABEL_FONTSIZE)
    plt.title('Dust UTXO Attack Effect - Transaction Byte Distribution', fontsize=20, pad=15)

    nonzero_v = [v for v in victim_sizes if v > 0]
    min_v = min(nonzero_v) if nonzero_v else 0
    stats_v = {
        'Min':    min_v,
        'Max':    max(victim_sizes),
        'Mean':   statistics.mean(victim_sizes),
        'Median': statistics.median(victim_sizes),
    }
    text_v = (f"Victim Virtual bytes\n"
              f"Min:    {stats_v['Min']:.2f}\n"
              f"Max:    {stats_v['Max']:.2f}\n"
              f"Mean:   {stats_v['Mean']:.2f}\n"
              f"Median: {stats_v['Median']:.2f}")
    plt.text(0.025, 0.95, text_v, transform=ax.transAxes,
             fontsize=STATS_FONTSIZE, verticalalignment='top',
             bbox=dict(boxstyle='square,pad=0.5', facecolor='white', alpha=0.8))

    nonzero_a = [a for a in attack_sizes if a > 0]
    min_a = min(nonzero_a) if nonzero_a else 0
    stats_a = {
        'Min':    min_a,
        'Max':    max(attack_sizes) if attack_sizes else 0,
        'Mean':   statistics.mean(attack_sizes) if attack_sizes else 0,
        'Median': statistics.median(attack_sizes) if attack_sizes else 0,
    }
    text_a = (f"Attack Virtual bytes\n"
              f"Min:    {stats_a['Min']:.2f}\n"
              f"Max:    {stats_a['Max']:.2f}\n"
              f"Mean:   {stats_a['Mean']:.2f}\n"
              f"Median: {stats_a['Median']:.2f}")
    plt.text(0.025, 0.65, text_a, transform=ax.transAxes,
             fontsize=STATS_FONTSIZE, verticalalignment='top',
             bbox=dict(boxstyle='square,pad=0.5', facecolor='white', alpha=0.8))

    plt.grid(True, which='major', linestyle='--', alpha=0.9, linewidth=GRID_LINEWIDTH)
    plt.tight_layout()
    plt.savefig('attack_effect_bytes_plot.png', dpi=600)
    print("Saved: attack_effect_bytes_plot.png")

if __name__ == "__main__":
    main()