# AI-Powered Excel Interviewer

An intelligent, adaptive screening system that automates Excel proficiency interviews using AI-powered evaluation and dynamic questioning.

## Mission

Solve the business problems of **inconsistency**, **cost**, and **time bottlenecks** in manual Excel screening by creating an automated AI agent that conducts structured, adaptive interviews.

## Core Innovation: Knowledge-Driven Intelligence

**The Challenge**: No pre-existing interview data means traditional ML approaches are impossible.

**Our Solution**: A knowledge-driven system powered by `adaptive_question_bank.json`:
- **Question Bank**: Categorized questions by topic and difficulty (Easy → Medium → Hard)
- **Expert Rubrics**: Every question paired with detailed evaluation criteria
- **Consistent Scoring**: AI grades against expert-defined standards, not subjective interpretation

## Adaptive Agent Architecture

### Multi-Persona AI System
1. **The Grader** (`evaluate_answer`): Strict AI evaluator that returns structured JSON scores
2. **The Reporter** (`generate_final_report`): Hiring manager persona that synthesizes interview data
3. **The Agent** (`app.py`): Main orchestrator managing UI, state, and interview flow

### Intelligent Decision Engine
The agent tracks candidate state and adapts in real-time:
- **Correct answers** (Score 4-5) → Promote to harder questions
- **Partial answers** (Score 3) → Stay at current difficulty
- **Poor answers** (Score 1-2) → Demote to easier questions

Interview ends when clear signal is found (e.g., 3 hard questions passed, or 2 consecutive failures).

## Tech Stack

- **Python**: AI/ML ecosystem standard
- **Google Gemini**: Advanced reasoning with native JSON output
- **Streamlit**: Rapid deployment and stateful chat interface
- **Streamlit Community Cloud**: Free hosting from GitHub

## Enterprise Features

### Security
- **Password wall** prevents unauthorized access
- API keys secured via `st.secrets`

### Test Integrity
- **Silent scoring** - no real-time feedback to candidates
- Background adaptive logic maintains interview validity

### Automated Reporting
- **Email pipeline** sends detailed reports to hiring managers
- **Fallback logging** ensures 100% data capture
- Candidates see only generic completion message

## Deployment

The application is deployed on Streamlit Community Cloud with automatic updates from this repository.

## Business Impact

**Before**: Manual, inconsistent screening with interviewer bias and scheduling bottlenecks

**After**: Automated, objective evaluation with instant, detailed reports delivered to hiring managers

---

*This system transforms Excel screening from a manual bottleneck into an intelligent, scalable, and consistent automated process.*
