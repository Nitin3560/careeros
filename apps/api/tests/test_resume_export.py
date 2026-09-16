from types import SimpleNamespace

from app.services import resume_export


def test_generate_tailored_latex_keeps_master_sections_and_six_skill_lines():
    job = SimpleNamespace(
        title="Backend Engineer",
        company="Example",
        description_text="Python FastAPI PostgreSQL Docker",
    )

    latex = resume_export.generate_tailored_latex(
        job,
        {"hard_requirements": [{"skill": "Python"}, {"skill": "FastAPI"}]},
        [],
    )

    assert "\\section{Technical Skills}" in latex
    assert "\\section{Work Experience}" in latex
    assert "\\section{Projects}" in latex
    assert "\\section{Education}" in latex
    assert latex.count("\\textbf{") >= 6
    assert "FastAPI" in latex


def test_skill_lines_preserve_fixed_template_density():
    job = SimpleNamespace(title="Software Engineer, New Grad", company="IXL", description_text="")

    latex = resume_export.generate_tailored_latex(
        job,
        {
            "preferred": [
                {"type": "technology", "value": "TypeScript"},
                {"type": "technology", "value": "JavaScript"},
                {"type": "technology", "value": "React Native"},
                {"type": "technology", "value": "MySQL"},
                {"type": "technology", "value": "MongoDB"},
                {"type": "technology", "value": "Valkey"},
                {"type": "technology", "value": "Unix"},
            ]
        },
        [],
    )

    assert "Languages: TypeScript/JavaScript, Python, Go, Java, SQL, C++ (C++17)" in latex
    assert "\\textbf{Languages}" not in latex
    assert "TypeScript/JavaScript, JavaScript" not in latex
    assert "AI Agents:" in latex
    assert "Frontend:" in latex
    assert "Backend \\& APIs:" in latex
    assert "Cloud \\& Data:" in latex
    assert "Delivery \\& Practices:" in latex


def test_bold_scope_matches_requested_resume_fields():
    job = SimpleNamespace(title="Software Engineer, New Grad", company="IXL", description_text="")

    latex = resume_export.generate_tailored_latex(job, {}, [], project_limit=3)

    assert "\\textbf{\\Large Nitin Singh Rathore}" in latex
    assert "\\textbf{#1} $|$ #2" in latex
    assert "\\textbf{IEEE CSCN 2026}" in latex
    assert "M.S. Thesis{: \\textbf{Cross-Layer Supervisory Control for Low-Altitude UAV Swarm Networks}}" in latex
    assert "\\textbf{University of Texas at Arlington}" in latex
    assert "\\textbf{Acropolis Institute of Technology \\& Research}" in latex

    assert "\\textbf{Languages}" not in latex
    assert "\\textbf{Software Engineer}" not in latex
    assert "\\textbf{WERBOOZ Pvt. Ltd}" not in latex


def test_project_order_matches_reference_style():
    job = SimpleNamespace(
        title="Robotics Software Engineer",
        company="Example",
        description_text="C++ ROS 2 PX4 robotics embedded systems",
    )

    latex = resume_export.generate_tailored_latex(job, {}, [], project_limit=1)

    assert "{YoMeets}" in latex
    assert "{CareerOS}" not in latex


def test_write_tailored_resume_retries_with_two_projects(monkeypatch, tmp_path):
    calls = []

    def fake_compile(tex_path):
        return tex_path.with_suffix(".pdf")

    def fake_page_count(_pdf_path):
        calls.append(1)
        return 2 if len(calls) == 1 else 1

    monkeypatch.setattr(resume_export, "compile_latex_resume", fake_compile)
    monkeypatch.setattr(resume_export, "pdf_page_count", fake_page_count)

    result = resume_export.write_tailored_resume(
        tmp_path,
        SimpleNamespace(title="Backend Engineer", company="Example", description_text="Python"),
        {},
        [],
    )

    assert result["project_count"] == 2
    assert len(calls) == 2
