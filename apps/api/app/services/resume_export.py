import io
import re
import shutil
import subprocess
from pathlib import Path
from xml.sax.saxutils import escape


RESUME_FILENAME = "Nitin_Singh_Rathore_Resume"

BASE_SKILL_LINES = {
    "Languages": ["Python", "TypeScript/JavaScript", "Java", "Go", "SQL", "C++ (C++17)"],
    "Frontend": ["React", "TypeScript", "Next.js", "HTML5", "CSS3", "Responsive Web UI"],
    "Backend \\& APIs": [
        "FastAPI",
        "REST APIs",
        "Microservices",
        "Event-Driven Services",
        "Notifications",
        "Third-Party Integrations",
    ],
    "AI Agents": [
        "Agentic Workflows",
        "LLM Tool-Calling",
        "RAG",
        "Agent Evaluation",
        "Cursor",
        "Copilot",
        "Claude Code",
    ],
    "Data \\& Cloud": [
        "PostgreSQL",
        "Redis",
        "Kafka",
        "AWS",
        "GCP",
        "Docker",
        "Kubernetes",
        "Terraform",
        "CI/CD",
    ],
    "Delivery": [
        "End-to-End Ownership",
        "Client-Facing Delivery",
        "Production Debugging",
        "Code Review",
        "Testing",
    ],
}

PROJECTS = {
    "yomeets": {
        "name": "YoMeets",
        "subtitle": "AI Meeting \\& Execution Assistant \\href{https://github.com/Nitin3560/YoMeets}{\\underline{\\small github}}",
        "tech": "TypeScript, Node.js, PostgreSQL/pgvector, Deepgram, LLM APIs, GitHub/Google APIs",
        "dates": "Jun 2026 -- July 2026",
        "bullets": [
            "Built a Node.js/TypeScript assistant extracting decisions, owners, and action items from meetings via LLM extraction and RAG, at 94\\% precision.",
            "Shipped an agent executing those commitments across 3 API integrations, at 98\\% success over 150+ evaluated actions.",
        ],
    },
    "careeros": {
        "name": "CareerOS",
        "subtitle": "Large-Scale Data Processing \\& Search Platform \\href{https://github.com/Nitin3560/careeros}{\\underline{\\small github}}",
        "tech": "React/Next.js, TypeScript, Python, FastAPI, PostgreSQL, Redis/RQ, Docker",
        "dates": "July 2026 -- Present",
        "bullets": [
            "Built a full-stack job matching platform on React/Next.js and FastAPI, ingesting from 50 sources and ranking 326K+ records.",
            "Cut median matching latency from $\\sim$690 ms to $\\sim$3.5 ms by profiling a bottleneck and moving ranking into PostgreSQL.",
        ],
    },
    "cloudqueue": {
        "name": "CloudQueue",
        "subtitle": "Highly Available Distributed Task Queue",
        "tech": "Python, Redis, Kubernetes, Docker, AWS, Terraform, Linux",
        "dates": "Mar 2026 -- Jun 2026",
        "bullets": [
            "Built a REST API-driven task queue in Python where a Kubernetes worker pool runs jobs asynchronously at $\\sim$1.4K/sec.",
            "Implemented at-least-once delivery with idempotent execution, recovering from worker crashes in $<$10s with 0 duplicates.",
        ],
    },
    "twinguard": {
        "name": "TwinGuard",
        "subtitle": "Trust-Aware Real-Time UAV Autonomy Framework \\href{https://github.com/Nitin3560/TwinGuard}{\\underline{\\small github}}",
        "tech": "C++17, ROS 2, PX4 SITL, Gazebo, BehaviorTree.CPP, Nav2, Docker, GoogleTest",
        "dates": "Jun 2026 -- July 2026",
        "bullets": [
            "Built a trust-aware UAV autonomy framework in C++17 and ROS 2, adapting navigation under injected localization faults.",
            "Cut fault-recovery time 53.8\\% and tracking RMSE 49.8\\% with authority modes before unreliable state propagated.",
        ],
    },
}

