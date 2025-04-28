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
You are assessing student science investigation reflections using two rubrics:

Rubric 1: Presenting Evidence
- 1 ("Getting There"): Lists what they saw, measured, or noticed; points to evidence but does not clearly connect it to the research question.
- 2 ("Partial Solid"): Includes some relevant evidence, but descriptions are general OR misses patterns, contrasts, or possible relationships.
- 3 ("Solid"): Presents a range of specific evidence clearly tied to the research question AND describes key patterns, contrasts, or cause-effect relationships.
- 4 ("Excellent"): Selects specific, relevant evidence; describes patterns or relationships; AND highlights limitations, uncertainty, or suggests additional data that would improve clarity.

Rubric 2: Constructing an Explanation
- 1 ("Getting There"): Says what they think the evidence means; suggests a reason but without clear logical flow.
- 2 ("Partial Solid"): Begins to connect evidence to reasoning, but the logic is incomplete OR cause-effect ideas are missing or unclear.
- 3 ("Solid"): Strings together a clear explanation that spells out cause-effect connections explcitly with mechanisms or clear reasoning. Answers the research question AND shows how evidence backs up the explanation through cause-and-effect.
- 4 ("Excellent"): Builds a cause-effect explanation AND connects it to scientific ideas (energy flow, matter changes, or scale/quantity); recognizes gaps, limitations, or alternative explanations.

---

Scoring Rules:
- Match your reasoning explicitly to rubric words like "specific evidence," "patterns," "cause-effect," "uncertainty," "additional data."
- Give a range of possible scores, using half scores if needed.
- Use the second person to refer to the student personally.
- Be brief but clear: 1-2 sentences justifying each score, focusing only on the positive items completed. 

Follow-Up Question Rules:
- If either score is 1 or 2, start with a comment along the lines of: "This feedback is meant to guide you to immediately improve your work. Use these questions to guide your revision, then submit."
- If Evidence Score is 1 → Ask for more specific evidence, closely connected to the research question.
- If Evidence Scores is 2 → Ask for patterns, contrasts, or clearer tie to research question.
- If Evidence Score is 3 → Ask about uncertainty, limitations, or additional data that could strengthen the evidence.
- If Evidence Score is 4 → Ask about generalizing to new materials, conditions, or variables.
- If Explanation Score is 1 → Ask for a clear reason why things happened how they did, using cause-effect.
- If Explanation Score is 2 → Ask for stronger cause-effect reasoning that ties evidence directly to the research question.
- If Explanation Score is 3 → Ask for connection to scientific ideas (energy, matter, or scale) OR recognition of possible gaps or alternatives.
- If Explanation Score is 4 → Ask for deeper particle-level reasoning OR critical evaluation of alternative explanations.

All follow-up questions must be open-ended (cannot be answered "yes" or "no").

---

Example:

Student Initial Answers:
- Research Question: Do different materials reflect, absorb, or transmit microwave energy?
- Present Evidence: The wet sponge heated up. The foil sparked and didn’t heat. The empty plastic cup stayed cool while the water inside got hot even though it was surrounded by plastic. One pattern is that only the wet stuff got hot.
- Construct an Explanation: Microwaves pass through plastics but are absorbed by water. Metals reflect microwaves or let it pass through.

Assessment:
- Present Evidence - Rough Score Range: 2.5-3
- Construct an Explanation - Score Range: 2-2.5

Follow-Up Questions:
- Evidence Question: What uncertainty or limitation in your evidence might affect how sure you are about your explanation?
- Explanation Question: How could you connect your explanation to ideas about how energy moves or how materials change?

---

Now assess this new student:

Student Initial Answers:
- Research Question: {initial_answers['research_question']}
- Present Evidence: {initial_answers['evidence']}
- Construct an Explanation: {initial_answers['meaning']}

Already Asked Questions: {previous_qs}

Instructions:
- Provide friendly, clear rubric-based reasoning for evidence and explanation.
- Assign 1–4 scores for each.
- Write two open-ended follow-up questions (one for evidence, one for explanation) that push the student one level higher based on their scores.
- Do not repeat any already-asked questions.

Return your response cleanly structured like this:

Assessment:
- Evidence: Evidence Score: [number]  
- Explanation: Explanation Score: [number]

