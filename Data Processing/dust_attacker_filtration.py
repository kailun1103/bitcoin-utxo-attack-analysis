#!/usr/bin/env python3
# coding: utf-8
"""
Annotate Dust Attacker Transactions Based on Fee Rate Outliers
This script scans JSON files containing Bitcoin UTXO transactions, computes the
upper outlier threshold (Q3 + m * IQR) for the fee rate distribution, and marks
each transaction as a dust attacker ("dust_attacker"="1") if all its sent UTXO
sub-transactions have fee rates below or equal to the threshold; otherwise, it
marks it as non-dust-attacker ("dust_attacker"="0").
"""
import os
import time
import json
import numpy as np
from concurrent.futures import ProcessPoolExecutor, as_completed
from tqdm import tqdm

# Attempt to use orjson for performance; fallback to standard json
try:
    import orjson as _oj
    def load_json_bytes(fp):
        return _oj.loads(fp.read())
    def dump_json_bytes(obj, fp):
        fp.write(_oj.dumps(obj))
except ImportError:
    import json as _oj
    def load_json_bytes(fp):
        return _oj.load(fp)
    def dump_json_bytes(obj, fp):
        _oj.dump(obj, fp, ensure_ascii=False, separators=(',', ':'))


def extract_fee_rates(file_path):
    """Extract all fee rates from 'sent_utxo_uxns' entries in a JSON file."""
    rates = []
    try:
        with open(file_path, 'rb') as f:
            data = load_json_bytes(f)
    except Exception:
        return rates

    records = data if isinstance(data, list) else [data]
    for record in records:
        for sub in record.get('sent_utxo_uxns', []):
            try:
                rate = float(sub.get('Txn Fee Rate', 0))
                rates.append(rate)
            except (TypeError, ValueError):
                continue
    return rates


def annotate_transactions(file_path, upper_threshold):
    """Annotate each transaction in the file as dust attacker or not."""
    processed = filtered_out = 0
    try:
        with open(file_path, 'rb') as f:
            data = load_json_bytes(f)
    except Exception:
        return processed, filtered_out

    records = data if isinstance(data, list) else [data]
    for record in records:
        processed += 1
        # If any sub-transaction fee rate exceeds threshold, mark as non-dust
        is_dust = True
        for sub in record.get('sent_utxo_uxns', []):
            try:
                if float(sub.get('Txn Fee Rate', 0)) > upper_threshold:
                    is_dust = False
                    filtered_out += 1
                    break
            except (TypeError, ValueError):
                continue
        record['dust_attacker'] = '1' if is_dust else '0'

    # Write back annotated data
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            if isinstance(data, list):
                dump_json_bytes(data, f)
            else:
                dump_json_bytes(records[0], f)
    except Exception:
        pass

    return processed, filtered_out


def main():
    root_dir = '2024_utxo'
    start_time = time.time()

    # Gather JSON files
    json_files = []
    for dirpath, _, filenames in os.walk(root_dir):
        for filename in filenames:
            if filename.lower().endswith('.json'):
                json_files.append(os.path.join(dirpath, filename))

    if not json_files:
        print('No JSON files found.')
        return

    # Extract all fee rates in parallel
    all_rates = []
    with ProcessPoolExecutor() as executor:
        futures = {executor.submit(extract_fee_rates, fp): fp for fp in json_files}
        for future in tqdm(as_completed(futures), total=len(futures), desc='Collecting fee rates'):
            all_rates.extend(future.result())

    if not all_rates:
        print('No fee rates collected.')
        return

    arr = np.array(all_rates, dtype=float)
    q1, q3 = np.percentile(arr, [25, 75])
    iqr = q3 - q1
    m = 1.5  # Outlier multiplier
    upper = q3 + m * iqr

    print(f'Collected {len(arr)} fee rates')
    print(f'Q1={q1:.4f}, Q3={q3:.4f}, IQR={iqr:.4f}')
    print(f'Upper threshold (Q3+{m}*IQR)={upper:.4f}\n')

    # Annotate transactions in parallel
    total_processed = total_filtered = 0
    with ProcessPoolExecutor() as executor:
        futures = {executor.submit(annotate_transactions, fp, upper): fp for fp in json_files}
        for future in tqdm(as_completed(futures), total=len(futures), desc='Annotating files'):
            proc, filt = future.result()
            total_processed += proc
            total_filtered += filt

    elapsed = time.time() - start_time
    print(f'\nAnnotation complete:')
    print(f'  Total transactions processed: {total_processed}')
    print(f'  Transactions marked non-dust (0): {total_filtered}')
    print(f'Elapsed time: {elapsed:.2f} seconds')


if __name__ == '__main__':
    main()
