#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
compute_attack_metrics.py

Recursively scans all JSON files in a specified directory, recomputes and overwrites
for each transaction:
  • victim_cost_btc for each input UTXO (bytes × fee_rate)
  • total_victim_cost_btc (sum of all input costs)
  • attack_cost_btc for each output UTXO in "sent_utxo_uxns"
  • total_attack_cost_btc (sum of all output costs)
  • attack_effect (%) = total_victim_cost_btc / total_attack_cost_btc × 100

All fields are recalculated unconditionally and written back in place.
"""
import os
import json
import time
from concurrent.futures import ProcessPoolExecutor, as_completed

DEFAULT_FEE_RATE = 1  # satoshi per byte


def calculate_cost_btc(utxo_entry, fee_rate):
    """
    Calculate cost in BTC: bytes × fee_rate (sat/B) ÷ 1e8.
    utxo_entry may be a dict or a JSON string containing a dict with a "bytes" field.
    Returns a formatted string with 8 decimal places, or None on error.
    """
    try:
        if isinstance(utxo_entry, str):
            utxo_entry = json.loads(utxo_entry)
        if not isinstance(utxo_entry, dict):
            return None
        b = int(utxo_entry.get("bytes", 0))
        rate = max(float(fee_rate or 0), DEFAULT_FEE_RATE)
        cost = b * rate / 1e8
        return f"{cost:.8f}"
    except Exception:
        return None


def process_file(path):
    """
    Read a JSON file, recompute metrics for each transaction, and overwrite the file.
    Returns True on success, False on any error.
    """
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception:
        return False

    records = data if isinstance(data, list) else [data]
    for tx in records:
        # Recompute input costs
        total_victim = 0.0
        fee_rate = tx.get('Txn Fee Rate', 0)
        inputs = tx.get('Txn Input UTXO Details')
        if inputs is not None:
            raw = inputs
            is_str = isinstance(raw, str)
            entries = json.loads(raw) if is_str else raw
            if isinstance(entries, dict):
                cost = calculate_cost_btc(entries, fee_rate)
                if cost is not None:
                    entries['victim_cost_btc'] = cost
                    total_victim += float(cost)
            elif isinstance(entries, list):
                for item in entries:
                    if isinstance(item, dict):
                        cost = calculate_cost_btc(item, fee_rate)
                        if cost is not None:
                            item['victim_cost_btc'] = cost
                            total_victim += float(cost)
            tx['Txn Input UTXO Details'] = json.dumps(entries, ensure_ascii=False) if is_str else entries
        tx['total_victim_cost_btc'] = f"{total_victim:.8f}"

        # Recompute attack costs
        total_attack = 0.0
        for sent in tx.get('sent_utxo_uxns', []):
            outputs = sent.get('Txn Output UTXO Details')
            rate_out = sent.get('Txn Fee Rate', 0)
            if outputs is None:
                continue
            raw_out = outputs
            is_str_out = isinstance(raw_out, str)
            entry = json.loads(raw_out) if is_str_out else raw_out
            cost = calculate_cost_btc(entry, rate_out)
            if cost is not None:
                entry['attack_cost_btc'] = cost
                total_attack += float(cost)
            sent['Txn Output UTXO Details'] = json.dumps(entry, ensure_ascii=False) if is_str_out else entry
        tx['total_attack_cost_btc'] = f"{total_attack:.8f}"

        # Recompute attack effect percentage
        vc = float(tx['total_victim_cost_btc'])
        ac = float(tx['total_attack_cost_btc'])
        tx['attack_effect'] = f"{(vc / ac * 100) if ac > 0 else 0.0:.2f}"

    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(records if isinstance(data, list) else records[0], f,
                      ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


def main():
    input_dir = 'updated'
    files = []
    for root, _, filenames in os.walk(input_dir):
        for fn in filenames:
            if fn.lower().endswith('.json'):
                files.append(os.path.join(root, fn))

    print(f"Found {len(files)} JSON files; starting processing...")
    start = time.time()
    success_count = 0
    with ProcessPoolExecutor() as executor:
        futures = {executor.submit(process_file, fp): fp for fp in files}
        for future in as_completed(futures):
            if future.result():
                success_count += 1
                rel = os.path.relpath(futures[future], input_dir)
                print(f"✓ Updated: {rel}")

    elapsed = time.time() - start
    print(f"Processed {len(files)} files, {success_count} succeeded in {elapsed:.2f}s.")


if __name__ == '__main__':
    main()
