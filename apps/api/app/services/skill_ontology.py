import re

EQUIVALENTS = {
    "golang": "go",
    "k8s": "kubernetes",
    "postgres": "postgresql",
    "python3": "python",
    "react.js": "react",
    "reactjs": "react",
    "node": "node.js",
    "nodejs": "node.js",
    "ts": "typescript",
    "js": "javascript",
}

SPECIALIZATIONS = {
    "fastapi": {"python", "rest api", "backend"},
    "postgresql": {"sql", "relational database", "rdbms", "database"},
    "react": {"javascript", "frontend", "web"},
    "docker": {"containers", "containerization"},
    "kubernetes": {"containers", "orchestration"},
    "ros2": {"robotics", "robot operating system"},
    "px4": {"uav", "autonomy", "flight control"},
    "gazebo": {"simulation", "robotics simulation"},
    "kalman filters": {"sensor fusion", "state estimation"},
    "distributed systems": {"backend", "systems"},
}

KNOWN_TERMS = {
    *EQUIVALENTS.keys(),
    *EQUIVALENTS.values(),
    *SPECIALIZATIONS.keys(),
    *(term for terms in SPECIALIZATIONS.values() for term in terms),
}


def canonical(term: str) -> str:
    normalized = " ".join(str(term or "").lower().replace("/", " ").split())
    return EQUIVALENTS.get(normalized, normalized)


def expanded_profile_terms(terms: set[str]) -> set[str]:
    expanded = set()
    for term in terms:
        base = canonical(term)
        expanded.add(base)
        expanded.update(SPECIALIZATIONS.get(base, set()))
    return expanded


def requirement_terms(value: str) -> set[str]:
    raw = str(value or "").lower()
    split_ready = (
        raw.replace("and/or", ",")
        .replace("/", ",")
        .replace(";", ",")
    )
    split_ready = re.sub(r"\b(?:or|and)\b", ",", split_ready)
    parts = {canonical(part.strip()) for part in split_ready.split(",") if part.strip()}

    searchable = canonical(raw)
    for term in KNOWN_TERMS:
        canonical_term = canonical(term)
        if re.search(rf"\b{re.escape(canonical_term)}\b", searchable):
            parts.add(canonical_term)

    return {part for part in parts if part}
