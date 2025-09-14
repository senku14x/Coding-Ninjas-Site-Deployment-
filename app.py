import streamlit as st
import google.generativeai as genai
import json
import random
import os

# --- 1. CONFIGURATION & SETUP ---

# Set page config for a cleaner look
st.set_page_config(
    page_title="AI Excel Interviewer",
    page_icon="🤖",
    layout="centered"
)

# Configure the API Key using Streamlit's secrets management
# (You must add your "GOOGLE_API_KEY" to your Streamlit app's secrets)
try:
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
except FileNotFoundError:
    # This is a fallback for local testing if you don't have a secrets.toml file
    # You can manually paste your API key here for local testing ONLY.
    # DO NOT push this to GitHub with your key visible.
    try:
        from google.colab import userdata
        API_KEY = userdata.get('GOOGLE_API_KEY')
        genai.configure(api_key=API_KEY)
    except (ImportError, KeyError):
        st.error("Google API Key not found. Please add it to your Streamlit secrets.", icon="🚨")
        st.stop()
        

# --- 2. LOAD KNOWLEDGE BASE (Cached) ---

@st.cache_data  # This caches the file load, so we only read it once
def load_knowledge_base():
    """Loads the adaptive question bank from the JSON file."""
    try:
        with open('adaptive_question_bank.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        st.error("FATAL: adaptive_question_bank.json file not found.", icon="🚨")
        return None
    except json.JSONDecodeError:
        st.error("FATAL: Error decoding adaptive_question_bank.json. Please validate the JSON.", icon="🚨")
        return None

knowledge_base = load_knowledge_base()
if not knowledge_base:
    st.stop()


# --- 3. ALL CORE AI & AGENT FUNCTIONS (Copied from Colab) ---

# --- MODEL DEFINITIONS ---
# Model for the Evaluator (outputs JSON)
evaluator_model = genai.GenerativeModel(
    'gemini-2.5-pro', # Or 'gemini-2.5-flash'
    generation_config={"response_mime_type": "application/json"}
)
# Model for the Final Report (outputs text)
report_model = genai.GenerativeModel('gemini-2.5-pro')

# --- CONSTANTS ---
FAILURE_THRESHOLD = 2
SUCCESS_THRESHOLD = 3
MAX_QUESTIONS = 15

def evaluate_answer(question_text, user_answer, evaluation_rubric):
    """
    Evaluates a user's answer against a specific rubric using the AI model.
    (This is our "Brain" function from Task 2.2)
    """
    prompt_template = f"""
    You are a strict, fair, and expert Excel Interview Grader. Your ONLY job is to evaluate a candidate's answer by comparing it directly against the official evaluation rubric.
    Rules:
    1.  Compare the "Candidate's Answer" only against the "Official Rubric."
    2.  Assign a score from 1 to 5 based on this scale:
        - 5 (Perfect): Fully addresses all rubric points.
        - 4 (Great): Mostly correct but misses a minor detail.
        - 3 (Partial): Understands the core concept but misses key components.
        - 2 (Poor): Mentions a keyword but fundamentally misunderstands.
        - 1 (Incorrect): Completely wrong or irrelevant.
    3.  Write one sentence of constructive feedback.
    4.  You MUST respond with ONLY a valid JSON object: {{"score": integer, "feedback": "string"}}

    [DATA FOR EVALUATION]:
    [QUESTION]: {question_text}
    [RUBRIC]: {evaluation_rubric}
    [CANDIDATE'S ANSWER]: {user_answer}

    Respond with ONLY the valid JSON object:
    """
    try:
        response = evaluator_model.generate_content(prompt_template)
        return json.loads(response.text)
    except Exception as e:
        print(f"Evaluation Error: {e}")
        return {"score": 1, "feedback": "Error: Could not evaluate the answer."}

def generate_final_report(transcript_history):
    """
    Takes the complete interview transcript and generates a comprehensive report.
    (This is our "Report Generator" function from Task 2.4)
    """
    transcript_json = json.dumps(transcript_history, indent=2)
    report_prompt = f"""
    You are a helpful Senior Data Manager writing a performance report for a job candidate's Excel mock interview.
    You will be given the complete transcript as a JSON object. Synthesize this data into a high-level, human-readable report. DO NOT just list the questions.
    
    Please structure your report with these Markdown sections:
    
    ## Overall Performance Summary
    Start with a 2-3 sentence summary of their performance.
    
    ## Key Strengths
    Identify topics where they excelled (scores 4-5), referencing specific concepts they understood.
    
    ## Areas for Improvement
    Identify topics where they struggled (scores 1-3) and provide constructive advice.
    
    ## Final Recommendation
    Conclude with a final readiness assessment (e.g., "Ready for a junior role," "Needs review," "Strong advanced skills").
    
    ---
    CANDIDATE INTERVIEW TRANSCRIPT (JSON):
    {transcript_json}
    ---
    
    Write the complete, professional feedback report:
    """
    try:
        response = report_model.generate_content(report_prompt)
        return response.text
    except Exception as e:
        return f"An error occurred while generating the report: {e}"

def get_next_question(current_difficulty, questions_asked_ids):
    """
    Finds a valid question from our knowledge base.
    (This is our Helper function from Task 2.3)
    """
    all_questions_in_pool = []
    for topic, questions in knowledge_base.items():
        for q in questions:
            q['topic_name'] = topic 
            all_questions_in_pool.append(q)
            
    filtered_by_difficulty = [q for q in all_questions_in_pool if q['difficulty'] == current_difficulty]
    available_questions = [q for q in filtered_by_difficulty if q['id'] not in questions_asked_ids]
    
    if available_questions:
        return random.choice(available_questions)
    else:
        # Fallback: If no questions left at this difficulty, try another level
        fallback_available = [q for q in all_questions_in_pool if q['id'] not in questions_asked_ids]
        return random.choice(fallback_available) if fallback_available else None


# --- 4. STREAMLIT APP LOGIC ---

st.title("🤖 AI-Powered Excel Interviewer")

# Initialize the chat and agent state (THIS IS CRITICAL)
def initialize_state():
    """Sets up all the session state variables we need."""
    # Chat history
    st.session_state.messages = []
    
    # Agent State (all our counters and trackers from the flowchart)
    st.session_state.interview_history = []
    st.session_state.questions_asked_ids = []
    st.session_state.current_difficulty = "Easy"
    st.session_state.consecutive_failures = 0
    st.session_state.hard_questions_passed = 0
    st.session_state.interview_complete = False
    
    # Ask the first question
    st.session_state.messages.append({"role": "ai", "content": "Welcome! I am your AI mock interviewer. I will ask adaptive questions. The interview will end if you pass 3 Hard questions, fail 2 questions in a row, or we hit the 15-question limit. Let's begin."})
    first_question = get_next_question("Easy", [])
    if first_question:
        st.session_state.current_question_data = first_question
        st.session_state.questions_asked_ids.append(first_question['id'])
        st.session_state.messages.append({"role": "ai", "content": first_question['question_text']})
    else:
        st.error("Could not load first question. Knowledge base empty?")
        st.session_state.interview_complete = True

# --- Main App Execution ---

# Check if state is initialized, if not, run the setup
if "messages" not in st.session_state:
    initialize_state()

# Display all past messages from the chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Main event loop: This runs ONLY if the interview is NOT complete
if not st.session_state.interview_complete:
    
    # Get user input (This is the "pause" in our app)
    if prompt := st.chat_input("Your answer..."):
        # 1. Add user's answer to history and display it
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # 2. Get the question they just answered (that we saved in state)
        last_question = st.session_state.current_question_data
        
        # 3. Call the "Brain" (Evaluate the answer)
        with st.spinner("Analyzing answer..."):
            evaluation = evaluate_answer(
                last_question['question_text'],
                prompt,
                last_question['evaluation_rubric']
            )
        
        # 4. Add the AI's feedback to history and display it
        feedback_text = f"**[Score: {evaluation['score']}/5]** {evaluation['feedback']}"
        st.session_state.messages.append({"role": "ai", "content": feedback_text})
        with st.chat_message("ai"):
            st.markdown(feedback_text)

        # 5. Manage State (Add to transcript and update agent logic)
        st.session_state.interview_history.append({
            "topic": last_question['topic_name'],
            "difficulty": last_question['difficulty'],
            "question": last_question['question_text'],
            "answer": prompt,
            "score": evaluation['score'],
            "feedback": evaluation['feedback']
        })
        
        # 6. Run the "Decision Engine" (Update state counters)
        score = evaluation['score']
        if score >= 4:
            st.session_state.consecutive_failures = 0
            if st.session_state.current_difficulty == "Easy":
                st.session_state.current_difficulty = "Medium"
            elif st.session_state.current_difficulty == "Medium":
                st.session_state.current_difficulty = "Hard"
            elif st.session_state.current_difficulty == "Hard":
                st.session_state.hard_questions_passed += 1
        elif score <= 2:
            st.session_state.consecutive_failures += 1
            if st.session_state.current_difficulty == "Hard":
                st.session_state.current_difficulty = "Medium"

        # 7. Check All Break Conditions
        break_condition_met = False
        conclusion_message = ""

        if st.session_state.consecutive_failures >= FAILURE_THRESHOLD:
            break_condition_met = True
            conclusion_message = f"🤖 You've struggled on {st.session_state.consecutive_failures} questions in a row. We'll stop here for today. Generating your final report..."
        elif st.session_state.hard_questions_passed >= SUCCESS_THRESHOLD:
            break_condition_met = True
            conclusion_message = f"🤖 You've successfully passed {st.session_state.hard_questions_passed} advanced questions. That's an excellent performance! Generating your final report..."
        elif len(st.session_state.questions_asked_ids) >= MAX_QUESTIONS:
            break_condition_met = True
            conclusion_message = f"🤖 We've reached the {MAX_QUESTIONS} question limit. We have enough information. Generating your final report..."

        # 8. Act on Break Condition (if met)
        if break_condition_met:
            st.session_state.interview_complete = True
            st.session_state.messages.append({"role": "ai", "content": conclusion_message})
            with st.chat_message("ai"):
                st.markdown(conclusion_message)
            
            with st.spinner("Generating your final feedback report..."):
                final_report = generate_final_report(st.session_state.interview_history)
                st.session_state.messages.append({"role": "ai", "content": final_report})
                with st.chat_message("ai"):
                    st.markdown(final_report)
            
            st.info("Interview complete! You can refresh the page to start a new interview.")

        # 9. If NO Break: Ask the NEXT Question
        else:
            with st.spinner("Selecting next question..."):
                next_question = get_next_question(st.session_state.current_difficulty, st.session_state.questions_asked_ids)
                if next_question:
                    st.session_state.current_question_data = next_question # Save new question
                    st.session_state.questions_asked_ids.append(next_question['id'])
                    next_q_text = f"**Difficulty: {next_question['difficulty']} | Topic: {next_question['topic_name']}**\n\n{next_question['question_text']}"
                    st.session_state.messages.append({"role": "ai", "content": next_q_text})
                    with st.chat_message("ai"):
                        st.markdown(next_q_text)
                else:
                    # Exhaustion Path (no questions left)
                    st.session_state.interview_complete = True
                    exhaustion_msg = "🤖 It looks like we've run out of questions in our database! We'll conclude here. Generating report..."
                    st.session_state.messages.append({"role": "ai", "content": exhaustion_msg})
                    with st.chat_message("ai"):
                        st.markdown(exhaustion_msg)
                    with st.spinner("Generating your final feedback report..."):
                        final_report = generate_final_report(st.session_state.interview_history)
                        st.session_state.messages.append({"role": "ai", "content": final_report})
                        with st.chat_message("ai"):
                            st.markdown(final_report)
