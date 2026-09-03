import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))

import apply_title_filter  # noqa: E402


def matches(pattern: str, title: str) -> bool:
    return re.search(pattern.replace(r"\y", r"\b"), title, re.IGNORECASE) is not None


def test_role_head_filter_excludes_sales_engineer_not_sales_platform():
    assert matches(apply_title_filter.ROLE_HEAD_PATTERN, "Senior Sales Engineer")
    assert not matches(
        apply_title_filter.ROLE_HEAD_PATTERN,
        "Software Engineer, Sales Platform",
    )


def test_seniority_filter_excludes_staff_principal_and_architect():
    assert matches(apply_title_filter.SENIORITY_PATTERN, "Staff Software Engineer")
    assert matches(apply_title_filter.SENIORITY_PATTERN, "Principal Software Engineer")
    assert matches(apply_title_filter.SENIORITY_PATTERN, "Software Architect")


def test_swe_title_filter_keeps_early_career_relevant_titles():
    assert matches(apply_title_filter.SWE_TITLE_PATTERN, "Software Engineer")
    assert matches(apply_title_filter.SWE_TITLE_PATTERN, "Backend Engineer")
    assert matches(apply_title_filter.SWE_TITLE_PATTERN, "Machine Learning Engineer")
