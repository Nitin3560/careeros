import importlib.util
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[3] / "scripts" / "audit_source_eligibility.py"
SPEC = importlib.util.spec_from_file_location("audit_source_eligibility_script", SCRIPT_PATH)
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)


def test_audit_source_eligibility_prints_source_distribution(monkeypatch, capsys):
    class FakeResult:
        def all(self):
            return [("amazon", 450, 1123, 40.1), ("greenhouse", 5698, 190137, 3.0)]

    class FakeDb:
        def execute(self, statement):
            sql = str(statement)
            assert "count(*) FILTER (WHERE eligible)" in sql
            assert "GROUP BY 1" in sql
            return FakeResult()

        def close(self):
            return None

    monkeypatch.setattr(audit, "SessionLocal", lambda: FakeDb())

    audit.main()

    output = capsys.readouterr().out
    assert "source" in output
    assert "amazon" in output
    assert "450" in output
    assert "40.1%" in output