PROJECT_KEYWORDS = {
    "yomeets": {"llm", "rag", "agent", "agents", "ai", "nlp", "speech", "meeting", "tool-calling", "vector", "pgvector"},
    "careeros": {"react", "next", "fastapi", "full-stack", "fullstack", "frontend", "backend", "postgresql", "search", "ranking", "product"},
    "cloudqueue": {"distributed", "queue", "kubernetes", "aws", "terraform", "redis", "throughput", "worker", "scraping", "infrastructure"},
    "twinguard": {"c++", "robotics", "ros", "px4", "uav", "embedded", "real-time", "realtime", "nav2", "gazebo", "systems"},
}


def _latex_escape(value: object) -> str:
    text = str(value or "")
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    return "".join(replacements.get(char, char) for char in text)


def _ensure_period(value: str) -> str:
    stripped = value.strip()
    if not stripped:
        return stripped
    return stripped if stripped.endswith(".") else f"{stripped}."


def _plain_terms(requirements: dict | None, job=None) -> list[str]:
    values: list[str] = []
    if job is not None:
        values.extend([getattr(job, "title", "") or "", getattr(job, "company", "") or ""])
        values.append((getattr(job, "description_text", "") or "")[:3000])
    for section in ("hard_requirements", "preferred", "skills", "technologies"):
        for item in (requirements or {}).get(section, []) or []:
            if isinstance(item, dict):
                values.append(item.get("skill") or item.get("value") or item.get("source_text") or "")
            else:
                values.append(str(item))
    return [value for value in values if value]


def _jd_keywords(requirements: dict | None, job=None) -> list[str]:
    text = " ".join(_plain_terms(requirements, job))
    protected = [
        "Python",
        "TypeScript",
        "JavaScript",
        "Java",
        "Go",
        "SQL",
        "C++",
        "React",
        "Next.js",
        "FastAPI",
        "PostgreSQL",
        "MySQL",
        "MongoDB",
        "Redis",
        "Valkey",
        "Kafka",
        "AWS",
        "GCP",
        "Azure",
        "Docker",
        "Kubernetes",
        "Terraform",
        "CI/CD",
        "REST APIs",
        "Microservices",
        "Distributed Systems",
        "Concurrency",
        "Scalability",
        "Performance",
        "Caching",
        "RAG",
        "LLM",
        "Vector Search",
        "Agentic Workflows",
        "Testing",
        "Unix",
        "React Native",
    ]
    found = []
    lowered = text.lower()
    for keyword in protected:
        if keyword.lower() in lowered and keyword not in found:
            found.append(keyword)
    return found[:18]


def _skill_lines(requirements: dict | None, job=None) -> list[tuple[str, list[str]]]:
    lines = {label: list(values) for label, values in BASE_SKILL_LINES.items()}
    for keyword in _jd_keywords(requirements, job):
        target = "Delivery"
        if keyword == "JavaScript" and "TypeScript/JavaScript" in lines["Languages"]:
            continue
        if keyword == "TypeScript" and "TypeScript/JavaScript" in lines["Languages"]:
            continue
        if keyword in {"Python", "TypeScript", "JavaScript", "Java", "Go", "SQL", "C++"}:
            target = "Languages"
        elif keyword in {"React", "Next.js", "React Native"}:
            target = "Frontend"
        elif keyword in {"FastAPI", "REST APIs", "Microservices"}:
            target = "Backend \\& APIs"
        elif keyword in {"RAG", "LLM", "Vector Search", "Agentic Workflows"}:
            target = "AI Agents"
        elif keyword in {
            "PostgreSQL",
            "MySQL",
            "MongoDB",
            "Redis",
            "Valkey",
            "Kafka",
            "AWS",
            "GCP",
            "Azure",
            "Docker",
            "Kubernetes",
            "Terraform",
            "CI/CD",
        }:
            target = "Data \\& Cloud"
        elif keyword == "Unix":
            target = "Delivery"
        if keyword not in lines[target]:
            lines[target].insert(0, keyword)
    return list(lines.items())


