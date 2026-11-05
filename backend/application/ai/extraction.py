from __future__ import annotations

import re
from typing import Dict, List, Optional, Set, Tuple
from datetime import date

from application.ai.schemas import DEGREE_LEVELS, EducationEntry

_DEFAULT_ALIASES: Dict[str, str] = {

    "js": "JavaScript", "javascript": "JavaScript", "ecmascript": "JavaScript",
    "es6": "JavaScript", "es2015": "JavaScript", "es2020": "JavaScript",
    "typescript": "TypeScript", "ts": "TypeScript",
    "react": "React", "react.js": "React", "reactjs": "React",
    "react native": "React Native", "react-native": "React Native",
    "next": "Next.js", "next.js": "Next.js", "nextjs": "Next.js",
    "vue": "Vue", "vue.js": "Vue", "vuejs": "Vue",
    "nuxt": "Nuxt.js", "nuxt.js": "Nuxt.js", "nuxtjs": "Nuxt.js",
    "angular": "Angular", "angularjs": "Angular", "angular.js": "Angular",
    "svelte": "Svelte", "sveltekit": "SvelteKit",
    "node": "Node.js", "node.js": "Node.js", "nodejs": "Node.js",
    "express": "Express", "express.js": "Express", "expressjs": "Express",
    "nest": "NestJS", "nestjs": "NestJS", "nest.js": "NestJS",
    "deno": "Deno", "bun": "Bun",
    "jquery": "jQuery", "webpack": "Webpack", "vite": "Vite",
    "babel": "Babel", "eslint": "ESLint", "prettier": "Prettier",
    "jest": "Jest", "mocha": "Mocha", "cypress": "Cypress",
    "playwright": "Playwright", "puppeteer": "Puppeteer",
    "storybook": "Storybook", "tailwind": "Tailwind CSS",
    "tailwindcss": "Tailwind CSS", "tailwind css": "Tailwind CSS",
    "bootstrap": "Bootstrap", "material ui": "Material UI",
    "mui": "Material UI", "chakra ui": "Chakra UI",
    "styled components": "Styled Components", "sass": "Sass",
    "scss": "Sass", "less": "Less",

    "python": "Python", "python3": "Python", "py": "Python",
    "django": "Django", "flask": "Flask", "fastapi": "FastAPI",
    "fast api": "FastAPI", "tornado": "Tornado",
    "celery": "Celery", "gunicorn": "Gunicorn", "uvicorn": "Uvicorn",
    "pytest": "pytest", "unittest": "unittest",
    "pandas": "pandas", "numpy": "NumPy", "np": "NumPy",
    "scipy": "SciPy", "matplotlib": "Matplotlib",
    "scikit-learn": "scikit-learn", "sklearn": "scikit-learn",
    "tensorflow": "TensorFlow", "tf": "TensorFlow",
    "pytorch": "PyTorch", "torch": "PyTorch",
    "keras": "Keras", "huggingface": "Hugging Face",
    "hugging face": "Hugging Face", "transformers": "Transformers",
    "langchain": "LangChain", "llamaindex": "LlamaIndex",
    "spacy": "spaCy", "nltk": "NLTK",
    "opencv": "OpenCV", "pillow": "Pillow",
    "pydantic": "Pydantic", "sqlalchemy": "SQLAlchemy",
    "alembic": "Alembic", "beautifulsoup": "BeautifulSoup",
    "scrapy": "Scrapy", "airflow": "Apache Airflow",
    "apache airflow": "Apache Airflow", "luigi": "Luigi",
    "dask": "Dask", "ray": "Ray",
    "streamlit": "Streamlit", "gradio": "Gradio",
    "jupyterlab": "JupyterLab", "jupyter": "Jupyter",
    "poetry": "Poetry", "pip": "pip", "conda": "Conda",
    "pipenv": "Pipenv",

    "java": "Java", "kotlin": "Kotlin", "scala": "Scala",
    "spring": "Spring", "spring boot": "Spring Boot",
    "springboot": "Spring Boot", "hibernate": "Hibernate",
    "maven": "Maven", "gradle": "Gradle",
    "junit": "JUnit", "groovy": "Groovy", "clojure": "Clojure",

    "c": "C", "c++": "C++", "cpp": "C++", "modern c++": "C++", "embedded c": "C",
    "c#": "C#", "csharp": "C#", "c sharp": "C#",
    ".net": ".NET", "dotnet": ".NET", "asp.net": "ASP.NET",
    "rust": "Rust", "go": "Go", "golang": "Go",
    "zig": "Zig", "swift": "Swift", "objective-c": "Objective-C",
    "objc": "Objective-C",

    "docker": "Docker", "kubernetes": "Kubernetes", "k8s": "Kubernetes",
    "helm": "Helm", "terraform": "Terraform", "ansible": "Ansible",
    "puppet": "Puppet", "chef": "Chef", "vagrant": "Vagrant",
    "jenkins": "Jenkins", "github actions": "GitHub Actions",
    "gitlab ci": "GitLab CI", "circleci": "CircleCI",
    "travis ci": "Travis CI", "travisci": "Travis CI",
    "argo cd": "Argo CD", "argocd": "Argo CD",
    "prometheus": "Prometheus", "grafana": "Grafana",
    "datadog": "Datadog", "new relic": "New Relic",
    "elk": "ELK Stack", "logstash": "Logstash",
    "elasticsearch": "Elasticsearch", "kibana": "Kibana",
    "splunk": "Splunk", "nagios": "Nagios",
    "nginx": "NGINX", "apache": "Apache HTTP Server",
    "haproxy": "HAProxy", "envoy": "Envoy",
    "istio": "Istio", "linkerd": "Linkerd",
    "consul": "Consul", "vault": "HashiCorp Vault",
    "packer": "Packer",

    "aws": "AWS", "amazon web services": "AWS",
    "gcp": "GCP", "google cloud": "GCP",
    "google cloud platform": "GCP",
    "azure": "Azure", "microsoft azure": "Azure",
    "s3": "AWS S3", "ec2": "AWS EC2", "lambda": "AWS Lambda",
    "dynamodb": "DynamoDB", "cloudfront": "CloudFront",
    "cloudformation": "CloudFormation", "cdk": "AWS CDK",
    "sqs": "AWS SQS", "sns": "AWS SNS", "ecs": "AWS ECS",
    "eks": "AWS EKS", "fargate": "AWS Fargate",
    "sagemaker": "AWS SageMaker",
    "heroku": "Heroku", "vercel": "Vercel", "netlify": "Netlify",
    "digitalocean": "DigitalOcean", "linode": "Linode",
    "cloudflare": "Cloudflare",

    "sql": "SQL", "mysql": "MySQL", "postgresql": "PostgreSQL",
    "postgres": "PostgreSQL", "pg": "PostgreSQL",
    "sqlite": "SQLite", "mariadb": "MariaDB",
    "oracle": "Oracle DB", "oracle db": "Oracle DB",
    "sql server": "SQL Server", "mssql": "SQL Server",
    "mongodb": "MongoDB", "mongo": "MongoDB",
    "redis": "Redis", "memcached": "Memcached",
    "cassandra": "Cassandra", "dynamodb": "DynamoDB",
    "couchdb": "CouchDB", "couchbase": "Couchbase",
    "neo4j": "Neo4j", "firebase": "Firebase",
    "firestore": "Firestore", "supabase": "Supabase",
    "cockroachdb": "CockroachDB",
    "influxdb": "InfluxDB", "timescaledb": "TimescaleDB",

    "kafka": "Apache Kafka", "apache kafka": "Apache Kafka",
    "rabbitmq": "RabbitMQ", "rabbit mq": "RabbitMQ",
    "nats": "NATS", "pulsar": "Apache Pulsar",
    "zeromq": "ZeroMQ", "activemq": "ActiveMQ",

    "git": "Git", "github": "GitHub", "gitlab": "GitLab",
    "bitbucket": "Bitbucket", "svn": "SVN", "subversion": "SVN",
    "mercurial": "Mercurial",

    "machine learning": "Machine Learning", "ml": "Machine Learning",
    "deep learning": "Deep Learning", "dl": "Deep Learning",
    "artificial intelligence": "AI", "ai": "AI",
    "nlp": "NLP", "natural language processing": "NLP",
    "computer vision": "Computer Vision", "cv": "Computer Vision",
    "reinforcement learning": "Reinforcement Learning", "rl": "Reinforcement Learning",
    "llm": "LLM", "large language model": "LLM",
    "generative ai": "Generative AI", "gen ai": "Generative AI",
    "rag": "RAG", "retrieval augmented generation": "RAG",
    "mlops": "MLOps", "data engineering": "Data Engineering",
    "data science": "Data Science", "data analysis": "Data Analysis",
    "etl": "ETL", "data pipeline": "Data Pipeline",
    "feature engineering": "Feature Engineering",
    "a/b testing": "A/B Testing", "ab testing": "A/B Testing",
    "spark": "Apache Spark", "apache spark": "Apache Spark",
    "pyspark": "PySpark", "hadoop": "Hadoop",
    "hive": "Apache Hive", "presto": "Presto",
    "trino": "Trino", "dbt": "dbt",
    "snowflake": "Snowflake", "redshift": "Amazon Redshift",
    "bigquery": "BigQuery", "google bigquery": "BigQuery",
    "databricks": "Databricks", "mlflow": "MLflow",
    "kubeflow": "Kubeflow", "wandb": "Weights & Biases",
    "weights and biases": "Weights & Biases",

    "ios": "iOS", "android": "Android", "android sdk": "Android", "android studio": "Android Studio",
    "flutter": "Flutter", "dart": "Dart",
    "swiftui": "SwiftUI", "jetpack compose": "Jetpack Compose",
    "xamarin": "Xamarin", "cordova": "Cordova",
    "ionic": "Ionic", "expo": "Expo",

    "selenium": "Selenium", "appium": "Appium",
    "testng": "TestNG", "robot framework": "Robot Framework",
    "postman": "Postman", "insomnia": "Insomnia",
    "k6": "k6", "locust": "Locust", "jmeter": "JMeter",
    "gatling": "Gatling",

    "rest": "REST", "restful": "REST", "rest api": "REST",
    "graphql": "GraphQL", "grpc": "gRPC",
    "websocket": "WebSocket", "websockets": "WebSocket",
    "soap": "SOAP", "openapi": "OpenAPI",
    "swagger": "Swagger", "protobuf": "Protocol Buffers",
    "protocol buffers": "Protocol Buffers",
    "json": "JSON", "xml": "XML", "yaml": "YAML",
    "csv": "CSV", "avro": "Avro", "parquet": "Parquet",

    "oauth": "OAuth", "oauth2": "OAuth 2.0", "oauth 2.0": "OAuth 2.0",
    "jwt": "JWT", "saml": "SAML", "ldap": "LDAP",
    "ssl": "SSL/TLS", "tls": "SSL/TLS",
    "owasp": "OWASP", "penetration testing": "Penetration Testing",
    "cybersecurity": "Cybersecurity", "network security": "Cybersecurity",
    "information security": "Cybersecurity", "appsec": "Cybersecurity",
    "infosec": "Cybersecurity",

    "linux": "Linux", "ubuntu": "Ubuntu", "centos": "CentOS",
    "debian": "Debian", "rhel": "RHEL", "windows": "Windows",
    "macos": "macOS", "bash": "Bash", "shell": "Shell Scripting",
    "powershell": "PowerShell", "zsh": "Zsh",
    "vim": "Vim", "emacs": "Emacs", "vscode": "VS Code",
    "visual studio code": "VS Code", "intellij": "IntelliJ IDEA",
    "pycharm": "PyCharm", "eclipse": "Eclipse",
    "figma": "Figma", "sketch": "Sketch",
    "jira": "Jira", "confluence": "Confluence",
    "trello": "Trello", "asana": "Asana",
    "slack": "Slack", "notion": "Notion",
    "agile": "Agile", "scrum": "Scrum", "kanban": "Kanban",
    "ci/cd": "CI/CD", "cicd": "CI/CD",
    "tdd": "TDD", "bdd": "BDD",
    "microservices": "Microservices", "monolith": "Monolith",
    "event-driven": "Event-Driven Architecture",
    "event driven": "Event-Driven Architecture",
    "ddd": "Domain-Driven Design",
    "domain driven design": "Domain-Driven Design",
    "clean architecture": "Clean Architecture",
    "design patterns": "Design Patterns",
    "solid": "SOLID Principles",

    "leadership": "Leadership", "communication": "Communication",
    "problem solving": "Problem Solving", "problem-solving": "Problem Solving",
    "teamwork": "Teamwork", "mentoring": "Mentoring",
    "project management": "Project Management",
}

