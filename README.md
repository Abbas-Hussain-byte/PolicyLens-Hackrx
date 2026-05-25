# PolicyLens AI — Insurance Intelligence Platform

**Fast, Trusted Insurance Intelligence** — Understand complex insurance policies instantly with AI-powered analysis, clause-grounded accuracy, and trust-first design.

![PolicyLens AI](https://img.shields.io/badge/PolicyLens-AI-blue?style=for-the-badge)
![Python](https://img.shields.io/badge/Python-3.11+-green?style=flat-square)
![Next.js](https://img.shields.io/badge/Next.js-15-black?style=flat-square)
![License](https://img.shields.io/badge/License-MIT-blue?style=flat-square)

## 🎯 What It Does

PolicyLens AI is **not** just another "chat with PDF" tool. It's a specialized **Insurance Decision & Claim Intelligence Platform** that:

- 📄 **Explains policies** in simple language anyone can understand
- ✅ **Checks eligibility** for conditions against your policy
- ⚠️ **Detects exclusions** and hidden policy traps
- 📋 **Lists claim requirements** with exact documentation needed
- 🔍 **Compares policies** side by side with recommendations
- 🛡️ **Prevents claim denials** by highlighting ambiguous clauses
- 🌍 **Multilingual** — responds in 6+ languages
- 🟢🟡🔴 **Trust indicators** — confidence scoring on every answer

## 🏗️ Architecture

```
┌─────────────────┐      ┌──────────────────────────────────────────┐
│  Next.js Frontend│ ──── │  FastAPI Backend                         │
│  (Dashboard UI)  │      │  ┌─────────┐  ┌───────────────────────┐ │
│                  │      │  │ Adaptive │  │ Intelligence Engine    │ │
│  • Upload        │      │  │ Router   │──│ • Answer Engine       │ │
│  • Chat + Trust  │      │  │ T1/T2/T3 │  │ • Verifier            │ │
│  • Eligibility   │      │  └─────────┘  │ • Eligibility Checker  │ │
│  • Exclusions    │      │               │ • Exclusion Finder     │ │
│  • Comparison    │      │  ┌─────────┐  │ • Comparator           │ │
│                  │      │  │ Hybrid   │  └───────────────────────┘ │
│                  │      │  │Retriever │  ┌───────────────────────┐ │
│                  │      │  │FAISS+BM25│  │ Gemini 2.0 Flash      │ │
│                  │      │  └─────────┘  │ (Free Tier)            │ │
│                  │      │               └───────────────────────┘ │
└─────────────────┘      └──────────────────────────────────────────┘
```

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+
- Free Gemini API key from [aistudio.google.com](https://aistudio.google.com)

### 1. Backend Setup

```bash
cd backend
python -m venv venv
venv\Scripts\activate   # Windows
# source venv/bin/activate  # Mac/Linux

pip install -r requirements.txt

# Create .env file
cp .env.example .env
# Edit .env and add your GEMINI_API_KEY

# Run backend
python -m uvicorn app.main:app --reload --port 8000
```

### 2. Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

### 3. Open
- Frontend: http://localhost:3000
- Backend API docs: http://localhost:8000/docs

## 📊 Key Features

### Adaptive Intelligence (3-Tier System)
| Tier | Type | Speed | Example |
|------|------|-------|---------|
| 🟢 Tier 1 | Fast Info | 1-2s | "What is a deductible?" |
| 🟡 Tier 2 | Grounded Q&A | 3-5s | "Is maternity covered?" |
| 🔴 Tier 3 | Verified | 5-10s | "Am I eligible with diabetes?" |

### Trust-First Design
Every answer includes:
- **Confidence badge** (🟢 High / 🟡 Medium / 🔴 Low)
- **Source clauses** with page numbers
- **Ambiguity warnings** for vague policy language
- **Verification status** for high-risk queries

### Anti-Hallucination (3-Layer Guard)
1. **Retrieval Grounding** — answers only from your policy's actual clauses
2. **Confidence Scoring** — automatic quality assessment
3. **Verification Pass** — second LLM check for high-risk questions

## 🛠️ Tech Stack

| Component | Technology |
|-----------|-----------|
| Backend | FastAPI (Python) |
| Frontend | Next.js 15 + Tailwind CSS |
| LLM | Gemini 2.0 Flash (free tier) |
| Embeddings | sentence-transformers (all-MiniLM-L6-v2) |
| Vector Store | FAISS (local) |
| Keyword Search | BM25 (rank-bm25) |
| PDF Parsing | pdfplumber |
| Animations | Framer Motion |

## 📝 API Documentation

Full API docs available at `/docs` when running the backend.

Key endpoints:
- `POST /api/policies/upload` — Upload PDF
- `POST /api/query/ask` — Ask a question
- `POST /api/query/eligibility` — Check eligibility
- `POST /api/query/exclusions` — Find exclusions
- `POST /api/compare/` — Compare policies
- `POST /api/query/batch` — Batch processing

## 📄 License

MIT License
