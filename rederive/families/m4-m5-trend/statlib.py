"""Self-implemented statistical quantiles for the re-derivation.
numpy only; beta/gamma quantiles via math + bisection. Tested against COMMON.md values.
"""
import math


def _betacf(a, b, x):
    # continued fraction for incomplete beta (Numerical Recipes)
    MAXIT = 500
    EPS = 3.0e-16
    FPMIN = 1.0e-300
    qab = a + b
    qap = a + 1.0
    qam = a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < FPMIN:
        d = FPMIN
    d = 1.0 / d
    h = d
    for m in range(1, MAXIT + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < FPMIN:
            d = FPMIN
        c = 1.0 + aa / c
        if abs(c) < FPMIN:
            c = FPMIN
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < FPMIN:
            d = FPMIN
        c = 1.0 + aa / c
        if abs(c) < FPMIN:
            c = FPMIN
        d = 1.0 / d
        de = d * c
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
    bt = math.exp(lbeta + a * math.log(x) + b * math.log(1.0 - x))
    if x < (a + 1.0) / (a + b + 2.0):
        return bt * _betacf(a, b, x) / a
    else:
        return 1.0 - bt * _betacf(b, a, 1.0 - x) / b


def beta_quantile(p, a, b):
    """Inverse of regularized incomplete beta via bisection."""
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
    """Two-sided Clopper-Pearson for a binomial proportion. k may be fractional.
    Returns (lower, upper). Uses beta quantiles."""
    if n <= 0:
        return (0.0, 1.0)
    if k <= 0:
        lo = 0.0
    else:
        lo = beta_quantile(alpha / 2.0, k, n - k + 1.0)
    if k >= n:
        hi = 1.0
    else:
        hi = beta_quantile(1.0 - alpha / 2.0, k + 1.0, n - k)
    return (lo, hi)


# ---- incomplete gamma for Poisson/Garwood ----
def _gammp_series(a, x):
    EPS = 3.0e-16
    ap = a
    s = 1.0 / a
    dl = s
    for _ in range(1000):
        ap += 1.0
        dl *= x / ap
        s += dl
        if abs(dl) < abs(s) * EPS:
            break
    return s * math.exp(-x + a * math.log(x) - math.lgamma(a))


def _gammq_cf(a, x):
    FPMIN = 1.0e-300
    EPS = 3.0e-16
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
        if abs(de - 1.0) < EPS:
            break
    return math.exp(-x + a * math.log(x) - math.lgamma(a)) * h


def gammp(a, x):
    """Lower regularized incomplete gamma P(a,x)."""
    if x <= 0.0:
        return 0.0
    if x < a + 1.0:
        return _gammp_series(a, x)
    else:
        return 1.0 - _gammq_cf(a, x)


def chi2_quantile(p, nu):
    """Inverse chi-square CDF via bisection on gammp (chi2 cdf = P(nu/2, x/2))."""
    if p <= 0.0:
        return 0.0
    if p >= 1.0:
        return float('inf')
    a = nu / 2.0
    lo, hi = 0.0, 1.0
    while gammp(a, hi / 2.0) < p:
        hi *= 2.0
        if hi > 1e8:
            break
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if gammp(a, mid / 2.0) < p:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def garwood(k, exposure=1.0, alpha=0.05):
    """Garwood exact two-sided Poisson interval for rate = k/exposure.
    lower = chi2_{alpha/2}(2k)/2 ; upper = chi2_{1-alpha/2}(2k+2)/2, divided by exposure."""
    if k <= 0:
        lo = 0.0
    else:
        lo = chi2_quantile(alpha / 2.0, 2.0 * k) / 2.0
    hi = chi2_quantile(1.0 - alpha / 2.0, 2.0 * k + 2.0) / 2.0
    return (lo / exposure, hi / exposure)


if __name__ == '__main__':
    # Tests from COMMON.md
    print('Clopper-Pearson lower with all successes = 0.025^(1/m):')
    for m in (3, 6, 18, 36):
        lo, hi = clopper_pearson(m, m)
        print(f'  m={m}: lower={lo:.5f}  expected {0.025**(1.0/m):.5f}')
    print('Garwood upper at k=0 (per unit exposure):', garwood(0, 1.0))
    print('  expected upper 3.6889')
    print('Garwood at k=10:', garwood(10, 1.0))
    print('  expected [4.7954, 18.3904]')