class SkillNormalizer:

    def __init__(self, extra_aliases: Optional[Dict[str, str]] = None) -> None:
        self._aliases: Dict[str, str] = dict(_DEFAULT_ALIASES)
        if extra_aliases:
            self.add_aliases(extra_aliases)

    def add_aliases(self, aliases: Dict[str, str]) -> None:
        for alias, canonical in aliases.items():
            self._aliases[alias.lower().strip()] = canonical

    def normalize(self, skill: str) -> str:
        if not skill or not skill.strip():
            return skill
        key = skill.lower().strip()
        canonical = self._aliases.get(key)
        if canonical:
            return canonical
        stripped = re.sub(r"\s*\d+(\.\d+)*\s*$", "", key)
        if stripped != key:
            canonical = self._aliases.get(stripped)
            if canonical:
                return canonical
        return skill.strip()

    def normalize_list(self, skills: List[str]) -> List[str]:
        seen: Set[str] = set()
        result: List[str] = []
        for skill in skills:
            canonical = self.normalize(skill)
            key = canonical.lower()
            if key not in seen:
                seen.add(key)
                result.append(canonical)
        return result

    @property
    def canonical_skills(self) -> Set[str]:
        return set(self._aliases.values())

_BULLET_RE = re.compile(r"^[\-\*\u2022\u25CF\u25E6\u2043\u2219]\s*")

