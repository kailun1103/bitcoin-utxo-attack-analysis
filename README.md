## Overview
This repository contains a suite of Python scripts for analyzing and visualizing attack effects on Bitcoin UTXO transactions, with a focus on dust attacks. It was developed to support IEEE peer review and reproducible research in blockchain security.

## Repository Structure
```bash
$ tree -L 1
bitcoin-utxo-attack-analysis/
├── annotate_fee_rate.py
├── compute_attack_metrics.py
├── annotate_utxo_script_bytes.py
├── script_address_classifier.py
├── plot_dust_attack_byte_distribution.py
├── plot_dust_attack_fee_rate_distribution.py
├── plot_dust_attack_roi_trend.py
├── plot_dust_attack_script_distribution.py
├── boxplot_p2tr_redirect_attack_impact.py
├── README.md
├── LICENSE
└── 2024_utxo/
```  

## Scripts Description
- **annotate_fee_rate.py**: Marks each transaction in JSON files as dust attacker based on fee rate outlier detection.
- **compute_attack_metrics.py**: Recalculates and overwrites victim and attack cost metrics (`victim_cost_btc`, `attack_cost_btc`, `total_*`, `attack_effect`) for each transaction.
- **annotate_utxo_script_bytes.py**: Identifies script types for inputs and outputs, computes byte sizes, and annotates JSON entries with `scriptType` and `bytes` fields.
- **script_address_classifier.py**: Classifies each UTXO input by script/address type (P2PKH, P2SH, P2WPKH, P2WSH, P2TR, P2SH-P2WPKH, P2SH-P2WSH, etc.) and annotates `scriptType`.
- **plot_dust_attack_byte_distribution.py**: Generates cumulative distribution facet plots of UTXO byte sizes by category.
- **plot_dust_attack_fee_rate_distribution.py**: Visualizes smoothed fee rate distributions (victim vs. attacker) with threshold markers.
- **plot_dust_attack_roi_trend.py**: Plots attack effect ROI trends on a log–linear scale with inset for last 0.5% segment.
- **plot_dust_attack_script_distribution.py**: Creates facet-scatter visualizations of attack ROI distribution across script types.
- **boxplot_p2tr_redirect_attack_impact.py**: Produces boxplots of redirect attack impact ROI for P2TR key-path transactions.

## Installation
Requires Python 3.8 or later. Install dependencies:
```bash
pip install numpy tqdm matplotlib orjson pandas
```

## Usage
Run scripts from the repository root. Example:
```bash
python annotate_fee_rate.py
python plot_dust_attack_roi_trend.py
```
Each script may require adjusting the `FOLDER` or input paths in its header.

## For IEEE Review
This codebase accompanies the manuscript “Dust UTXO Transaction Attacks Recognition and Effect Evaluation for Bitcoin Blockchain Systems.” All scripts are structured for clarity, modularity, and reproducibility. Sample data should be placed under `2024_utxo/`.

## License
The MIT License (MIT)

Copyright (c) 2025 Li-Chen Cheng, Yean-Fu Wen, Kai-Lun Chang

Permission is hereby granted, free of charge, to any person obtaining a copy of
this software and associated documentation files (the "Software"), to deal in
the Software without restriction, including without limitation the rights to
use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies
of the Software, and to permit persons to whom the Software is furnished to do
so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
