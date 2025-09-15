import streamlit as st
import google.generativeai as genai
import json
import random
import os
import pandas as pd
from streamlit_gsheets import GSheetsConnection  # Make sure this is in requirements.txt
import datetime # Make sure this is in requirements.txt

# --- 1. CONFIGURATION & SETUP ---

# Set page config
st.set_page_config(
    page_title="AI Excel Interviewer",
    page_icon="🤖",
    layout="centered"
)

# Configure the API Key from secrets
try:
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
except Exception as e:
    st.error("Google API Key not found. Please add it to your Streamlit secrets.", icon="🚨")
    st.stop()

# --- 2. LOAD KNOWLEDGE BASE (Cached) ---

@st.cache_data  # This caches the file load
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

# --- 3. ALL CORE AI & AGENT FUNCTIONS ---

# --- MODEL DEFINITIONS ---
evaluator_model = genai.GenerativeModel(
    'gemini-2.5-pro',
    generation_config={"response_mime_type": "application/json"}
)
report_model = genai.GenerativeModel('gemini-2.5-pro')

# --- CONSTANTS ---
FAILURE_THRESHOLD = 2
SUCCESS_THRESHOLD = 3
MAX_QUESTIONS = 15

def evaluate_answer(question_text, user_answer, evaluation_rubric):
    prompt_template = f"""
    You are a strict, fair, and expert Excel Interview Grader. Your ONLY job is to evaluate a candidate's answer by comparing it directly against the official evaluation rubric.
    Rules:
    1.  Compare the "Candidate's Answer" only against the "Official Rubric."
    2.  Assign a score from 1 to 5.
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
    transcript_json = json.dumps(transcript_history, indent=2)
    report_prompt = f"""
    You are a helpful Senior Data Manager writing a performance report for a job candidate's Excel mock interview.
    You will be given the complete transcript as a JSON object. Synthesize this data into a high-level, human-readable report.
    Please structure your report with these Markdown sections:
    ## Overall Performance Summary
    ## Key Strengths
    ## Areas for Improvement
    ## Final Recommendation
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
        fallback_available = [q for q in all_questions_in_pool if q['id'] not in questions_asked_ids]
        return random.choice(fallback_available) if fallback_available else None

def save_report_to_gsheet(candidate_name, final_report, full_history):
    """Connects to Google Sheets and appends the new report."""
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        
        new_report_data = pd.DataFrame(
            [
                {
                    "Candidate Name": candidate_name,
                    "Date": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
                    "Final Report": final_report,
                    "Full Transcript (JSON)": json.dumps(full_history) 
                }
            ]
        )
        
        conn.append(
            worksheet="Sheet1", # Or your specific sheet name
            data=new_report_data,
            header=False 
        )
        return True
    except Exception as e:
        print(f"Google Sheets Error: {e}")
        print("--- FALLBACK: PRIVATE HIRING MANAGER REPORT (Sheet Save Failed) ---")
        print(f"Candidate: {candidate_name}")
        print(final_report)
        print("--- END OF REPORT ---")
        return False

# --- 4. STREAMLIT APP LOGIC ---

st.title("🤖 AI-Powered Excel Interviewer")

# --- PASSWORD WALL ---
try:
    correct_password = st.secrets["APP_PASSWORD"]
except KeyError:
    st.error("Password not configured for this app. Please contact the administrator.")
    st.stop()

password_attempt = st.text_input("Enter Access Password:", type="password")

