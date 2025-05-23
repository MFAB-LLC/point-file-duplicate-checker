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
        csv_data = response.content.decode('utf-8')
        return csv_data
    except Exception as e:
        print(f"Error fetching CSV from {file_url}: {e}")
        return None

# Function to get attachments and relevant data from Airtable
def get_attachments():
    try:
        url = f"https://api.airtable.com/v0/{BASE_ID}/{TABLE_NAME}?sort[0][field]=Created%20Time&sort[0][direction]=desc&maxRecords=1"
        headers = {"Authorization": f"Bearer {AIRTABLE_ACCESS_TOKEN}"}
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        records = response.json().get('records', [])
        submissions = []

        for record in records:
            fields = record.get('fields', {})
            name = fields.get('Name', 'Unknown')
            email = fields.get('Email', '')
            if not email:
                continue

            file_data, file_names = [], []
            attachment_fields = ['Upload Files']

            for field_name in attachment_fields:
                if field_name in fields and isinstance(fields[field_name], list):
                    for attachment in fields[field_name]:
                        file_url = attachment['url']
                        file_name = attachment['filename']
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

# Function to find duplicates in the first column across multiple CSV files, comparing full rows
def find_duplicates(file_data, file_names):
    try:
        point_map = {}
        row_map = {}

        def process_csv(csv_content, file_name):
            csv_reader = csv.reader(StringIO(csv_content))
            for row in csv_reader:
                if not row:
                    continue
                point = row[0]
                full_row = ','.join(row)

                point_map.setdefault(point, set()).add(file_name)
                row_map.setdefault(point, set()).add(full_row)

        for content, name in zip(file_data, file_names):
            process_csv(content, name)

        result = {}
        for point, files in point_map.items():
            if len(files) > 1:
                is_full_row_dup = len(row_map[point]) == 1
                result[point] = (files, is_full_row_dup)

        return result

    except Exception as e:
        error_msg = f"Error comparing files: {str(e)}"
        print(error_msg)
        send_email("File Comparison Error", error_msg, ADMIN_EMAIL, ADMIN_EMAIL)
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
            all_files = set(file for files, _ in duplicates.values() for file in files)
            result_body += f"{', '.join(all_files)}\n\n"

            for key, (files, is_full_row_dup) in duplicates.items():
                note = "(row)" if is_full_row_dup else "(number only)"
                result_body += f"- {key} {note}\n"
        else:
            result_subject = f"{name}: No Duplicates Found"
            result_body = "No duplicates found in the submitted files."

        send_email(result_subject, result_body, email, ADMIN_EMAIL)

if __name__ == "__main__":
    main()
