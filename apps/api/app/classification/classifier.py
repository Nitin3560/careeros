from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, asdict

VERSION = 2
US_STATES = set("AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY DC".split())
NON_US = re.compile(r"\b(?:Afghanistan|Albania|Algeria|Andorra|Angola|Antigua and Barbuda|Armenia|Australia|Austria|Azerbaijan|Bahamas|Bahrain|Bangladesh|Barbados|Belarus|Belgium|Belize|Benin|Bhutan|Bolivia|Bosnia and Herzegovina|Botswana|Brazil|Brunei|Bulgaria|Burkina Faso|Burundi|Cambodia|Cameroon|Canada|Cape Verde|Central African Republic|Chad|Chile|China|Colombia|Comoros|Congo|Costa Rica|Croatia|Cuba|Cyprus|Czech Republic|Denmark|Djibouti|Dominica|Dominican Republic|Ecuador|Egypt|El Salvador|Equatorial Guinea|Eritrea|Estonia|Eswatini|Ethiopia|Fiji|Finland|France|Gabon|Gambia|Georgia|Germany|Ghana|Greece|Grenada|Guatemala|Guinea|Guyana|Haiti|Honduras|Hungary|Iceland|India|Indonesia|Iran|Iraq|Ireland|Israel|Italy|Ivory Coast|Jamaica|Japan|Jordan|Kazakhstan|Kenya|Kiribati|Kosovo|Kuwait|Kyrgyzstan|Laos|Latvia|Lebanon|Lesotho|Liberia|Libya|Liechtenstein|Lithuania|Luxembourg|Madagascar|Malawi|Malaysia|Maldives|Mali|Malta|Marshall Islands|Mauritania|Mauritius|Mexico|Micronesia|Moldova|Monaco|Mongolia|Montenegro|Morocco|Mozambique|Myanmar|Namibia|Nauru|Nepal|Netherlands|New Zealand|Nicaragua|Niger|Nigeria|North Korea|North Macedonia|Norway|Oman|Pakistan|Palau|Palestine|Panama|Papua New Guinea|Paraguay|Peru|Philippines|Poland|Portugal|Qatar|Romania|Russia|Rwanda|Saint Kitts and Nevis|Saint Lucia|Saint Vincent|Samoa|San Marino|Sao Tome|Saudi Arabia|Senegal|Serbia|Seychelles|Sierra Leone|Singapore|Slovakia|Slovenia|Solomon Islands|Somalia|South Africa|South Korea|South Sudan|Spain|Sri Lanka|Sudan|Suriname|Sweden|Switzerland|Syria|Taiwan|Tajikistan|Tanzania|Thailand|Timor-Leste|Togo|Tonga|Trinidad and Tobago|Tunisia|Turkey|Turkmenistan|Tuvalu|Uganda|Ukraine|United Arab Emirates|United Kingdom|UK|Uruguay|Uzbekistan|Vanuatu|Vatican City|Venezuela|Vietnam|Yemen|Zambia|Zimbabwe|Barcelona|Paris|Amsterdam|Milan|Sao Paulo|São Paulo|Taguig|Noida|Nairobi|Berlin|Munich|London|Dublin|Toronto|Vancouver|Montreal|Warsaw|Krakow|Madrid|Lisbon|Zurich|Stockholm|Tel Aviv|Singapore|Tokyo|Sydney|Melbourne|Shanghai|Beijing|Shenzhen|Bangalore|Hyderabad|Mumbai|Pune|Chennai|Delhi|Gurgaon|Bogota|Medellin|Buenos Aires|Belgrade|Manila|Jakarta|Americas|Cambridge\s*,?\s*(?:UK|United Kingdom)|Remote\s*[-–]\s*(?:EMEA|APAC|LATAM|Europe|Canada|India))\b", re.I)
TECH = re.compile(r"\b(?:software|developer|programmer|swe|sde|backend|back[- ]?end|front[- ]?end|full[- ]?stack|web developer|mobile|ios|android|machine learning|ml|ai|data engineer|data scientist|devops|sre|site reliability|cloud engineer|platform engineer|infrastructure engineer|security engineer|systems engineer|computer vision|nlp|robotics software|embedded software|firmware|qa engineer|sdet|test engineer)\b", re.I)
NONTECH = re.compile(r"\b(?:mechanical|electrical|chemical|civil|industrial|process|manufacturing|quality|packaging|rf|hvac|technician|laboratory|drug|clinical|biological|nurse|physician|patient care|curriculum|business development|land developer|sales engineer|solutions engineer|developer advocate|technical account manager|customer engineer)\b", re.I)
NONTECH = re.compile(NONTECH.pattern[:-3] + r"|machinist|\bcnc\b|trainer|ai trainer|business analyst|statistical (?:programmer|analyst)|power user|annotator|labeler|manual tester|\boperator\b|ai workflows engineer)", re.I)
SENIOR = re.compile(r"\b(?:senior|sr|snr|staff|principal|advisor|lead|manager|mgr|director|architect|head of|vp|distinguished|fellow|prin|iii|iv|l[5-9]|e[5-9]|ic[3-9])\b|(?:engineer|developer|scientist|architect)\s+[3-9]\b", re.I)
SENIOR_FALSE_POSITIVE = re.compile(r"\b(?:lead generation|package manager|staffing|principal financial|headless|director of photography)\b", re.I)
EXEMPT = re.compile(r"\b(?:new grad(?:uate)?|junior|jr|entry[- ]level|associate|university|campus|i level|graduate program|rotational)\b", re.I)
NEW_GRAD = re.compile(r"\b(?:new grad(?:uate)?|university grad|campus hire|entry[- ]level|junior|jr|associate engineer|engineer i|co-op|20\d{2} grad)\b", re.I)
US_CITIES = """Abilene|Akron|Albany|Albuquerque|Alexandria|Allentown|Amarillo|Anaheim|Anchorage|Ann Arbor|Asheville|Atlanta|Augusta|Aurora|Austin|Bakersfield|Baltimore|Baton Rouge|Bellevue|Billings|Boise|Boston|Boulder|Bridgeport|Brownsville|Buffalo|Burbank|Canton|Cape Coral|Cary|Carrollton|Cedar Rapids|Chandler|Charleston|Charlotte|Chattanooga|Chesapeake|Chicago|Chula Vista|Cincinnati|Clarksville|Clearwater|Cleveland|Colorado Springs|Columbia|Concord|Coral Springs|Corona|Corpus Christi|Costa Mesa|Dallas|Dayton|Denton|Denver|Des Moines|Detroit|Durham|El Paso|Eugene|Evansville|Everett|Fairfield|Fayetteville|Flint|Fort Collins|Fort Lauderdale|Fort Myers|Fort Wayne|Fremont|Fresno|Frisco|Fullerton|Gainesville|Garden Grove|Garland|Gilbert|Glendale|Grand Prairie|Grand Rapids|Greensboro|Greeley|Green Bay|Hampton|Hartford|Hayward|Henderson|Hialeah|High Point|Hollywood|Honolulu|Houston|Huntsville|Indianapolis|Independence|Irvine|Irving|Jackson|Jacksonville|Jersey City|Joliet|Kalamazoo|Kansas City|Killeen|Knoxville|Lafayette|Lakeland|Lancaster|Lansing|Laredo|Las Vegas|Lexington|Lincoln|Little Rock|Long Beach|Los Angeles|Louisville|Lowell|Lubbock|Macon|Madison|Manchester|McAllen|McKinney|Memphis|Mesa|Mesquite|Miami|Milwaukee|Minneapolis|Miramar|Mobile|Modesto|Montgomery|Moreno Valley|Murfreesboro|Murrieta|Naperville|Nashville|New Haven|New Orleans|New York|Newark|Newport News|Norfolk|Norman|North Charleston|North Las Vegas|Oakland|Oceanside|Oklahoma City|Omaha|Ontario|Orlando|Overland Park|Oxnard|Palm Bay|Palmdale|Pasadena|Paterson|Pembroke Pines|Peoria|Philadelphia|Phoenix|Pittsburgh|Plano|Pomona|Pompano Beach|Portland|Providence|Provo|Raleigh|Rancho Cucamonga|Reno|Richmond|Riverside|Roanoke|Rochester|Rockford|Sacramento|Saint Louis|Saint Paul|Salem|Salinas|Salt Lake City|San Antonio|San Bernardino|San Diego|San Francisco|San Jose|Santa Ana|Santa Barbara|Santa Clara|Santa Clarita|Santa Rosa|Savannah|Scottsdale|Seattle|Shreveport|Simi Valley|Sioux Falls|Spokane|Springfield|Stamford|Stockton|Sunnyvale|Syracuse|Tacoma|Tallahassee|Tampa|Tempe|Thornton|Thousand Oaks|Toledo|Topeka|Torrance|Tucson|Tulsa|Tuscaloosa|Virginia Beach|Visalia|Vista|Waco|Washington|Waterbury|West Covina|Wichita|Wilmington|Winston-Salem|Worcester|Palo Alto|Mountain View|Menlo Park|Redwood City|Santa Monica|San Mateo|Cambridge|Arlington|Columbus|Portland|Birmingham""".split("|")
AMBIGUOUS_CITIES = {"cambridge", "portland", "birmingham", "london", "arlington", "san jose", "columbus"}
REQUIRED = re.compile(r"^(?:requirements?|qualifications?|minimum|basic qualifications?|required qualifications?|what we look for|what we're looking for|what you bring|what you have|who you are|about you|must have)$", re.I)
PREFERRED = re.compile(r"^(?:preferred qualifications?|nice to have|bonus points?|a plus|ideally)$", re.I)

