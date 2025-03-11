#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Streamlit frontend for the AI-Powered CXR Report Generator.
This application allows users to upload chest X-ray images or CSV files
and generates structured radiological reports using AI.
"""
import os
import sys
# Add the project root directory to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
import logging
import asyncio
import streamlit as st
import aiohttp
import pandas as pd
import requests

# Use absolute imports to ensure consistency
from app.config.config import settings
from app.middleware.exception import exception_message
from app.middleware.logger import setup_logger
from app.services.file_service import (
    read_upload_file, 
    validate_image_file,
    save_report
)
from app.services.auth import AuthService

setup_logger()

st.set_page_config(
    page_title='AI-Powered CXR Report Generator',
    page_icon='🩻',
    layout='wide'
)

# Initialize session state variables for state management
if 'reset_counter' not in st.session_state:
    st.session_state.reset_counter = 0
if 'response_content' not in st.session_state:
    st.session_state.response_content = None
if 'last_submit_time' not in st.session_state:
    st.session_state.last_submit_time = 0
if 'page' not in st.session_state:
    st.session_state.page = "login"  # Start with login page
if 'selected_case_id' not in st.session_state:
    st.session_state.selected_case_id = None
if 'features' not in st.session_state:
    st.session_state.features = None
if 'predictions' not in st.session_state:
    st.session_state.predictions = None
if 'temp_image_path' not in st.session_state:
    st.session_state.temp_image_path = None
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'username' not in st.session_state:
    st.session_state.username = None
if 'user_role' not in st.session_state:
    st.session_state.user_role = None
if 'auth_token' not in st.session_state:
    st.session_state.auth_token = None
if 'login_error' not in st.session_state:
    st.session_state.login_error = None
if 'flagging_mode' not in st.session_state:
    st.session_state.flagging_mode = False

# --- Auth Utility Functions ---

def make_authenticated_request(url, method="GET", params=None, json_data=None):
    """
    Make an authenticated request to the backend API with the current auth token.
    
    Args:
        url: API endpoint URL
        method: HTTP method (GET, POST, etc.)
        params: URL parameters
        json_data: JSON payload for POST requests
        
    Returns:
        Response object
    """
    headers = {}
    if st.session_state.auth_token:
        headers["Authorization"] = f"Bearer {st.session_state.auth_token}"
    
    try:
        if method.upper() == "GET":
            return requests.get(url, params=params, headers=headers)
        elif method.upper() == "POST":
            return requests.post(url, params=params, json=json_data, headers=headers)
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")
    except requests.RequestException as e:
        logging.error(f"[APP] Request error: {exception_message(e)}")
        raise Exception(f"API request failed: {exception_message(e)}")
    

# --- Backend API Communication Functions ---

async def process_image_via_backend(image_content: bytes, filename: str) -> str:
    """
    Send image directly to the backend process_image endpoint to generate a report.
    """
    try:
        logging.info(f"[APP] Sending image to backend: {filename} ({len(image_content)} bytes)")

        async with aiohttp.ClientSession() as session:
            # Include auth token in headers
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {st.session_state.auth_token}"
            }
            
            # Instead of form data, send as JSON with byte encoding
            payload = {
                "file_content": image_content.decode('latin1'),  # Encode bytes to string
                "filename": filename
            }
            
            # Send to the backend's process_image_bytes endpoint
            endpoint_url = f"{settings.API_URL}/process_image_bytes/"
            logging.info(f"[APP] Sending request to: {endpoint_url}")
            
            async with session.post(
                endpoint_url, 
                json=payload,
                headers=headers
            ) as response:
                logging.info(f"[APP] Backend response status: {response.status}")
                
                # Handle authentication errors
                if response.status == 401:
                    logging.warning("[APP] Authentication failed. Redirecting to login.")
                    st.session_state.authenticated = False
                    st.session_state.auth_token = None
                    st.session_state.page = "login"
                    st.session_state.login_error = "Your session has expired. Please log in again."
                    raise Exception("Authentication failed. Please log in again.")
                
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"Backend processing failed: {response.status} - {error_text}")
                
                # Parse the response
                response_data = await response.json()
                logging.debug(f"[APP] Response data: {str(response_data)[:200]}...")

                # Extract the report content
                report_content = response_data
                # Extract features and predictions if available
                features = response_data.get("features", [])
                predictions = response_data.get("predictions", [])
                
                # Store in session state
                st.session_state.features = features
                st.session_state.predictions = predictions

                # Extract the report content from the structured response
                if isinstance(response_data, dict) and "report" in response_data:
                    logging.info("[APP] response_data is a dict with 'report' key")
                    report_content = response_data["report"]
                elif isinstance(response_data, dict) and "choices" in response_data:
                    logging.info("[APP] response_data is a dict with 'choices' key")
                    report_content = response_data["choices"][0]["message"]["content"]
                else:
                    logging.info("[APP] response_data is not a dict with 'report' or 'choices' key")
                    report_content = str(response_data)
                
                logging.info(f"[APP] Report content received: {len(str(report_content))} characters")
                return report_content
    except aiohttp.ClientError as e:
        error_msg = f"Communication error with backend: {exception_message(e)}"
        logging.error(f"[APP] {error_msg}")
        raise Exception(error_msg)
    except Exception as e:
        error_msg = f"Error processing image via backend: {exception_message(e)}"
        logging.error(f"[APP] {error_msg}")
        raise Exception(error_msg)
    
# --- Synchronous Processing Function ---

def process_and_generate_report(image_file=None) -> str:
    """
    Process an image file and generate a report using the backend API.
    
    Args:
        image_file: Streamlit UploadFile for image
        
    Returns:
        Generated report content
        
    Raises:
        Exception: If processing fails
    """
    try:
        # Create a new event loop for this function
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        async def async_process():
            # Process image file
            if image_file:
                with st.spinner("Processing image..."):
                    # Read the image content
                    image_content = await read_upload_file(image_file)
                    
                    # Save temporary image file
                    temp_dir = os.path.join(settings.ROOT_PATH, "storage", "temp")
                    os.makedirs(temp_dir, exist_ok=True)
                    temp_image_path = os.path.join(temp_dir, image_file.name)
                    with open(temp_image_path, "wb") as f:
                        f.write(image_content)
                    
                    st.session_state.temp_image_path = temp_image_path
                    
                    # Validate it's a proper image
                    logging.info(f"[APP] Validating image: {image_file.name}")
                    validate_image_file(image_file.name, image_content)
                    
                    # Process via backend
                    report_content = await process_image_via_backend(image_content, image_file.name)
                    return report_content
            else:
                raise ValueError("No image file provided for processing")

        # Run the async function and return results
        return loop.run_until_complete(async_process())
    except ValueError as e:
        # Handle validation errors
        error_msg = f"Invalid input: {exception_message(e)}"
        logging.error(f"[APP] {error_msg}")
        raise Exception(error_msg)
    except Exception as e:
        # Handle all other errors
        logging.error(f"[APP] Error in process_and_generate_report: {exception_message(e)}")
        raise
    finally:
        # Clean up the event loop
        try:
            loop.close()
        except:
            pass

# --- Page Navigation ---

def change_page(page):
    """Change the current page in the application"""
    st.session_state.page = page
    
    # Reset any page-specific state if needed
    if page == "main":
        st.session_state.selected_case_id = None
    elif page == "login" and st.session_state.authenticated:
        # If already authenticated, go to main page
        st.session_state.page = "main"

def logout_user():
    """Log out the current user"""
    st.session_state.authenticated = False
    st.session_state.username = None
    st.session_state.user_role = None
    st.session_state.auth_token = None
    change_page("login")

# --- Page Components ---

def login_page():
    """Login page to authenticate users"""    
    # Display login error if there is one
    if st.session_state.login_error:
        st.error(st.session_state.login_error)
        st.session_state.login_error = None
    
    # Create a narrower container for login
    col1, login_container, col2 = st.columns([1, 1, 1])
    with login_container:
        st.markdown("### 🩻 AI-Powered CXR AI Report Generator")
        st.markdown("## Login")
        # st.markdown("<h2 style='text-align: center;'>Login</h2>", unsafe_allow_html=True)
        
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        login_button = st.button("Login", key="login_button")
        
        if login_button:
            auth_service = AuthService()
            if auth_service.verify_credentials(username, password):
                # Set authenticated state
                st.session_state.authenticated = True
                st.session_state.username = username
                
                # Set default user role
                st.session_state.user_role = {
                    "role": "User",
                    "can_verify": True  # Give verification permission to all users for now
                }
                
                # Create a simple token (in production, use JWT or similar)
                import hashlib
                import time
                token_string = f"{username}:{int(time.time())}"
                st.session_state.auth_token = hashlib.sha256(token_string.encode()).hexdigest()
                
                # Change to main page
                change_page("main")
                st.success("Login successful!")
                st.rerun()
            else:
                st.error("Invalid username or password")

def main_page():
    """Main upload and processing page"""
    # Check if user is authenticated
    if "authenticated" not in st.session_state:
        st.session_state["authenticated"] = False
    
    # Show login page if not authenticated
    if not st.session_state["authenticated"]:
        login_page()
        return

    st.html("<h1 style='text-align: center;'>AI-Powered CXR Report Generator</h1>")
    
    # User information in sidebar
    with st.sidebar:
        st.markdown(f"**Logged in as:** {st.session_state.username}")
        st.markdown(f"**Role:** {st.session_state.user_role.get('role', 'User')}")
        # Keep this logout button
        if st.button("Logout", key="main_logout"):
            logout_user()
            st.rerun()
    
    # Create the three-column layout
    col_introduction, col_upload, col_report = st.columns(3)
    
    with col_introduction:
        st.markdown("### Instruction")
        with st.expander("📖 User Guide / 使用說明"):
            tab_english, tab_chinese = st.tabs(["English (EN)", "中文 (ZH)"])
            
            with tab_english:
                st.write("""
                **Welcome to the Chest X-ray Report AI Assistant**
                         
                **Usage**
                - **Step 1:** Upload your CXR image (JPG).
                - **Step 2:** Click **Submit** to get the report draft.
                - **Step 3:** See the report draft in the **Report (draft)** section.

                **Feedback**
                If the report draft is wrong:
                - Keep the CXR image.
                - Save the report result.
                - Exaplain the error.
                - Send everything to the developer to fix the issue.

                **Important**
                - Wait patiently for the analysis.
                - The image should be a clear chest X-ray in JPG format.
                """)
            
            with tab_chinese:
                st.write("""                  
                **歡迎使用胸部 X 光報告 AI 助理**
                
                **使用方法**
                - **步驟 1：** 上傳您的 CXR 影像 (JPG)。
                - **步驟 2：** 點選 **Submit** 按鈕，經分析後可取得報告。
                - **步驟 3：** 在 **Report (draft)** 查看報告。

                **回饋**
                如果報告草稿有誤：
                - 保留 CXR 影像。
                - 儲存報告結果。
                - 提供錯誤說明。
                - 將以上所有內容傳送給開發人員以解決問題。

                **重要提示**
                - 耐心等待分析。
                - 影像應為 JPG 格式的清晰胸部 X 光片。
                """)

    with col_upload:
        st.markdown("### Upload Data")
            
        # Upload with reset-capable keys
        uploaded_image = st.file_uploader(
            "🩻 Upload your CXR image file (jpg):",
            accept_multiple_files=False,
            type=["jpg", "jpeg"],
            key=f"image_{st.session_state.reset_counter}"
        )

        # Process selected data source
        json_data = None
        data_name = "Unknown"
        
        if uploaded_image:
            data_name = uploaded_image.name
            st.write(f"Selected image: {uploaded_image.name}")

        # Submit and Clear buttons side by side
        col_submit, col_clear = st.columns(2)
        with col_submit:
            if st.button("Submit", key="submit_button"):
                if can_submit():
                    if uploaded_image:
                        try:
                            report_content = process_and_generate_report(image_file=uploaded_image)
                                                
                            # Update UI and save report
                            st.session_state.response_content = report_content
                            if report_content:
                                try:
                                    # Use file service to save the report
                                    individual_path, master_path = save_report(uploaded_image.name, report_content)
                                    
                                    # Save complete case data
                                    if st.session_state.temp_image_path:
                                        case_data = {
                                            "image_path": st.session_state.temp_image_path,
                                            "image_name": uploaded_image.name,
                                            "features": st.session_state.features if st.session_state.features else [],
                                            "predictions": st.session_state.predictions if st.session_state.predictions else [],
                                            "report_content": report_content
                                        }
                                        
                                        # Save case data using authenticated backend API
                                        response = make_authenticated_request(
                                            f"{settings.API_URL}/api/save_case/", 
                                            method="POST",
                                            json_data=case_data
                                        )
                                        
                                        if response.status_code == 200:
                                            case_data = response.json()
                                            if case_data.get("success", False):
                                                st.session_state.case_id = case_data.get("case_id")
                                                st.success("Report generated and case saved!")
                                        else:
                                            st.success("Report generated successfully!")
                                            logging.warning(f"[APP] Failed to save case data: {response.status_code}")
                                    else:
                                        st.success("Report generated successfully!")
                                    
                                    logging.info(f"[APP] Report saved to {individual_path}")
                                except Exception as e:
                                    st.warning(f"Report generated but could not be saved: {exception_message(e)}")
                                    logging.error(f"[APP] Error saving report: {exception_message(e)}")
                        except Exception as e:
                            st.error(f"An error occurred: {exception_message(e)}")
                            logging.error(f"[APP] Error during processing: {exception_message(e)}")
                    else:
                        st.warning("Please upload a chest X-ray image to analyze.")
        
        with col_clear:
            if st.button("Clear", key="clear_button"):
                st.session_state.reset_counter += 1
                st.session_state.response_content = None
                st.session_state.features = None
                st.session_state.predictions = None
                st.session_state.temp_image_path = None
                logging.info("[APP] Cleared uploaded data and report.")
                st.rerun()

    with col_report:
        st.markdown("### Report (draft)")
        st.write("View all past reports in the 'Case History' page")
        
        # Display current report
        if st.session_state.response_content:
            logging.info(f"[APP] Displaying report ({len(st.session_state.response_content)} chars)")
            tab_markdown, tab_text = st.tabs(["Markdown", "Text"])
            with tab_markdown:
                st.markdown(st.session_state.response_content)
            with tab_text:
                st.text_area("Generated Report", st.session_state.response_content, height=500)

def case_history_page():
    """Display case history page"""
    # Check authentication
    if not st.session_state.authenticated:
        change_page("login")
        st.rerun()
        return
    
    st.title("Case History")
    
    # Back button
    if st.button("← Back to Main"):
        change_page("main")
    
    # Get cases from backend
    try:
        response = make_authenticated_request(f"{settings.API_URL}/api/cases/")
        
        if response.status_code == 200:
            data = response.json()
            if data.get("success", False) and data.get("cases", []):
                cases = data.get("cases", [])
                st.write(f"Found {len(cases)} cases")
                
                for case in cases:
                    # Create an expander for each case
                    with st.expander(f"{case['image_name']} - {case['timestamp'][:19]}"):
                        # Add view button
                        if st.button("View Details", key=f"view_{case['case_id']}"):
                            st.session_state.selected_case_id = case["case_id"]
                            change_page("case_details")
            else:
                st.info("No cases found. Process some images first.")
        else:
            st.error(f"Failed to fetch case history: {response.status_code}")
    except Exception as e:
        st.error(f"Error loading case history: {exception_message(e)}")
        logging.error(f"[APP] Error loading case history: {exception_message(e)}")

def case_details_page():
    """Show details for a specific case"""
    # Check authentication
    if not st.session_state.authenticated:
        change_page("login")
        st.rerun()
        return
    
    st.title("Case Details")
    
    # Back button
    if st.button("← Back to Case History"):
        change_page("case_history")
    
    # Check if there's a selected case
    if not st.session_state.selected_case_id:
        st.error("No case selected")
        change_page("case_history")
        return
    
    # Fetch case data from backend
    try:
        case_id = st.session_state.selected_case_id
        response = make_authenticated_request(f"{settings.API_URL}/api/cases/{case_id}")
        
        if response.status_code == 200:
            data = response.json()
            if data.get("success", False):
                case_data = data.get("case_data", {})
                
                # Display case information
                st.subheader(f"Case ID: {case_id}")
                st.write(f"Image: {case_data.get('image', {}).get('name', 'Unknown')}")
                st.write(f"Date: {case_data.get('timestamp', 'Unknown')[:19]}")
                
                # Display user info if available
                if "user" in case_data and case_data["user"]:
                    st.write(f"Created by: {case_data['user']}")
                
                # Create columns for image and report
                col1, col2 = st.columns(2)
                
                with col1:
                    # Display the image
                    st.subheader("X-ray Image")
                    image_path = os.path.join(
                        settings.ROOT_PATH,
                        "storage", 
                        case_data.get("image", {}).get("path", "")
                    )
                    
                    if os.path.exists(image_path):
                        st.image(image_path)
                    else:
                        st.error(f"Image file not found: {image_path}")
                    
                    # Display predictions as dataframe
                    st.subheader("AI Predictions")
                    predictions = case_data.get("predictions", [])
                    if predictions:
                        df = pd.DataFrame(predictions)
                        st.dataframe(df)
                    else:
                        st.info("No predictions available")
                
                with col2:
                    # Display report
                    st.subheader("Generated AI Report")
                    report_content = case_data.get("report", {}).get("content", "")
                    st.markdown(report_content)
                    
                    # Add verification options
                    st.subheader("Verification")
                    
                    # Show current verification status if it exists
                    if "verification" in case_data:
                        status = case_data["verification"].get("status", "pending")
                        timestamp = case_data["verification"].get("timestamp", "")
                        verified_by = case_data["verification"].get("verified_by", "")
                        
                        if timestamp:
                            timestamp = timestamp[:19]
                        
                        if status == "verified":
                            st.success(f"✓ Verified on {timestamp} by {verified_by or 'unknown'}")
                        elif status == "flagged":
                            reason = case_data["verification"].get("reason", "No reason provided")
                            st.warning(f"⚠ Flagged for review on {timestamp} by {verified_by or 'unknown'}: {reason}")
                        else:
                            st.info("Pending verification")
                    
                    # Check if user has permission to verify
                    can_verify = st.session_state.user_role.get("can_verify", False)
                    
                    if can_verify:
                        # Create verification buttons
                        verification_col1, verification_col2 = st.columns(2)
                        
                        with verification_col1:
                            if st.button("Mark as Correct", key=f"correct_{case_id}"):
                                # Call the verify API endpoint
                                response = make_authenticated_request(
                                    f"{settings.API_URL}/api/cases/{case_id}/verify",
                                    method="POST",
                                    params={"status": "verified"}
                                )
                                
                                if response.status_code == 200 and response.json().get("success", False):
                                    st.success("Report marked as correct")
                                    time.sleep(1)  # Brief pause to show success message
                                    st.rerun()  # Refresh to show updated status
                                else:
                                    error_msg = response.json().get("error", "Unknown error")
                                    st.error(f"Failed to mark as correct: {error_msg}")
                        
                        with verification_col2:
                            # Toggle flagging mode
                            if not st.session_state.flagging_mode:
                                if st.button("Flag for Review", key=f"flag_{case_id}"):
                                    st.session_state.flagging_mode = True
                                    st.rerun()
                            else:
                                if st.button("Cancel Flagging", key=f"cancel_{case_id}"):
                                    st.session_state.flagging_mode = False
                                    st.rerun()
                        
                        # Show flagging interface when in flagging mode
                        if st.session_state.flagging_mode:
                            st.write("Please provide a reason for flagging this report:")
                            reason = st.text_area(
                                "Reason for flagging",
                                key=f"reason_{case_id}",
                                placeholder="Please explain why this report needs review"
                            )
                            
                            submit_col1, submit_col2 = st.columns([1, 3])
                            with submit_col1:
                                if st.button("Submit Flag", key=f"submit_{case_id}"):
                                    if reason.strip():
                                        # Call the verify API endpoint with reason
                                        response = make_authenticated_request(
                                            f"{settings.API_URL}/api/cases/{case_id}/verify",
                                            method="POST",
                                            params={"status": "flagged", "reason": reason}
                                        )
                                        
                                        if response.status_code == 200 and response.json().get("success", False):
                                            st.session_state.flagging_mode = False
                                            st.warning("Report flagged for review")
                                            time.sleep(1)  # Brief pause to show success message
                                            st.rerun()  # Refresh to show updated status
                                        else:
                                            error_msg = response.json().get("error", "Unknown error")
                                            st.error(f"Failed to flag for review: {error_msg}")
                                    else:
                                        st.error("Please provide a reason for flagging")
                    else:
                        st.info("You don't have permission to verify reports")

            else:
                st.error(f"Failed to fetch case details: {data.get('error', 'Unknown error')}")
        else:
            st.error(f"Failed to fetch case: {response.status_code}")
    except Exception as e:
        st.error(f"Error loading case details: {exception_message(e)}")
        logging.error(f"[APP] Error loading case details: {exception_message(e)}")

# --- Helper Functions ---

def can_submit() -> bool:
    """
    Check if enough time has passed since the last submission to prevent spam.
    
    Returns:
        True if submission is allowed, False otherwise
    """
    current_time = time.time()
    last_submit_time = st.session_state.get('last_submit_time', 0)
    cooldown_period = 10  # 10 seconds cooldown
    
    if current_time - last_submit_time >= cooldown_period:
        st.session_state['last_submit_time'] = current_time
        return True
    
    remaining_time = cooldown_period - (current_time - last_submit_time)
    st.warning(f"Please wait {remaining_time:.1f} seconds before submitting again.")
    logging.warning(f"[APP] Submission blocked; cooldown period: {remaining_time:.1f}s remaining")
    return False

# --- Main App Logic ---
def main():
    """Main application entry point"""
    # Only show navigation sidebar if authenticated
    if st.session_state.authenticated:
        # Add sidebar navigation
        st.sidebar.title("Navigation")
        
        # Navigation buttons
        if st.sidebar.button("Home", key="nav_home"):
            change_page("main")
            
        if st.sidebar.button("Case History", key="nav_history"):
            change_page("case_history")
    
    # Display the current page based on session state
    if st.session_state.page == "login":
        login_page()
    elif st.session_state.page == "main":
        main_page()
    elif st.session_state.page == "case_history":
        case_history_page()
    elif st.session_state.page == "case_details":
        case_details_page()

# Run the application
if __name__ == "__main__":
    main()