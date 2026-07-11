import streamlit as st
import os
import imaplib
import email
import zipfile
import tempfile
import io
from email.header import decode_header

# --- APP CONFIGURATION ---
# --- APP CONFIGURATION ---
st.set_page_config(page_title="Zoho Resume Extractor", page_icon="app_icon.png")


# ==========================================
# 1. SECURITY GATE (Railway Master Password)
# ==========================================
MASTER_PASSWORD = os.environ.get("APP_MASTER_PASSWORD", "local_dev_password")

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.title("🔒 Secure Access only for AOL HR")
    st.write("This app is locked to prevent unauthorized compute usage.")
    pwd_input = st.text_input("Enter Master Password:", type="password")
    
    if st.button("Unlock App"):
        if pwd_input == MASTER_PASSWORD:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("Access Denied. Incorrect Master Password.")
    st.stop()


# ==========================================
# 2. HELPER FUNCTIONS
# ==========================================
def clean_filename(filename):
    """Removes invalid characters from file names to prevent OS errors."""
    return "".join(c for c in filename if c.isalnum() or c in (' ', '.', '_', '-')).rstrip()

def get_decoded_subject(msg):
    """Safely extracts and decodes the email subject line."""
    raw_subject = msg.get("Subject", "")
    if not raw_subject:
        return ""
        
    decoded_parts = decode_header(raw_subject)
    subject_str = ""
    for part, charset in decoded_parts:
        if isinstance(part, bytes):
            subject_str += part.decode(charset or 'utf-8', errors='ignore')
        else:
            subject_str += str(part)
    return subject_str.lower()


# ==========================================
# 3. MAIN EXTRACTOR APPLICATION UI & LOGIC
# ==========================================
st.image("app_icon.png", width=100) # Adjust the width number to make it bigger/smaller
st.title("AOL Human Resources ")
st.write("Extract attachments containing 'CV' or 'Resume' in the filename, OR from emails with 'Resume' in the subject.")

# INSTRUCTIONS FOR ZOHO
st.markdown("""
### 🔐 How to Generate Your Zoho App Password
To protect your account, Zoho requires an App-Specific Password for this tool.

**Follow these steps:**
1. Log into your [Zoho Accounts Security Page](https://accounts.zoho.com/home#security).
2. Look for **App Passwords** and click on it. (Ensure Two-Factor Authentication is enabled first).
3. Click **Generate New Password**.
4. Name it "Resume Extractor" and click Generate.
5. Copy the password provided and paste it below. 

*Note: You must also ensure IMAP is enabled in your Zoho Mail Settings (Settings > Mail Accounts > IMAP Access).*
""")

st.markdown("---")
st.markdown("### Enter Zoho Credentials")
email_input = st.text_input("Zoho Email Address", placeholder="you@zohomail.com")
password_input = st.text_input("Zoho App Password", type="password", placeholder="Paste your generated app password")

if st.button("Extract & Zip Resumes"):
    if not email_input or not password_input:
        st.error("Please provide both your Zoho email address and App Password.")
    else:
        with st.spinner("Connecting to Zoho and scanning your inbox. This may take a few minutes..."):
            try:
                # 1. Connect to Zoho IMAP Server
                mail = imaplib.IMAP4_SSL("imap.zoho.com")
                mail.login(email_input, password_input)
                
                # 2. Select the Inbox
                # Note: Unlike Gmail's "All Mail", traditional IMAP requires specifying a folder. 
                mail.select('"INBOX"')
                
                # 3. Standard IMAP Search Query
                # This asks the server for emails containing "resume" or "cv" in the subject or text.
                search_query = 'OR TEXT "resume" TEXT "cv"'
                status, messages = mail.search(None, search_query)
                
                if status != "OK" or not messages[0]:
                    st.warning("No emails found matching the criteria in your Inbox.")
                else:
                    email_ids = messages[0].split()
                    total_emails = len(email_ids)
                    st.success(f"Found {total_emails} potential emails. Filtering and extracting attachments...")
                    
                    with tempfile.TemporaryDirectory() as temp_dir:
                        saved_count = 0
                        progress_bar = st.progress(0)
                        
                        valid_doc_extensions = ('.pdf', '.doc', '.docx', '.txt', '.rtf')
                        
                        for index, e_id in enumerate(email_ids):
                            res, msg_data = mail.fetch(e_id, "(RFC822)")
                            for response_part in msg_data:
                                if isinstance(response_part, tuple):
                                    msg = email.message_from_bytes(response_part[1])
                                    
                                    subject_lower = get_decoded_subject(msg)
                                    
                                    if msg.is_multipart():
                                        for part in msg.walk():
                                            if part.get_content_maintype() == 'multipart' or part.get('Content-Disposition') is None:
                                                continue

                                            filename = part.get_filename()
                                            if filename:
                                                decoded, charset = decode_header(filename)[0]
                                                if isinstance(decoded, bytes):
                                                    filename = decoded.decode(charset or 'utf-8')
                                                
                                                filename = clean_filename(filename)
                                                fname_lower = filename.lower()
                                                
                                                is_document = fname_lower.endswith(valid_doc_extensions)
                                                
                                                # Strict filtering applied in Python to drop false-positives from the broad IMAP search
                                                if 'cv' in fname_lower or 'resume' in fname_lower or ('resume' in subject_lower and is_document):
                                                    filepath = os.path.join(temp_dir, filename)
                                                    
                                                    # Collision handling
                                                    counter = 1
                                                    base_name, ext = os.path.splitext(filename)
                                                    while os.path.exists(filepath):
                                                        filepath = os.path.join(temp_dir, f"{base_name}_{counter}{ext}")
                                                        counter += 1

                                                    with open(filepath, "wb") as f:
                                                        f.write(part.get_payload(decode=True))
                                                    saved_count += 1
                            
                            progress_bar.progress((index + 1) / total_emails)
                        
                        if saved_count > 0:
                            st.success(f"Successfully processed {saved_count} resumes! Preparing your download...")
                            
                            zip_buffer = io.BytesIO()
                            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zipf:
                                for root, _, files in os.walk(temp_dir):
                                    for file in files:
                                        file_path = os.path.join(root, file)
                                        zipf.write(file_path, arcname=file)
                            
                            st.download_button(
                                label="⬇️ Download Resumes (ZIP)",
                                data=zip_buffer.getvalue(),
                                file_name="zoho_extracted_resumes.zip",
                                mime="application/zip",
                                type="primary"
                            )
                        else:
                            st.warning("Processed potential emails, but no matching resume files were found.")
                            
                mail.logout()
            
            except imaplib.IMAP4.error:
                st.error("Authentication failed. Ensure IMAP is enabled in Zoho and your App Password is correct.")
            except Exception as e:
                st.error(f"An unexpected error occurred: {e}")
