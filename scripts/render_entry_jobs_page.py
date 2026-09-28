#!/usr/bin/env python3
"""Render the marked README job feed as a small, self-contained Pages site."""
from __future__ import annotations

import argparse
from html import escape
from pathlib import Path
import re
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
START_MARKER = "<!-- ENTRY_JOBS:START -->"
END_MARKER = "<!-- ENTRY_JOBS:END -->"
LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
ALLOWED_ROLE_TAG_RE = re.compile(r"</?(?:br|sub)>", re.IGNORECASE)
BAD_TITLE_RE = re.compile(
    r"\b(intern|internship|co-?op|apprentice|analyst|sales|marketer|trainer|"
    r"mechanic|machinist|technician|"
    r"operator|power user|annotator|labeler|mechanical|electrical|footwear|"
    r"product\s+(?:developer|designer|owner|manager)|associate,?\s+store|"
    r"retail|quality|clinical|recruiter|designer|support|customer|vice president|"
    r"\bvp\b|level\s*(?:3|iii|4|iv|5|v))\b", re.I,
)
TECH_TITLE_RE = re.compile(
    r"\b(software|sde|developer|backend|frontend|front[- ]?end|full[- ]?stack|"
    r"platform|infrastructure|site reliability|\bsre\b|devops|machine learning|"
    r"\bml\b|\bai\b|data engineer|data scientist|member of technical staff|\bmts\b|"
    r"firmware|embedded|systems engineer|security engineer|cloud engineer|mobile engineer|"
    r"ios engineer|android engineer|\bengineer\b|\bprogrammer\b|\bscientist\b)", re.I,
)
US_LOCATION_RE = re.compile(
    r"\b(?:United States|USA|U\.S\.|US Remote|Remote,?\s+US)\b|"
    r",\s*(?:AL|AK|AZ|AR|CA|CO|CT|DE|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|"
    r"MI|MN|MS|MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|"
    r"VT|VA|WA|WV|WI|WY|DC)(?:\s+\d{5}(?:-\d{4})?)?\s*$|"
    r"\b(?:Alabama|Alaska|Arizona|Arkansas|California|Colorado|Connecticut|Delaware|"
    r"Florida|Georgia|Hawaii|Idaho|Illinois|Indiana|Iowa|Kansas|Kentucky|Louisiana|"
    r"Maine|Maryland|Massachusetts|Michigan|Minnesota|Mississippi|Missouri|Montana|"
    r"Nebraska|Nevada|New Hampshire|New Jersey|New Mexico|New York|North Carolina|"
    r"North Dakota|Ohio|Oklahoma|Oregon|Pennsylvania|Rhode Island|South Carolina|"
    r"South Dakota|Tennessee|Texas|Utah|Vermont|Virginia|Washington|West Virginia|"
    r"Wisconsin|Wyoming|District of Columbia)\b", re.I,
)
NON_US_SIGNAL_RE = re.compile(
    r"\b(?:India|Bengaluru|Bangalore|Hyderabad|Pune|Mumbai|Chennai|Delhi|Noida|"
    r"Gurugram|Gurgaon|Kolkata|Bhubaneswar|Philippines|Taguig|Nairobi|Kenya|"
    r"Romania|Spain|Barcelona|United Kingdom|UK|England|"
    r"Netherlands|Amsterdam|Italy|Milan|France|Paris|Brazil|Sao Paulo|São Paulo|"
    r"South Africa|Australia|Sydney|Vietnam|Ho Chi Minh City|Singapore|"
    r"Czech Republic|Prague|Poland|Germany|Japan|Taiwan|Toronto|Vancouver|Canada|"
    r"Mexico|Argentina|Chile|Colombia|Portugal|Switzerland|Belgium|Austria|"
    r"Sweden|Norway|Denmark|Finland|Ireland|Dublin|New Zealand|Israel|UAE|Dubai|"
    r"Saudi Arabia|Thailand|Malaysia|Indonesia|Pakistan|Bangladesh|Ukraine|Turkey|"
    r"Cairo|Egypt|Nigeria|Ghana|Morocco|Peru|Costa Rica)\b", re.I,
)
NON_US_CODE_SIGNAL_RE = re.compile(
    r"(?:^|[,/])(?:DE|FR|IT|ES|NL|IN|BR|AU|SG|JP|ZA|MX|GB|UK|TW|TWN|BRA|PL|RO|IE|VN|PH|NZ|CH|BE|AT|SE|NO|DK|FI|IL|AE|SA|TH|MY|ID|PK|BD|UA|TR|EG|NG|GH|MA|PE|CR)-",
    re.I,
)
EARLY_PAGE_SENIOR_TITLE_RE = re.compile(
    r"\b(?:senior|sr\.?|staff|principal|distinguished|director|vice president|vp|head of|manager|lead)\b|"
    r"\b(?:III|IV|V|[3-9])\b",
    re.I,
)


