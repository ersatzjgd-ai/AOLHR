import streamlit as st
import os
import imaplib
import email
import zipfile
import tempfile
import io
from email.header import decode_header

# --- APP CONFIGURATION ---
st.set_page_config(page_title="Gmail Resume Extractor", page_icon="📄")

# ==========================================
# 1. SECURITY GATE (Railway Master Password)
# ==========================================
# Pulls the secret password from Railway's environment variables. 
# (Defaults to "local_dev_password" if you run it locally without setting an env var)
MASTER_PASSWORD = os.environ.get("APP_MASTER_PASSWORD", "local_dev_password")

# Initialize session state for authentication
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

# If not authenticated, show the lock screen and stop execution
if not st.session_state.authenticated:
    st.title("🔒 Secure Access")
    st.write("This app is locked to prevent unauthorized compute usage.")
    pwd_input = st.text_input("Enter Master Password:", type="password")
    
    if st.button("Unlock App"):
        if pwd_input == MASTER_PASSWORD:
            st.session_state.authenticated = True
            st.rerun()  # Refresh the page to load the actual app
        else:
            st.error("Access Denied. Incorrect Master Password.")
    st.stop()  # Prevents any code below this line from running until unlocked


# ==========================================
# 2. HELPER FUNCTIONS
# ==========================================
def clean_filename(filename):
    """Removes invalid characters from file names to prevent OS errors."""
    return "".join(c for c in filename if c.isalnum() or c in (' ', '.', '_', '-')).rstrip()


# ==========================================
# 3. MAIN EXTRACTOR APPLICATION UI & LOGIC
# ==========================================
st.title("📄 Bulk Gmail Resume Extractor")
st.write("Extract all attachments containing 'CV' or 'Resume' in the filename from your entire Gmail history.")

st.markdown("### Enter Gmail Credentials")
st.info("Reminder: You must use a 16-digit **App Password**, not your standard Gmail password.")
email_input = st.text_input("Gmail Address", placeholder="you@gmail.com")
password_input = st.text_input("App Password", type="password", placeholder="16-digit app password (no spaces)")

if st.button("Extract & Zip Resumes"):
    if not email_input or not password_input:
        st.error("Please provide both your Gmail address and App Password.")
    else:
        with st.spinner("Connecting to Gmail and searching your entire history. This may take a few minutes..."):
            try:
                # Connect and Authenticate
                mail = imaplib.IMAP4_SSL("imap.gmail.com")
                mail.login(email_input, password_input)
                
                # Search All Mail on Google's Servers
                mail.select('"[Gmail]/All Mail"')
                search_query = 'has:attachment (filename:cv OR filename:resume)'
                status, messages = mail.search(None, 'X-GM-RAW', f'"{search_query}"')
                
                if status != "OK" or not messages[0]:
                    st.warning("No emails found matching the criteria.")
                else:
                    email_ids = messages[0].split()
                    total_emails = len(email_ids)
                    st.success(f"Found {total_emails} emails with matching attachments. Beginning extraction...")
                    
                    # Process Downloads in a Secure Temporary Directory
                    with tempfile.TemporaryDirectory() as temp_dir:
                        saved_count = 0
                        progress_bar = st.progress(0)
                        
                        for index, e_id in enumerate(email_ids):
                            res, msg_data = mail.fetch(e_id, "(RFC822)")
                            for response_part in msg_data:
                                if isinstance(response_part, tuple):
                                    msg = email.message_from_bytes(response_part[1])
                                    
                                    if msg.is_multipart():
                                        for part in msg.walk():
                                            if part.get_content_maintype() == 'multipart' or part.get('Content-Disposition') is None:
                                                continue

                                            filename = part.get_filename()
                                            if filename:
                                                # Handle special character encoding in filenames
                                                decoded, charset = decode_header(filename)[0]
                                                if isinstance(decoded, bytes):
                                                    filename = decoded.decode(charset or 'utf-8')
                                                
                                                filename = clean_filename(filename)
                                                fname_lower = filename.lower()
                                                
                                                # Strict check for CV or Resume in the actual file name
                                                if 'cv' in fname_lower or 'resume' in fname_lower:
                                                    filepath = os.path.join(temp_dir, filename)
                                                    
                                                    # Collision handling for identically named files (e.g. resume(1).pdf)
                                                    counter = 1
                                                    base_name, ext = os.path.splitext(filename)
                                                    while os.path.exists(filepath):
                                                        filepath = os.path.join(temp_dir, f"{base_name}_{counter}{ext}")
                                                        counter += 1

                                                    with open(filepath, "wb") as f:
                                                        f.write(part.get_payload(decode=True))
                                                    saved_count += 1
                            
                            # Update visual progress bar
                            progress_bar.progress((index + 1) / total_emails)
                        
                        # Zip the files directly into memory (prevents server clutter)
                        if saved_count > 0:
                            st.success(f"Successfully processed {saved_count} resumes! Preparing your download...")
                            
                            zip_buffer = io.BytesIO()
                            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zipf:
                                for root, _, files in os.walk(temp_dir):
                                    for file in files:
                                        file_path = os.path.join(root, file)
                                        zipf.write(file_path, arcname=file)
                            
                            # Trigger Streamlit Download Button
                            st.download_button(
                                label="⬇️ Download Resumes (ZIP)",
                                data=zip_buffer.getvalue(),
                                file_name="extracted_resumes.zip",
                                mime="application/zip",
                                type="primary"
                            )
                        else:
                            st.warning("Processed emails, but no matching files were successfully extracted.")
                            
                mail.logout()
            
            except imaplib.IMAP4.error:
                st.error("Authentication failed. Please verify your Gmail address and 16-digit App Password.")
            except Exception as e:
                st.error(f"An unexpected error occurred: {e}")
