"""Beta / gamma quantiles, Clopper-Pearson and Garwood intervals, implemented with math only.
Run `python3 -I statlib.py` to self-test against the values pinned in COMMON.md.
"""
import math


def _betacf(a, b, x):
    # Continued fraction for the incomplete beta (Numerical Recipes).
    MAXIT, EPS, FPMIN = 1000, 3.0e-15, 1.0e-300
    qab, qap, qam = a + b, a + 1.0, a - 1.0
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


def clopper_pearson(k, n, alpha=0.05):
    """Two-sided CP interval for a binomial proportion. k successes of n (k, n may be fractional)."""
    if n <= 0:
        return (0.0, 1.0)
    lo = 0.0 if k <= 0 else beta_quantile(alpha / 2.0, k, n - k + 1.0)
    hi = 1.0 if k >= n else beta_quantile(1.0 - alpha / 2.0, k + 1.0, n - k)
    return (lo, hi)


# ---- incomplete gamma for Garwood (Poisson) ----

def _gammp(a, x):
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
            if abs(d) < abs(s) * 1.0e-15:
                break
        return s * math.exp(-x + a * math.log(x) - math.lgamma(a))
    else:
        # continued fraction for Q, then P = 1 - Q
        FPMIN = 1.0e-300
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
            if abs(de - 1.0) < 1.0e-15:
                break
        q = math.exp(-x + a * math.log(x) - math.lgamma(a)) * h
        return 1.0 - q


def chi2_quantile(p, dof):
    """Inverse chi-square CDF via bisection on the regularized lower gamma."""
    if p <= 0.0:
        return 0.0
    a = dof / 2.0
    lo, hi = 0.0, 1.0
    while _gammp(a, hi / 2.0) < p:
        hi *= 2.0
        if hi > 1e12:
            break
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if _gammp(a, mid / 2.0) < p:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def garwood(k, exposure=1.0, alpha=0.05):
    """Exact two-sided Poisson (Garwood) interval on count k over exposure, per unit exposure."""
    lo = 0.0 if k == 0 else 0.5 * chi2_quantile(alpha / 2.0, 2 * k) / exposure
    hi = 0.5 * chi2_quantile(1.0 - alpha / 2.0, 2 * (k + 1)) / exposure
    return (lo, hi)


if __name__ == '__main__':
    print('CP lower bound, all successes = 0.025^(1/m):')
    for m in (3, 6, 18, 36):
        lo, hi = clopper_pearson(m, m)
        print(f'  m={m}: lo={lo:.5f}  expected {0.025 ** (1.0 / m):.5f}')
    print('Garwood upper at k=0 (per unit exposure):', garwood(0, 1.0)[1], 'expected 3.6889')
    print('Garwood at k=10:', garwood(10, 1.0), 'expected [4.7954, 18.3904]')