def _project_order(requirements: dict | None, job=None) -> list[str]:
    text = " ".join(_plain_terms(requirements, job)).lower()
    scored = []
    for key, keywords in PROJECT_KEYWORDS.items():
        score = sum(1 for keyword in keywords if keyword in text)
        scored.append((score, key))
    scored.sort(key=lambda item: (-item[0], ["yomeets", "careeros", "cloudqueue", "twinguard"].index(item[1])))
    ordered = [key for _, key in scored]
    return ordered[:3]


def _merge_tailored_bullets(project: dict, tailored_bullets: list[dict]) -> list[str]:
    base = list(project["bullets"])
    if project["name"] != "CareerOS" or not tailored_bullets:
        return base
    replacement = [_latex_escape(_ensure_period(bullet.get("text", ""))) for bullet in tailored_bullets[:2] if bullet.get("text")]
    if len(replacement) >= 2:
        return replacement[:2]
    if len(replacement) == 1:
        return [replacement[0], base[1]]
    return base


def _render_skills(requirements: dict | None, job=None) -> str:
    rendered = []
    for index, (label, values) in enumerate(_skill_lines(requirements, job)):
        suffix = r" \\[3pt]" if index < 5 else ""
        compact_values = []
        for value in values:
            if value not in compact_values:
                compact_values.append(value)
        rendered.append(f"     \\textbf{{{label}:}} {', '.join(compact_values[:11])}{suffix}")
    return "\n".join(rendered)


def _render_projects(
    requirements: dict | None,
    job=None,
    tailored_bullets: list[dict] | None = None,
    project_limit: int = 3,
) -> str:
    chunks = []
    for key in _project_order(requirements, job)[:project_limit]:
        project = PROJECTS[key]
        bullets = _merge_tailored_bullets(project, tailored_bullets or [])
        chunk = rf"""\resumeProjectHeading
  {{{project["name"]}}}{{{project["subtitle"]}}}{{{project["dates"]}}}
  {{{project["tech"]}}}
\resumeItemListStart
  \resumeItem{{{bullets[0]}}}
  \resumeItem{{{bullets[1]}}}
\resumeItemListEnd"""
        chunks.append(chunk)
    return "\n\n".join(chunks)


