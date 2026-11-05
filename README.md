# CareerConnect

CareerConnect is an AI-powered job discovery and hiring platform designed to bridge candidates and recruiters with calibrated candidate-job matching, semantic retrieval, and autonomous recruitment agents.

Built with a Django REST Framework backend and a React/Vite frontend, the platform features a multi-stage search and ranking pipeline (Bi-Encoder embeddings + FAISS vector search + BM25 + LightGBM LambdaMART ranker) along with background automation agents powered by LangGraph and Celery.

---

## Key Features

### For Candidates
- **Intelligent Job Discovery**: Search and filter opportunities across technical domains, seniority levels, compensation ranges, and work arrangements (Remote, Hybrid, On-site).
- **AI-Powered Autofill**: Upload resumes (PDF/DOCX) to automatically parse candidate profiles, technical competencies, work history, and education.
- **Application Tracking**: Monitor application lifecycle states in real time (Applied, In Review, Shortlisted, Interview Scheduled, Rejected).
- **Autonomous Job Search**: Auto-apply agent scans and submits applications based on candidate preferences within strict weekly ceilings.

### For Recruiters
- **Job Pipeline Management**: Create, edit, publish, and manage job listings with structured role requirements and required skill tags.
- **Calibrated Match Scoring**: Machine-learning-based relevance scores scaled from 0 to 100 with clear recruiter decision bands:
  - **Shortlist** ($\ge 84$): High confidence match
  - **Review** ($45–83$): Moderate match for manual inspection
  - **Reject** ($< 45$): Clear qualification mismatch
- **Explainable Match Insights**: Grounded breakdowns detailing skill overlaps, key strengths, and competency gaps.
- **Interview Scheduling**: Propose and schedule candidate interview slots directly through the dashboard.

### Core Architecture & AI Engine
- **Hybrid Search & Retrieval**: Combines dense vector search (`all-MiniLM-L6-v2` embeddings via FAISS) with sparse lexical search (BM25) fused using Reciprocal Rank Fusion (RRF).
- **Learning-to-Rank (LTR)**: A 14-feature LightGBM LambdaMART ranking model calibrated via Platt scaling to produce reliable percentage scores.
- **Autonomous Agents**: LangGraph workflows orchestrate candidate screening, weekly digest generation, scheduled follow-ups, and auto-applications.
- **Enterprise Safety**: Concurrency row-locking (`select_for_update`) prevents quota abuse, claim-then-send patterns ensure at-most-once notification delivery, and non-root container profiles enforce least-privilege security.

---

## Tech Stack

| Layer | Technologies |
|---|---|
| **Frontend** | React 18, Vite, Tailwind CSS, Lucide Icons, Axios |
| **Backend** | Python 3.11+, Django 5, Django REST Framework (DRF) |
| **AI / Machine Learning** | LightGBM, FAISS, PyTorch, HuggingFace Sentence-Transformers, Google Gemini LLM |
| **Agents & Task Queue** | LangGraph, Celery, Celery Beat |
| **Databases & Cache** | PostgreSQL 16, Redis 7 |
| **Object Storage** | MinIO / AWS S3 compatible blob storage |
| **Containerization & CI** | Docker, Docker Compose, GitHub Actions |

---

## Project Structure

```
.
├── backend/
│   ├── application/          # Core jobs, applications, and AI matching pipeline
│   ├── agents/               # LangGraph automation agents (Screening, Auto-Apply, Digest)
│   ├── users/                # Custom User, CandidateProfile, and RecruiterProfile models
│   ├── job/                  # Django project settings, WSGI/ASGI, Celery config
│   ├── eval/                 # Golden datasets, benchmark suites, and validation tests
│   ├── scripts/              # Maintenance scripts (model training, backup/restore)
│   ├── docs/                 # Deployment guides and operational documentation
│   ├── data/                 # FAISS vector index and serialized LightGBM models
│   └── Dockerfile            # Multi-stage production container build
├── frontend/
│   ├── src/                  # React components, pages, context, and API clients
│   ├── public/               # Static assets
│   ├── package.json          # Node dependencies and scripts
│   └── Dockerfile            # Production Nginx container build
├── career_copilot/           # Companion microservice for job board scraping & syndication
├── docker-compose.yml        # Multi-container orchestration (PostgreSQL, Redis, MinIO, API, Frontend)
└── .github/workflows/        # Automated CI/CD pipelines
```

---

## Getting Started

### Prerequisites
- [Docker](https://docs.docker.com/get-docker/) & [Docker Compose](https://docs.docker.com/compose/)
- Alternatively for manual setup:
  - Python 3.11+
  - Node.js 20+
  - PostgreSQL 16 & Redis 7

---

### Method 1: Running with Docker Compose (Recommended)

1. **Clone the repository:**
   ```bash
   git clone https://github.com/your-username/careerconnect.git
   cd careerconnect
   ```

2. **Configure environment variables:**
   ```bash
   cp backend/.env.example backend/.env
   ```

3. **Start all services:**
   ```bash
   docker compose up -d --build
   ```

4. **Verify running containers:**
   ```bash
   docker compose ps
   ```

5. **Access the application:**
   - **Frontend**: [http://localhost:5173](http://localhost:5173)
   - **Backend API**: [http://localhost:8000](http://localhost:8000)
   - **API Documentation**: [http://localhost:8000/api/schema/swagger-ui/](http://localhost:8000/api/schema/swagger-ui/)
   - **MinIO Console**: [http://localhost:9001](http://localhost:9001)

---

### Method 2: Manual Local Setup

#### Backend Setup
```bash
cd backend

# Create and activate virtual environment
python -m venv venv
# On Windows:
venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install --index-url https://download.pytorch.org/whl/cpu --extra-index-url https://pypi.org/simple -r requirements-ml.txt

# Run migrations and start server
python manage.py migrate
python manage.py runserver 0.0.0.0:8000
```

#### Frontend Setup
```bash
cd frontend

# Install packages
npm install

# Start Vite development server
npm run dev
```

---

## Running Tests

### Backend & Evaluation Tests
```bash
# Run backend test suite
pytest backend/application/ai/tests/ -q

# Run evaluation and benchmark tests
pytest backend/eval/tests/ -q
```

### Frontend Tests
```bash
cd frontend
npm test
```

---

## Key API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/users/register/` | Register new Candidate or Recruiter account |
| `POST` | `/api/users/login/` | Obtain JWT authentication tokens |
| `GET` | `/api/jobs/` | List jobs with keyword, category, and location filters |
| `POST` | `/api/jobs/` | Create a new job listing (Recruiter only) |
| `POST` | `/api/applications/` | Submit a candidate application |
| `GET` | `/api/ai/recommendations/` | Retrieve personalized AI-ranked job recommendations |
| `POST` | `/api/ai/autofill/` | Parse uploaded resume text into candidate profile fields |
| `GET` | `/healthz` | Container liveness probe |
| `GET` | `/readyz` | Container readiness probe (checks DB, Redis, Cache) |

---

## License

This project is licensed under the MIT License - see the LICENSE file for details.
