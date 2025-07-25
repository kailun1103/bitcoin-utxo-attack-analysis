#!/usr/bin/env python3
# coding: utf-8
"""
Annotate and Compute Script Byte Sizes in UTXO Transaction JSON Records

This script walks through a directory of JSON files containing Bitcoin UTXO transactions,
identifies the script type for each input and output script, calculates its byte size,
and rewrites the JSON with additional "scriptType" and "bytes" fields while preserving
original structure and formatting.
"""
import os
import json
import glob
import time
import math
from collections import OrderedDict
from concurrent.futures import ProcessPoolExecutor

# Fixed byte sizes for known script types
SCRIPT_TYPE_BYTES = {
    'P2PKH': 34,
    'P2SH': 32,
    'P2WPKH': 31,
    'P2WSH': 43,
    'P2TR': 43,
    'OP_RETURN': 0,
    'UNKNOWN': 43
}


def identify_script_type(address: str) -> str:
    """Return script type based on address prefix or literal OP_RETURN."""
    if not address or not isinstance(address, str):
        return 'UNKNOWN'
    if address.startswith('OP_RETURN'):
        return 'OP_RETURN'
    if address.startswith('1'):
        return 'P2PKH'
    if address.startswith('3'):
        return 'P2SH'
    if address.startswith('bc1q'):
        return 'P2WPKH' if len(address) < 45 else 'P2WSH'
    if address.startswith('bc1p'):
        return 'P2TR'
    return 'UNKNOWN'


def varint_size(n: int) -> int:
    """Compute the size in bytes of a Bitcoin varint encoding."""
    if n < 253:
        return 1
    if n < 65536:
        return 3
    return 5


def calculate_input_bytes(input_item: dict) -> int:
    """Calculate the byte size of a transaction input considering SegWit or legacy formats."""
    base = 32 + 4 + 4
    hexstr = input_item.get('scriptSig', {}).get('hex', '') if isinstance(input_item.get('scriptSig'), dict) else ''
    witness = input_item.get('txinwitness') or []

    if witness:
        # SegWit witness inclusion
        sb = len(hexstr) // 2 if hexstr else 0
        base_size = base + varint_size(sb) + sb
        wsize = 1
        for w in witness:
            wb = len(w) // 2
            wsize += varint_size(wb) + wb
        weight = base_size * 4 + wsize
        return math.ceil(weight / 4)

    # Legacy P2PKH and P2SH
    if hexstr:
        sb = len(hexstr) // 2
        return base + varint_size(sb) + sb
    return base + 1


def add_bytes_to_item(item: dict, is_input: bool = False) -> dict:
    """Annotate a JSON object with its scriptType and byte size."""
    if is_input:
        item['bytes'] = calculate_input_bytes(item)
    else:
        st = item.get('scriptType') or identify_script_type(item.get('outputHash',''))
        item['scriptType'] = st
        item['bytes'] = SCRIPT_TYPE_BYTES.get(st, SCRIPT_TYPE_BYTES['UNKNOWN'])
    return item


def process_utxo_details(details):
    """Process a UTXO details field (string or object), adding scriptType and bytes."""
    if not details:
        return details
    is_str = isinstance(details, str)
    try:
        obj = json.loads(details) if is_str else details
        if isinstance(obj, list):
            for i, entry in enumerate(obj):
                if 'inputHash' in entry:
                    entry['scriptType'] = identify_script_type(entry.get('inputHash',''))
                    obj[i] = add_bytes_to_item(entry, True)
                elif 'outputHash' in entry:
                    entry['scriptType'] = identify_script_type(entry.get('outputHash',''))
                    obj[i] = add_bytes_to_item(entry, False)
        elif isinstance(obj, dict):
            key = 'inputHash' if 'inputHash' in obj else 'outputHash'
            obj['scriptType'] = identify_script_type(obj.get(key, ''))
            obj = add_bytes_to_item(obj, key=='inputHash')
        return json.dumps(obj, ensure_ascii=False) if is_str else obj
    except Exception:
        return details


