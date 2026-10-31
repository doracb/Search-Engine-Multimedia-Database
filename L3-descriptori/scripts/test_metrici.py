"""
Testele pentru metrici.py. Toate trebuie sa treaca inainte de T4.

    docker compose exec jupyter python /home/jovyan/proiect/L3-descriptori/scripts/test_metrici.py

Primele trei teste sunt exercitiul din C3 (sistemele A, B, C, R = 4).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import metrici as m  # noqa: E402

CAZURI = []


def caz(f):
    CAZURI.append(f)
    return f


def aprox(a, b, tol=1e-3):
    return abs(a - b) <= tol


@caz
def sistemul_A():
    e = [1, 0, 1, 1, 0]
    assert aprox(m.precizie_la_k(e, 5), 0.60), m.precizie_la_k(e, 5)
    assert aprox(m.rapel_la_k(e, 5, 4), 0.75), m.rapel_la_k(e, 5, 4)
    assert aprox(m.precizie_medie(e, 4), 0.604), m.precizie_medie(e, 4)


@caz
def sistemul_B():
    e = [0, 1, 1, 0, 1]
    assert aprox(m.precizie_la_k(e, 5), 0.60)
    assert aprox(m.rapel_la_k(e, 5, 4), 0.75)
    assert aprox(m.precizie_medie(e, 4), 0.442), m.precizie_medie(e, 4)


@caz
def sistemul_C():
    e = [1, 1, 0, 0, 0]
    assert aprox(m.precizie_la_k(e, 5), 0.40)
    assert aprox(m.rapel_la_k(e, 5, 4), 0.50)
    assert aprox(m.precizie_medie(e, 4), 0.500), m.precizie_medie(e, 4)


@caz
def precizie_la_rang_mic():
    e = [1, 0, 1, 1, 0]
    assert aprox(m.precizie_la_k(e, 1), 1.0)
    assert aprox(m.precizie_la_k(e, 2), 0.5)
    assert aprox(m.precizie_la_k(e, 3), 2 / 3)


@caz
def clasament_mai_scurt_decat_k():
    # 3 rezultate, toate relevante, dar k = 10: P@10 = 3/10, nu 1
    e = [1, 1, 1]
    assert aprox(m.precizie_la_k(e, 10), 0.3), m.precizie_la_k(e, 10)


@caz
def niciun_relevant_cunoscut():
    e = [0, 0, 0]
    assert m.rapel_la_k(e, 3, 0) == 0
    assert m.precizie_medie(e, 0) == 0


@caz
def relevante_negasite_scad_AP():
    # aceleasi rezultate, dar 10 relevante in total: AP scade de 10/4 ori fata de R = 4
    e = [1, 0, 1, 1, 0]
    assert aprox(m.precizie_medie(e, 10), 0.604 * 4 / 10, 2e-3)


@caz
def clasament_perfect():
    assert aprox(m.precizie_medie([1, 1, 1, 0, 0], 3), 1.0)


def main():
    esecuri = 0
    for f in CAZURI:
        try:
            f()
            print(f"  [ok]   {f.__name__}")
        except NotImplementedError as e:
            esecuri += 1
            print(f"  [TODO] {f.__name__}: {e}")
        except AssertionError as e:
            esecuri += 1
            print(f"  [ESEC] {f.__name__}: valoare obtinuta {e}")
    print()
    if esecuri:
        print(f"{esecuri} din {len(CAZURI)} teste nu trec.")
        sys.exit(1)
    print(f"Toate cele {len(CAZURI)} teste trec.")


if __name__ == "__main__":
    main()