_LIST_SPLIT_RE = re.compile(r"[,/|;]|\b(?:and|or)\b", re.IGNORECASE)

_LIST_DELIMITER_RE = re.compile(r"[,/|;]")

_LABEL_PREFIX_RE = re.compile(r"^[A-Za-z][A-Za-z /&\-]{1,40}:\s*(.+)$")

_PROSE_TRIGGER_RE = re.compile(
    r"(?:"
    r"\busing\b"
    r"|\bincluding\b"
    r"|\bsuch\s+as\b"
    r"|\blike\b"
    r"|\bexperience\s+(?:in|with|using)\b"
    r"|\bknowledge\s+of\b"
    r"|\bfamiliarity\s+with\b"
    r"|\bproficiency\s+(?:in|with)\b"
    r"|\bskilled?\s+(?:in|with)\b"
    r"|\bexpertise\s+(?:in|with)\b"
    r"|\bworked?\s+with\b"
    r"|\bproficient\s+(?:in|with)\b"
    r"|\b(?:required|requirements?|must have|skills?|technologies?|tech stack|tools?):\s*"
    r")"
    r"\s+([^.!?;:]{2,150})",
    re.IGNORECASE,
)

_PROSE_SPLIT_RE = re.compile(r"[,/|;]|\band\b|\bor\b", re.IGNORECASE)