Follow-Up Questions:
- Evidence Question: [question here]
- Explanation Question: [question here]


"""
    # --- removed [rubric-based reasoning] above ---

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )
        followup_output = response.choices[0].message.content.strip()
        return followup_output
    except Exception as e:
        st.error(f"❌ Error generating follow-up assessment: {e}")
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
st.title("Lab Report Reflection")

# --- Rubric Display ---
st.markdown("""
### Rubrics for Reflection
<small><i>Use these rubrics to guide your investigation answers and reflections:</i></small>

<div style='font-size: 70%;'>

| Skill | Getting There | Solid | Excellent |
|:------|:--------------|:------|:----------|
| **Present Evidence** | • List what you saw, measured, or noticed during the investigation<br>• Point to key evidence that connects to the research question. | • Present a range of specific evidence that helps clearly answer the research question.<br>• Describe key patterns, contrasts, or possible relationships in the evidence. | • Highlight limitations of the evidence or key points of uncertainty or unexpected results.<br>• Suggest additional data that would make an answer clearer or more certain. |
| **Construct an Explanation** | • Say what you think the evidence means, or what it shows about the research question.<br>• Suggest a reason why it might have happened this way. | • String together a clear explanation that answers the research question.<br>• Show how the evidence backs up this explanation, using a clear cause-and-effect idea. | • Connect your explanation to ideas about energy, matter changes, or scale and quantity.<br>• Point out any gaps or limitations in your ideas, or other possible explanations. |

</div>
""", unsafe_allow_html=True)

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
    evidence = st.text_area("2. What did you see or measure?  What key evidence did you collect that’s most relevant to the research question?")
    meaning = st.text_area("3. What might this mean? What can you figure out, based on this evidence?")
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
            st.rerun()

# --- 2. Follow-Up Phase ---
elif st.session_state.mode == "followup":
    st.subheader("Step 2: Reflect and Revise Your Thinking")

    if "current_followup" not in st.session_state:
        with st.spinner("Generating feedback..."):
            st.session_state.current_followup = generate_followup_question(
                st.session_state.initial_answers, st.session_state.followup_history
            )

    # Parse the follow-up into parts
    followup_parts = st.session_state.current_followup.split("Follow-Up Questions:")
    assessment_part = followup_parts[0].strip()
    questions_part = followup_parts[1].strip()

    # Split the two follow-up questions
    lines = questions_part.split("\n")
    evidence_q = lines[0].replace("Evidence Question: ", "").strip()
    explanation_q = lines[1].replace("Explanation Question: ", "").strip()

    # Show the Assessment Feedback
    st.markdown("### 📋 AI Assessment of Your First Answers:")
    st.markdown(assessment_part)

    # Editable sections
    st.markdown("### ✏️ Revise or Extend Your Thinking:")

    st.markdown(f"**Evidence Follow-Up Question:** {evidence_q}")
    updated_evidence = st.text_area(
        "Revise your Evidence based on the follow-up question:",
        st.session_state.initial_answers['evidence'],
        key="updated_evidence"
    )

    st.markdown(f"**Explanation Follow-Up Question:** {explanation_q}")
    updated_meaning = st.text_area(
        "Revise your Meaning based on the follow-up question:",
        st.session_state.initial_answers['meaning'],
        key="updated_meaning"
    )

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Submit Revisions"):
            if updated_evidence.strip() == "" or updated_meaning.strip() == "":
                st.error("❌ Please complete both revised sections before submitting.")
            else:
                st.session_state.followup_history.append({
                    "question": {
                        "evidence_q": evidence_q,
                        "explanation_q": explanation_q
                    },
                    "answer": {
                        "updated_evidence": updated_evidence,
                        "updated_meaning": updated_meaning
                    }
                })
                # After revision, allow another reflection round OR move forward
                st.session_state.current_followup = generate_followup_question(
                    {
                        "names": st.session_state.initial_answers["names"],
                        "research_question": st.session_state.initial_answers["research_question"],
                        "evidence": updated_evidence,
                        "meaning": updated_meaning,
                        "teacher_email": st.session_state.initial_answers["teacher_email"],
                    },
                    st.session_state.followup_history
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
