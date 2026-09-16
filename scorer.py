"""70-bit binary surrogate scorer.

X: (N, 70) binary  ->  Y: (N, 6) scalars

1) deterministic ground truth with many non-differentiable points
2) random sampling of a 7000-point training set
3) three surrogates built from those 7000 points
4) risk-coverage scoring with a calibrated "data lack" rejection path
"""

import numpy as np

N_BITS = 70
N_OUT = 6
N_TRAIN = 7000
N_TEST = 2000
GT_SEED = 20240917
TRAIN_SEED = 1
TEST_SEED = 2
N_ENSEMBLE = 5
SUBSAMPLE = 0.8
TARGET_R2 = 0.5
METHODS = ("idw", "expknn", "bitint")


# =============================================================
# ground-truth constants (frozen by GT_SEED)
# =============================================================
_g = np.random.default_rng(GT_SEED)
_IU = np.triu_indices(N_BITS, k=1)
_sel = _g.choice(_IU[0].shape[0], size=60, replace=False)
_PI = _IU[0][_sel]
_PJ = _IU[1][_sel]
_W0 = _g.normal(0.0, 1.0, N_BITS)
_WP = _g.normal(0.0, 1.5, 60)
_WB = _g.normal(0.0, 4.0, 7)
_WG = _g.normal(0.0, 1.0, (10, 7))
_W5 = _g.uniform(0.5, 2.5, N_BITS)


# =============================================================
# ground truth
# =============================================================
def ground_truth(X):
    X = np.asarray(X, dtype=np.float64)
    n = X.shape[0]

    s0 = X @ _W0
    y0 = np.abs(s0 - 3.0) + 0.5 * np.abs(s0 + 5.0) - 0.3 * np.abs(s0 - 11.0)

    y1 = np.clip((X[:, _PI] * X[:, _PJ]) @ _WP, -8.0, 14.0)

    parity = np.mod(X.reshape(n, 7, 10).sum(axis=2), 2.0)
    y2 = parity @ _WB

    cum = np.zeros((n, N_BITS + 1))
    cum[:, 1:] = np.cumsum(X, axis=1)
    win = cum[:, 7:] - cum[:, :-7]
    y3 = 1.7 * win.max(axis=1) - win.min(axis=1)

    grp = (X.reshape(n, 10, 7) * _WG).sum(axis=2)
    y4 = grp.max(axis=1) - grp.min(axis=1)

    y5 = np.abs(np.mod(X @ _W5, 9.0) - 4.5)

    return np.stack([y0, y1, y2, y3, y4, y5], axis=1)


# =============================================================
# sampling
# =============================================================
def sample_dataset(n_rows, seed):
    rng = np.random.default_rng(seed)
    X = rng.integers(0, 2, size=(n_rows, N_BITS), dtype=np.int8)
    return X, ground_truth(X)


# =============================================================
# hamming distance
# =============================================================
def hamming_matrix(A, B):
    A = np.asarray(A, dtype=np.float32)
    B = np.asarray(B, dtype=np.float32)
    return A.sum(1)[:, None] + B.sum(1)[None, :] - 2.0 * (A @ B.T)


# =============================================================
# bit-intersection features: [1, bits, pairwise AND]
# =============================================================
def bit_features(X):
    X = np.asarray(X, dtype=np.float32)
    inter = X[:, _IU[0]] * X[:, _IU[1]]
    ones = np.ones((X.shape[0], 1), dtype=np.float32)
    return np.concatenate([ones, X, inter], axis=1)


# =============================================================
# surrogate
# =============================================================
class Surrogate:
    def __init__(self, method, k=48, tau=3.0, ridge=30.0):
        if method not in METHODS:
            raise ValueError(f"unknown method: {method}")
        self.method = method
        self.k = k
        self.tau = tau
        self.ridge = ridge

    def fit(self, X, Y):
        self.X = np.asarray(X, dtype=np.int8)
        self.Y = np.asarray(Y, dtype=np.float64)
        if self.method == "bitint":
            F = bit_features(self.X)
            gram = (F.T @ F).astype(np.float64)
            gram[np.diag_indices_from(gram)] += self.ridge
            self.coef = np.linalg.solve(gram, F.T.astype(np.float64) @ self.Y)
        return self

    def neighbors(self, Xq):
        D = hamming_matrix(Xq, self.X)
        idx = np.argpartition(D, self.k, axis=1)[:, : self.k]
        return idx, np.take_along_axis(D, idx, axis=1)

    def predict(self, Xq):
        if self.method == "bitint":
            return bit_features(Xq) @ self.coef
        idx, d = self.neighbors(Xq)
        if self.method == "idw":
            w = 1.0 / (d + 0.5)
        else:
            w = np.exp(-(d - d.min(axis=1, keepdims=True)) / self.tau)
        w = w / w.sum(axis=1, keepdims=True)
        return np.einsum("mk,mkc->mc", w, self.Y[idx])