def generate_tailored_latex(
    job,
    requirements: dict | None,
    bullets: list[dict] | None = None,
    project_limit: int = 3,
) -> str:
    return rf"""%-------------------------
% Resume in Latex
% Author : Jake Gutierrez
% Based off of: https://github.com/sb2nov/resume
% License : MIT
%------------------------

\documentclass[letterpaper,10pt]{{article}}

\usepackage{{latexsym}}
\usepackage[empty]{{fullpage}}
\usepackage{{titlesec}}
\usepackage{{marvosym}}
\usepackage[usenames,dvipsnames]{{color}}
\usepackage{{verbatim}}
\usepackage{{enumitem}}
\usepackage[hidelinks]{{hyperref}}
\usepackage{{fancyhdr}}
\usepackage[english]{{babel}}
\usepackage{{tabularx}}
\usepackage{{iftex}}
\ifPDFTeX
\input{{glyphtounicode}}
\fi
\usepackage{{newtxtext}}
\usepackage{{newtxmath}}

\pagestyle{{fancy}}
\fancyhf{{}}
\fancyfoot{{}}
\renewcommand{{\headrulewidth}}{{0pt}}
\renewcommand{{\footrulewidth}}{{0pt}}

\addtolength{{\oddsidemargin}}{{-0.57in}}
\addtolength{{\evensidemargin}}{{-0.57in}}
\addtolength{{\textwidth}}{{1.14in}}
\addtolength{{\topmargin}}{{-.82in}}
\addtolength{{\textheight}}{{1.88in}}

\urlstyle{{same}}

\raggedbottom
\raggedright
\setlength{{\tabcolsep}}{{0in}}

\titleformat{{\section}}{{\bfseries\raggedright\Large}}{{}}{{0em}}{{}}[\color{{black}}\titlerule]
\titlespacing*{{\section}}{{0pt}}{{11pt}}{{5pt}}
\setlist[itemize]{{parsep=0pt,partopsep=0pt,itemsep=3pt,topsep=2pt}}

\ifPDFTeX
\pdfgentounicode=1
\fi

\newcommand{{\resumeItem}}[1]{{
  \item\small{{
    {{#1}}
  }}
}}

\newcommand{{\resumeSubheading}}[4]{{
  \vspace{{1pt}}\item
    \begin{{tabular*}}{{0.97\textwidth}}[t]{{l@{{\extracolsep{{\fill}}}}r}}
      \textbf{{\large #1}} & {{\normalfont\small #2}} \\
      \textit{{\small #3}} & \textit{{\small #4}} \\
    \end{{tabular*}}\vspace{{-1pt}}
}}

\newcommand{{\resumeProjectHeading}}[4]{{
  \item
  \begin{{tabular*}}{{0.97\textwidth}}{{l@{{\extracolsep{{\fill}}}}r}}
    {{\large\textbf{{#1}} $|$ #2}} & {{\normalfont\small #3}} \\
  \end{{tabular*}}\vspace{{-2pt}}\\
  {{\small\textit{{#4}}}}\par\vspace{{-1pt}}
}}

\renewcommand\labelitemii{{$\vcenter{{\hbox{{\tiny$\bullet$}}}}$}}

\newcommand{{\resumeSubHeadingListStart}}{{\begin{{itemize}}[leftmargin=0.15in, label={{}},itemsep=7pt,topsep=2pt]}}
\newcommand{{\resumeSubHeadingListEnd}}{{\end{{itemize}}}}
\newcommand{{\resumeItemListStart}}{{\begin{{itemize}}[leftmargin=0.24in,itemsep=3pt,topsep=1pt]}}
\newcommand{{\resumeItemListEnd}}{{\end{{itemize}}}}

\begin{{document}}

\begin{{center}}
    \textbf{{\LARGE Nitin Singh Rathore}} \\ \vspace{{1pt}}
    \small +1 817 819 8146 $|$ \href{{mailto:nxr3560@mavs.uta.edu}}{{\underline{{nxr3560@mavs.uta.edu}}}} $|$
    \href{{https://www.linkedin.com/in/nitin-singh-rathore}}{{\underline{{linkedin.com/in/nitin-singh-rathore}}}} $|$
    \href{{https://github.com/Nitin3560}}{{\underline{{github.com/Nitin3560}}}} $|$
    \href{{https://www.nitinsinghrathore.us/}}{{\underline{{nitinsinghrathore.us}}}}
\end{{center}}

\section{{Technical Skills}}
 \begin{{itemize}}[leftmargin=0.18in, label={{}},itemsep=0pt,topsep=0pt]
    \small{{\item[]{{
{_render_skills(requirements, job)}
    }}}}
 \end{{itemize}}

\section{{Work Experience}}
  \resumeSubHeadingListStart

    \resumeSubheading
  {{Software Engineer}}{{Sept 2023 -- Oct 2024}}
  {{WERBOOZ Pvt. Ltd}}{{Indore, India}}
  \resumeItemListStart
    \resumeItem{{Built and maintained 6 production backend services in Java and Apex across 3 client applications, delivering REST APIs for scheduling, billing, and authentication that cut manual processing $\sim$40\%.}}
    \resumeItem{{Refactored 15+ high-latency SQL/SOQL queries across backend microservices, improving query performance 35\% via indexing and caching.}}
    \resumeItem{{Engineered REST and SOAP API integrations with 5+ internal and third-party systems, sustaining 99.8\% uptime with JSON/XML mapping and retry logic.}}
    \resumeItem{{Authored 500+ automated test cases (JUnit, Postman, Tosca) in CI/CD, cutting post-release defects 30\% and resolving 12 incidents within 2-hour SLA.}}
  \resumeItemListEnd

    \resumeSubheading
  {{Software Engineer Intern}}{{Feb 2023 -- Sept 2023}}
  {{WERBOOZ Pvt. Ltd}}{{Indore, India}}
  \resumeItemListStart
    \resumeItem{{Refactored 4 Java/SQL data-access modules into reusable components, cutting average query execution from $\sim$320 ms to $\sim$275 ms ($\sim$15\% faster).}}
    \resumeItem{{Delivered 4 backend features across 2 production releases through Git pull requests and peer code review, adding JUnit tests that prevented 20+ defects across 3 release cycles.}}
  \resumeItemListEnd

\resumeSubheading
  {{Graduate Teaching Assistant}}{{Aug 2025 -- Present}}
  {{CSE Department, University of Texas at Arlington}}{{Arlington, Texas}}
  \resumeItemListStart
    \resumeItem{{Built a Python tool automating grading for 50+ weekly assignments; mentored 100+ students debugging Python and C/C++ in Data Science and ML coursework.}}
  \resumeItemListEnd

  \resumeSubHeadingListEnd

\section{{Projects}}
    \begin{{itemize}}[leftmargin=0.15in,label={{}},itemsep=8pt,topsep=2pt]
{_render_projects(requirements, job, bullets, project_limit=project_limit)}
    \resumeSubHeadingListEnd

\section{{Research \& Publications}}
 \begin{{itemize}}[leftmargin=0.15in, label={{}}]
    \small{{\item{{
     \textbf{{IEEE CSCN 2026}}{{: Integrity-Aware Digital Twin Synchronization for ISAC-Enabled UAV Networks}} \\
     \textbf{{M.S. Thesis}}{{: Cross-Layer Supervisory Control for Low-Altitude UAV Swarm Networks}}
    }}}}
 \end{{itemize}}

\section{{Education}}
\begin{{itemize}}[leftmargin=0.15in,label={{}},topsep=2pt]
\item
\begin{{minipage}}[t]{{0.48\linewidth}}
\small\textbf{{University of Texas at Arlington}}\\
\textit{{M.S. Computer Science}} $|$ Expected Dec 2026\\
Arlington, Texas
\end{{minipage}}\hfill
\begin{{minipage}}[t]{{0.50\linewidth}}
\small\textbf{{Acropolis Institute of Technology \& Research}}\\
\textit{{B.Tech. Computer Science}} $|$ 2019 -- 2023\\
India
\end{{minipage}}
\end{{itemize}}

\end{{document}}
"""


