"""70-bit binary surrogate scorer.

X: (N, 70) binary  ->  Y: (N, 6) scalars

1) deterministic ground truth with many non-differentiable points
2) random sampling of a 7000-point training set
3) three surrogates built from those 7000 points
4) risk-coverage scoring with an explicit "data lack" rejection path
"""

import numpy as np

N_BITS = 70
N_OUT = 6
N_TRAIN = 7000
N_TEST = 2000
GT_SEED = 20240917
TRAIN_SEED = 1
TEST_SEED = 2


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
        self.method = method
        self.k = k
        self.tau = tau
        self.ridge = ridge

    def fit(self, X, Y):
        self.X = np.asarray(X, dtype=np.int8)
        self.Y = np.asarray(Y, dtype=np.float64)
        self.y_mean = self.Y.mean(axis=0)
        self.y_std = self.Y.std(axis=0)
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

    def trust(self, idx, d):
        spread = (self.Y[idx].std(axis=1) / self.y_std).mean(axis=1)
        return 1.0 - spread - d.min(axis=1) / N_BITS

    def predict(self, Xq):
        idx, d = self.neighbors(Xq)
        if self.method == "bitint":
            yhat = bit_features(Xq) @ self.coef
        else:
            if self.method == "idw":
                w = 1.0 / (d + 0.5)
            else:
                w = np.exp(-(d - d.min(axis=1, keepdims=True)) / self.tau)
            w = w / w.sum(axis=1, keepdims=True)
            yhat = np.einsum("mk,mkc->mc", w, self.Y[idx])
        return yhat, self.trust(idx, d)


# =============================================================
# metrics against a fixed reference scale
# =============================================================
def score_columns(Y, Yhat, ref_var):
    nmae = np.abs(Y - Yhat).mean(axis=0) / np.sqrt(ref_var)
    mse = ((Y - Yhat) ** 2).mean(axis=0)
    return nmae, 1.0 - mse / ref_var


# =============================================================
# risk-coverage: score only the most-trusted fraction
# =============================================================
def risk_coverage(Y, Yhat, trust, ref_var, levels):
    order = np.argsort(-trust)
    rows = []
    for c in levels:
        take = order[: max(1, int(round(c * order.shape[0])))]
        nmae, r2 = score_columns(Y[take], Yhat[take], ref_var)
        rows.append((c, nmae.mean(), r2.mean()))
    return rows


# =============================================================
# report
# =============================================================
def main():
    Xtr, Ytr = sample_dataset(N_TRAIN, TRAIN_SEED)
    Xte, Yte = sample_dataset(N_TEST, TEST_SEED)
    ref_var = Yte.var(axis=0)

    print("train %s  test %s" % (Xtr.shape, Xte.shape))
    print("popcount train: mean %.1f  min %d  max %d"
          % (Xtr.sum(1).mean(), Xtr.sum(1).min(), Xtr.sum(1).max()))

    base = np.repeat(Ytr.mean(axis=0)[None, :], N_TEST, axis=0)
    bn, br = score_columns(Yte, base, ref_var)
    print("\nbaseline (train mean)   nMAE %.3f   R2 %+.3f" % (bn.mean(), br.mean()))

    levels = [1.0, 0.8, 0.5, 0.2, 0.05]
    for method in ["idw", "expknn", "bitint"]:
        model = Surrogate(method).fit(Xtr, Ytr)
        yhat, trust = model.predict(Xte)
        nmae, r2 = score_columns(Yte, yhat, ref_var)

        print("\n=== %s ===" % method)
        print("per-output nMAE " + "  ".join("y%d %.3f" % (i, nmae[i]) for i in range(N_OUT)))
        print("per-output R2   " + "  ".join("y%d %+.3f" % (i, r2[i]) for i in range(N_OUT)))
        print("coverage   nMAE     R2")
        for cov, m, r in risk_coverage(Yte, yhat, trust, ref_var, levels):
            print("  %4.0f%%   %.3f   %+.3f" % (cov * 100, m, r))


if __name__ == "__main__":
    main()