def normalize_title(value: str | None) -> str:
    value = unicodedata.normalize("NFKC", value or "")
    value = value.translate(str.maketrans({"–": "-", "—": "-", "−": "-", "‘": "'", "’": "'", "“": '"', "”": '"'}))
    return re.sub(r"\s+", " ", value).strip().rstrip(".,;:|")

def classify_location(value: str | None) -> tuple[str, str]:
    text = re.sub(r"\s+", " ", value or "").strip()
    if not text: return "unknown", "missing"
    if re.search(r"\bamericas\b", text, re.I): return "non_us", "non-US region signal"
    parts = re.split(r"\s*(?:;|\||/|\bor\b|\band\b|\n)\s*", text, flags=re.I)
    state_phrases = "Alabama|Alaska|Arizona|Arkansas|California|Colorado|Connecticut|Delaware|Florida|Georgia|Hawaii|Idaho|Illinois|Indiana|Iowa|Kansas|Kentucky|Louisiana|Maine|Maryland|Massachusetts|Michigan|Minnesota|Mississippi|Missouri|Montana|Nebraska|Nevada|New Hampshire|New Jersey|New Mexico|New York|North Carolina|North Dakota|Ohio|Oklahoma|Oregon|Pennsylvania|Rhode Island|South Carolina|South Dakota|Tennessee|Texas|Utah|Vermont|Virginia|Washington|West Virginia|Wisconsin|Wyoming|District of Columbia".split("|")
    foreign_found = False
    for part in parts:
        state_match = re.search(r",\s*([A-Z]{2})(?:\s+\d{5}(?:-\d{4})?)?(?:\s*,?\s*(?:United States|USA))?\s*$", part)
        if state_match and state_match.group(1) in US_STATES: return "us", "state code"
        if any(re.search(rf",\s*{re.escape(name)}(?:\s+\d{{5}})?\s*$", part, re.I) for name in state_phrases): return "us", "state name"
        if re.search(r"\b(?:United States|USA|US-Remote|Remote\s*-\s*US)\b", part, re.I): return "us", "US signal"
        if re.search(r"cambridge.*\b(?:uk|united kingdom)\b", part, re.I) or NON_US.search(part):
            foreign_found = True
            continue
        if re.match(r"^\s*\d+\s+locations?\s*$", part, re.I): continue
        ambiguous_hit = next((city for city in AMBIGUOUS_CITIES if re.search(rf"\b{re.escape(city)}\b", part, re.I)), None)
        if ambiguous_hit and not re.search(r",\s*[A-Z]{2}\b|\b(?:US|USA|United States)\b", part): continue
        if any(re.search(rf"\b{re.escape(city)}\b", part, re.I) for city in US_CITIES): return "us", "US city"
    if foreign_found: return "non_us", "foreign country/city signal"
    return "unknown", "multiple locations" if re.search(r"\b\d+\s+locations?\b", text, re.I) else "no parseable US signal"

