import os
import openai
import pickle
import json
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from collections import defaultdict
from email.mime.text import MIMEText
import base64
from dotenv import load_dotenv

load_dotenv(dotenv_path=".env")

openai.api_key = os.getenv("OPENAI_API_KEY")

# print("Key Loaded:", openai.api_key is not None)


SCOPES = ['https://www.googleapis.com/auth/gmail.readonly','https://www.googleapis.com/auth/gmail.send']

def authenticate_email():
    creds=None
    if os.path.exists('token.json'):
        with open('token.json','rb') as token:
            creds=pickle.load(token)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow=InstalledAppFlow.from_client_secrets_file('Credentials.json',SCOPES)
            creds=flow.run_local_server(port=0)
        with open('token.json','wb') as token:
            pickle.dump(creds,token)
    return creds


def get_emails(service):
    print("Fetching emails...")
    results = service.users().messages().list(userId='me', maxResults=20,q="category:primary").execute()
    messages = results.get('messages', [])
    
    categorized_emails = categorize_emails(service, messages)
    
    # Create a summary text
    summary_text = "Your daily email summary:\n\n"
    for category, emails in categorized_emails.items():
        summary_text += f"--- {category} ---\n"
        for email in emails:
            summary_text += f"Subject: {email['subject']}\nSummary: {email['summary']}\n\n"
    
    return summary_text

def summarize_content(content):
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that summarizes emails into concise 2–3 sentence summaries for Aishwarya Janardhana Rajur. Dont mention Aishwarya Janardhana in every email as you are doing this summary for me. Also, make sure if there are next steps titled email with a link, categorise them under Online assesments. If the subject has ask for scheduling a call with them or it is sent from an actual person, categorize it to Recruiter reachout"},
                {"role": "user", "content": f"""
Summarize this email in 2–3 sentences and categorize it into one of the following and also make sure to categorise applied application email to job applications and not recruiter reachout. Also recruiter reachout is one where recruiter is scheduling for a call or some real human messaging:
Recruiter reachout, Online Assesments, Job Applications, Rejections, Shopping, Tech Newsletters, or Other.

Respond ONLY in this JSON format:
{{"summary": "...", "category": "..."}}.

Email content:
{content}
                """}
            ],
            max_tokens=100,
            temperature=0.3
            
        )
        return json.loads(response.choices[0].message["content"].strip())
    except Exception as e:
        print(f"An error occurred with OpenAI API: {e}")
        return content[:100]  # Fallback to the first 100 chars if API fails

def categorize_emails(service, messages):
    categorized_emails = defaultdict(list)

    for message in messages:
        msg = service.users().messages().get(userId='me', id=message['id']).execute()
        headers = msg['payload']['headers']
        snippet = msg.get('snippet', 'No Snippet')

        # Get subject or use fallback
        subject = next((h['value'] for h in headers if h['name'] == 'Subject'), '').strip()
        if not subject or subject.lower() == "no subject":
            subject = snippet[:30] + "..."

        # Summarize and categorize using GPT
        full_content = snippet
        result = summarize_content(full_content)
        summary = result.get("summary", snippet[:100])
        category = result.get("category", "Other")

        categorized_emails[category].append({'subject': subject, 'summary': summary})
    return categorized_emails



def create_message(to, subject, body):
    message = MIMEText(body)
    message['to'] = to
    message['subject'] = subject
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    return {'raw': raw}

def send_summary_email(service, summary_text, recipient_email):
    # Use the recipient_email here for flexibility
    message = create_message(recipient_email, "Daily Email Summary", summary_text)
    send_message(service, "me", message)

def send_message(service, user_id, message):
    try:
        sent_message = service.users().messages().send(userId=user_id, body=message).execute()
        print(f"Message sent successfully! Message ID: {sent_message['id']}")
    except Exception as e:
        print(f"An error occurred while sending the email: {e}")

def main():
    creds = authenticate_email()
    service = build('gmail', 'v1', credentials=creds)
    
    # Fetch and categorize emails with AI-generated summaries
    summary_text = get_emails(service)

    recipient_email = "aishwarya.j.rajur@gmail.com"
    
    # Send the summary email to yourself
    send_summary_email(service, summary_text, recipient_email)

if __name__ == '__main__':
    main()
