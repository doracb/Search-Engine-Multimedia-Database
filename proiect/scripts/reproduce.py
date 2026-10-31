"""Reproduce C2/A4 offline, fara a modifica etichetele. Python standard."""
import argparse
import csv
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def read(path):
    with path.open(newline='', encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))

def write(path, rows):
    with path.open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

def rrf(q, k):
    scores = {}
    for key in ('vectori', 'text_complet'):
        for rank, p in enumerate(q[key], 1):
            scores[p] = scores.get(p, 0.0) + 1 / (k + rank)
    return sorted(scores, key=lambda p: (-scores[p], p))

def name_key(meta, p):
    return ' '.join(re.findall(r'\w+', (meta[p].get('nume') or '').casefold())) or f'produs_{p}'

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--k', type=int, default=60)
    a = ap.parse_args()
    if a.k < 0:
        ap.error('k trebuie sa fie >= 0')
    src = ROOT / 'date/candidati_ficsi.json'
    sha = hashlib.sha256(src.read_bytes()).hexdigest()
    if sha != (ROOT / 'date/candidati_ficsi.sha256').read_text().strip():
        raise SystemExit('STOP: amprenta candidatilor difera')
    queries = json.loads(src.read_text(encoding='utf-8'))['interogari']
    meta = {int(r['id_produs']): r for r in json.loads((ROOT / 'date/catalog_comun.json').read_text(encoding='utf-8'))}
    labels = {}
    for q in queries:
        for r in read(ROOT / 'etichete' / (q['id'] + '.csv')):
            key = (q['id'], int(r['id_produs']))
            if key in labels or r['relevant'].strip() not in ('0', '1'):
                raise SystemExit(f'STOP: eticheta duplicata sau invalida: {key}')
            labels[key] = int(r['relevant'])
    def precision(qid, seq):
        missing = [p for p in seq if (qid, p) not in labels]
        if missing:
            raise SystemExit(f'STOP: etichete lipsa pentru {qid}: {missing}')
        return sum(labels[(qid, p)] for p in seq) / 10
    out = ROOT / 'rezultate_reproduse'
    out.mkdir(exist_ok=True)
    detail = []
    for q in queries:
        for system, k, seq in [('vectori', '', q['vectori'][:10]), ('text', '', q['text_complet'][:10])] + [('hibrid', k, rrf(q, k)[:10]) for k in (0,5,10,20,40,60,100,200)]:
            detail.append({'id': q['id'], 'sistem': system, 'k_rrf': k, 'rezultate_intoarse': len(seq), 'P@10': precision(q['id'], seq)})
    write(out / 'c2_pe_interogare.csv', detail)
    for system, k in [('vectori', ''), ('text', '')] + [('hibrid', k) for k in (0,5,10,20,40,60,100,200)]:
        subset = [r['P@10'] for r in detail if r['sistem'] == system and r['k_rrf'] == k]
        print(f'C2 {system:8} k={str(k):3} P@10={sum(subset)/len(subset):.3f}')
    a4 = []
    for q in queries:
        order = rrf(q, a.k)
        available = [p for p in order if meta[p]['stoc'] is not None and meta[p]['stoc'] > 0]
        seen, unique = set(), []
        for p in available:
            key = name_key(meta, p)
            if key not in seen:
                seen.add(key)
                unique.append(p)
        for method, seq in [('initial', order[:10]), ('stoc', available[:10]), ('stoc_diversitate', unique[:10])]:
            names = [name_key(meta, p) for p in seq]
            stocked = [p for p in seq if meta[p]['stoc'] is not None and meta[p]['stoc'] > 0]
            a4.append({'id': q['id'], 'metoda': method, 'rezultate_intoarse': len(seq), 'P@10': precision(q['id'], seq), 'relevante_in_stoc_din_10': precision(q['id'], stocked), 'epuizate_sau_stoc_necunoscut': len(seq)-len(stocked), 'repetari_nume': len(names)-len(set(names))})
    write(out / f'a4_k{a.k}_pe_interogare.csv', a4)
    for method in ('initial', 'stoc', 'stoc_diversitate'):
        sub = [r for r in a4 if r['metoda'] == method]
        print(f'A4 k={a.k} {method:18} P@10={sum(r["P@10"] for r in sub)/len(sub):.3f} epuizate={sum(r["epuizate_sau_stoc_necunoscut"] for r in sub)} repetari={sum(r["repetari_nume"] for r in sub)}')
    # Comparatie independenta cu toate scorurile furnizate la configuratia originala.
    for filename, generated, keys in [('c2_pe_interogare.csv', detail, ('id','sistem','k_rrf'))] + ([('a4_pe_interogare.csv', a4, ('id','metoda'))] if a.k == 60 else []):
        expected = {tuple(str(r[k]) for k in keys): r for r in read(ROOT / 'rezultate' / filename)}
        for r in generated:
            key = tuple(str(r[k]) for k in keys)
            if key not in expected or abs(float(expected[key]['P@10']) - r['P@10']) > 1e-10:
                raise SystemExit(f'STOP: rezultat diferit: {filename}, {key}')
        if len(expected) != len(generated):
            raise SystemExit(f'STOP: numar de randuri diferit: {filename}')
    print('GATA: scorurile corespund fisierelor sursa. Etichetele nu au fost modificate.')

if __name__ == '__main__':
    main()