EEO = re.compile(r"equal opportunity|do not discriminate|does not discriminate|without regard to|regardless of race|protected status|protected characteristics|\bEEO\b", re.I)
BENEFITS = re.compile(r"benefit|401\s*\(k\)|insurance|paid time off|compensation package", re.I)

def _sponsorship_signal(sentence: str) -> tuple[str, str] | None:
    if EEO.search(sentence) or BENEFITS.search(sentence): return None
    if re.search(r"(?:unable to|cannot|will not|do not|does not|no)\b[^.]{0,80}\b(?:sponsor|sponsorship|visa sponsorship)\b|without\s+sponsorship|(?:now|at this time)\s+or\s+in\s+the\s+future[^.]{0,40}sponsor", sentence, re.I): return "no_sponsorship", sentence[:300].strip()
    if re.search(r"(?:u\.s\.?|us)\s+citizen(?:ship)?\s+(?:is\s+)?required|must be a\s+(?:u\.s\.?|us)\s+citizen|(?:u\.s\.?|us)\s+citizens\s+only|must be a\s+(?:u\.s\.?|us)\s+person", sentence, re.I): return "citizenship", sentence[:300].strip()
    if re.search(r"active\s+security\s+clearance|must\s+(?:have|possess).*clearance|ts/sci|top secret|polygraph", sentence, re.I) and not re.search(r"no\s+clearance\s+required", sentence, re.I): return "clearance", sentence[:300].strip()
    if re.search(r"must be a\s+(?:u\.s\.?|us)\s+person.*itar|requires?\s+access\s+to\s+export[- ]controlled", sentence, re.I): return "itar", sentence[:300].strip()
    return None

