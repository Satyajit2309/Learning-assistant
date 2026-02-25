<p align="center">
  <img src="https://img.shields.io/badge/Django-6.0-092E20?style=for-the-badge&logo=django&logoColor=white" alt="Django 6.0"/>
  <img src="https://img.shields.io/badge/Python-3.13-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python 3.13"/>
  <img src="https://img.shields.io/badge/Google%20Gemini-AI-4285F4?style=for-the-badge&logo=google&logoColor=white" alt="Google Gemini"/>
  <img src="https://img.shields.io/badge/LangChain-🦜-1C3C3C?style=for-the-badge" alt="LangChain"/>
  <img src="https://img.shields.io/badge/PostgreSQL-16-4169E1?style=for-the-badge&logo=postgresql&logoColor=white" alt="PostgreSQL"/>
  <img src="https://img.shields.io/badge/Docker-Ready-2496ED?style=for-the-badge&logo=docker&logoColor=white" alt="Docker"/>
</p>

<h1 align="center">🧠 LearnAI — AI-Powered Learning Assistant</h1>

<p align="center">
  <strong>Transform your study materials into interactive learning experiences powered by AI.</strong><br/>
  Upload documents. Generate summaries, quizzes, flashcards, flowcharts, podcasts, and more — all with one click.
</p>

<p align="center">
  <a href="https://learning-assistant-624635513183.asia-south1.run.app">
    <img src="https://img.shields.io/badge/🌐_Live_Demo-Visit_Website-00D9C0?style=for-the-badge&logoColor=white" alt="Live Demo"/>
  </a>
</p>

---

## ✨ Features at a Glance

| Feature | Description |
|:--------|:------------|
| 📄 **AI Summaries** | Upload PDFs, DOCX, TXT, or images and get intelligent summaries (brief, detailed, or bullet-point) |
| 🤖 **RAG Chatbot** | Chat with your documents — ask questions, get explanations, and explore concepts interactively |
| ❓ **Quiz Generation** | Auto-generate MCQ quizzes with configurable difficulty (Easy / Medium / Hard) and instant scoring |
| 🃏 **Smart Flashcards** | Priority-based flashcards with mastery tracking and progress percentages |
| 🔀 **Concept Flowcharts** | Visualize topic relationships with auto-generated interactive flowcharts |
| 🎙️ **AI Podcasts** | Two AI hosts discuss your material in a conversational podcast, generated via text-to-speech |
| ✅ **Answer Evaluation** | Upload handwritten answer sheets (OCR) for AI-powered per-question scoring and feedback |
| 📊 **Progress Analytics** | Dashboards with charts for quiz scores, flashcard mastery, XP points, streaks, and more |
| 🎮 **Gamification** | XP points, levels, daily streaks, and accuracy tracking to keep you motivated |

---

## 🎯 How It Works

```
┌──────────────┐     ┌──────────────────┐     ┌─────────────────────┐
│  Upload Docs │────▶│  AI Processing   │────▶│  Interactive Tools   │
│  PDF / DOCX  │     │  Google Gemini   │     │  Quizzes, Cards...   │
│  TXT / IMG   │     │  + LangChain     │     │  Podcasts, Chatbot   │
└──────────────┘     └──────────────────┘     └─────────────────────┘
                              │
                     ┌────────▼────────┐
                     │  Vector Store   │
                     │  FAISS + RAG    │
                     │  for Chatbot    │
                     └─────────────────┘
```

1. **Upload** your study materials (PDF, DOCX, TXT, Markdown, or images)
2. **Generate** AI-powered summaries to understand key concepts
3. **Learn** through quizzes, flashcards, flowcharts, and podcasts
4. **Chat** with your documents for deeper understanding via RAG
5. **Evaluate** your handwritten answers with OCR + AI scoring
6. **Track** your progress with XP, levels, streaks, and analytics

---

## 🛠️ Tech Stack

### Backend
| Technology | Purpose |
|:-----------|:--------|
| **Django 6.0** | Web framework & ORM |
| **Python 3.13** | Core language |
| **PostgreSQL 16** | Primary database |
| **Gunicorn** | Production WSGI server |
| **WhiteNoise** | Static file serving |

### AI & Machine Learning
| Technology | Purpose |
|:-----------|:--------|
| **Google Gemini** | LLM for content generation (summaries, quizzes, evaluations, chat) |
| **LangChain** | AI orchestration, prompt management, and RAG pipeline |
| **FAISS** | Vector similarity search for document-based chatbot |
| **Edge-TTS** | Text-to-speech for AI podcast generation |

