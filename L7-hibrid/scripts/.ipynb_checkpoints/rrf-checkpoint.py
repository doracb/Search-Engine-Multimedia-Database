"""
L7, T2 — Fuziunea pe ranguri (Reciprocal Rank Fusion). COMPLETATI functia.

    scor_RRF(d) = suma, pe fiecare lista in care apare d, a  1 / (k + rang_d)

rangul incepe de la 1; un produs care lipseste dintr-o lista nu primeste
nimic de la ea. La egalitate de scor, ordinea nu conteaza pentru teste.

Verificare:
    docker compose exec jupyter python /home/jovyan/proiect/L7-hibrid/scripts/rrf.py
"""

from __future__ import annotations


def fuziune_rrf(liste: list[list[int]], k: int = 60) -> list[tuple[int, float]]:
    """liste: clasamente (id-uri, de la cel mai bun in jos).

    Intoarce [(id, scor)], ordonat descrescator dupa scor.
    """
    scoruri = {}
    for clasament in liste:
        for rang, element in enumerate(clasament, start=1):
            if element not in scoruri:
                scoruri[element] = 0.0
            scoruri[element] += 1.0 / (k + rang)

    rezultat_sortat = sorted(scoruri.items(), key=lambda x: x[1], reverse=True)
    return rezultat_sortat


# ---------------------------------------------------------------------
# Teste
# ---------------------------------------------------------------------

def _teste() -> None:
    # 1. O singura lista: ordinea se pastreaza.
    r = fuziune_rrf([[7, 3, 9]])
    assert [x for x, _ in r] == [7, 3, 9], r
    assert abs(r[0][1] - 1 / 61) < 1e-9, r

    # 2. Doua liste. A e pe locul 1 si 3; B pe 2 si 1; C doar pe 2; D doar pe 3.
    vect = ["A", "B", "D"]
    text = ["B", "C", "A"]
    r = dict(fuziune_rrf([vect, text], k=60))
    assert abs(r["A"] - (1 / 61 + 1 / 63)) < 1e-9
    assert abs(r["B"] - (1 / 62 + 1 / 61)) < 1e-9
    assert abs(r["C"] - 1 / 62) < 1e-9
    assert abs(r["D"] - 1 / 63) < 1e-9
    ordine = [x for x, _ in fuziune_rrf([vect, text], k=60)]
    assert ordine[:2] == ["B", "A"], ordine

    # 3. Cu k = 0, locul 1 intr-o singura lista (1/1) valoreaza cat locul 2
    #    in ambele liste (1/2 + 1/2). Cu k = 60, al doilea castiga clar.
    r = dict(fuziune_rrf([["X", "Y"], ["Z", "Y"]], k=0))
    assert abs(r["Y"] - 1.0) < 1e-9 and abs(r["X"] - 1.0) < 1e-9

    # 4. Liste goale.
    assert fuziune_rrf([[], []]) == []
    print("Toate testele RRF trec.")


if __name__ == "__main__":
    try:
        _teste()
    except NotImplementedError as e:
        print(f"[TODO] {e}")
    except AssertionError as e:
        print(f"[ESEC] {e}")
