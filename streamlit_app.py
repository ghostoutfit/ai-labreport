import streamlit as st
import base64
import os
from email.mime.text import MIMEText
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from openai import OpenAI


# --- Gmail Setup ---
def load_credentials():
    creds = Credentials(
        token=None,
        refresh_token=st.secrets["GOOGLE_REFRESH_TOKEN"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=st.secrets["GOOGLE_CLIENT_ID"],
        client_secret=st.secrets["GOOGLE_CLIENT_SECRET"],
        scopes=["https://www.googleapis.com/auth/gmail.send"],
    )
    if creds.expired or not creds.valid:
        creds.refresh(Request())
    return creds

def send_email(to, subject, body_text):
    creds = load_credentials()
    service = build('gmail', 'v1', credentials=creds)

    message = MIMEText(body_text)
    message['To'] = to
    message['From'] = 'me'
    message['Subject'] = subject

    raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
    body = {'raw': raw_message}

    sent = service.users().messages().send(userId='me', body=body).execute()
    return sent['id']

# --- OpenAI Setup ---
try:
    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
except KeyError:
    st.error("❌ OPENAI_API_KEY not found. Please check your .streamlit/secrets.toml or environment variables.")
    st.stop()

# --- AI Follow-Up Generator ---
def generate_followup_question(initial_answers, history):
    previous_qs = [h["question"] for h in history]

    prompt = f"""
You are helping students reflect on a science investigation.
Here were their initial answers:

Research Question: {initial_answers['research_question']}
Evidence Collected: {initial_answers['evidence']}
Interpretation: {initial_answers['meaning']}

Suggest ONE thoughtful follow-up question that is NOT a yes/no question.
Make it slightly harder if their answers were strong, or easier if their answers were vague.
Avoid repeating any of these already-asked questions: {previous_qs}
Only return the question text.
"""

    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )
        followup_question = response.choices[0].message.content.strip()
        return followup_question
    except Exception as e:
        st.error(f"❌ Error generating follow-up question: {e}")
        st.stop()

# --- Email Summary Generator ---
def create_summary(initial_answers, followup_history):
    summary = f"""Student Names: {initial_answers['names']}
Research Question: {initial_answers['research_question']}
Evidence Collected: {initial_answers['evidence']}
Interpretation: {initial_answers['meaning']}

Follow-Up Discussion:
"""
    for idx, entry in enumerate(followup_history, start=1):
        summary += f"\nQ{idx}: {entry['question']}\nA{idx}: {entry['answer']}\n"
    
    return summary

# --- Streamlit Front-End ---
st.title("🔬 Student Lab Report Sender")

# Initialize Session State
if "initial_answers" not in st.session_state:
    st.session_state.initial_answers = {}
if "followup_history" not in st.session_state:
    st.session_state.followup_history = []
if "mode" not in st.session_state:
    st.session_state.mode = "input"

# --- 1. Input Phase ---
if st.session_state.mode == "input":
    st.subheader("Step 1: Fill in your investigation details")

    names = st.text_input("0. What are your names?")
    research_question = st.text_area("1. What is your research question?")
    evidence = st.text_area("2. What key evidence did you collect during the investigation?")
    meaning = st.text_area("3. What do you think it means?")
    teacher_email = st.text_input("4. What is your teacher's email address?")

    if st.button("Submit Answers"):
        if not (names and research_question and evidence and meaning and teacher_email):
            st.error("❌ Please fill out all fields before submitting.")
        else:
            st.session_state.initial_answers = {
                "names": names,
                "research_question": research_question,
                "evidence": evidence,
                "meaning": meaning,
                "teacher_email": teacher_email,
            }
            st.session_state.mode = "followup"
            st.rerun()  # 🔥 Forces Streamlit to re-run immediately

# --- 2. Follow-Up Phase ---
elif st.session_state.mode == "followup":
    st.subheader("Step 2: Answer AI Follow-up Questions")

    if "current_question" not in st.session_state:
        with st.spinner("Generating a question..."):
            st.session_state.current_question = generate_followup_question(
                st.session_state.initial_answers, st.session_state.followup_history
            )

    st.write(f"💬 {st.session_state.current_question}")
    followup_answer = st.text_input("Your answer:")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Submit Follow-Up Answer"):
            if followup_answer.strip() == "":
                st.error("❌ Please answer the follow-up question.")
            else:
                st.session_state.followup_history.append({
                    "question": st.session_state.current_question,
                    "answer": followup_answer
                })
                st.session_state.current_question = generate_followup_question(
                    st.session_state.initial_answers, st.session_state.followup_history
                )
                st.rerun()

    with col2:
        if st.button("Finish and Send Summary"):
            st.session_state.mode = "send_summary"
            st.rerun()

# --- 3. Email Sending Phase ---
elif st.session_state.mode == "send_summary":
    st.subheader("Step 3: Send your work to your teacher")

    email_body = create_summary(st.session_state.initial_answers, st.session_state.followup_history)

    st.text_area("📋 Email Preview:", email_body, height=300)

    if st.button("Send Email Now"):
        try:
            message_id = send_email(
                st.session_state.initial_answers["teacher_email"],
                subject="Lab Investigation Summary",
                body_text=email_body
            )
            st.success(f"✅ Email sent successfully! Message ID: {message_id}")
        except Exception as e:
            st.error(f"❌ Failed to send email: {e}")