def process_transaction_list(details, is_input=False):
    """Process transaction detail list field, adding scriptType and bytes."""
    if not details:
        return details
    is_str = isinstance(details, str)
    try:
        arr = json.loads(details) if is_str else details
        if isinstance(arr, list):
            for i, entry in enumerate(arr):
                if is_input and 'inputHash' in entry:
                    entry['scriptType'] = identify_script_type(entry.get('inputHash',''))
                    arr[i] = add_bytes_to_item(entry, True)
                elif not is_input and 'outputHash' in entry:
                    entry['scriptType'] = identify_script_type(entry.get('outputHash',''))
                    arr[i] = add_bytes_to_item(entry, False)
        return json.dumps(arr, ensure_ascii=False) if is_str else arr
    except Exception:
        return details


def process_file(path, input_dir, output_dir):
    """Read a JSON file, annotate script details, and write to output directory."""
    rel = os.path.relpath(path, input_dir)
    dest = os.path.join(output_dir, rel)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"[ERROR] {rel}: {e}")
        return

    records = data if isinstance(data, list) else [data]
    for tx in records:
        if 'Txn Input UTXO Details' in tx:
            tx['Txn Input UTXO Details'] = process_utxo_details(tx['Txn Input UTXO Details'])
        if 'Txn Input Details' in tx:
            tx['Txn Input Details'] = process_transaction_list(tx['Txn Input Details'], True)
        if 'Txn Output Details' in tx:
            tx['Txn Output Details'] = process_transaction_list(tx['Txn Output Details'], False)

        sent = tx.get('sent_utxo_uxns', [])
        if isinstance(sent, list):
            inp = tx.get('Txn Input UTXO Details', [])
            try:
                inp = json.loads(inp) if isinstance(inp, str) else inp
            except:
                inp = []
            mapping = {}
            for u in inp:
                tid, amt = u.get('txid'), u.get('amount')
                if tid and amt:
                    mapping.setdefault(tid, []).append(float(amt))

            for i, s in enumerate(sent):
                if 'Txn Output Details' in s:
                    s['Txn Output Details'] = process_transaction_list(s['Txn Output Details'], False)
                tid = s.get('Txn Hash')
                try:
                    outs = json.loads(s.get('Txn Output Details','')) if isinstance(s.get('Txn Output Details'), str) else s.get('Txn Output Details',[])
                except:
                    outs = []
                matched = None
                for o in outs:
                    if any(abs(float(o.get('amount',0)) - x) < 1e-8 for x in mapping.get(tid, [])):
                        matched = o
                        break
                ordered = OrderedDict()
                for k, v in s.items():
                    ordered[k] = v
                    if k == 'Txn Output Details':
                        if matched:
                            matched['scriptType'] = identify_script_type(matched.get('outputHash',''))
                            matched = add_bytes_to_item(matched, False)
                            ordered['Txn Output UTXO Details'] = json.dumps(matched, ensure_ascii=False)
                        else:
                            ordered['Txn Output UTXO Details'] = '[]'
                sent[i] = ordered

    with open(dest, 'w', encoding='utf-8') as f:
        json.dump(records if isinstance(data, list) else records[0], f, ensure_ascii=False, indent=2)
    print(f"[OK] {rel}")


def main():
    input_dir = 'updated'
    output_dir = 'annotated'
    os.makedirs(output_dir, exist_ok=True)
    files = glob.glob(os.path.join(input_dir, '**', '*.json'), recursive=True)
    print(f"Found {len(files)} JSON files in '{input_dir}'")
    start = time.time()
    with ProcessPoolExecutor(max_workers=os.cpu_count() or 4) as executor:
        for _ in executor.map(lambda p: process_file(p, input_dir, output_dir), files):
            pass
    print(f"Completed in {time.time()-start:.2f} seconds. Output in '{output_dir}'")

if __name__ == '__main__':
    main()
