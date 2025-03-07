# ./app/app.py
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Streamlit frontend for the AI-Powered CXR Report Generator.
This application allows users to upload chest X-ray images or CSV files
and generates structured radiological reports using AI.
"""

import json
import time
import logging
import asyncio

import streamlit as st
import aiohttp

# Use absolute imports to ensure consistency
from app.config import settings
from app.middleware.exception import exception_message
from app.middleware.logger import setup_logger
# Import services
from app.services.file_service import (
    read_upload_file, 
    validate_image_file,
    save_report,
    get_recent_reports
)

# Set up logging for debugging and monitoring
setup_logger()

# Configure the Streamlit page layout and title
st.set_page_config(
    page_title='AI-Powered CXR Report Generator',
    page_icon='🩻',
    layout='wide'
)

st.html("<h1 style='text-align: center;'>AI-Powered CXR Report Generator</h1>")

# Initialize session state variables for state management
if 'reset_counter' not in st.session_state:
    st.session_state.reset_counter = 0
if 'response_content' not in st.session_state:
    st.session_state.response_content = None
if 'last_submit_time' not in st.session_state:
    st.session_state.last_submit_time = 0

# --- Backend API Communication Functions ---

async def process_image_via_backend(image_content: bytes, filename: str) -> str:
    """
    Send image directly to the backend process_image endpoint to generate a report.
    
    Args:
        image_content: Raw image bytes
        filename: Original filename for logging
        
    Returns:
        Generated report content
        
    Raises:
        Exception: If processing fails
    """
    try:
        logging.info(f"[APP] Sending image to backend: {filename} ({len(image_content)} bytes)")
        
        async with aiohttp.ClientSession() as session:
            # Prepare the form data with the image file
            form = aiohttp.FormData()
            form.add_field('file', image_content, filename=filename, content_type='image/jpeg')
            
            # Send to the backend's process_image endpoint
            async with session.post(f"{settings.BACKEND_URL}/process_image/", data=form) as response:
                logging.info(f"[APP] Backend response status: {response.status}")
                
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"Backend processing failed: {response.status} - {error_text}")
                
                # Parse the response
                response_data = await response.json()
                logging.debug(f"[APP] Response data: {response_data[:200]}...")
                
                # The response is a JSON string, so we need to parse it
                response_obj = json.loads(response_data)
                report_content = response_obj["choices"][0]["message"]["content"]
                logging.info(f"[APP] Report content received: {len(report_content)} characters")
                
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
        async def async_process():
            # Process image file
            if image_file:
                with st.spinner("Processing image..."):
                    # Read the image content
                    image_content = await read_upload_file(image_file)
                    
                    # Validate it's a proper image
                    validate_image_file(image_file.name, image_content)
                    
                    # Process via backend
                    report_content = await process_image_via_backend(image_content, image_file.name)
                    return report_content
            else:
                raise ValueError("No image file provided for processing")

        # Run the async function and return results
        return asyncio.run(async_process())
    except ValueError as e:
        # Handle validation errors
        error_msg = f"Invalid input: {exception_message(e)}"
        logging.error(f"[APP] {error_msg}")
        raise Exception(error_msg)
    except Exception as e:
        # Handle all other errors
        logging.error(f"[APP] Error in process_and_generate_report: {exception_message(e)}")
        raise

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

# --- Main Layout ---

col_introduction, col_upload, col_report = st.columns(3)

with col_introduction:
    st.markdown("### Instruction")
    with st.expander("📖 User Guide / 使用說明"):
        tab_english, tab_chinese = st.tabs(["English (EN)", "中文 (ZH)"])
        
        with tab_english:
            st.write("""
            **Welcome to the Chest X-ray Report AI Assistant:**

            - **Step 1:** Upload your CXR image (JPG).

            - **Step 2:** Click "Submit" to get the report draft.

            - **Step 3:** See the report draft in the "Report" section.

            - **Feedback:** If the report draft is wrong:
            - Keep the CXR image.
            - Save the report result.
            - Exaplain the error.
            - Send everything to the developer to fix the issue.

            **Important:**
            - Wait patiently for the analysis.
            - The image should be a clear chest X-ray in JPG format.
            """)
        
        with tab_chinese:
            st.write("""                  
            **歡迎使用胸部 X 光報告 AI 助理：**
            
            - **步驟 1：**上傳您的 CXR 影像 (JPG)。

            - **步驟2：**點選「Submit」以取得報告草稿。

            - **步驟 3：**查看「Report」部分的報告草稿。

            - **回饋**：如果報告草稿有誤：
            - 保留 CXR 影像。
            - 儲存報告結果。
            - 提供錯誤說明。
            - 將所有內容傳送給開發人員以解決問題。

            **重要提示：**
            - 耐心等待分析。
            - 影像應為 JPG 格式的清晰胸部 X 光片。
            """)

with col_upload:
    st.markdown("### Upload Data")
    st.write("Please select a method to upload data:")
    
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
        if st.button("Submit"):
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
        if st.button("Clear"):
            st.session_state.reset_counter += 1
            st.session_state.response_content = None
            logging.info("[APP] Cleared uploaded data and report.")
            st.experimental_rerun()
       
with col_report:
    st.markdown("### Report (draft)")
    
    # Display current report
    if st.session_state.response_content:
        logging.info(f"[APP] Displaying report ({len(st.session_state.response_content)} chars)")
        tab_markdown, tab_text = st.tabs(["Markdown", "Text"])
        
        with tab_markdown:
            st.markdown(st.session_state.response_content)
        
        with tab_text:
            st.text_area("Generated Report", st.session_state.response_content, height=300)
    
    # Add section for recent reports
    with st.expander("Recent Reports"):
        try:
            recent_reports = get_recent_reports(limit=5)
            if recent_reports:
                for idx, report in enumerate(recent_reports):
                    report_date = report.get('created_at_str', 'Unknown date')
                    report_name = report.get('data_name', 'Unknown file')
                    
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.markdown(f"**{idx+1}. {report_name}**")
                        st.caption(f"Created: {report_date}")
                    
                    with col2:
                        if st.button("View", key=f"view_report_{idx}"):
                            st.session_state.response_content = report.get('report_content', '')
                            st.experimental_rerun()
                    
                    st.divider()
            else:
                st.write("No previous reports found.")
        except Exception as e:
            st.write(f"Could not load recent reports: {exception_message(e)}")
            logging.error(f"[APP] Error loading recent reports: {exception_message(e)}")