### Document Processing
| Technology | Purpose |
|:-----------|:--------|
| **PyPDF2** | PDF text extraction |
| **python-docx** | DOCX file processing |
| **Pillow** | Image handling |
| **OCR** | Handwritten text extraction for answer evaluation |

### DevOps & Deployment
| Technology | Purpose |
|:-----------|:--------|
| **Docker** | Containerization |
| **Docker Compose** | Multi-container orchestration (app + PostgreSQL) |
| **Google Cloud Run** | Production hosting (serverless containers) |
| **Artifact Registry** | Docker image storage on GCP |

---

## 📁 Project Structure

```
Learning-Assistant/
├── config/                  # Django project settings
│   ├── settings.py          # Main configuration
│   ├── urls.py              # Root URL routing
│   └── wsgi.py              # WSGI entry point
│
├── accounts/                # User management
│   ├── models.py            # Custom User + UserProfile (XP, levels, streaks)
│   ├── forms.py             # Registration & profile forms
│   └── views.py             # Auth views (login, register, profile)
│
├── learning_assistant/      # Core application
│   ├── models.py            # Document, Summary, Quiz, Flashcard,
│   │                        # Flowchart, Podcast, Evaluation, ChatSession
│   ├── views.py             # All feature views & API endpoints
│   ├── urls.py              # Feature URL routing
│   │
│   ├── agents/              # 🤖 AI Agent modules
│   │   ├── base.py          # Base agent class
│   │   ├── summary_agent.py # AI summary generation
│   │   ├── quiz_agent.py    # Quiz question generation
│   │   ├── flashcard_agent.py
│   │   ├── flowchart_agent.py
│   │   ├── podcast_agent.py # Conversational script generation
│   │   ├── evaluation_agent.py # Answer sheet evaluation
│   │   ├── chatbot_agent.py # RAG-based chatbot
│   │   └── registry.py      # Agent registration & discovery
│   │
│   └── services/            # 🔧 Core services
│       ├── document_processor.py  # PDF/DOCX/TXT/Image ingestion
│       ├── vector_store.py        # FAISS vector store management
│       └── ocr_service.py         # OCR for handwritten text
│
├── templates/               # Django HTML templates
│   ├── base.html            # Base layout
│   └── pages/               # Feature pages
│       ├── home.html        # Landing page
│       ├── summary.html     # AI summary interface
│       ├── chatbot.html     # RAG chatbot interface
│       ├── quiz.html        # Quiz listing
│       ├── take_quiz.html   # Quiz taking interface
│       ├── flashcards.html  # Flashcard management
│       ├── flowchart.html   # Flowchart listing
│       ├── podcast.html     # Podcast listing
│       ├── evaluations.html # Answer evaluation
│       └── analytics.html   # Progress dashboard
│
├── static/                  # CSS, JS, and static assets
├── media/                   # User uploads & generated audio
├── vector_store/            # FAISS index files
│
├── Dockerfile               # Container configuration
├── docker-compose.yml       # Multi-container setup
├── requirements.txt         # Python dependencies
└── manage.py                # Django CLI
```

---

## 🚀 Getting Started

### Prerequisites