# Check if the password is correct
if password_attempt == correct_password:
    
    # --- ASK FOR CANDIDATE NAME ---
    if "candidate_name" not in st.session_state:
        st.session_state.candidate_name = None

    if not st.session_state.candidate_name:
        st.session_state.candidate_name = st.text_input("Please enter your full name to begin:")
        if st.session_state.candidate_name:
            st.rerun() 
        else:
            st.info("Please enter your name to start the interview.")
            st.stop()
    
    # --- IF PASSWORD & NAME IS GIVEN, RUN APP ---
    
    def initialize_state(candidate_name):
        st.session_state.messages = []
        st.session_state.interview_history = []
        st.session_state.questions_asked_ids = []
        st.session_state.current_difficulty = "Easy"
        st.session_state.consecutive_failures = 0
        st.session_state.hard_questions_passed = 0
        st.session_state.interview_complete = False
        st.session_state.messages.append({"role": "ai", "content": f"Welcome, {candidate_name}! I am your AI mock interviewer. Let's begin."})
        first_question = get_next_question("Easy", [])
        if first_question:
            st.session_state.current_question_data = first_question
            st.session_state.questions_asked_ids.append(first_question['id'])
            
            # Difficulty is hidden from the candidate
            st.session_state.messages.append({"role": "ai", "content": f"**Topic: {first_question['topic_name']}**\n\n{first_question['question_text']}"})
        else:
            st.error("Could not load first question.")
            st.session_state.interview_complete = True

    # --- Main App Execution ---
    if "messages" not in st.session_state:
        initialize_state(st.session_state.candidate_name)

    # Display all past messages
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Main event loop: Runs ONLY if the interview is NOT complete
    if not st.session_state.interview_complete:
        
        if prompt := st.chat_input("Your answer..."):
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)

            last_question = st.session_state.current_question_data
            
            # --- MODIFICATION: Spinner text changed for neutral feedback ---
            with st.spinner("Processing answer..."):
                evaluation = evaluate_answer(
                    last_question['question_text'],
                    prompt,
                    last_question['evaluation_rubric']
                )
            
            # --- MODIFICATION: FEEDBACK BLOCK IS REMOVED ---
            # The candidate no longer sees the score or feedback.
            # We just save it and move on.
            
            # 5. Manage State (Silently)
            st.session_state.interview_history.append({
                "topic": last_question['topic_name'],
                "difficulty": last_question['difficulty'], # We still save difficulty for the report
                "question": last_question['question_text'],
                "answer": prompt,
                "score": evaluation['score'],
                "feedback": evaluation['feedback'] # Saved for the report
            })
            st.session_state.questions_asked_ids.append(last_question['id'])

            # 6. Run the "Decision Engine" (Silently)
            score = evaluation['score']
            if score >= 4:
                st.session_state.consecutive_failures = 0
                if st.session_state.current_difficulty == "Easy": st.session_state.current_difficulty = "Medium"
                elif st.session_state.current_difficulty == "Medium": st.session_state.current_difficulty = "Hard"
                elif st.session_state.current_difficulty == "Hard": st.session_state.hard_questions_passed += 1
            elif score <= 2:
                st.session_state.consecutive_failures += 1
                if st.session_state.current_difficulty == "Hard": st.session_state.current_difficulty = "Medium"

            # 7. Check All Break Conditions
            break_condition_met = False
            conclusion_message = ""

            if st.session_state.consecutive_failures >= FAILURE_THRESHOLD:
                break_condition_met = True
                conclusion_message = "🤖 You've struggled on several questions. We'll stop here. Submitting your report..."
            elif st.session_state.hard_questions_passed >= SUCCESS_THRESHOLD:
                break_condition_met = True
                conclusion_message = "🤖 You've passed several advanced questions. Excellent performance! Submitting your report..."
            elif len(st.session_state.questions_asked_ids) >= MAX_QUESTIONS:
                break_condition_met = True
                conclusion_message = f"🤖 We've reached the {MAX_QUESTIONS} question limit. Submitting your report..."

            # 8. Act on Break Condition (if met)
            if break_condition_met:
                st.session_state.interview_complete = True
                st.session_state.messages.append({"role": "ai", "content": conclusion_message})
                with st.chat_message("ai"):
                    st.markdown(conclusion_message)
                
                with st.spinner("Generating and submitting your final report..."):
                    final_report = generate_final_report(st.session_state.interview_history)
                    
                    save_success = save_report_to_gsheet(
                        st.session_state.candidate_name, 
                        final_report, 
                        st.session_state.interview_history
                    )
                    
                    if save_success:
                        print(f"Successfully saved report for {st.session_state.candidate_name} to Google Sheets.")
                    else:
                        print(f"Failed to save report for {st.session_state.candidate_name} to Google Sheets. Check logs.")
                        
                    thank_you_message = "Thank you for completing the interview! Your results have been successfully submitted to the hiring team for review. You may now close this window."
                    st.session_state.messages.append({"role": "ai", "content": thank_you_message})
                    with st.chat_message("ai"):
                        st.markdown(thank_you_message)
                
                st.info("Interview complete! You may now close this window.")

            # 9. If NO Break: Ask the NEXT Question
            else:
                with st.spinner("Selecting next question..."):
                    next_question = get_next_question(st.session_state.current_difficulty, st.session_state.questions_asked_ids)
                    if next_question:
                        st.session_state.current_question_data = next_question
                        st.session_state.questions_asked_ids.append(next_question['id'])
                        
                        # Difficulty is hidden
                        next_q_text = f"**Topic: {next_question['topic_name']}**\n\n{next_question['question_text']}"
                        st.session_state.messages.append({"role": "ai", "content": next_q_text})
                        # We must re-run the script to show the new message
                        st.rerun() 
                    else:
                        # --- HIDE REPORT & SAVE TO GSHEET (on Exhaustion) ---
                        st.session_state.interview_complete = True
                        exhaustion_msg = "🤖 We've run out of questions! Submitting your report..."
                        st.session_state.messages.append({"role": "ai", "content": exhaustion_msg})
                        with st.chat_message("ai"):
                            st.markdown(exhaustion_msg)
                            
                        with st.spinner("Generating and submitting your final report..."):
                            final_report = generate_final_report(st.session_state.interview_history)
                            
                            save_success = save_report_to_gsheet(
                                st.session_state.candidate_name, 
                                final_report,
                                st.session_state.interview_history
                            )
                            
                            if save_success:
                                print(f"Successfully saved report for {st.session_state.candidate_name} to Google Sheets.")
                            else:
                                print(f"Failed to save report for {st.session_state.candidate_name} to Google Sheets. Check logs.")

                            thank_you_message = "Thank you for completing the interview! Your results have been successfully submitted to the hiring team for review. You may now close this window."
                            st.session_state.messages.append({"role": "ai", "content": thank_you_message})
                            with st.chat_message("ai"):
                                st.markdown(thank_you_message)
                        
                        st.info("Interview complete! You may now close this window.")
                                
elif password_attempt: # If they typed *something* but it wasn't the correct password
    st.error("Password incorrect. Please try again.", icon="🚨")
else: # If the password field is empty
    st.info("Please enter the password to begin the interview.")
