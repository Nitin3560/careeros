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


def test_skill_lines_include_structured_jd_technologies_without_duplicate_typescript():
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

    assert "TypeScript/JavaScript, JavaScript" not in latex
    assert "React Native" in latex
    assert "MySQL" in latex
    assert "MongoDB" in latex
    assert "Valkey" in latex
    assert "Unix" in latex


def test_project_order_uses_job_terms():
    job = SimpleNamespace(
        title="Robotics Software Engineer",
        company="Example",
        description_text="C++ ROS 2 PX4 robotics embedded systems",
    )

    latex = resume_export.generate_tailored_latex(job, {}, [], project_limit=1)

    assert "{TwinGuard}" in latex
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