_STOPWORDS: Set[str] = {
    "the", "and", "with", "for", "of", "a", "an", "to", "in", "on", "or",
    "experience", "years", "year", "strong", "good", "knowledge", "skills",
    "ability", "including", "etc", "responsibilities", "requirements",
    "we", "you", "our", "team", "work", "working", "familiarity",
    "understanding", "proficiency", "proficient", "exposure", "background",
    "plus", "must", "should", "prior", "using", "via", "its", "their",
    "managed", "built", "used", "developed", "deployed", "worked",
    "created", "designed", "implemented", "led", "responsible",
    "required", "is", "are", "have", "has", "be", "need", "needed",
    "programming", "development", "concepts", "fundamentals", "fundamental",
    "technologies", "technology", "tools", "tool", "expertise",
    "library", "libraries", "level", "related", "field", "practice",
    "practices", "another", "good", "strong",
}

_PROSE_EXTRA_STOPWORDS: Set[str] = {
    "scalable", "apis", "api", "systems", "system", "services", "service",
    "applications", "application", "solutions", "solution", "platforms",
    "platform", "various", "multiple", "several", "modern", "latest",
    "enterprise", "production", "large", "complex", "build", "building",
    "develop", "developing", "design", "designing", "maintain", "maintaining",
    "deploy", "deploying", "implement", "implementing", "collaborate",
    "collaborating", "developers", "engineers", "backend", "frontend",
    "fullstack", "full-stack", "stack", "other",
}

_NOISE_RE = re.compile(
    r"(?:"
    r"^\+?[\d\s\-()]{7,}$"
    r"|[\w\.-]+@[\w\.-]+"
    r"|https?://|www\.|\.(?:com|org|edu|io|in/)|github\.com|linkedin\.com"
    r"|\b(?:cgpa|gpa|percentage|score|marks)\b"
    r"|\b(?:b\.?tech|m\.?tech|b\.?e\.?|b\.?s\.?|m\.?s\.?|b\.?a\.?|m\.?a\.?|bachelor|master|ph\.?d|college|university|school|institute|degree)\b"
    r"|\b(?:san francisco|ca|ny|tx|wa|remote|seattle|new york|austin)\b"
    r"|\b(?:senior|lead|staff|principal|junior|mid)?\s*(?:software|frontend|backend|full\s*stack|sre|systems|devops|data|platform|machine\s*learning|ml|appsec|security|qa|sdet|embedded|firmware|technical|database|cloud)?\s*(?:developer|engineer|specialist|administrator|recruiter|executive|analyst|intern|architect|scientist|researcher|dba|manager)\b"
    r")",
    re.IGNORECASE,
)

_ACTION_VERB_LINE_RE = re.compile(
    r"^(?:built|designed|developed|implemented|performed|improved|created|"
    r"introduced|enabled|automated|contributed|contributing|worked|managed|"
    r"collaborated|conducted|written|actively|seeking|looking|architected|"
    r"engineered|maintained|packaged|configured|integrated|fine-tuned|tuned|"
    r"scripted|administered|audited|profiling|leveraged|spearheaded|streamlined|"
    r"monitored|evaluated|resolved|tested|debugged|authored|"
    r"added|simulated|stored|explored|trained|applied)\b",
    re.IGNORECASE,
)

_MIN_CHARS = 2
_MAX_WORDS = 5

def _strip_bullet(raw: str) -> str:
    return _BULLET_RE.sub("", raw).strip(" \t.:-\u2022")

def _trim_stopword_edges(phrase: str) -> str:
    words = phrase.split()
    while words:
        w = words[0].lower()
        if w in _STOPWORDS or w.rstrip("s") in _STOPWORDS or w.isdigit():
            words.pop(0)
        else:
            break
    while words:
        w = words[-1].lower()
        if w in _STOPWORDS or w.rstrip("s") in _STOPWORDS or w.isdigit():
            words.pop()
        else:
            break
    return " ".join(words)

def _is_valid_candidate(phrase: str, extra_stopwords: Set[str] = frozenset()) -> bool:
    if not phrase:
        return False
    words = phrase.split()
    if not words or len(words) > _MAX_WORDS:
        return False
    if len(phrase) < _MIN_CHARS:
        return False
    if not any(c.isalpha() for c in phrase):
        return False
    if phrase.isdigit() or sum(c.isdigit() for c in phrase) >= 5:
        return False
    if _NOISE_RE.search(phrase):
        return False
    if re.search(r"[a-zA-Z]+[0-9]{2,}", phrase):
        return False
    lower = phrase.lower()
    stem = lower.rstrip("s")
    if lower in _STOPWORDS or stem in _STOPWORDS:
        return False
    if lower in extra_stopwords or stem in extra_stopwords:
        return False
    return True

def _deduplicate(candidates: Set[str]) -> List[str]:
    seen: dict[str, str] = {}
    for c in candidates:
        seen.setdefault(c.lower(), c)
    return sorted(seen.values(), key=str.lower)