def extract_feed(readme: str) -> str:
    start = readme.find(START_MARKER)
    end = readme.find(END_MARKER)
    if start < 0 or end < 0 or end <= start:
        raise ValueError("README is missing a valid ENTRY_JOBS marker pair")
    return readme[start + len(START_MARKER):end].strip()


def split_row(line: str) -> list[str]:
    """Split a Markdown table row while preserving escaped pipes in cells."""
    value = line.strip()
    if value.startswith("|"):
        value = value[1:]
    if value.endswith("|"):
        value = value[:-1]
    cells = re.split(r"(?<!\\)\|", value)
    return [cell.strip().replace(r"\|", "|") for cell in cells]


def _safe_href(value: str) -> str | None:
    parsed = urlsplit(value.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        return None
    return escape(value.strip(), quote=True)


def _inline(value: str, *, role: bool = False) -> str:
    """Escape text and convert only the tiny Markdown/HTML subset the feed uses."""
    safe_tags: dict[str, str] = {}
    if role:
        def stash(match: re.Match[str]) -> str:
            token = f"__SAFE_TAG_{len(safe_tags)}__"
            safe_tags[token] = match.group(0).lower()
            return token
        value = ALLOWED_ROLE_TAG_RE.sub(stash, value)

    rendered: list[str] = []
    cursor = 0
    for match in LINK_RE.finditer(value):
        rendered.append(escape(value[cursor:match.start()]))
        href = _safe_href(match.group(2))
        label = escape(match.group(1))
        rendered.append(
            f'<a href="{href}" target="_blank" rel="noopener noreferrer">{label}</a>'
            if href else label
        )
        cursor = match.end()
    rendered.append(escape(value[cursor:]))
    result = "".join(rendered)
    result = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", result)
    for token, tag in safe_tags.items():
        result = result.replace(token, tag)
    return result


def parse_feed(markdown: str) -> tuple[list[str], list[dict[str, object]]]:
    lines = markdown.splitlines()
    summary: list[str] = []
    tiers: list[dict[str, object]] = []
    current: dict[str, object] | None = None
    in_table = False
    table_headers: list[str] = []

    for line in lines:
        stripped = line.strip()
        tier_heading = re.match(r"###\s+(Tier\s+[123])\s*$", stripped, re.IGNORECASE)
        if tier_heading:
            current = {"name": tier_heading.group(1).title(), "description": "", "jobs": []}
            tiers.append(current)
            in_table = False
            table_headers = []
            continue
        if not stripped:
            in_table = False
            continue
        if stripped.startswith("#### "):
            continue
        if stripped.startswith("| ") or stripped.startswith("|"):
            cells = split_row(stripped)
            if cells and set(cells[0]) <= {"-", ":"}:
                continue
            if len(cells) >= 7 and cells[0].casefold() == "company" and cells[1].casefold() == "role":
                table_headers = [cell.casefold() for cell in cells]
                in_table = True
                continue
            if current is not None and in_table and len(cells) >= len(table_headers):
                job = dict(zip(table_headers, cells))
                if all(key in job for key in ("company", "role", "experience", "posted", "found", "salary", "apply")):
                    if "location" not in job:
                        location_match = re.search(r"<sub>(.*?)</sub>", str(job.get("role", "")), re.I)
                        job["location"] = location_match.group(1) if location_match else ""
                        if location_match:
                            job["role"] = re.sub(r"<sub>.*?</sub>", "", str(job["role"]), flags=re.I).strip()
                    if _qualifies_for_page(job):
                        current["jobs"].append(job)
            continue
        if stripped.startswith("## ") or stripped.startswith("Quick links:"):
            continue
        if current is not None:
            if stripped.casefold().startswith("no matching roles"):
                continue
            if current["jobs"]:
                continue
            if not current["description"]:
                current["description"] = stripped
            elif not in_table:
                current["description"] = f'{current["description"]} {stripped}'
        elif not stripped.startswith("<!--"):
            summary.append(stripped)
    return summary, tiers


def _qualifies_for_page(job: dict[str, object]) -> bool:
    role = re.sub(r"<[^>]*>", " ", str(job.get("role", "")))
    role = role.replace(r"\(", "(").replace(r"\)", ")")
    role = re.sub(r"\\\([^)]*\\\)", " ", role)
    location = str(job.get("location", "")).strip().casefold()
    if not TECH_TITLE_RE.search(role) or BAD_TITLE_RE.search(role):
        return False
    # Some ATS feeds leave location blank/unknown even though the canonical
    # application URL embeds the work city or country. Treat explicit foreign
    # URL evidence as non-US instead of letting it pass as merely unknown.
    apply_markdown = str(job.get("apply", ""))
    apply_match = LINK_RE.search(apply_markdown)
    apply_url = apply_match.group(2) if apply_match else apply_markdown
    raw_path = urlsplit(apply_url).path
    path = raw_path.replace("-", " ").replace("_", " ")
    if (
        NON_US_SIGNAL_RE.search(location)
        or NON_US_SIGNAL_RE.search(path)
        or NON_US_CODE_SIGNAL_RE.search(location)
        or NON_US_CODE_SIGNAL_RE.search(raw_path)
    ):
        return False
    if "unknown location" in location:
        return False
    if not location or not US_LOCATION_RE.search(location):
        return False
    return True


def experience_bucket(value: str) -> str:
    """Group the feed's human-readable experience labels for the page filter."""
    normalized = re.sub(r"\s+", " ", value.strip().casefold()).replace("–", "-").replace("—", "-")
    if not normalized or normalized in {"not stated", "unknown", "n/a"}:
        return "unknown"
    if "new grad" in normalized or "new graduate" in normalized:
        return "early"
    numbers = [int(number) for number in re.findall(r"\d+", normalized)]
    if not numbers:
        return "unknown"
    if "+" in normalized:
        minimum = numbers[0]
        if minimum == 2:
            return "two-plus"
        if minimum < 2:
            return "one-plus"
        return "three-plus" if minimum < 6 else "senior"
    if len(numbers) >= 2:
        low, high = numbers[0], numbers[1]
    else:
        low = high = numbers[0]
    if high <= 2:
        return "early"
    if low <= 5:
        return "mid"
    return "senior"


def is_early_career_job(job: dict[str, object]) -> bool:
    """Keep only explicit 0–2-year labels or new-grad roles on the focused page."""
    role = re.sub(r"<[^>]*>", " ", str(job.get("role", "")))
    if EARLY_PAGE_SENIOR_TITLE_RE.search(role):
        return False
    new_grad_title = re.search(r"\b(?:new\s+grad(?:uate)?|university\s+graduate)\b", role, re.I)
    bucket = experience_bucket(str(job.get("experience", "")))
    return bucket == "early" or (bucket == "unknown" and bool(new_grad_title))


FILTER_SCRIPT = """<script>
(() => {
  const cards = [...document.querySelectorAll('.job')];
  const controls = {
    experience: document.getElementById('experience-filter'),
    posted: document.getElementById('posted-filter'),
    tier: document.getElementById('tier-filter'),
    company: document.getElementById('company-filter'),
    keyword: document.getElementById('keyword-filter'),
    salary: document.getElementById('salary-filter'),
  };
  const count = document.getElementById('visible-job-count');
  const sections = [...document.querySelectorAll('main > section')];
  function update() {
    const company = controls.company.value.trim().toLocaleLowerCase();
    const keyword = controls.keyword.value.trim().toLocaleLowerCase();
    let visible = 0;
    for (const card of cards) {
      const expOk = controls.experience.value === 'all' || card.dataset.experience === controls.experience.value;
      const tierOk = controls.tier.value === 'all' || card.dataset.tier === controls.tier.value;
      const companyOk = !company || card.dataset.company.toLocaleLowerCase().includes(company);
      const searchable = `${card.dataset.role} ${card.dataset.company} ${card.dataset.location}`.toLocaleLowerCase();
      const keywordOk = !keyword || searchable.includes(keyword);
      const salaryOk = !controls.salary.checked || card.dataset.salary === 'yes';
      let postedOk = true;
      const days = Number(controls.posted.value);
      if (days) {
        const posted = card.dataset.posted;
        const postedAt = posted ? Date.parse(`${posted}T23:59:59Z`) : NaN;
        postedOk = Number.isFinite(postedAt) && postedAt >= Date.now() - days * 86400000;
      }
      const show = expOk && tierOk && companyOk && keywordOk && salaryOk && postedOk;
      card.hidden = !show;
      if (show) visible += 1;
    }
    for (const section of sections) {
      section.hidden = !section.querySelector('.job:not([hidden])');
    }
    count.textContent = `Showing ${visible.toLocaleString()} of ${cards.length.toLocaleString()} jobs`;
  }
  for (const control of Object.values(controls)) {
    control.addEventListener(control.tagName === 'INPUT' ? 'input' : 'change', update);
  }
  document.getElementById('reset-filters').addEventListener('click', () => {
    controls.experience.value = 'all';
    controls.posted.value = '0';
    controls.tier.value = 'all';
    controls.company.value = '';
    controls.keyword.value = '';
    controls.salary.checked = false;
    update();
  });
  update();
})();
</script>"""


def render_page(readme: str, *, early_career_only: bool = False) -> str:
    summary, tiers = parse_feed(extract_feed(readme))
    if early_career_only:
        for tier in tiers:
            tier["jobs"] = [job for job in tier["jobs"] if is_early_career_job(job)]
    title = "CareerOS New Grad & 0–2 Year U.S. Tech Jobs" if early_career_only else "CareerOS Recent U.S. Tech Jobs"
    total_jobs = sum(len(tier["jobs"]) for tier in tiers)
    summary = [
        re.sub(r"Current feed size: \*\*[\d,]+\*\* roles", f"Current feed size: **{total_jobs}** roles", line)
        for line in summary
    ]
    summary_html = "".join(f"<p>{_inline(line)}</p>" for line in summary)
    empty_notice = (
        '<p class="no-current-jobs">No current classified technology postings were found in the feed window.</p>'
        if total_jobs == 0 else ""
    )
    nav = "".join(
        f'<a href="#{escape(str(tier["name"]).lower().replace(" ", "-"))}">{escape(str(tier["name"]))}</a>'
        for tier in tiers
    )
    sections: list[str] = []
    for tier in tiers:
        tier_name = str(tier["name"])
        jobs = tier["jobs"]
        cards: list[str] = []
        for job in jobs:
            apply = _inline(str(job["apply"]))
            location = str(job.get("location") or "")
            location_markup = f'<p class="job-location">{_inline(location)}</p>' if location else ""
            experience = str(job.get("experience") or "Not stated")
            posted = str(job.get("posted") or "")
            posted_date = posted if re.fullmatch(r"\d{4}-\d{2}-\d{2}", posted) else ""
            experience_filter_value = (
                "early" if early_career_only and is_early_career_job(job)
                else experience_bucket(experience)
            )
            card_data = (
                f' data-company="{escape(str(job["company"]), quote=True)}"'
                f' data-role="{escape(str(job["role"]), quote=True)}"'
                f' data-location="{escape(location, quote=True)}"'
                f' data-experience="{experience_filter_value}"'
                f' data-posted="{escape(posted_date, quote=True)}"'
                f' data-tier="{escape(tier_name, quote=True)}"'
                f' data-salary="{"yes" if str(job.get("salary", "")).strip() else "no"}"'
            )
            cards.append(
                f'<article class="job"{card_data}>'
                f'<div class="job-top"><div><h3>{_inline(str(job["role"]), role=True)}</h3>'
                f'<p class="company">{_inline(str(job["company"]))}</p>'
                f'{location_markup}</div>'
                f'<div class="apply">{apply}</div></div>'
                '<dl>'
                f'<div><dt>Experience</dt><dd>{_inline(experience)}</dd></div>'
                f'<div><dt>Posted</dt><dd>{_inline(str(job["posted"]))}</dd></div>'
                f'<div><dt>Found</dt><dd>{_inline(str(job["found"]))}</dd></div>'
                f'<div><dt>Salary</dt><dd>{_inline(str(job["salary"])) or "Not listed"}</dd></div>'
                '</dl></article>'
            )
        description = f'<p class="tier-description">{_inline(str(tier["description"]))}</p>' if tier["description"] else ""
        content = "".join(cards) if cards else '<p class="empty">No matching roles in this tier right now.</p>'
        sections.append(
            f'<section id="{escape(tier_name.lower().replace(" ", "-"))}" data-tier-section>'
            f'<h2>{escape(tier_name)}</h2>{description}{content}</section>'
        )

    page_links = (
        '<p class="page-links"><a href="./">All recent tech jobs</a></p>'
        if early_career_only else
        '<p class="page-links"><a href="./early-career.html">New Grad &amp; 0–2 Year Roles</a></p>'
    )
    experience_control = (
        '<label>Experience<select id="experience-filter" disabled><option value="early" selected>New Grad / 0–2 years only</option></select></label>'
        if early_career_only else
        '<label>Experience<select id="experience-filter"><option value="all">Any experience</option><option value="early">New grad / 0–2 years</option><option value="one-plus">1+ years</option><option value="two-plus">2+ years</option><option value="mid">3–5 years</option><option value="three-plus">3+ years</option><option value="senior">6+ years</option><option value="unknown">Not stated</option></select></label>'
    )
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="description" content="Recent U.S. software and technology roles from CareerOS.">
<title>{title}</title><style>
:root{{color-scheme:light dark;--bg:#0b1020;--card:#151d30;--line:#2c3851;--text:#edf2fc;--muted:#aebbd1;--link:#8ab4ff;--accent:#b6f09c}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--text);font:16px/1.5 system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}}
main{{max-width:960px;margin:auto;padding:26px 16px 56px}}header{{margin-bottom:28px}}h1{{font-size:1.8rem;line-height:1.2;margin:0 0 10px}}header p{{color:var(--muted);margin:8px 0}}nav{{display:flex;gap:10px;flex-wrap:wrap;margin-top:18px}}nav a,.apply a{{color:var(--link);font-weight:650;text-decoration-thickness:1px;text-underline-offset:3px}}
section{{margin:30px 0}}h2{{font-size:1.2rem;border-bottom:1px solid var(--line);padding-bottom:8px;margin:0 0 6px}}.tier-description{{color:var(--muted);margin:0 0 12px}}.no-current-jobs{{border:1px solid var(--line);border-radius:10px;padding:12px;color:var(--muted)}}
.job{{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px 18px;margin:12px 0}}.job-top{{display:flex;justify-content:space-between;gap:18px;align-items:flex-start}}h3{{font-size:1.05rem;line-height:1.35;margin:0}}.company{{font-weight:650;margin:4px 0 0;color:var(--muted)}}.apply{{white-space:nowrap;padding-top:1px}}
.job-location{{color:var(--muted);margin:3px 0 0;font-size:.9rem}}
dl{{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px 16px;margin:16px 0 0}}dt{{color:var(--muted);font-size:.75rem;text-transform:uppercase;letter-spacing:.04em}}dd{{margin:2px 0 0}}.empty{{color:var(--muted);padding:16px 0}}
.filters{{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin:20px 0 10px;padding:16px;background:var(--card);border:1px solid var(--line);border-radius:14px}}.filters label{{display:grid;gap:5px;color:var(--muted);font-size:.82rem}}.filters input,.filters select,.filters button{{min-width:0;border:1px solid var(--line);border-radius:8px;padding:9px;background:var(--bg);color:var(--text);font:inherit}}.filters .check{{display:flex;align-items:center;gap:8px;align-self:end;padding:10px 0}}.filters .check input{{accent-color:var(--accent)}}.filters button{{cursor:pointer;color:var(--text);font-weight:650}}.filter-status{{color:var(--muted);margin:8px 2px 18px;font-size:.9rem}}.filter-help{{grid-column:1/-1;color:var(--muted);font-size:.78rem;margin:0}}[hidden]{{display:none!important}}.page-links{{margin:12px 0;color:var(--muted)}}.page-links a{{color:var(--link);font-weight:650}}
@media(max-width:600px){{main{{padding:20px 12px 40px}}.job{{padding:14px}}.job-top{{display:block}}.apply{{padding-top:10px}}dl{{grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}}}}
</style></head><body><main><header><h1>{title}</h1>{summary_html}{empty_notice}<nav aria-label="Job tiers">{nav}</nav></header>
{page_links}<div class="filters" aria-label="Filter jobs">
{experience_control}
<label>Posted within<select id="posted-filter"><option value="0">Any time</option><option value="1">24 hours</option><option value="3">3 days</option><option value="7">7 days</option></select></label>
<label>Company<input id="company-filter" type="search" placeholder="Company name"></label>
<label>Keyword<input id="keyword-filter" type="search" placeholder="Role, skill, or location"></label>
<label>Company size<select id="tier-filter"><option value="all">All tiers</option><option value="Tier 1">Tier 1 · Large</option><option value="Tier 2">Tier 2 · Mid-sized</option><option value="Tier 3">Tier 3 · Startup</option></select></label>
<label class="check"><input id="salary-filter" type="checkbox"> Salary listed</label>
<button id="reset-filters" type="button">Reset filters</button>
<p class="filter-help">Posting-date filters use the employer’s posted date. Jobs without a posted date remain visible under “Any time.”</p>
</div><p class="filter-status" id="visible-job-count" aria-live="polite"></p>
{''.join(sections)}{FILTER_SCRIPT}</main></body></html>'''


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--readme", type=Path, default=ROOT / "README.md")
    parser.add_argument("--output", type=Path, default=ROOT / "site" / "index.html")
    parser.add_argument("--early-career-output", type=Path, default=ROOT / "site" / "early-career.html")
    args = parser.parse_args()
    readme = args.readme.read_text(encoding="utf-8")
    page = render_page(readme)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(page, encoding="utf-8")
    print(f"wrote {args.output}")
    early_page = render_page(readme, early_career_only=True)
    args.early_career_output.parent.mkdir(parents=True, exist_ok=True)
    args.early_career_output.write_text(early_page, encoding="utf-8")
    print(f"wrote {args.early_career_output}")


if __name__ == "__main__":
    main()