def classify_job(title: str | None, description: str | None = "", location: str | None = None) -> dict:
    title_n = normalize_title(title)
    reasons = []
    tech = bool(TECH.search(title_n)) and not bool(NONTECH.search(title_n))
    if not tech: reasons.append("ambiguous_title" if not NONTECH.search(title_n) else "non_tech_title")
    strong_senior = re.search(r"\b(?:senior|staff|principal|distinguished|director|vp|head of)\b", title_n, re.I)
    weak_senior = re.search(r"\b(?:sr|snr|advisor|lead|manager|mgr|architect|fellow|prin|iii|iv|l[5-9]|e[5-9]|ic[3-9])\b|(?:engineer|developer|scientist|researcher|architect)\s+[3-9]\b", title_n, re.I)
    senior = bool(strong_senior or (weak_senior and not EXEMPT.search(title_n))) and not bool(SENIOR_FALSE_POSITIVE.search(title_n))
    grad = bool(NEW_GRAD.search(title_n))
    loc, loc_reason = classify_location(location)
    text = description or ""
    sponsorship = None; sponsorship_rule = None
    for sentence in re.split(r"(?<![A-Z])(?<=[.!?])\s+", text):
        signal = _sponsorship_signal(sentence)
        if signal: sponsorship_rule, sponsorship = signal; break
    title_signal = _sponsorship_signal(title_n)
    if title_signal: sponsorship_rule, sponsorship = title_signal
    elif re.search(r"\bcleared\b", title_n, re.I): sponsorship_rule, sponsorship = "clearance", title_n[:300]
    if senior: reasons.append("senior_title")
    if loc == "non_us": reasons.append("non_us_location")
    if sponsorship is not None: reasons.append("sponsorship_restriction")
    required_chunks = []
    headings = list(re.finditer(r"^##\s+(.+)$", text, flags=re.M))
    required_heading_found = False
    for index, heading in enumerate(headings):
        name = heading.group(1).strip().rstrip(":").replace("’", "'")
        if REQUIRED.match(name):
            required_heading_found = True
            end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
            required_chunks.append(text[heading.end():end])
    required_text = " ".join(required_chunks)
    years = [int(x) for x in re.findall(r"\b(\d+)\s*\+?\s+years?", required_text, re.I)]
    subfield = "general"
    for pattern, name in ((r"backend|back[- ]?end", "backend"), (r"front[- ]?end|web", "frontend"), (r"full[- ]?stack", "fullstack"), (r"mobile|ios|android", "mobile"), (r"machine learning|\bml\b|\bai\b|nlp|computer vision", "ml_ai"), (r"data", "data"), (r"devops|sre|cloud|platform|infrastructure", "infra_devops"), (r"security", "security"), (r"embedded|firmware", "embedded"), (r"qa|sdet|test", "qa")):
        if re.search(pattern, title_n, re.I): subfield = name; break
    employment = "full_time"
    if re.search(r"\b(?:intern|internship)\b", title_n, re.I) and not re.search(r"internal|international", title_n, re.I): employment = "intern"
    elif re.search(r"\bco[- ]?op\b", title_n, re.I): employment = "co_op"
    elif re.search(r"\bcontract(?:or)?\b", title_n, re.I): employment = "contract"
    elif re.search(r"\bpart[- ]?time\b", title_n, re.I): employment = "part_time"
    if employment not in {"full_time", "unknown"}: reasons.append(f"employment_type_{employment}")
    alternatives = re.findall(r"(?:BS|MS|PhD)\s*\+?\s*\d+\s*years?", required_text, re.I) or None
    return {"title_normalized": title_n, "is_tech_title": tech, "tech_subfield": subfield, "is_senior_title": senior, "seniority_level": "senior" if senior else None, "is_new_grad_title": grad, "employment_type": employment, "location_class": loc, "location_reason": loc_reason, "sponsorship_block": sponsorship is not None, "sponsorship_evidence": sponsorship, "sponsorship_rule": sponsorship_rule, "min_years_required": min(years) if years else None, "min_years_alternatives": alternatives, "years_source": "required_section" if years else "none", "parse_tier": 1 if required_heading_found else (2 if headings else 3), "exclusion_reasons": reasons, "classifier_version": VERSION}