class SkillExtractionPipeline:

    def extract(self, section_text: str) -> List[str]:
        if not section_text or not section_text.strip():
            return []
        candidates: Set[str] = set()
        for raw_line in section_text.splitlines():
            stripped = raw_line.strip()
            if not stripped:
                continue
            line = _strip_bullet(raw_line).strip(" \t.:;!?")
            if not line:
                continue
            label_match = _LABEL_PREFIX_RE.match(line)
            if label_match:
                self._split_and_add(label_match.group(1), candidates)
                continue
            if _ACTION_VERB_LINE_RE.match(line):
                continue
            is_bullet = bool(_BULLET_RE.match(stripped))
            is_prose_sentence = stripped.endswith((".", "!", "?")) and not is_bullet and line.count(",") < 2
            if not is_prose_sentence and (_LIST_SPLIT_RE.search(line) and len(line.split()) <= 15):
                self._split_and_add(line, candidates)
                continue
            if is_bullet and len(line.split()) <= 10:
                trimmed = _trim_stopword_edges(line)
                if _is_valid_candidate(trimmed) and len(trimmed.split()) <= _MAX_WORDS:
                    candidates.add(trimmed)
                continue
        if candidates:
            return _deduplicate(candidates)
        return self.extract_from_prose(section_text)

    def extract_from_prose(self, prose_text: str) -> List[str]:
        if not prose_text or not prose_text.strip():
            return []
        candidates: Set[str] = set()
        for match in _PROSE_TRIGGER_RE.finditer(prose_text):
            fragment = match.group(1)
            for raw_part in _PROSE_SPLIT_RE.split(fragment):
                phrase = _trim_stopword_edges(_strip_bullet(raw_part))
                if _is_valid_candidate(phrase, extra_stopwords=_PROSE_EXTRA_STOPWORDS):
                    candidates.add(phrase)
        return _deduplicate(candidates)

    def _split_and_add(self, source: str, candidates: Set[str]) -> None:
        clean_source = re.sub(
            r"https?://\S+|www\.\S+|\S+@\S+|\b[\w\.-]+\.(?:com|org|edu|io|in)\S*",
            "",
            source,
            flags=re.IGNORECASE,
        )
        clean_source = clean_source.replace("(", ", ").replace(")", ", ")
        for part in _LIST_SPLIT_RE.split(clean_source):
            phrase = _trim_stopword_edges(_strip_bullet(part))
            if _is_valid_candidate(phrase):
                candidates.add(phrase)

_DEFAULT_NORMALIZER = SkillNormalizer()
_ALTERNATIVE_SPLIT_RE = re.compile(r"\s+or\s+|/|\|", re.IGNORECASE)
_CONJUNCTION_SPLIT_RE = re.compile(r"\s+and\s+|,", re.IGNORECASE)

_SKILL_EMB_CACHE: Dict[str, np.ndarray] = {}

def soft_match_skill(
    req_skill: str,
    candidate_skills: Sequence[str],
    embedder: Any,
    threshold: float = 0.80,
) -> Tuple[bool, Optional[str]]:
    if not embedder or not req_skill.strip() or not candidate_skills:
        return False, None
    import numpy as np
    req_clean = req_skill.strip().lower()
    if req_clean not in _SKILL_EMB_CACHE:
        try:
            vec = embedder.embed_text(req_clean)
            norm = np.linalg.norm(vec)
            _SKILL_EMB_CACHE[req_clean] = vec / norm if norm > 0 else vec
        except Exception:
            return False, None
    req_vec = _SKILL_EMB_CACHE.get(req_clean)
    if req_vec is None:
        return False, None

    best_sim = -1.0
    best_cand = None
    for cand in candidate_skills:
        c_clean = cand.strip().lower()
        if not c_clean:
            continue
        if c_clean not in _SKILL_EMB_CACHE:
            try:
                vec = embedder.embed_text(c_clean)
                norm = np.linalg.norm(vec)
                _SKILL_EMB_CACHE[c_clean] = vec / norm if norm > 0 else vec
            except Exception:
                continue
        cand_vec = _SKILL_EMB_CACHE.get(c_clean)
        if cand_vec is not None:
            sim = float(np.dot(req_vec, cand_vec))
            if sim > best_sim:
                best_sim = sim
                best_cand = cand

    if best_sim >= threshold and best_cand is not None:
        return True, f"{best_cand} (soft {best_sim:.2f})"
    return False, None

