import re

EQUIVALENTS = {
    "amazon web services": "aws",
    "ci cd": "ci/cd",
    "cicd": "ci/cd",
    "continuous integration": "ci/cd",
    "continuous delivery": "ci/cd",
    "continuous deployment": "ci/cd",
    "ci/cd pipelines": "ci/cd",
    "c sharp": "c#",
    "cpp": "c++",
    "gcp": "google cloud",
    "golang": "go",
    "google cloud platform": "google cloud",
    "graphql api": "graphql",
    "k8s": "kubernetes",
    "llms": "llm",
    "large language model": "llm",
    "large language models": "llm",
    "next": "next.js",
    "nextjs": "next.js",
    "postgres": "postgresql",
    "postgres sql": "postgresql",
    "python3": "python",
    "react.js": "react",
    "reactjs": "react",
    "redis cache": "redis",
    "rest": "rest api",
    "rest apis": "rest api",
    "restful api": "rest api",
    "rq": "redis queue",
    "node": "node.js",
    "nodejs": "node.js",
    "ts": "typescript",
    "js": "javascript",
    "vector db": "vector database",
    "vector search": "vector database",
}

SPECIALIZATIONS = {
    "airflow": {"data engineering", "workflow orchestration"},
    "angular": {"javascript", "typescript", "frontend", "web"},
    "ansible": {"configuration management", "devops", "infrastructure automation"},
    "aws lambda": {"aws", "serverless", "cloud"},
    "aws": {"cloud"},
    "azure": {"cloud"},
    "bash": {"shell scripting", "linux"},
    "c#": {"programming language", "backend"},
    "c++": {"programming language", "systems"},
    "celery": {"python", "background jobs", "task queue"},
    "ci/cd": {"devops", "developer tools"},
    "claude code": {"ai coding tools", "developer tools"},
    "code reviews": {"software engineering", "collaboration"},
    "cursor": {"ai coding tools", "developer tools"},
    "databricks": {"data engineering", "spark", "analytics"},
    "datadog": {"observability", "monitoring"},
    "django": {"python", "backend", "web"},
    "docker": {"containers", "containerization", "devops"},
    "elasticsearch": {"search", "information retrieval"},
    "fastapi": {"python", "rest api", "backend", "web"},
    "flask": {"python", "rest api", "backend", "web"},
    "github actions": {"ci/cd", "devops"},
    "git": {"source control management", "version control"},
    "google cloud": {"cloud"},
    "grafana": {"observability", "monitoring", "metrics"},
    "graphql": {"api", "backend"},
    "grpc": {"api", "backend", "distributed systems"},
    "helm": {"kubernetes", "devops"},
    "java": {"programming language", "backend"},
    "jenkins": {"ci/cd", "devops"},
    "jest": {"testing", "javascript", "frontend testing"},
    "kafka": {"event streaming", "distributed systems", "messaging"},
    "kotlin": {"programming language", "backend", "android"},
    "langchain": {"llm", "rag", "ai"},
    "linux": {"operating systems", "systems"},
    "llm": {"ai", "machine learning"},
    "mongodb": {"nosql database", "database"},
    "mysql": {"sql", "relational database", "database"},
    "next.js": {"react", "javascript", "typescript", "frontend", "web"},
    "perl": {"programming language", "scripting"},
    "pinecone": {"vector database", "vector search", "rag"},
    "playwright": {"testing", "end-to-end testing", "browser automation"},
    "postgresql": {"sql", "relational database", "rdbms", "database"},
    "prometheus": {"observability", "monitoring", "metrics"},
    "pytest": {"testing", "python"},
    "rag": {"llm", "information retrieval", "ai"},
    "rabbitmq": {"message queue", "messaging", "distributed systems"},
    "react": {"javascript", "frontend", "web"},
    "redis": {"cache", "in-memory database", "database"},
    "redis queue": {"background jobs", "task queue", "redis"},
    "rest api": {"api", "backend"},
    "rust": {"programming language", "systems"},
    "scala": {"programming language", "backend", "data engineering"},
    "sqlalchemy": {"python", "orm", "database"},
    "snowflake": {"data warehouse", "analytics", "sql"},
    "spark": {"data engineering", "distributed systems"},
    "sql server": {"sql", "relational database", "database"},
    "supabase": {"postgresql", "backend as a service"},
    "swift": {"programming language", "ios"},
    "swiftui": {"swift", "ios", "frontend"},
    "tailwind": {"css", "frontend", "web"},
    "terraform": {"infrastructure as code", "devops", "cloud"},
    "typescript": {"javascript", "frontend", "web"},
    "vitest": {"testing", "javascript", "frontend testing"},
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


def relation(profile_term: str, requirement_term: str) -> str | None:
    profile_base = canonical(profile_term)
    requirement_base = canonical(requirement_term)
    if profile_base == requirement_base:
        return "equivalent"
    if requirement_base in SPECIALIZATIONS.get(profile_base, set()):
        return "specialization"
    return None


def satisfies_requirement(profile_term: str, requirement_term: str) -> bool:
    return relation(profile_term, requirement_term) is not None


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
