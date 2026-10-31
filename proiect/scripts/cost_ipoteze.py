"""Reface modelul didactic L7, cu volume si preturi declarate ca ipoteze."""
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRET_STOCARE = 0.023
PRET_TRANSFER = 0.09
GB_GRATUITI = 100
ORE_LUNA = 730
IMAGINI = 44412
GB_IMAGINI = 0.567  # aproximare din rezultatele L2, nu masuratoare noua
DIMENSIUNI = 512
IMAGINI_NOI = 2000
DEBIT_EMB = 300  # ipoteza cursului, nu debit masurat pe laptop
INST = [(16,.1071),(32,.2142),(64,.4284),(128,.8568),(256,1.7136),(512,3.4272)]

rows = []
for factor in (1,100):
    vectori_gb = IMAGINI * factor * DIMENSIUNI * 4 / 1e9
    ram = 16 + 2 * vectori_gb * 1.5
    ram_inst, pret_ora = next((r,p) for r,p in INST if r >= ram)
    valori = {
        'stocare_usd': GB_IMAGINI*factor*PRET_STOCARE,
        'transfer_usd': max(600*factor-GB_GRATUITI,0)*PRET_TRANSFER,
        'server_usd': pret_ora*ORE_LUNA,
        'embeddings_usd': IMAGINI_NOI*factor/DEBIT_EMB/3600*pret_ora,
        'operare_build_usd': 8*25,
    }
    total=sum(valori.values())
    row={'factor':factor,**{k:round(v,6) for k,v in valori.items()},'total_build_usd':round(total,2),'prag_abonament_buy_usd':round(valori['server_usd']+(8-2)*25,2),'ram_instanta_gb':ram_inst}
    rows.append(row)
    print(row)
out=ROOT/'rezultate_reproduse'
out.mkdir(exist_ok=True)
with (out/'cost_ipoteze.csv').open('w',newline='',encoding='utf-8') as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
print('Ipoteze didactice, fara oferta gestionata, TVA sau redundanta.')