def match_skill(
    required_skill: str,
    candidate_skills_lower: Set[str],
    normalizer: Optional[SkillNormalizer] = None,
    embedder: Optional[Any] = None,
    soft_match_threshold: float = 0.80,
) -> Tuple[bool, Optional[str]]:
    if not required_skill or not required_skill.strip():
        return False, None
    norm = normalizer or _DEFAULT_NORMALIZER
    req_clean = required_skill.strip()
    req_lower = req_clean.lower()
    req_canonical = norm.normalize(req_clean).lower()
    cand_canonical = {norm.normalize(s).lower() for s in candidate_skills_lower}
    if req_lower in candidate_skills_lower or req_canonical in candidate_skills_lower or req_canonical in cand_canonical:
        return True, req_clean
    if _ALTERNATIVE_SPLIT_RE.search(req_clean):
        options = [opt.strip() for opt in _ALTERNATIVE_SPLIT_RE.split(req_clean) if opt.strip()]
        for opt in options:
            matched, label = match_skill(opt, candidate_skills_lower, norm, embedder, soft_match_threshold)
            if matched:
                return True, label
    if _CONJUNCTION_SPLIT_RE.search(req_clean):
        parts = [p.strip() for p in _CONJUNCTION_SPLIT_RE.split(req_clean) if p.strip()]
        if len(parts) > 1:
            all_matched = True
            matched_labels: List[str] = []
            for p in parts:
                matched, label = match_skill(p, candidate_skills_lower, norm, embedder, soft_match_threshold)
                if not matched:
                    all_matched = False
                    break
                if label:
                    matched_labels.append(label)
            if all_matched:
                return True, " & ".join(matched_labels)
    for cand_skill in candidate_skills_lower:
        if len(cand_skill) >= 2:
            pattern = rf"\b{re.escape(cand_skill)}\b"
            if re.search(pattern, req_lower):
                return True, cand_skill.title()
    if embedder is not None and candidate_skills_lower:
        return soft_match_skill(req_clean, list(candidate_skills_lower), embedder, threshold=soft_match_threshold)
    return False, None

def evaluate_skill_coverage(
    required_skills: List[str],
    candidate_skills: List[str],
    normalizer: Optional[SkillNormalizer] = None,
    embedder: Optional[Any] = None,
    soft_match_threshold: float = 0.80,
) -> Tuple[float, List[Tuple[str, str]], List[str]]:
    if not required_skills:
        return 1.0, [], []
    norm = normalizer or _DEFAULT_NORMALIZER
    cand_lower: Set[str] = {s.lower().strip() for s in candidate_skills if s and s.strip()}
    cand_lower.update({norm.normalize(s).lower() for s in candidate_skills if s and s.strip()})
    matched_pairs: List[Tuple[str, str]] = []
    matched_credits: List[float] = []
    missing: List[str] = []
    for req in required_skills:
        if not req.strip():
            continue
        is_matched, evidence_label = match_skill(req, cand_lower, norm, embedder=embedder, soft_match_threshold=soft_match_threshold)
        if is_matched:
            is_soft = bool(evidence_label and "(soft" in evidence_label)
            credit = 0.65 if is_soft else 1.0
            matched_credits.append(credit)
            matched_pairs.append((req, evidence_label or req))
        else:
            missing.append(req)
    total = len(matched_pairs) + len(missing)
    ratio = sum(matched_credits) / total if total > 0 else 1.0
    return ratio, matched_pairs, missing

SENIORITY_ORDINAL = {
    "":          0,
    "intern":    1,
    "junior":    2,
    "mid":       3,
    "senior":    4,
    "lead":      5,
    "principal": 6,
}

_TITLE_PATTERNS = [
    (re.compile(r"\b(?:principal|distinguished|fellow|staff(?:\s+[\w]+){0,3}\s+(?:engineer|developer|architect|scientist|lead|specialist|manager))\b", re.IGNORECASE), "principal"),
    (re.compile(r"\b(?:tech\s+lead|team\s+lead|engineering\s+lead|lead(?:\s+[\w]+){0,3}\s+(?:engineer|developer|architect|sdet|specialist|manager|analyst))\b", re.IGNORECASE), "lead"),
    (re.compile(r"\b(?:senior|sr\.?|head\s+of)(?:\s+[\w]+){0,3}\s+(?:engineer|developer|architect|consultant|manager|specialist|analyst|recruiter|executive|sre|dba)?\b", re.IGNORECASE), "senior"),
    (re.compile(r"\b(?:junior|jr\.?|entry[\s-]?level|associate)\b", re.IGNORECASE), "junior"),
    (re.compile(r"\b(?:intern|internship|trainee|apprentice|co-?op|student|undergraduate|fresher)\b", re.IGNORECASE), "intern"),
]

_STUDENT_INDICATORS = re.compile(
    r"\b(?:undergraduate|student|pursuing\s+(?:b\.?tech|b\.?e|degree|bachelor)|freshman|sophomore|fresher|seeking\s+internship)\b",
    re.IGNORECASE,
)

class SeniorityExtractor:

    def extract(
        self,
        text: str = "",
        years_experience: Optional[float] = None,
        degree_level: Optional[int] = None,
    ) -> str:
        if not text:
            if years_experience is not None:
                return self._from_years(years_experience)
            return ""
        is_student = bool(_STUDENT_INDICATORS.search(text))
        has_low_experience = years_experience is None or years_experience < 1.0
        if is_student and has_low_experience:
            return "intern"

        header_text = "\n".join(text.strip().splitlines()[:6])
        header_label = self._from_title_keywords(header_text)
        if header_label:
            if has_low_experience and SENIORITY_ORDINAL.get(header_label, 0) >= SENIORITY_ORDINAL["senior"]:
                if is_student:
                    return "intern"
                return "junior"
            return header_label

        title_label = self._from_title_keywords(text)
        if title_label:
            if has_low_experience and SENIORITY_ORDINAL.get(title_label, 0) >= SENIORITY_ORDINAL["senior"]:
                if is_student:
                    return "intern"
                return "junior"
            return title_label
        if years_experience is not None:
            return self._from_years(years_experience)
        if is_student:
            return "intern"
        return "mid"

    def _from_title_keywords(self, text: str) -> str:
        if not text:
            return ""
        best_label = ""
        best_ordinal = 0
        for pattern, label in _TITLE_PATTERNS:
            if pattern.search(text):
                ordinal = SENIORITY_ORDINAL.get(label, 0)
                if ordinal > best_ordinal:
                    best_ordinal = ordinal
                    best_label = label
        return best_label

    def _from_years(self, years: float) -> str:
        if years < 0.5:
            return "intern"
        if years < 2:
            return "junior"
        if years < 5:
            return "mid"
        if years < 10:
            return "senior"
        if years < 15:
            return "lead"
        return "principal"

