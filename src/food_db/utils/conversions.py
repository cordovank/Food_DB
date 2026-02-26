from __future__ import annotations

OZ_TO_G = 28.349523125
LB_TO_G = 453.59237


def g_to_oz(g: float) -> float:
    return g / OZ_TO_G


def oz_to_g(oz: float) -> float:
    return oz * OZ_TO_G


def mg_to_g(mg: float) -> float:
    return mg / 1000.0


def g_to_mg(g: float) -> float:
    return g * 1000.0
