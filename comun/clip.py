"""
Encoderul CLIP (OpenCLIP), folosit in L5 si L7.

Modelul este salvat in imaginea Docker bdm-jupyter:2.0 la construire, deci
in laborator nu se descarca nimic. Vectorii catalogului NU se calculeaza in
laborator: vor fi furnizati  (artefacte/L5_clip.npz). In laborator
rulam doar encoderul de TEXT, care e rapid.
"""

from __future__ import annotations

import os
from functools import lru_cache

import numpy as np

MODEL = os.environ.get("BDM_CLIP_MODEL", "ViT-B-32")
PONDERI = os.environ.get("BDM_CLIP_PONDERI", "laion2b_s34b_b79k")


@lru_cache(maxsize=1)
def _model():
    import open_clip
    import torch

    torch.set_num_threads(max(1, (os.cpu_count() or 2) // 2))
    model, _, preprocesare = open_clip.create_model_and_transforms(MODEL, pretrained=PONDERI)
    model.eval()
    return model, preprocesare, open_clip.get_tokenizer(MODEL)


def _normalizeaza(x: np.ndarray) -> np.ndarray:
    return (x / (np.linalg.norm(x, axis=1, keepdims=True) + 1e-12)).astype(np.float32)


def vectori_text(texte: list[str]) -> np.ndarray:
    """Un vector normalizat (512 pentru ViT-B-32) pentru fiecare text."""
    import torch

    model, _, tok = _model()
    with torch.no_grad():
        v = model.encode_text(tok(list(texte))).float().cpu().numpy()
    return _normalizeaza(v)


def vectori_imagine(imagini) -> np.ndarray:
    """imagini: lista de PIL.Image. Folosit de profesor la precalcul."""
    import torch

    model, prep, _ = _model()
    with torch.no_grad():
        lot = torch.stack([prep(im.convert("RGB")) for im in imagini])
        v = model.encode_image(lot).float().cpu().numpy()
    return _normalizeaza(v)


def descriere() -> str:
    return f"OpenCLIP {MODEL} / {PONDERI}"