- **Python 3.13+**
- **PostgreSQL 16+** (or use Docker)
- **Google Gemini API Key** — [Get one here](https://aistudio.google.com/app/apikey)

### 1. Clone the Repository

```bash
git clone https://github.com/Satyajit2309/Learning-assistant.git
cd Learning-assistant
```

### 2. Set Up Virtual Environment

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

Copy the example env file and fill in your values:

```bash
cp .env.example .env
```

Edit `.env`:

```env
# Required — Get from https://aistudio.google.com/app/apikey
GEMINI_API_KEY=your_gemini_api_key_here

# PostgreSQL Database
DB_NAME=learning_assistant_db
DB_USER=postgres
DB_PASSWORD=your_password
DB_HOST=localhost
DB_PORT=5432

# Django (optional)
SECRET_KEY=your_secret_key
DEBUG=True
```

### 5. Set Up the Database

```bash
python manage.py migrate
python manage.py createsuperuser
```

### 6. Run the Development Server

```bash
python manage.py runserver
```

Visit **http://127.0.0.1:8000** and start learning! 🎉

---

## 🐳 Docker Setup

Run the entire stack (app + PostgreSQL) with Docker Compose:

```bash
# Build and start all services
docker-compose up --build

# Run migrations
docker-compose exec web python manage.py migrate

# Create admin user
docker-compose exec web python manage.py createsuperuser
```

The app will be available at **http://localhost:8001**.

---

## 🌐 Live Demo

The application is deployed and live on **Google Cloud Run**:

<p align="center">
  <a href="https://learning-assistant-624635513183.asia-south1.run.app">
    <img src="https://img.shields.io/badge/🚀_Try_It_Now-learning--assistant.run.app-00D9C0?style=for-the-badge" alt="Visit Live Demo"/>
  </a>
</p>

| Infrastructure | Service |
|:--------------|:--------|
| **Hosting** | Google Cloud Run (asia-south1) |
| **Database** | Supabase PostgreSQL |
| **Container Registry** | Google Artifact Registry |

---

## 📸 Feature Deep Dive

### 📄 AI Summaries
Upload any study material and get AI-generated summaries in three formats:
- **Brief** — Quick overview of key points
- **Detailed** — Comprehensive breakdown with explanations
- **Bullet Points** — Scannable list of core concepts

### 🤖 RAG Chatbot
Your intelligent study companion powered by Retrieval-Augmented Generation:
- Documents are chunked and embedded into a **FAISS vector store**
- Ask any question and get contextually accurate answers grounded in your materials
- Multi-session support — maintain different conversations per document

### ❓ Interactive Quizzes
Test your knowledge with AI-generated multiple-choice quizzes:
- **3 difficulty levels**: Easy, Medium, Hard
- **Configurable question count**
- Instant feedback with explanations for each answer
- **XP rewards** scaled by difficulty and performance

### 🃏 Smart Flashcards
Priority-based flashcards that focus on what matters:
- Cards ranked by importance: *Critical → High → Medium → Low*
- Track mastery with a flip-to-reveal study interface
- Progress percentages per flashcard set

### 🔀 Concept Flowcharts
Visualize how concepts connect:
- Auto-generated nodes (concepts, actions, decisions) and edges (relationships)
- Interactive graph visualization
- Configurable detail levels: Simple, Medium, Detailed

### 🎙️ AI Podcasts
Listen to your study materials:
- AI generates a **two-host conversational script** from your content
- Converted to audio using **Edge-TTS**
- Downloadable MP3 files
- Three depth levels for different learning needs

### ✅ Answer Sheet Evaluation
Get AI-powered feedback on handwritten answers:
- Upload scanned answer sheets (PDF/Images)
- OCR extracts handwritten text
- AI evaluates each answer against reference material
- Per-question **percentage scores + detailed feedback**

### 📊 Progress Analytics
Comprehensive learning dashboard:
- Quiz score trends and accuracy rates
- Flashcard mastery progression
- Document upload & activity history
- XP points, current level, and streak tracking

---

## 🎮 Gamification System

Stay motivated with a built-in rewards system:

| Element | How It Works |
|:--------|:-------------|
| **XP Points** | Earn XP from quizzes and evaluations, scaled by difficulty |
| **Levels** | Level up every 1,000 XP |
| **Daily Streaks** | Consecutive days of activity, with longest streak tracking |
| **Accuracy Stats** | Track correct answers and quiz pass rates |
| **Study Goals** | Set daily study time goals |

---

## 🔒 Supported File Formats

| Format | Extensions |
|:-------|:-----------|
| PDF Documents | `.pdf` |
| Word Documents | `.docx` |
| Plain Text | `.txt`, `.md` |
| Images (OCR) | `.png`, `.jpg`, `.jpeg` |

> **Max upload size**: 10 MB per file

---

## 🤝 Contributing

Contributions are welcome! Here's how to get started:

1. **Fork** the repository
2. **Create** a feature branch (`git checkout -b feature/amazing-feature`)
3. **Commit** your changes (`git commit -m 'Add amazing feature'`)
4. **Push** to the branch (`git push origin feature/amazing-feature`)
5. **Open** a Pull Request

---

## 📄 License

This project is open-source and available under the [MIT License](LICENSE).

---

## 👨‍💻 Author

**Satyajit** — [GitHub](https://github.com/Satyajit2309)

---

<p align="center">
  <strong>⭐ If this project helped you, consider giving it a star!</strong><br/><br/>
  <a href="https://learning-assistant-624635513183.asia-south1.run.app">
    <img src="https://img.shields.io/badge/Try_LearnAI_Now-00D9C0?style=for-the-badge&logo=rocket&logoColor=white" alt="Try LearnAI"/>
  </a>
</p>
