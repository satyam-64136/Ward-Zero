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

def assess(readings, notes):
    """readings: list of dicts (oldest->newest) with hr, spo2, sbp, temp. notes: list of strings."""
    if not readings:
        return {"level": "Low", "score": 0, "reasons": ["Waiting for sensor data…"], "early_warning": False, "pts": {}}
    r = readings[-1]
    pts = {"HR": _band(r["hr"], HR), "SpO2": _band(r["spo2"], SPO2),
           "SBP": _band(r["sbp"], SBP), "Temp": _band(r["temp"], TEMP)}
    score = sum(pts.values())
    reasons = [f"{k} {v}" + {"HR": " bpm", "SpO2": "%", "SBP": " mmHg", "Temp": " °C"}[k]
               + f" (+{pts[k]})" for k, v in
               [("HR", round(r["hr"])), ("SpO2", round(r["spo2"], 1)), ("SBP", round(r["sbp"])), ("Temp", round(r["temp"], 1))]
               if pts[k]]

    # Trend (proxy for 24-48h deterioration): first 6 vs last 6 readings of the window
    trend = 0
    w = readings[-24:]
    if len(w) >= 12:
        a, b = w[:6], w[-6:]
        d = lambda k: _mean([x[k] for x in b]) - _mean([x[k] for x in a])
        if d("spo2") <= -3:
            trend += 2; reasons.append(f"SpO2 trending down {_mean([x['spo2'] for x in a]):.0f}→{_mean([x['spo2'] for x in b]):.0f}%")
        if d("hr") >= 15:
            trend += 1; reasons.append(f"Heart rate rising +{d('hr'):.0f} bpm")
        if d("sbp") <= -15:
            trend += 1; reasons.append(f"Systolic BP falling {d('sbp'):.0f} mmHg")
        if d("temp") >= 0.8:
            trend += 1; reasons.append(f"Temperature rising +{d('temp'):.1f} °C")
    score += trend

    # Caregiver notes (English + Hindi keywords)
    text = " ".join(notes).lower()
    hits = [label for label, kws in KEYWORDS.items() if any(k in text for k in kws)]
    for h in hits:
        reasons.append(f"Caregiver note mentions {h} (+1)")
    score += min(len(hits), 3)

    level = "High" if score >= 6 else "Medium" if (score >= 3 or 3 in pts.values()) else "Low"
    early = trend >= 2
    if early and level == "Low":
        level = "Medium"
    if early:
        reasons.append("Early-warning: pattern suggests possible deterioration")
    if not reasons:
        reasons = ["Vitals within expected range"]
    return {"level": level, "score": score, "reasons": reasons, "early_warning": early, "pts": pts}
