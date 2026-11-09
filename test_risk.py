"""Unit tests for the explainable risk engine (pure functions, no server needed).
Run: python -m unittest -v"""
import unittest

from risk import _level, _note_hits, _trend, assess


def r(hr=76, spo2=97, sbp=120, temp=36.8, dbp=78):
    return dict(hr=hr, spo2=spo2, sbp=sbp, temp=temp, dbp=dbp)


def series(n, **end):
    """n readings drifting from a stable baseline to the given end values."""
    base = r()
    out = []
    for i in range(n):
        f = i / (n - 1)
        out.append({k: base[k] + (end.get(k, base[k]) - base[k]) * f for k in base})
    return out


class RiskEngine(unittest.TestCase):
    def test_no_data_is_low_and_says_so(self):
        j = assess([], [])
        self.assertEqual((j["level"], j["score"]), ("Low", 0))
        self.assertIn("Waiting", j["reasons"][0])

    def test_normal_vitals_are_low_with_a_reason(self):
        j = assess([r()], [])
        self.assertEqual((j["level"], j["score"]), ("Low", 0))
        self.assertEqual(j["reasons"], ["Vitals within expected range"])

    def test_every_point_is_explained(self):
        j = assess([r(hr=118, spo2=88, sbp=96, temp=38.7)], [])
        self.assertEqual(j["pts"], {"HR": 2, "SpO2": 3, "SBP": 2, "Temp": 1})
        shown = sum(int(x.split("(+")[1].rstrip(")")) for x in j["reasons"] if "(+" in x)
        self.assertEqual(shown, j["score"])  # the reasons add up to the score

    def test_spo2_band_edges(self):
        pts = lambda v: assess([r(spo2=v)], [])["pts"]["SpO2"]  # noqa: E731
        self.assertEqual([pts(91), pts(92), pts(93), pts(94), pts(95), pts(96)], [3, 2, 2, 1, 1, 0])

    def test_hr_both_directions_are_flagged(self):
        pts = lambda v: assess([r(hr=v)], [])["pts"]["HR"]  # noqa: E731
        self.assertEqual([pts(38), pts(45), pts(70), pts(100), pts(120), pts(140)], [3, 1, 0, 1, 2, 3])

    def test_one_critical_vital_alone_is_medium(self):
        j = assess([r(spo2=90)], [])
        self.assertEqual((j["score"], j["level"]), (3, "Medium"))

    def test_score_six_or_more_is_high(self):
        self.assertEqual(assess([r(hr=135, spo2=88, sbp=85, temp=39.5)], [])["level"], "High")

    def test_trend_needs_enough_history(self):
        self.assertEqual(_trend(series(11, spo2=85)), (0, []))

    def test_falling_spo2_and_rising_hr_raise_early_warning(self):
        j = assess(series(24, spo2=93, hr=96), [])
        self.assertTrue(j["early_warning"])
        self.assertIn(j["level"], ("Medium", "High"))
        self.assertTrue(any("trending down" in x for x in j["reasons"]))
        self.assertTrue(any("possible deterioration" in x for x in j["reasons"]))  # hedged wording

    def test_steady_vitals_never_raise_early_warning(self):
        self.assertFalse(assess(series(24), [])["early_warning"])

    def test_hindi_and_english_notes_add_points_capped_at_three(self):
        self.assertEqual(_note_hits(["saans phool rahi hai", "चक्कर", "I feel weak"]), ["breathlessness", "dizziness", "weakness/confusion"])
        many = ["breathless dizzy fever vomit weak chest pain"]
        self.assertEqual(len(_note_hits(many)), 3)
        self.assertEqual(assess([r()], many)["score"], 3)

    def test_level_mapping(self):
        self.assertEqual([_level(0, {}, False), _level(3, {}, False), _level(6, {}, False)], ["Low", "Medium", "High"])
        self.assertEqual(_level(1, {}, True), "Medium")


if __name__ == "__main__":
    unittest.main()
