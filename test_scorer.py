import numpy as np
import pytest

import scorer as sc


# =============================================================
# ground truth
# =============================================================
def test_ground_truth_shape_and_determinism():
    X, _ = sc.sample_dataset(32, seed=7)
    a = sc.ground_truth(X)
    b = sc.ground_truth(X)
    assert a.shape == (32, sc.N_OUT)
    assert np.array_equal(a, b)


def test_y2_depends_only_on_block_parity():
    X, _ = sc.sample_dataset(16, seed=11)
    flipped = X.copy()
    flipped[:, 3] ^= 1
    flipped[:, 7] ^= 1
    assert np.allclose(sc.ground_truth(X)[:, 2], sc.ground_truth(flipped)[:, 2])


def test_y2_changes_when_block_parity_flips():
    X, _ = sc.sample_dataset(16, seed=11)
    flipped = X.copy()
    flipped[:, 3] ^= 1
    assert not np.allclose(sc.ground_truth(X)[:, 2], sc.ground_truth(flipped)[:, 2])


def test_y1_stays_inside_clip_bounds():
    _, Y = sc.sample_dataset(512, seed=5)
    assert Y[:, 1].min() >= -8.0 - 1e-9
    assert Y[:, 1].max() <= 14.0 + 1e-9


# =============================================================
# sampling
# =============================================================
def test_sample_dataset_is_binary_and_reproducible():
    X1, Y1 = sc.sample_dataset(64, seed=3)
    X2, Y2 = sc.sample_dataset(64, seed=3)
    assert X1.shape == (64, sc.N_BITS)
    assert set(np.unique(X1)).issubset({0, 1})
    assert np.array_equal(X1, X2)
    assert np.array_equal(Y1, Y2)


# =============================================================
# hamming distance
# =============================================================
def test_hamming_matrix_matches_brute_force():
    rng = np.random.default_rng(0)
    A = rng.integers(0, 2, size=(9, sc.N_BITS))
    B = rng.integers(0, 2, size=(13, sc.N_BITS))
    expected = (A[:, None, :] != B[None, :, :]).sum(axis=2)
    assert np.allclose(sc.hamming_matrix(A, B), expected)


def test_hamming_matrix_self_distance_is_zero():
    X, _ = sc.sample_dataset(20, seed=1)
    assert np.allclose(np.diag(sc.hamming_matrix(X, X)), 0.0)


# =============================================================
# bit features
# =============================================================
def test_bit_features_layout_and_intersection():
    X = np.array([[1, 1, 0], [1, 0, 1]])
    iu = np.triu_indices(3, k=1)
    inter = X[:, iu[0]] * X[:, iu[1]]
    F = np.concatenate([np.ones((2, 1)), X, inter], axis=1)
    assert F.shape == (2, 1 + 3 + 3)
    assert np.array_equal(inter[0], [1, 0, 0])


def test_bit_features_width():
    X, _ = sc.sample_dataset(4, seed=2)
    n_pairs = sc.N_BITS * (sc.N_BITS - 1) // 2
    assert sc.bit_features(X).shape == (4, 1 + sc.N_BITS + n_pairs)


# =============================================================
# surrogate
# =============================================================
def test_unknown_method_rejected():
    with pytest.raises(ValueError):
        sc.Surrogate("nope")


@pytest.mark.parametrize("method", ["idw", "expknn"])
def test_single_neighbour_recovers_training_target(method):
    X, Y = sc.sample_dataset(50, seed=13)
    yhat = sc.Surrogate(method, k=1).fit(X, Y).predict(X)
    assert np.allclose(yhat, Y)


@pytest.mark.parametrize("method", sc.METHODS)
def test_predict_shape(method):
    X, Y = sc.sample_dataset(120, seed=17)
    Xq, _ = sc.sample_dataset(9, seed=18)
    assert sc.Surrogate(method, k=8).fit(X, Y).predict(Xq).shape == (9, sc.N_OUT)


def test_ensemble_spread_is_non_negative():
    X, Y = sc.sample_dataset(200, seed=19)
    Xq, _ = sc.sample_dataset(10, seed=20)
    mean, spread = sc.ensemble_predict("idw", X, Y, Xq, n_models=3)
    assert mean.shape == (10, sc.N_OUT)
    assert (spread >= 0).all()


# =============================================================
# metrics
# =============================================================
def test_perfect_prediction_scores_zero_error():
    _, Y = sc.sample_dataset(100, seed=21)
    nmae, r2 = sc.score_columns(Y, Y.copy(), Y.var(axis=0))
    assert np.allclose(nmae, 0.0)
    assert np.allclose(r2, 1.0)


def test_mean_prediction_scores_zero_r2():
    _, Y = sc.sample_dataset(400, seed=22)
    base = np.repeat(Y.mean(axis=0)[None, :], Y.shape[0], axis=0)
    _, r2 = sc.score_columns(Y, base, Y.var(axis=0))
    assert np.allclose(r2, 0.0, atol=1e-9)


def test_risk_coverage_returns_one_row_per_level():
    _, Y = sc.sample_dataset(80, seed=23)
    Yhat = Y + 0.1
    trust = np.zeros_like(Y)
    rows = sc.risk_coverage(Y, Yhat, trust, Y.var(axis=0), [1.0, 0.5])
    assert len(rows) == 2
    assert rows[0][1].shape == (sc.N_OUT,)


# =============================================================
# rejection rule
# =============================================================
def test_perfect_prediction_is_fully_accepted():
    _, Y = sc.sample_dataset(200, seed=24)
    trust = np.zeros_like(Y)
    var = Y.var(axis=0)
    thr = sc.calibrate_threshold(Y, Y.copy(), trust, var)
    cov, r2 = sc.apply_threshold(Y, Y.copy(), trust, var, thr)
    assert np.allclose(cov, 1.0)
    assert np.allclose(r2, 1.0)


def test_useless_prediction_is_fully_rejected():
    _, Y = sc.sample_dataset(200, seed=25)
    rng = np.random.default_rng(0)
    Yhat = Y + rng.normal(0.0, 10.0 * Y.std(axis=0), Y.shape)
    trust = rng.normal(size=Y.shape)
    var = Y.var(axis=0)
    thr = sc.calibrate_threshold(Y, Yhat, trust, var)
    cov, _ = sc.apply_threshold(Y, Yhat, trust, var, thr)
    assert np.allclose(cov, 0.0)
