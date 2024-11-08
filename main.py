import os
import openai
import pickle
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from collections import defaultdict
from email.mime.text import MIMEText
import base64


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
    results = service.users().messages().list(userId='me', maxResults=10, q="category:primary").execute()
    messages = results.get('messages', [])
    
    categorized_emails = categorize_emails(service, messages)
    
    # Create a summary text
    summary_text = "Your daily email summary:\n\n"
    for category, emails in categorized_emails.items():
        summary_text += f"--- {category} ---\n"
        for email in emails:
            summary_text += f"Subject: {email['subject']}\nSummary: {email['summary']}\n\n"
    
    return summary_text

openai.api_key = openai.api_key = os.getenv("OPENAI_API_KEY")
def summarize_content(content):
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": f"Summarize the following email content:\n\n{content}"}],
            max_tokens=50
            
        )
        return response.choices[0].message['content'].strip()
    except Exception as e:
        print(f"An error occurred with OpenAI API: {e}")
        return content[:100]  # Fallback to the first 100 chars if API fails

def categorize_emails(service, messages):
    categorized_emails = defaultdict(list)

    for message in messages:
        # Retrieve full email message
        msg = service.users().messages().get(userId='me', id=message['id']).execute()
        headers = msg['payload']['headers']
        
        # Extract subject and snippet
        subject = next((header['value'] for header in headers if header['name'] == 'Subject'), 'No Subject')
        snippet = msg.get('snippet', 'No Snippet')
        
        # Fetch and summarize the full email text
        full_content = msg.get('snippet', 'No Content Available')
        summary = summarize_content(full_content)
        
        # Categorize based on keywords
        if any(keyword in subject.lower() for keyword in ['thanks for applying', 'application received']):
            categorized_emails['Job Applications'].append({'subject': subject, 'summary': summary})
        elif any(keyword in subject.lower() for keyword in ['rejected', 'sorry', 'regret']):
            categorized_emails['Rejections'].append({'subject': subject, 'summary': summary})
        elif any(keyword in subject.lower() for keyword in ['reward', 'coupon', 'sale', 'discount']):
            categorized_emails['Shopping Codes'].append({'subject': subject, 'summary': summary})
        elif any(keyword in subject.lower() for keyword in ['newsletter', 'tech', 'update']):
            categorized_emails['Tech Newsletters'].append({'subject': subject, 'summary': summary})
        else:
            categorized_emails['Other'].append({'subject': subject, 'summary': summary})

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

    recipient_email = "aishwaryajanardhana@gmail.com"
    
    # Send the summary email to yourself
    send_summary_email(service, summary_text, recipient_email)

if __name__ == '__main__':
    main()
