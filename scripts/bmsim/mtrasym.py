"""MTR_asym computation from Z-spectra."""
from __future__ import annotations

import numpy as np


def compute_mtrasym(
    offsets_ppm: np.ndarray,
    z: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """
  Compute MTR_asym(ppm) = Z(-ppm) - Z(+ppm) on positive offsets.

  For each offset ``w > 0``, the partner at ``-w`` is matched (nearest within
  1e-6 ppm). Unmatched points are omitted.

  Returns
  -------
  asym_ppm, mtrasym
    Positive offset grid and asymmetry values.
  """
    offsets_ppm = np.asarray(offsets_ppm, dtype=float)
    z = np.asarray(z, dtype=float)

    pos_mask = offsets_ppm > 0
    pos_ppm = offsets_ppm[pos_mask]
    pos_z = z[pos_mask]

    neg_ppm = offsets_ppm[offsets_ppm < 0]
    neg_z = z[offsets_ppm < 0]

    if neg_ppm.size == 0:
        return np.array([]), np.array([])

    order = np.argsort(neg_ppm)
    neg_ppm = neg_ppm[order]
    neg_z = neg_z[order]

    asym_vals = []
    asym_ppm = []
    for w, z_pos in zip(pos_ppm, pos_z):
        if not np.isfinite(z_pos):
            continue
        idx = np.where(np.isclose(-w, neg_ppm, atol=1e-6, rtol=0))[0]
        if idx.size == 0:
            continue
        z_neg = neg_z[idx[0]]
        if not np.isfinite(z_neg):
            continue
        asym_ppm.append(w)
        asym_vals.append(z_neg - z_pos)

    return np.asarray(asym_ppm), np.asarray(asym_vals)