def compile_latex_resume(tex_path: Path) -> Path:
    tectonic = shutil.which("tectonic")
    if tectonic is None:
        raise RuntimeError("tectonic is not installed; wrote .tex but could not compile PDF")
    try:
        subprocess.run(
            [tectonic, tex_path.name],
            cwd=tex_path.parent,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=60,
        )
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"LaTeX compile failed:\n{exc.stdout}") from exc
    pdf_path = tex_path.with_suffix(".pdf")
    if not pdf_path.exists() or pdf_path.stat().st_size == 0:
        raise RuntimeError("LaTeX compile did not produce a PDF")
    return pdf_path


def pdf_page_count(pdf_path: Path) -> int | None:
    pdfinfo = shutil.which("pdfinfo")
    if pdfinfo is None:
        return None
    result = subprocess.run(
        [pdfinfo, str(pdf_path)],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=20,
    )
    match = re.search(r"^Pages:\s+(\d+)$", result.stdout, flags=re.M)
    return int(match.group(1)) if match else None


def write_tailored_resume(output_dir: Path, job, requirements: dict | None, bullets: list[dict] | None = None) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    tex_path = output_dir / f"{RESUME_FILENAME}.tex"
    last_page_count = None
    for project_limit in (3, 2):
        tex_path.write_text(
            generate_tailored_latex(job, requirements, bullets, project_limit=project_limit),
            encoding="utf-8",
        )
        pdf_path = compile_latex_resume(tex_path)
        page_count = pdf_page_count(pdf_path)
        last_page_count = page_count
        if page_count in (None, 1):
            return {
                "tex_path": str(tex_path),
                "pdf_path": str(pdf_path),
                "page_count": page_count,
                "project_count": project_limit,
            }
    raise RuntimeError(f"compiled resume must be one page; got {last_page_count}")


