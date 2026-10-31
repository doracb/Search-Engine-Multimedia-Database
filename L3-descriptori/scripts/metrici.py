"""
L3, T2 — Metricile de evaluare. ACEST FISIER IL COMPLETATI VOI.

Conventii, aceleasi ca in C3:
  etichete : lista de 0/1 pe pozitiile clasamentului, de la rangul 1 in jos
             ex. [1, 0, 1, 1, 0]  inseamna  ✓ ✗ ✓ ✓ ✗
  k        : rangul de taiere
  R        : numarul TOTAL de produse relevante cunoscute pentru interogare
             (nu doar cele gasite in clasament)

Reguli pentru cazurile-limita (testele le verifica):
  - daca clasamentul e mai scurt decat k, pozitiile lipsa conteaza ca nerelevante;
  - daca R = 0, rapelul si AP sunt 0 (nu impartiti la zero).

Verificare:
  docker compose exec jupyter python /home/jovyan/proiect/L3-descriptori/scripts/test_metrici.py
"""

from __future__ import annotations


def precizie_la_k(etichete: list[int], k: int) -> float:
    """P@k = (relevante intre primele k) / k"""
    relevante_gasite = sum(etichete[:k])
    return relevante_gasite / k


def rapel_la_k(etichete: list[int], k: int, R: int) -> float:
    """R@k = (relevante intre primele k) / R"""
    if R == 0:
        return 0.0
    relevante_gasite = sum(etichete[:k])
    return relevante_gasite / R


def precizie_medie(etichete: list[int], R: int) -> float:
    """AP = (1/R) * suma, pe fiecare pozitie i cu element relevant, a P@i.

    Exemplul din curs: ✓ ✗ ✓ ✓ ✗ cu R = 4
        AP = (1/1 + 2/3 + 3/4) / 4 = 0,604
    """
    if R == 0:
        return 0.0
        
    suma_precizii = 0.0
    relevante_pana_aici = 0
   
    for i, eticheta in enumerate(etichete):
        if eticheta == 1:
            relevante_pana_aici += 1
            suma_precizii += relevante_pana_aici / (i + 1)
            
    return suma_precizii / R
