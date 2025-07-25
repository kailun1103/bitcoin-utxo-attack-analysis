import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
import matplotlib.ticker as ticker
import matplotlib.colors as mcolors

# Font settings (KaiTi)
bk_font = FontProperties(fname="BKAI00MP.ttf", size=24)
# Bold font for x-tick labels
bold_font = FontProperties(fname="BKAI00MP.ttf", size=14, weight="bold")

# Y-axis parameters
y_min, y_max, y_step = 0, 1000, 100
# ROI horizontal line
roi_line = 100  # 100%

# Light color box palette
BOX_COLORS = plt.cm.Pastel1.colors[:5]
# Darken factor
dark_factor = 0.5

def darken(color, factor=dark_factor):
    """Darken an RGB color by a given factor"""
    r, g, b = mcolors.to_rgb(color)
    return (r * factor, g * factor, b * factor)


def main():
    # Read CSV
    df = pd.read_csv('p2tr.csv')

    # Columns and labels
    columns = [
        'P2TR_P2SH-P2WPKH_matches',
        'P2TR_P2TR_script_path_matches',
        'P2TR_P2WSH_matches',
        'P2TR_P2PKH_matches',
        'P2TR_P2SH_matches'
    ]
    labels = [
        'P2TR(K) to \nP2SH-P2WPKH',
        'P2TR(K) to \nP2TR(S)',
        'P2TR(K) to \nP2WSH',
        'P2TR(K) to \nP2PKH',
        'P2TR(K) to \nP2SH'
    ]

    # Prepare data: drop NaN and zeros
    data, removed, means = [], [], []
    for col in columns:
        series = df[col].dropna()
        orig = len(series)
        series = series[series != 0]
        removed.append(orig - len(series))
        data.append(series.values)
        means.append(series.mean())

    # Print removal stats
    print("Removed zeros/NaNs:")
    for lbl, cnt in zip(labels, removed):
        print(f"  {lbl}: {cnt}")

    # Plot setup
    fig, ax = plt.subplots(figsize=(10, 6))
    # Thinner bottom spine
    ax.spines['bottom'].set_linewidth(1)
    ax.tick_params(axis='y', which='major', labelsize=16)

    # Boxplot
    bp = ax.boxplot(data, labels=labels, patch_artist=True)
    # Style boxes
    for i, base in enumerate(BOX_COLORS):
        edge = darken(base)
        bp['boxes'][i].set(facecolor=base, edgecolor=edge, linewidth=2)
        bp['medians'][i].set(color=edge, linewidth=3)
        for w in bp['whiskers'][2*i:2*i+2]: w.set(color=edge, linewidth=1.5)
        for c in bp['caps'][2*i:2*i+2]: c.set(color=edge, linewidth=1.5)
        bp['fliers'][i].set(marker='o', markerfacecolor=base, markeredgecolor=edge, alpha=0.7)

    # Mean markers and line (x lower, line upper)
    x = range(1, len(data)+1)
    ax.scatter(x, means, marker='x', s=64, color='darkgreen', zorder=2)
    ax.plot(
        x, means,
        linestyle='-', linewidth=4,
        color='rebeccapurple',
        marker='o', markersize=8,
        markerfacecolor='white',
        markeredgewidth=2,
        markeredgecolor='rebeccapurple',
        zorder=5,
        label='Attack Effect ROI Mean'
    )



    # ROI line
    ax.axhline(roi_line, color='red', linestyle='--', linewidth=3, alpha=0.5, label='Attack Effect ROI = 100%')

    # Y-axis limits and ticks with %
    ax.set_ylim(y_min, y_max)
    ax.yaxis.set_major_locator(ticker.MultipleLocator(y_step))
    ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda v, p: f"{int(v)}%"))

    # X-axis bold tick labels
    ax.set_xticklabels(labels, fontsize=14, rotation=0)

    # Labels and title
    ax.set_ylabel('Attack Effect ROI (%)', fontsize=18)
    ax.set_title('Dust UTXO Attack Impact - P2TR(K) Redirect Attack', fontsize=24, pad=25)

    # Grid and legend
    ax.grid(True, linestyle='--', alpha=0.7)
    ax.legend(fontsize=12, loc='upper left')
    plt.tight_layout()

    # Save and show
    plt.savefig('p2tr_redirect_attack_impact_plot.png', dpi=600)
    plt.show()

if __name__ == '__main__':
    main()
