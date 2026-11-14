"""Interval helpers (METHOD-b §4.0), pure Python: the regularized incomplete beta function, its
inverse, Clopper–Pearson limits with fractional successes, and Kish's effective count.

Clopper–Pearson with x successes in n trials (x, n real, 0 <= x <= n, n > 0):
  lower = 0                              if x == 0, else BetaInv(alpha/2;     x,     n - x + 1)
  upper = 1                              if x == n, else BetaInv(1 - alpha/2; x + 1, n - x)
At x = n the lower limit is (alpha/2)^(1/n); at x = 0 the upper limit is 1 - (alpha/2)^(1/n).
"""
import math

ALPHA = 0.05


def _betacf(a, b, x, itmax=500, eps=3e-16):
    # continued fraction for the incomplete beta (modified Lentz), Numerical Recipes 6.4
    tiny = 1e-300
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c, d = 1.0, 1.0 - qab * x / qap
    d = 1.0 / (d if abs(d) > tiny else tiny)
    h = d
    for m in range(1, itmax + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        d = 1.0 / (d if abs(d) > tiny else tiny)
        c = 1.0 + aa / c
        c = c if abs(c) > tiny else tiny
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        d = 1.0 / (d if abs(d) > tiny else tiny)
        c = 1.0 + aa / c
        c = c if abs(c) > tiny else tiny
        de = d * c
        h *= de
        if abs(de - 1.0) < eps:
            return h
    raise ArithmeticError('betacf did not converge')


def betainc(a, b, x):
    """Regularized incomplete beta I_x(a, b), a > 0, b > 0, 0 <= x <= 1."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    lbt = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log1p(-x)
    if x < (a + 1.0) / (a + b + 2.0):
        return math.exp(lbt) * _betacf(a, b, x) / a
    return 1.0 - math.exp(lbt) * _betacf(b, a, 1.0 - x) / b


def betainv(p, a, b, tol=1e-12):
    """x with I_x(a, b) = p, by bisection (I is increasing in x)."""
    if p <= 0.0:
        return 0.0
    if p >= 1.0:
        return 1.0
    lo, hi = 0.0, 1.0
    for _ in range(200):
        mid = (lo + hi) / 2
        if betainc(a, b, mid) < p:
            lo = mid
        else:
            hi = mid
        if hi - lo < tol:
            break
    return (lo + hi) / 2


def clopper_pearson(x, n, alpha=ALPHA):
    if n <= 0:
        raise ValueError('n must be positive')
    x = min(max(x, 0.0), n)
    lower = 0.0 if x <= 0 else betainv(alpha / 2, x, n - x + 1)
    upper = 1.0 if x >= n else betainv(1 - alpha / 2, x + 1, n - x)
    return lower, upper


def kish(weights):
    """Kish's effective count (sum w)^2 / sum w^2 over positive weights; 0 if none."""
    ws = [w for w in weights if w > 0]
    s, s2 = sum(ws), sum(w * w for w in ws)
    return (s * s / s2) if s2 > 0 else 0.0


def window_cp(share, window_denominators, alpha=ALPHA):
    """Window-level Clopper–Pearson for a share within one stratum (METHOD §4.0): trials are the
    effective number of occupied windows, m_eff = kish(window denominators); successes share * m_eff."""
    m = kish(window_denominators)
    if m <= 0:
        return None
    return clopper_pearson(share * m, m, alpha)
