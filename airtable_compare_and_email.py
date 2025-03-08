import requests
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


def fetch_records(api_key, base_id, table_name):
    url = f"https://api.airtable.com/v0/{base_id}/{table_name}"
    headers = {"Authorization": f"Bearer {api_key}"}
    response = requests.get(url, headers=headers)
    return response.json().get("records", [])


def extract_filenames(record):
    filenames = []
    for field, attachments in record.get("fields", {}).items():
        if isinstance(attachments, list):
            for attachment in attachments:
                filename = attachment.get("filename")
                if filename:
                    filenames.append(filename)
    return filenames


def find_duplicates(records):
    point_files = {}
    
    for record in records:
        filenames = extract_filenames(record)
        points = record.get("fields", {}).get("Points", [])
        
        for point in points:
            if point not in point_files:
                point_files[point] = set()
            point_files[point].update(filenames)

    duplicates = {k: v for k, v in point_files.items() if len(v) > 1}
    return duplicates


def send_email(subject, body, smtp_server, smtp_port, email_address, email_password, recipient_email, admin_email):
    msg = MIMEMultipart()
    msg['From'] = email_address
    msg['To'] = recipient_email
    msg['Bcc'] = admin_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))

    server = smtplib.SMTP(smtp_server, smtp_port)
    server.starttls()
    server.login(email_address, email_password)
    text = msg.as_string()
    server.sendmail(email_address, [recipient_email, admin_email], text)
    server.quit()


def main():
    import os

    api_key = os.getenv('AIRTABLE_API_KEY')
    base_id = os.getenv('BASE_ID')
    table_name = os.getenv('TABLE_NAME')
    smtp_server = os.getenv('SMTP_SERVER')
    smtp_port = os.getenv('SMTP_PORT')
    email_address = os.getenv('EMAIL_ADDRESS')
    email_password = os.getenv('EMAIL_PASSWORD')
    admin_email = os.getenv('ADMIN_EMAIL')
    recipient_email = os.getenv('RECIPIENT_EMAIL')

    records = fetch_records(api_key, base_id, table_name)
    duplicates = find_duplicates(records)

    name = table_name.replace("_", " ").title()
    
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


    send_email(result_subject, result_body, smtp_server, smtp_port, email_address, email_password, recipient_email, admin_email)


if __name__ == "__main__":
    main()
