"""Self-implemented special functions and intervals. numpy only. python3 -I."""
import math

# ---------- regularized incomplete beta ----------
def _betacf(a, b, x):
    MAXIT = 400
    EPS = 3e-16
    FPMIN = 1e-300
    qab = a + b
    qap = a + 1.0
    qam = a - 1.0
    c = 1.0
    dd = 1.0 - qab * x / qap
    if abs(dd) < FPMIN:
        dd = FPMIN
    dd = 1.0 / dd
    h = dd
    for m in range(1, MAXIT + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        dd = 1.0 + aa * dd
        if abs(dd) < FPMIN:
            dd = FPMIN
        c = 1.0 + aa / c
        if abs(c) < FPMIN:
            c = FPMIN
        dd = 1.0 / dd
        h *= dd * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        dd = 1.0 + aa * dd
        if abs(dd) < FPMIN:
            dd = FPMIN
        c = 1.0 + aa / c
        if abs(c) < FPMIN:
            c = FPMIN
        dd = 1.0 / dd
        de = dd * c
        h *= de
        if abs(de - 1.0) < EPS:
            break
    return h

def betai(a, b, x):
    """Regularized incomplete beta I_x(a,b)."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    lbeta = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
    bt = math.exp(lbeta + a * math.log(x) + b * math.log1p(-x))
    if x < (a + 1.0) / (a + b + 2.0):
        return bt * _betacf(a, b, x) / a
    else:
        return 1.0 - bt * _betacf(b, a, 1.0 - x) / b

def beta_quantile(p, a, b):
    """Inverse of I_x(a,b) by bisection."""
    if p <= 0.0:
        return 0.0
    if p >= 1.0:
        return 1.0
    lo, hi = 0.0, 1.0
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if betai(a, b, mid) < p:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)

# ---------- incomplete gamma / chi-square ----------
def gammp(a, x):
    """Regularized lower incomplete gamma P(a,x)."""
    if x <= 0.0:
        return 0.0
    if x < a + 1.0:
        # series
        ap = a
        s = 1.0 / a
        d = s
        for _ in range(1000):
            ap += 1.0
            d *= x / ap
            s += d
            if abs(d) < abs(s) * 3e-16:
                break
        return s * math.exp(-x + a * math.log(x) - math.lgamma(a))
    else:
        # continued fraction for Q, return 1-Q
        FPMIN = 1e-300
        b = x + 1.0 - a
        c = 1.0 / FPMIN
        d = 1.0 / b
        h = d
        for i in range(1, 1000):
            an = -i * (i - a)
            b += 2.0
            d = an * d + b
            if abs(d) < FPMIN:
                d = FPMIN
            c = b + an / c
            if abs(c) < FPMIN:
                c = FPMIN
            d = 1.0 / d
            de = d * c
            h *= de
            if abs(de - 1.0) < 3e-16:
                break
        q = math.exp(-x + a * math.log(x) - math.lgamma(a)) * h
        return 1.0 - q

def chi2_quantile(p, k):
    """Inverse CDF of chi-square with k dof via bisection on gammp(k/2, x/2)."""
    if p <= 0.0:
        return 0.0
    a = k / 2.0
    lo, hi = 0.0, 1.0
    while gammp(a, hi / 2.0) < p:
        hi *= 2.0
        if hi > 1e12:
            break
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if gammp(a, mid / 2.0) < p:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)

def garwood(k, exposure, alpha=0.05):
    """Exact two-sided Poisson (Garwood) CI for rate = count/exposure.
    lower = chi2_{alpha/2}(2k)/2 / exposure ; upper = chi2_{1-alpha/2}(2k+2)/2 / exposure."""
    if k == 0:
        lo = 0.0
    else:
        lo = chi2_quantile(alpha / 2.0, 2 * k) / 2.0 / exposure
    hi = chi2_quantile(1.0 - alpha / 2.0, 2 * k + 2) / 2.0 / exposure
    return lo, hi

def cp_lower(k, n, alpha=0.05):
    """Clopper-Pearson lower bound for a binomial proportion."""
    if k == 0:
        return 0.0
    return beta_quantile(alpha / 2.0, k, n - k + 1)

def cp_upper(k, n, alpha=0.05):
    if k == n:
        return 1.0
    return beta_quantile(1.0 - alpha / 2.0, k + 1, n - k)

if __name__ == "__main__":
    # Clopper-Pearson lower bound all successes = 0.025^(1/m)
    for m in (3, 6, 18, 36):
        v = cp_lower(m, m)
        print(f"CP lower k=n={m}: {v:.5f}  expect {0.025**(1.0/m):.5f}")
    # Garwood k=0 upper per unit exposure
    lo, hi = garwood(0, 1.0)
    print(f"Garwood k=0: [{lo:.4f},{hi:.4f}] expect upper 3.6889")
    lo, hi = garwood(10, 1.0)
    print(f"Garwood k=10: [{lo:.4f},{hi:.4f}] expect [4.7954,18.3904]")
