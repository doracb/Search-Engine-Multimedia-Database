"""
Metricile de evaluare — VERSIUNEA DE REFERINTA.

"""

from __future__ import annotations


def precizie_la_k(etichete: list[int], k: int) -> float:
    if k <= 0:
        return 0.0
    return sum(etichete[:k]) / k


def rapel_la_k(etichete: list[int], k: int, R: int) -> float:
    if R <= 0:
        return 0.0
    return sum(etichete[:k]) / R


def precizie_medie(etichete: list[int], R: int) -> float:
    if R <= 0:
        return 0.0
    gasite, suma = 0, 0.0
    for i, e in enumerate(etichete, start=1):
        if e:
            gasite += 1
            suma += gasite / i
    return suma / R