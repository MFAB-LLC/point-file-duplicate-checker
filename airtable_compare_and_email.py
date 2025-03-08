import requests
import csv
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from io import StringIO
import traceback

# Airtable and email configuration
AIRTABLE_ACCESS_TOKEN = os.getenv('AIRTABLE_ACCESS_TOKEN')
BASE_ID = os.getenv('BASE_ID')
TABLE_NAME = os.getenv('TABLE_NAME')
SMTP_SERVER = os.getenv('SMTP_SERVER')
SMTP_PORT = int(os.getenv('SMTP_PORT', 587))
EMAIL_ADDRESS = os.getenv('EMAIL_ADDRESS')
EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD')
ADMIN_EMAIL = os.getenv('ADMIN_EMAIL')

# Function to fetch CSV content from a given Airtable file URL
def fetch_csv_data(file_url):
    try:
        response = requests.get(file_url)
        response.raise_for_status()
        
        # Decode the content to text format
        csv_data = response.content.decode('utf-8')
        return csv_data

    except Exception as e:
        print(f"Error fetching CSV from {file_url}: {e}")
        return None

# Function to get attachments and relevant data from Airtable
def get_attachments():
    try:
        url = f"https://api.airtable.com/v0/{BASE_ID}/{TABLE_NAME}?sort[0][field]=Created Time&sort[0][direction]=desc&maxRecords=1"
        headers = {"Authorization": f"Bearer {AIRTABLE_ACCESS_TOKEN}"}
        
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        records = response.json().get('records', [])
        if not records:
            print("No new records found.")
            return []
        
        submissions = []

        for record in records:  # This should now only loop through the **latest** record
            fields = record.get('fields', {})
            name = fields.get('Name', 'Unknown')
            email = fields.get('Email', '')

            if not email:
                continue

            file_data, file_names = [], []

            # Loop through attachment fields (File 1 to File 5)
            attachment_fields = ['File 1', 'File 2', 'File 3', 'File 4', 'File 5']
            
            for field_name in attachment_fields:
                if field_name in fields and isinstance(fields[field_name], list):
                    file_url = fields[field_name][0]['url']
                    file_name = fields[field_name][0]['filename']  # Use actual filename from Airtable

                    print(f"Fetching data from {file_name}...")
                    csv_content = fetch_csv_data(file_url)

                    if csv_content:
                        file_data.append(csv_content)
                        file_names.append(file_name)

            if file_data:
                submissions.append({'name': name, 'email': email, 'file_data': file_data, 'file_names': file_names})

        return submissions

    except Exception as e:
        error_msg = f"Error fetching data from Airtable: {str(e)}"
        print(error_msg)
        send_email("Airtable Fetch Error", error_msg, ADMIN_EMAIL, ADMIN_EMAIL)
        return []

# Function to find duplicates in the first column across multiple CSV files
def find_duplicates(file_data, file_names):
    try:
        data_map = {}

        def load_first_column(csv_content, file_name):
            csv_reader = csv.reader(StringIO(csv_content))
            for row in csv_reader:
                if row:
                    key = row[0]
                    data_map.setdefault(key, set()).add(file_name)

        # Load data from each file
        for content, name in zip(file_data, file_names):
            load_first_column(content, name)

        # Return only the entries with duplicates
        return {k: v for k, v in data_map.items() if len(v) > 1}

    except Exception as e:
        error_msg = f"Error comparing files: {str(e)}"
        print(error_msg)
        send_email("File Comparison Error", error_msg, ADMIN_EMAIL)
        return {}

# Function to send the result email to the user
def send_email(subject, body, recipient, admin_email):
    try:
        msg = MIMEMultipart()
        msg['From'] = EMAIL_ADDRESS
        msg['To'] = recipient
        msg['Bcc'] = admin_email
        msg['Subject'] = subject
        
        msg.attach(MIMEText(body, 'plain'))
        
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
        
        print(f"Email sent to {recipient}")
    
    except Exception as e:
        print(f"Error sending email to {recipient}: {e}")
        traceback.print_exc()

# Main script to fetch data, check for duplicates, and notify users
def main():
    submissions = get_attachments()

    for submission in submissions:
        name = submission['name']
        email = submission['email']
        file_data = submission['file_data']
        file_names = submission['file_names']

        duplicates = find_duplicates(file_data, file_names)
        
        if duplicates:
            result_subject = f"{name}: Duplicates Found"
            result_body = "Duplicate point numbers listed below were found in the following files: " 
            
            # Collect and join filenames
            all_files = set(file for files in duplicates.values() for file in files)
            result_body += f"{', '.join(all_files)}\n\n"
        
            for key, files in duplicates.items():
                result_body += f"- {key}\n"
        else:
            result_subject = f"{name}: No Duplicates Found"
            result_body = "No duplicates found in the submitted files."
        
        # Send the results via email
        send_email(result_subject, result_body, email, ADMIN_EMAIL)

if __name__ == "__main__":
    main()
