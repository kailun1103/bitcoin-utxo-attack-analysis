#!/usr/bin/env python3
# coding: utf-8
"""
script_address_classifier.py

Recursively scan a directory of JSON transaction files, classify each UTXO
input script according to its address and witness data, and annotate the
field "scriptType" accordingly. Supported types include P2PKH, P2SH,
P2WPKH, P2WSH, P2TR (key vs. script path), P2SH-P2WPKH, P2SH-P2WSH,
and Non-Standard variants.

Outputs a summary count of all processed UTXOs by category.
"""
import os
import re
import json
time
from collections import defaultdict
from multiprocessing import Pool, cpu_count

# Regular expression for hex validation
HEX_RE = re.compile(r'^[0-9A-Fa-f]*$')

# Classification based on address prefix, scriptSig, and witness

def is_valid_hex(s: str) -> bool:
    """Return True if the string is valid hexadecimal."""
    return bool(HEX_RE.fullmatch(s.strip()))


def classify_utxo(utxo: dict) -> str:
    """Classify a UTXO input record into a script type."""
    addr = utxo.get('inputHash', '').strip()
    asm = utxo.get('scriptSig', {}).get('asm', '').strip().lower()
    hex_sig = utxo.get('scriptSig', {}).get('hex', '').strip().lower()
    witness = utxo.get('txinwitness', [])

    # P2PKH: starts with '1'
    if addr.startswith('1'):
        return 'P2PKH'
    # P2WPKH or P2WSH: bech32 'bc1q'
    if addr.startswith('bc1q'):
        return 'P2WPKH' if len(addr) < 45 else 'P2WSH'
    # P2SH variants: starts with '3'
    if addr.startswith('3'):
        has_sig = bool(asm and hex_sig and is_valid_hex(hex_sig))
        has_wit = bool(witness)
        # P2SH-P2WPKH
        if ('0014' in asm or hex_sig.startswith('160014')) and has_wit:
            return 'P2SH-P2WPKH'
        # P2SH-P2WSH
        if ('0020' in asm or hex_sig.startswith('220020')) and has_wit:
            return 'P2SH-P2WSH'
        # Legacy P2SH
        if has_sig and not has_wit:
            return 'P2SH'
        return 'Non-Standard P2SH'
    # Taproot: bech32 'bc1p'
    if addr.startswith('bc1p'):
        return 'P2TR_key_path' if len(witness) == 1 else 'P2TR_script_path'
    # Fallback: use existing scriptType if provided
    st = utxo.get('scriptType', '').upper()
    if st in ('P2SH', 'P2TR'):
        # Re-apply witness logic
        if st == 'P2SH':
            return classify_utxo({**utxo, 'inputHash':'3'})
        return 'P2TR_key_path' if len(witness)==1 else 'P2TR_script_path'
    return 'Non-Standard'


def process_file(path: str) -> dict:
    """Process a single JSON file, classify UTXOs, and return counts."""
    counts = defaultdict(int)
    total_utxos = 0
    try:
        data = json.load(open(path, 'r', encoding='utf-8'))
    except Exception:
        return {'total':0,'counts':counts}
    records = data if isinstance(data, list) else [data]

    for tx in records:
        # Classify Txn Input Details
        for key in ('Txn Input Details', 'Txn Input UTXO Details'):
            raw = tx.get(key, '[]')
            try:
                arr = json.loads(raw) if isinstance(raw, str) else raw
            except json.JSONDecodeError:
                continue
            updated = []
            for utxo in arr:
                if isinstance(utxo, dict):
                    cat = classify_utxo(utxo)
                    counts[cat] += 1
                    total_utxos += 1
                    utxo['scriptType'] = cat
                updated.append(utxo)
            tx[key] = json.dumps(updated, ensure_ascii=False) if isinstance(raw, str) else updated

    # Overwrite file with annotated data
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(records if isinstance(data,list) else records[0], f, ensure_ascii=False, indent=2)
    return {'total': total_utxos, 'counts': counts}


def main():
    source_dir = '2024_utxo/updated'
    files = [os.path.join(dp, fn)
             for dp,_,fns in os.walk(source_dir)
             for fn in fns if fn.lower().endswith('.json')]
    if not files:
        print(f'Error: no JSON files in {source_dir}')
        return

    total_counts = defaultdict(int)
    total_utxos = 0
    start = time.time()
    with Pool(min(8, cpu_count())) as pool:
        for result in pool.imap_unordered(process_file, files):
            total_utxos += result['total']
            for cat,count in result['counts'].items():
                total_counts[cat] += count

    elapsed = time.time() - start
    print(f'Processed {len(files)} files, classified {total_utxos} UTXOs in {elapsed:.2f}s')
    print('UTXO counts by script type:')
    for cat,count in sorted(total_counts.items()):
        print(f'  {cat}: {count}')


if __name__=='__main__':
    main()