_EXPLICIT_YEARS_RE = re.compile(
    r"(?:over\s+|more\s+than\s+|at\s+least\s+)?"
    r"(\d{1,2}(?:\.\d+)?)\+?\s*(?:years?|yrs?)"
    r"(?:\s+of)?\s*(?:experience|exp|professional|work|industry)?",
    re.IGNORECASE,
)

_MONTH_NAMES = (
    r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
)
_MONTH_YEAR_RE = re.compile(
    rf"({_MONTH_NAMES})\s*[,.]?\s*(\d{{4}})",
    re.IGNORECASE,
)
_DATE_RANGE_RE = re.compile(
    rf"({_MONTH_NAMES}\s*[,.]?\s*\d{{4}}|(?:19|20)\d{{2}})"
    r"\s*[-–—~to]+\s*"
    rf"({_MONTH_NAMES}\s*[,.]?\s*\d{{4}}|(?:19|20)\d{{2}}|[Pp]resent|[Cc]urrent|[Nn]ow|[Oo]ngoing)",
    re.IGNORECASE,
)

_BARE_YEAR_RANGE_RE = re.compile(
    r"\b((?:19|20)\d{2})\s*[-–—~to]+\s*((?:19|20)\d{2}|[Pp]resent|[Cc]urrent|[Nn]ow|[Oo]ngoing)\b",
    re.IGNORECASE,
)

_MONTH_MAP = {
    "jan": 1, "january": 1, "feb": 2, "february": 2,
    "mar": 3, "march": 3, "apr": 4, "april": 4,
    "may": 5, "jun": 6, "june": 6,
    "jul": 7, "july": 7, "aug": 8, "august": 8,
    "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10, "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}

_PRESENT_WORDS = frozenset({"present", "current", "now", "ongoing"})

_STUDENT_ACTIVITY_RE = re.compile(
    r"\b(?:college\s+committee|technical\s+committee|student\s+member|"
    r"student\s+chapter|student\s+club|university\s+club|hackathon|"
    r"extracurricular|academic\s+project|coursework|junior\s+college|schooling)\b",
    re.IGNORECASE,
)

class ExperienceExtractor:

    def extract(self, text: str) -> Optional[float]:
        if not text or not text.strip():
            return None
        explicit = self._extract_explicit(text)
        if explicit is not None:
            return explicit
        ranges = self._extract_date_ranges(text)
        if ranges:
            return self._sum_non_overlapping(ranges)
        return None

    def _extract_explicit(self, text: str) -> Optional[float]:
        matches = _EXPLICIT_YEARS_RE.findall(text)
        valid = [float(m) for m in matches if 0 < float(m) < 45]
        if not valid:
            return None
        return round(float(max(valid)), 1)

    def _is_student_line(self, line: str) -> bool:
        return bool(_STUDENT_ACTIVITY_RE.search(line))

    def _extract_date_ranges(self, text: str) -> List[Tuple[float, float]]:
        ranges: List[Tuple[float, float]] = []
        now = date.today()
        current_frac = now.year + (now.month - 1) / 12.0
        for line in text.splitlines():
            if not line.strip():
                continue
            if self._is_student_line(line):
                continue
            for match in _DATE_RANGE_RE.finditer(line):
                start_frac = self._parse_date_token(match.group(1))
                end_frac = self._parse_date_token(match.group(2))
                if start_frac is not None and end_frac is not None and end_frac > start_frac:
                    if end_frac > current_frac + 0.2:
                        continue
                    if end_frac - start_frac > 10.0:
                        continue
                    ranges.append((start_frac, end_frac))
            for match in _BARE_YEAR_RANGE_RE.finditer(line):
                start_frac = self._parse_date_token(match.group(1))
                end_frac = self._parse_date_token(match.group(2))
                if start_frac is not None and end_frac is not None and end_frac > start_frac:
                    if end_frac > current_frac + 0.2 or end_frac - start_frac > 10.0:
                        continue
                    if not any(abs(s - start_frac) < 0.5 and abs(e - end_frac) < 0.5 for s, e in ranges):
                        ranges.append((start_frac, end_frac))
        return ranges

    def _parse_date_token(self, token: str) -> Optional[float]:
        token = token.strip()
        if token.lower() in _PRESENT_WORDS:
            now = date.today()
            return now.year + (now.month - 1) / 12.0
        month_match = _MONTH_YEAR_RE.search(token)
        if month_match:
            month_str = month_match.group(1).lower().rstrip(".")
            year = int(month_match.group(2))
            month = _MONTH_MAP.get(month_str, 1)
            return year + (month - 1) / 12.0
        if re.fullmatch(r"(?:19|20)\d{2}", token):
            return float(int(token))
        return None

    def _sum_non_overlapping(self, ranges: List[Tuple[float, float]]) -> float:
        if not ranges:
            return 0.0
        sorted_ranges = sorted(ranges)
        merged: List[Tuple[float, float]] = [sorted_ranges[0]]
        for start, end in sorted_ranges[1:]:
            prev_start, prev_end = merged[-1]
            if start <= prev_end:
                merged[-1] = (prev_start, max(prev_end, end))
            else:
                merged.append((start, end))
        total = sum(end - start for start, end in merged)
        return round(total, 1)