# =============================================================
# ensemble disagreement: how hard the data pins each prediction down
# =============================================================
def ensemble_predict(method, X, Y, Xq, n_models=N_ENSEMBLE, seed=0):
    rng = np.random.default_rng(seed)
    n_keep = int(SUBSAMPLE * X.shape[0])
    preds = []
    for _ in range(n_models):
        sel = rng.choice(X.shape[0], size=n_keep, replace=False)
        preds.append(Surrogate(method).fit(X[sel], Y[sel]).predict(Xq))
    stacked = np.stack(preds)
    return stacked.mean(axis=0), stacked.std(axis=0)


# =============================================================
# metrics against a fixed reference scale
# =============================================================
def score_columns(Y, Yhat, ref_var):
    nmae = np.abs(Y - Yhat).mean(axis=0) / np.sqrt(ref_var)
    mse = ((Y - Yhat) ** 2).mean(axis=0)
    return nmae, 1.0 - mse / ref_var


# =============================================================
# risk-coverage: score only the most-trusted fraction, per output
# =============================================================
def risk_coverage(Y, Yhat, trust, ref_var, levels):
    n = Y.shape[0]
    rows = []
    for c in levels:
        keep = max(1, int(round(c * n)))
        nmae = np.zeros(N_OUT)
        r2 = np.zeros(N_OUT)
        for j in range(N_OUT):
            take = np.argsort(-trust[:, j])[:keep]
            err = Y[take, j] - Yhat[take, j]
            nmae[j] = np.abs(err).mean() / np.sqrt(ref_var[j])
            r2[j] = 1.0 - (err**2).mean() / ref_var[j]
        rows.append((c, nmae, r2))
    return rows


# =============================================================
# accept/reject rule calibrated on a held-out split
# =============================================================
def calibrate_threshold(Y, Yhat, trust, ref_var, target_r2=TARGET_R2):
    n = Y.shape[0]
    thresholds = np.full(N_OUT, np.inf)
    for j in range(N_OUT):
        order = np.argsort(-trust[:, j])
        err2 = (Y[order, j] - Yhat[order, j]) ** 2
        running_r2 = 1.0 - np.cumsum(err2) / (np.arange(1, n + 1) * ref_var[j])
        ok = np.flatnonzero(running_r2 >= target_r2)
        if ok.size > 0:
            thresholds[j] = trust[order[ok[-1]], j]
    return thresholds


def apply_threshold(Y, Yhat, trust, ref_var, thresholds):
    coverage = np.zeros(N_OUT)
    r2 = np.full(N_OUT, np.nan)
    for j in range(N_OUT):
        take = np.flatnonzero(trust[:, j] >= thresholds[j])
        coverage[j] = take.size / Y.shape[0]
        if take.size > 0:
            err = Y[take, j] - Yhat[take, j]
            r2[j] = 1.0 - (err**2).mean() / ref_var[j]
    return coverage, r2


# =============================================================
# report
# =============================================================
def main():
    Xtr, Ytr = sample_dataset(N_TRAIN, TRAIN_SEED)
    Xte, Yte = sample_dataset(N_TEST, TEST_SEED)
    half = N_TEST // 2
    ref_var = Yte.var(axis=0)

    print(f"train {Xtr.shape}  calib {half}  eval {N_TEST - half}")
    print(
        f"popcount train: mean {Xtr.sum(1).mean():.1f} "
        f"min {Xtr.sum(1).min()} max {Xtr.sum(1).max()}"
    )

    base = np.repeat(Ytr.mean(axis=0)[None, :], N_TEST - half, axis=0)
    bn, br = score_columns(Yte[half:], base, ref_var)
    print(f"\nbaseline (train mean)   nMAE {bn.mean():.3f}   R2 {br.mean():+.3f}")

    levels = [1.0, 0.8, 0.5, 0.2, 0.05]
    for method in METHODS:
        yhat, spread = ensemble_predict(method, Xtr, Ytr, Xte)
        trust = -spread / np.sqrt(ref_var)
        nmae, r2 = score_columns(Yte[half:], yhat[half:], ref_var)

        print(f"\n=== {method} ===")
        print("per-output nMAE " + "  ".join(f"y{i} {nmae[i]:.3f}" for i in range(N_OUT)))
        print("per-output R2   " + "  ".join(f"y{i} {r2[i]:+.3f}" for i in range(N_OUT)))

        print("coverage (R2)  " + " ".join(f"{'y' + str(i):>6}" for i in range(N_OUT)))
        for cov, _, rr in risk_coverage(Yte[half:], yhat[half:], trust[half:], ref_var, levels):
            print(f"     {cov * 100:4.0f}%     " + " ".join(f"{v:+.3f}" for v in rr))

        thr = calibrate_threshold(Yte[:half], yhat[:half], trust[:half], ref_var)
        cov, acc_r2 = apply_threshold(Yte[half:], yhat[half:], trust[half:], ref_var, thr)
        print(
            f"accept@R2>={TARGET_R2}  "
            + "  ".join(f"y{i} {cov[i] * 100:3.0f}%/{acc_r2[i]:+.2f}" for i in range(N_OUT))
        )


if __name__ == "__main__":
    main()
