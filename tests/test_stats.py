from engine.metrics.stats import mcnemar_exact, paired_mcnemar, rate, wilson_ci


def test_wilson_bounds():
    lo, hi = wilson_ci(0, 10)
    assert 0 <= lo <= hi <= 1
    assert lo == 0
    lo, hi = wilson_ci(10, 10)
    assert lo > 0.6 and hi > 0.99
    assert wilson_ci(0, 0) == (0.0, 0.0)


def test_rates():
    p, k, n = rate([True, False, True, True])
    assert (p, k, n) == (0.75, 3, 4)
    assert rate([]) == (0.0, 0, 0)


def test_mcnemar_exact_symmetric_and_significant():
    assert mcnemar_exact(0, 0) == 1.0
    assert abs(mcnemar_exact(3, 3) - 1.0) < 1e-9
    assert mcnemar_exact(10, 0) < 0.01


def test_paired_mcnemar_pairs():
    pairs = [(True, False), (True, False), (False, True), (True, True)]
    out = paired_mcnemar(pairs)
    assert out["before_only"] == 2
    assert out["after_only"] == 1
    assert 0 <= out["p_value"] <= 1