_DEGREE_KEYWORDS = sorted(DEGREE_LEVELS.keys(), key=len, reverse=True)
_DEGREE_RE = re.compile(
    r"(?:\b|\A)(" + "|".join(re.escape(k) for k in _DEGREE_KEYWORDS) + r")(?=[.,;/|\s]|\b|\Z)",
    re.IGNORECASE,
)

_DEGREE_PHRASE_RE = re.compile(
    r"\b(Bachelor(?:'s)?|Master(?:'s)?|Doctorate|Diploma|Associate|"
    r"B\.?Tech\b|M\.?Tech\b|B\.?E\.?\b|M\.?E\.?\b|B\.?S\.?\b|M\.?S\.?\b|B\.?A\.?\b|M\.?A\.?\b|MBA\b|MCA\b|BCA\b|Ph\.?D\b)"
    r"(?:\s+(?:in|of)\s+[A-Za-z\s&]+)?",
    re.IGNORECASE,
)

_CGPA_RE = re.compile(
    r"\b(?:CGPA|GPA|Score|Percentage)\s*[:=]?\s*(\d+(?:\.\d+)?(?:\s*/\s*\d+)?%?)",
    re.IGNORECASE,
)

_EDU_DATE_RANGE_RE = re.compile(
    r"\b((?:19|20)\d{2}\s*[-–—~to]+\s*(?:(?:19|20)\d{2}|[Pp]resent|[Cc]urrent|[Nn]ow|[Oo]ngoing))\b",
    re.IGNORECASE,
)

_INSTITUTION_KEYWORDS = re.compile(
    r"\b(?:College|University|Institute|School|Academy|Polytechnic)\b",
    re.IGNORECASE,
)

class EducationExtractor:

    def extract(self, text: str) -> Optional[int]:
        if not text or not text.strip():
            return None
        highest: Optional[int] = None
        for match in _DEGREE_RE.finditer(text):
            raw = match.group(1).lower()
            keyword = raw.rstrip(".")
            level = DEGREE_LEVELS.get(keyword)
            if level is None:
                level = DEGREE_LEVELS.get(keyword + ".")
            if level is None:
                level = DEGREE_LEVELS.get(raw)
            if level is not None:
                if highest is None or level > highest:
                    highest = level
        return highest

    def extract_details(self, text: str) -> List[EducationEntry]:
        if not text or not text.strip():
            return []
        entries: List[EducationEntry] = []
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        current_entry = EducationEntry()
        has_content = False
        for line in lines:
            if _INSTITUTION_KEYWORDS.search(line):
                if has_content and (current_entry.degree or current_entry.institution):
                    entries.append(current_entry)
                    current_entry = EducationEntry()
                    has_content = False
                date_match = _EDU_DATE_RANGE_RE.search(line)
                if date_match:
                    current_entry.dates = date_match.group(1).strip()
                    clean_inst = line[:date_match.start()].strip(" -|,")
                    current_entry.institution = clean_inst or line
                else:
                    current_entry.institution = line.split("|")[0].strip()
                has_content = True
            deg_match = _DEGREE_PHRASE_RE.search(line)
            if deg_match:
                if not current_entry.degree:
                    current_entry.degree = deg_match.group(0).strip(" -|,")
                    current_entry.degree_level = self.extract(current_entry.degree)
                    has_content = True
            cgpa_match = _CGPA_RE.search(line)
            if cgpa_match:
                current_entry.cgpa = cgpa_match.group(1).strip()
                has_content = True
            if not current_entry.dates:
                date_match = _EDU_DATE_RANGE_RE.search(line)
                if date_match:
                    current_entry.dates = date_match.group(1).strip()
                    has_content = True
        if has_content and (current_entry.degree or current_entry.institution):
            entries.append(current_entry)
        if not entries:
            level = self.extract(text)
            if level is not None:
                deg_match = _DEGREE_PHRASE_RE.search(text)
                degree = deg_match.group(0).strip(" -|,") if deg_match else ""
                cgpa_match = _CGPA_RE.search(text)
                cgpa = cgpa_match.group(1).strip() if cgpa_match else ""
                date_match = _EDU_DATE_RANGE_RE.search(text)
                dates = date_match.group(1).strip() if date_match else ""
                entries.append(EducationEntry(
                    degree=degree,
                    dates=dates,
                    cgpa=cgpa,
                    degree_level=level,
                ))
        return entries
