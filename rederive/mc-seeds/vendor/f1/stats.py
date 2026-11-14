"""Self-implemented beta / gamma quantiles for Clopper-Pearson and Garwood intervals.
numpy only; math.lgamma. python3 -I.
"""
import math

# ---- regularized incomplete beta I_x(a,b) via Lentz continued fraction ----
def _betacf(a, b, x):
    MAXIT, EPS, FPMIN = 2000, 3.0e-15, 1.0e-300
    qab, qap, qam = a + b, a + 1.0, a - 1.0
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


def betainc(a, b, x):
    """Regularized incomplete beta I_x(a,b)."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    lbeta = math.lgamma(a) + math.lgamma(b) - math.lgamma(a + b)
    bt = math.exp(a * math.log(x) + b * math.log(1.0 - x) - lbeta)
    if x < (a + 1.0) / (a + b + 2.0):
        return bt * _betacf(a, b, x) / a
    return 1.0 - bt * _betacf(b, a, 1.0 - x) / b


def betainv(p, a, b):
    """Inverse regularized incomplete beta: find x with I_x(a,b)=p, by bisection."""
    if p <= 0.0:
        return 0.0
    if p >= 1.0:
        return 1.0
    lo, hi = 0.0, 1.0
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if betainc(a, b, mid) < p:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


# ---- lower regularized incomplete gamma P(a,x) ----
def _gammp_series(a, x):
    EPS = 3.0e-15
    ap = a
    s = 1.0 / a
    de = s
    for _ in range(2000):
        ap += 1.0
        de *= x / ap
        s += de
        if abs(de) < abs(s) * EPS:
            break
    return s * math.exp(-x + a * math.log(x) - math.lgamma(a))


def _gammq_cf(a, x):
    FPMIN, EPS = 1.0e-300, 3.0e-15
    b = x + 1.0 - a
    c = 1.0 / FPMIN
    d = 1.0 / b
    h = d
    for i in range(1, 2000):
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
    return h * math.exp(-x + a * math.log(x) - math.lgamma(a))


def gammp(a, x):
    if x <= 0.0:
        return 0.0
    if x < a + 1.0:
        return _gammp_series(a, x)
    return 1.0 - _gammq_cf(a, x)


def gammainv(p, a):
    """x such that P(a,x)=p."""
    if p <= 0.0:
        return 0.0
    lo, hi = 0.0, max(1.0, a)
    while gammp(a, hi) < p:
        hi *= 2.0
        if hi > 1e12:
            break
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if gammp(a, mid) < p:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def chi2inv(p, df):
    return 2.0 * gammainv(p, df / 2.0)


# ---- Clopper-Pearson (two-sided 95%) for k successes of m trials (k may be fractional) ----
def clopper_pearson(k, m, alpha=0.05):
    if m <= 0:
        return (0.0, 1.0)
    lo = 0.0 if k <= 0 else betainv(alpha / 2.0, k, m - k + 1.0)
    hi = 1.0 if k >= m else betainv(1.0 - alpha / 2.0, k + 1.0, m - k)
    return (lo, hi)


# ---- Garwood exact two-sided 95% Poisson interval on count k over exposure E ----
def garwood(k, E, alpha=0.05):
    lo = 0.0 if k <= 0 else 0.5 * chi2inv(alpha / 2.0, 2 * k) / E
    hi = 0.5 * chi2inv(1.0 - alpha / 2.0, 2 * k + 2) / E
    return (lo, hi)


if __name__ == '__main__':
    # tests from COMMON.md
    for m, exp in [(3, 0.29240), (6, 0.54074), (18, 0.81470), (36, 0.90261)]:
        got = clopper_pearson(m, m)[0]
        print(f'CP lower all-success m={m}: {got:.5f} exp {exp} ok={abs(got-exp)<1e-4}')
        print(f'   0.025^(1/m) = {0.025**(1/m):.5f}')
    g0 = garwood(0, 1.0)
    print(f'Garwood k=0 upper per unit: {g0[1]:.4f} exp 3.6889 ok={abs(g0[1]-3.6889)<1e-3}')
    g10 = garwood(10, 1.0)
    print(f'Garwood k=10: [{g10[0]:.4f}, {g10[1]:.4f}] exp [4.7954, 18.3904]')
