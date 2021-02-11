import pytest
import numpy as np
from corona.utils import sparsify_mask


def test_sparsify():
    l = np.array([1, 2, 3, 6])
    idx = sparsify_mask(l, 0.1)
    assert np.all(l[idx] == l)

    l = np.array([1, 2, 3, 6])
    idx = sparsify_mask(l, 1)
    assert np.all(l[idx] == l)

    l = np.array([1, 2, 3, 6])
    idx = sparsify_mask(l, 1.1)
    assert np.all(l[idx] == l[[0, 2, 3]])

    l = np.array([1, 2, 3, 6])
    idx = sparsify_mask(l, 3)
    assert np.all(l[idx] == l[[0, 3]])
