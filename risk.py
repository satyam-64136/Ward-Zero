"""Transparent, explainable risk engine: NEWS2-style scoring + trend + note keywords.
Experimental prototype. NOT a medical device; no diagnosis."""

KEYWORDS = {  # English + romanized Hindi/Devanagari
    "breathlessness": ["breathless", "short of breath", "can't breathe", "cant breathe", "saans", "dum ghut", "सांस"],
    "chest pain": ["chest pain", "seene mein dard", "seene me dard", "सीने"],
    "dizziness": ["dizzy", "chakkar", "चक्कर"],
    "fever": ["fever", "bukhar", "बुखार"],
    "vomiting": ["vomit", "ulti", "उल्टी"],
    "weakness/confusion": ["confused", "weak", "kamzori", "behosh", "drowsy", "कमज़ोरी"],
}

def _band(v, bands):
    for _lo, hi, pts in bands:  # bands ascend; first hi >= v wins (no float gaps between bands)
        if v <= hi:
            return pts
    return 0

HR = [(0, 40, 3), (41, 50, 1), (51, 90, 0), (91, 110, 1), (111, 130, 2), (131, 999, 3)]
SPO2 = [(0, 91, 3), (91.01, 93, 2), (93.01, 95, 1), (95.01, 100, 0)]
SBP = [(0, 90, 3), (90.01, 100, 2), (100.01, 110, 1), (110.01, 219, 0), (219.01, 999, 3)]
TEMP = [(0, 35, 3), (35.01, 36, 1), (36.01, 38, 0), (38.01, 39, 1), (39.01, 50, 2)]

def _mean(xs):
    return sum(xs) / len(xs)

# name -> (bands, reading key, decimals, unit)
VITALS = {"HR": (HR, "hr", 0, " bpm"), "SpO2": (SPO2, "spo2", 1, "%"),
          "SBP": (SBP, "sbp", 0, " mmHg"), "Temp": (TEMP, "temp", 1, " °C")}

def _vitals(r):
    """Points per vital for the latest reading, with one readable reason per non-zero vital."""
    pts, reasons = {}, []
    for name, (bands, key, nd, unit) in VITALS.items():
        pts[name] = _band(r[key], bands)
        if pts[name]:
            shown = round(r[key]) if nd == 0 else round(r[key], nd)
            reasons.append(f"{name} {shown}{unit} (+{pts[name]})")
    return pts, reasons

def _trend(readings):
    """Proxy for 24-48h deterioration: first 6 vs last 6 readings of a 24-reading window."""
    w = readings[-24:]
    if len(w) < 12:
        return 0, []
    first, last = w[:6], w[-6:]
    avg = lambda rows, k: _mean([x[k] for x in rows])  # noqa: E731
    d = lambda k: avg(last, k) - avg(first, k)  # noqa: E731
    pts, why = 0, []
    if d("spo2") <= -3:
        pts += 2
        why.append(f"SpO2 trending down {avg(first, 'spo2'):.0f}→{avg(last, 'spo2'):.0f}%")
    if d("hr") >= 15:
        pts += 1
        why.append(f"Heart rate rising +{d('hr'):.0f} bpm")
    if d("sbp") <= -15:
        pts += 1
        why.append(f"Systolic BP falling {d('sbp'):.0f} mmHg")
    if d("temp") >= 0.8:
        pts += 1
        why.append(f"Temperature rising +{d('temp'):.1f} °C")
    return pts, why

def _note_hits(notes):
    """Symptom groups mentioned in recent caregiver notes (English + Hindi), at most 3 (+1 each)."""
    text = " ".join(notes).lower()
    return [label for label, kws in KEYWORDS.items() if any(k in text for k in kws)][:3]

def _level(score, pts, early):
    level = "High" if score >= 6 else "Medium" if (score >= 3 or 3 in pts.values()) else "Low"
    return "Medium" if early and level == "Low" else level

def assess(readings, notes):
    """readings: list of dicts (oldest->newest) with hr, spo2, sbp, temp. notes: list of strings."""
    if not readings:
        return {"level": "Low", "score": 0, "reasons": ["Waiting for sensor data…"], "early_warning": False, "pts": {}}
    pts, reasons = _vitals(readings[-1])
    trend, why = _trend(readings)
    hits = _note_hits(notes)
    reasons += why + [f"Caregiver note mentions {h} (+1)" for h in hits]
    score = sum(pts.values()) + trend + len(hits)
    early = trend >= 2
    if early:
        reasons.append("Early-warning: pattern suggests possible deterioration")
    return {"level": _level(score, pts, early), "score": score, "reasons": reasons or ["Vitals within expected range"],
            "early_warning": early, "pts": pts}