def generate_docx(content: dict) -> bytes:
    from docx import Document
    from docx.shared import Pt

    doc = Document()
    doc.add_heading(content.get("full_name") or "Resume", level=1)
    if content.get("summary"):
        doc.add_paragraph(content["summary"])
    skills = content.get("skills", [])
    if skills:
        doc.add_heading("Skills", level=2)
        doc.add_paragraph(", ".join(skill.get("name", "") for skill in skills if skill.get("name")))
    experience = content.get("experience", [])
    if experience:
        doc.add_heading("Experience", level=2)
        for exp in experience:
            paragraph = doc.add_paragraph()
            run = paragraph.add_run(exp.get("title", ""))
            run.bold = True
            if exp.get("company"):
                paragraph.add_run(f" - {exp['company']}")
            if exp.get("duration"):
                duration = doc.add_paragraph(exp["duration"])
                duration.runs[0].italic = True
                duration.runs[0].font.size = Pt(10)
            for highlight in exp.get("highlights", []):
                if highlight.strip():
                    doc.add_paragraph(highlight, style="List Bullet")
    education = content.get("education", [])
    if education:
        doc.add_heading("Education", level=2)
        for education_item in education:
            line = f"{education_item.get('degree', '')} - {education_item.get('institution', '')}"
            if education_item.get("year"):
                line += f" ({education_item['year']})"
            doc.add_paragraph(line)
    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer.read()


def _pdf_text(value: object) -> str:
    return escape(str(value or ""))


def generate_pdf(content: dict) -> bytes:
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.platypus import ListFlowable, ListItem, Paragraph, SimpleDocTemplate, Spacer

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.75 * inch, bottomMargin=0.75 * inch)
    styles = getSampleStyleSheet()
    heading_style = ParagraphStyle("SectionHeading", parent=styles["Heading2"], spaceBefore=12, spaceAfter=6)
    story = [Paragraph(_pdf_text(content.get("full_name") or "Resume"), styles["Title"])]
    if content.get("summary"):
        story.append(Spacer(1, 8))
        story.append(Paragraph(_pdf_text(content["summary"]), styles["Normal"]))
    skills = content.get("skills", [])
    if skills:
        story.append(Paragraph("Skills", heading_style))
        story.append(Paragraph(_pdf_text(", ".join(skill.get("name", "") for skill in skills if skill.get("name"))), styles["Normal"]))
    experience = content.get("experience", [])
    if experience:
        story.append(Paragraph("Experience", heading_style))
        for exp in experience:
            title_line = f"<b>{_pdf_text(exp.get('title', ''))}</b>"
            if exp.get("company"):
                title_line += f" - {_pdf_text(exp['company'])}"
            story.append(Paragraph(title_line, styles["Normal"]))
            if exp.get("duration"):
                story.append(Paragraph(f"<i>{_pdf_text(exp['duration'])}</i>", styles["Normal"]))
            bullets = [
                ListItem(Paragraph(_pdf_text(highlight), styles["Normal"]))
                for highlight in exp.get("highlights", [])
                if highlight.strip()
            ]
            if bullets:
                story.append(ListFlowable(bullets, bulletType="bullet"))
            story.append(Spacer(1, 6))
    education = content.get("education", [])
    if education:
        story.append(Paragraph("Education", heading_style))
        for education_item in education:
            line = f"{education_item.get('degree', '')} - {education_item.get('institution', '')}"
            if education_item.get("year"):
                line += f" ({education_item['year']})"
            story.append(Paragraph(_pdf_text(line), styles["Normal"]))
    doc.build(story)
    buffer.seek(0)
    return buffer.read()
