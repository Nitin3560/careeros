from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, asdict

VERSION = 1
US_STATES = set("AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY DC".split())
NON_US = re.compile(r"\b(?:Canada|India|United Kingdom|UK|Germany|France|Ireland|Singapore|Australia|Brazil|Mexico|Switzerland|Israel|Japan|China|Bangalore|Hyderabad|Mumbai|Pune|Chennai|London|Berlin|Toronto|Vancouver|Remote\s*[-–]\s*(?:EMEA|APAC|LATAM|Europe|Canada|India))\b", re.I)
TECH = re.compile(r"\b(?:software|developer|programmer|backend|back[- ]?end|front[- ]?end|full[- ]?stack|web developer|mobile|ios|android|machine learning|ml|ai|data engineer|data scientist|devops|sre|site reliability|cloud engineer|platform engineer|infrastructure engineer|security engineer|systems engineer|computer vision|nlp|robotics software|embedded software|firmware|qa engineer|sdet|test engineer)\b", re.I)
NONTECH = re.compile(r"\b(?:mechanical|electrical|chemical|civil|industrial|process|manufacturing|quality|packaging|rf|hvac|technician|laboratory|drug|clinical|biological|nurse|physician|patient care|curriculum|business development|land developer|sales engineer|solutions engineer|developer advocate|technical account manager|customer engineer)\b", re.I)
SENIOR = re.compile(r"\b(?:senior|sr|snr|staff|principal|advisor|lead|manager|mgr|director|architect|head of|vp|distinguished|fellow|prin|iii|iv|l[5-9]|e[5-9]|ic[3-9])\b|(?:engineer|developer|scientist|architect)\s+[3-9]\b", re.I)
EXEMPT = re.compile(r"\b(?:new grad(?:uate)?|junior|jr|entry[- ]level|associate|university|campus|i level|graduate program|rotational)\b", re.I)
NEW_GRAD = re.compile(r"\b(?:new grad(?:uate)?|university grad|campus hire|entry[- ]level|junior|jr|associate engineer|engineer i|co-op|20\d{2} grad)\b", re.I)
REQUIRED = re.compile(r"^(?:requirements?|qualifications?|minimum|basic qualifications?|required qualifications?|what we look for|what we're looking for|what you bring|what you have|who you are|about you|must have)$", re.I)
PREFERRED = re.compile(r"^(?:preferred qualifications?|nice to have|bonus points?|a plus|ideally)$", re.I)

def normalize_title(value: str | None) -> str:
    value = unicodedata.normalize("NFKC", value or "").replace("–", "-").replace("—", "-")
    return re.sub(r"\s+", " ", value).strip().rstrip(".,;:|")

def classify_location(value: str | None) -> tuple[str, str]:
    text = re.sub(r"\s+", " ", value or "").strip()
    if not text: return "unknown", "missing"
    if NON_US.search(text): return "non_us", "foreign country/city signal"
    parts = re.split(r"\s*(?:;|\||/|\bor\b|\band\b|\n)\s*", text, flags=re.I)
    for part in parts:
        if re.search(r",\s*([A-Z]{2})\b", part) and re.search(r",\s*([A-Z]{2})\b", part).group(1) in US_STATES: return "us", "state code"
        if re.search(r"\b(?:United States|USA|US-Remote|Remote\s*-\s*US)\b", part, re.I): return "us", "US signal"
        if re.search(r"\b(?:Boston|Seattle|Austin|Denver|Chicago|Atlanta|San Francisco|San Jose|San Diego|Los Angeles|New York|NYC|Palo Alto|Mountain View|Bellevue|Redmond|Boulder|Raleigh|Durham|Charlotte|Philadelphia|Dallas|Houston|Miami|Nashville|Portland|Sacramento|Irvine|Oakland)\b", part, re.I): return "us", "US city"
    return "unknown", "no parseable US signal"

def classify_job(title: str | None, description: str | None = "", location: str | None = None) -> dict:
    title_n = normalize_title(title)
    reasons = []
    tech = bool(TECH.search(title_n)) and not bool(NONTECH.search(title_n))
    if not tech: reasons.append("ambiguous_title" if not NONTECH.search(title_n) else "non_tech_title")
    senior = bool(SENIOR.search(title_n)) and not bool(EXEMPT.search(title_n))
    grad = bool(NEW_GRAD.search(title_n))
    loc, loc_reason = classify_location(location)
    text = description or ""
    sponsorship = None
    for sentence in re.split(r"(?<=[.!?])\s+", text):
        if re.search(r"(?:unable to|cannot|will not|do not|no visa)\s+(?:sponsor|provide sponsorship)|without sponsorship|us citizens only|citizenship is required|us person|ts/sci|itar|export control|polygraph", sentence, re.I) and not re.search(r"we sponsor|sponsorship is available|welcome candidates requiring sponsorship|no clearance required|sponsor a conference|citizenship status", sentence, re.I):
            sponsorship = sentence[:300].strip(); break
    if re.search(r"\b(?:cleared|security clearance|ts/sci|itar)\b", title_n, re.I): sponsorship = title_n
    required_chunks = []
    headings = list(re.finditer(r"^##\s+(.+)$", text, flags=re.M))
    for index, heading in enumerate(headings):
        name = heading.group(1).strip().rstrip(":")
        if REQUIRED.match(name):
            end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
            required_chunks.append(text[heading.end():end])
    required_text = " ".join(required_chunks)
    years = [int(x) for x in re.findall(r"\b(\d+)\s*\+?\s+years?", required_text, re.I)]
    return {"title_normalized": title_n, "is_tech_title": tech, "tech_subfield": "general", "is_senior_title": senior, "seniority_level": "senior" if senior else None, "is_new_grad_title": grad, "employment_type": "intern" if re.search(r"\bintern(?:ship)?\b", title_n, re.I) else "full_time", "location_class": loc, "location_reason": loc_reason, "sponsorship_block": sponsorship is not None, "sponsorship_evidence": sponsorship, "min_years_required": min(years) if years else None, "min_years_alternatives": years or None, "years_source": "required_section" if years else "none", "parse_tier": 1 if required_text else 3, "exclusion_reasons": reasons, "classifier_version": VERSION}
