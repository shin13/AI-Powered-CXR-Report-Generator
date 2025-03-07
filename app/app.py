# ./app/app.py
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Streamlit frontend for the AI-Powered CXR Report Generator.
This application allows users to upload chest X-ray images or CSV files
and generates structured radiological reports using AI.
"""

import os
import json
import time
import logging
import asyncio
from typing import Optional

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
    parse_csv_to_dataframe, 
    dataframe_to_json,
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

# Define paths to local example CSV files
example_files = {
    "Example 1": "app/data/[2024-12-27T08-58-10.869213] - 02054TSGH.csv",
    "Example 2": "app/data/[2024-12-27T08-58-11.574219] - 02056TSGH.csv",
    "Example 3": "app/data/[2024-12-27T08-58-15.908073] - 02057TSGH.csv",
    "Example 4": "app/data/[2024-12-27T08-58-18.146607] - 02058TSGH.csv",
    "Example 5": "app/data/[2024-12-27T08-58-03.829726] - 02059TSGH.csv",
}

# Validate existence of example files and notify user of missing ones
missing_files = [name for name, path in example_files.items() if not os.path.exists(path)]
if missing_files:
    st.warning(f"The following example files were not found: {', '.join(missing_files)}")

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
    
async def process_csv_via_backend(json_data: str) -> str:
    """
    Send CSV data as JSON to the backend to generate a report.
    
    Args:
        json_data: JSON string representation of the CSV data
        
    Returns:
        Generated report content
        
    Raises:
        Exception: If processing fails
    """
    try:
        logging.info(f"[APP] Sending JSON data to backend: {len(json_data)} bytes")
        
        async with aiohttp.ClientSession() as session:
            # Prepare the payload with the JSON data
            payload = {'data': json_data}
            
            # Send to the backend's upload_csv endpoint
            async with session.post(f"{settings.BACKEND_URL}/upload_csv/", json=payload) as response:
                logging.info(f"[APP] Backend response status: {response.status}")
                
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"Backend processing failed: {response.status} - {error_text}")
                
                # Parse the response
                response_data = await response.json()
                logging.debug(f"[APP] Response data type: {type(response_data)}")
                
                # The response is a JSON string, so we need to parse it
                if isinstance(response_data, str):
                    response_obj = json.loads(response_data)
                    report_content = response_obj["choices"][0]["message"]["content"]
                else:
                    report_content = response_data["choices"][0]["message"]["content"]
                
                logging.info(f"[APP] Report content received: {len(report_content)} characters")
                return report_content
    except aiohttp.ClientError as e:
        error_msg = f"Communication error with backend: {exception_message(e)}"
        logging.error(f"[APP] {error_msg}")
        raise Exception(error_msg)
    except Exception as e:
        error_msg = f"Error processing CSV data via backend: {exception_message(e)}"
        logging.error(f"[APP] {error_msg}")
        raise Exception(error_msg)

# --- Synchronous Processing Function ---

def process_and_generate_report(image_file=None, csv_file=None) -> str:
    """
    Process an image or CSV file and generate a report using the backend API.
    
    Args:
        image_file: Streamlit UploadFile for image
        csv_file: Streamlit UploadFile for CSV
        
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
            
            # Process CSV file
            elif csv_file:
                with st.spinner("Processing CSV..."):
                    # Read the CSV content
                    file_content = await read_upload_file(csv_file)
                    
                    # Parse to DataFrame and convert to JSON
                    df = parse_csv_to_dataframe(file_content)
                    json_data = dataframe_to_json(df)
                    
                    # Process via backend
                    report_content = await process_csv_via_backend(json_data)
                    return report_content
            else:
                raise ValueError("No file provided for processing")

        # Run the async function and return results
        return asyncio.run(async_process())
    except ValueError as e:
        # Handle validation errors
        error_msg = f"Invalid input: {exception_message(e)}"
        logging.error(f"[APP] {error_msg}")
        raise Exception(error_msg)
    except IOError as e:
        # Handle file errors
        error_msg = f"File operation failed: {exception_message(e)}"
        logging.error(f"[APP] {error_msg}")
        raise Exception(error_msg)
    except Exception as e:
        # Handle all other errors
        logging.error(f"[APP] Error in process_and_generate_report: {exception_message(e)}")
        raise

# --- Helper Functions ---

def preview_and_process_csv(file, file_label) -> Optional[str]:
    """
    Preview the uploaded CSV file and convert it to JSON for API processing.
    
    Args:
        file: File object (either UploadFile or file handle)
        file_label: Label for display purposes
        
    Returns:
        JSON string representation of the CSV data or None if processing fails
    """
    logging.info(f"[APP] Processing CSV file: {file_label}")
    st.write(f"Preview of {file_label}:")
    
    try:
        # Read file content
        if hasattr(file, 'read'):
            # For file-like objects
            file_content = file.read()
        else:
            # For UploadFile objects
            file_content = asyncio.run(read_upload_file(file))
        
        # Parse CSV to DataFrame
        df = parse_csv_to_dataframe(file_content)
        
        # Display preview
        st.write(f"File size: {len(file_content)} bytes")
        st.write(f"File length: {len(df)} rows")
        st.write(df.head())
        
        # Convert to JSON for API
        json_data = dataframe_to_json(df)
        logging.info(f"[APP] Converted JSON data size: {len(json_data)} bytes")
        
        return json_data
    except ValueError as e:
        st.error(f"Invalid CSV format: {exception_message(e)}")
        logging.error(f"[APP] CSV validation error: {exception_message(e)}")
        return None
    except Exception as e:
        st.error(f"Unable to process CSV file: {exception_message(e)}")
        logging.error(f"[APP] Error processing CSV file: {exception_message(e)}")
        return None

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

            - **Step 1:** Choose one option:
              - Upload your CXR image (JPG).
              - Upload your features CSV file.
              - Use an example features CSV.

            - **Step 2:** Click "Submit" to get the report draft.

            - **Step 3:** See the report draft in the "Report" section.

            - **Feedback:** If the report draft is wrong:
              - Keep the CXR image.
              - Save the report result.
              - Write an explanation.
              - Send everything to the developer to fix the issue.

            **Important:**
            - Wait patiently for the analysis.
            - Check that your CSV file fits the required format.
            
            **How to Get your CXR feature CSV file:**                   
            - Visit [Chest X-ray AI Analysis](https://aiotplatform.ndmctsgh.edu.tw/service-website) to obtain a linear probe result in CSV format.
            - Follow the [tutorial video](https://youtu.be/hTR3bbbA7-k?si=tgYsrgztebn-hS1X) for guidance.
            - Download the linear probe result in CSV format.             
            """)
            st.markdown("**Visual Guides:**")
            st.write("**Download your CSV file**")
            st.image("app/static/download.png", caption="CSV Download Location", use_container_width=True)
            st.write("**Required CSV Format**")
            st.image("app/static/example csv.png", caption="Example CSV preview", use_container_width=True)
        
        with tab_chinese:
            st.write("""
            **歡迎使用胸腔X光報告AI助手：**
                     
            - **步驟1：** 選擇一個選項：
              - 上傳您的CXR圖像（JPG）。
              - 上傳您的CSV檔案。
              - 使用範例CSV。

            - **步驟2：** 點擊「Submit」生成AI報告草稿。

            - **步驟3：** 在「Report」部分查看AI報告草稿。

            - **回饋：** 如果AI報告草稿有誤：
              - 保留CXR圖像。
              - 保存報告結果。
              - 寫下解釋。
              - 將所有內容發送給開發人員以改進。

            **重要：**
            - 請耐心等待分析完成。
            - 確保CSV檔案符合所需格式。

            - **如何取得您的CXR的特徵CSV檔案：**
              - 訪問 [胸部X光AI分析](https://aiotplatform.ndmctsgh.edu.tw/service-website) 取得胸部X光分析報告檔案（linear probe result in csv format)。
              - 參考 [教學影片](https://youtu.be/hTR3bbbA7-k?si=tgYsrgztebn-hS1X)。
              - 下載 linear probe result in CSV format。
            """)
            st.markdown("**圖片指引：**")
            st.write("**下載CSV檔案**")
            st.image("app/static/download.png", caption="CSV下載位置", use_container_width=True)
            st.write("**需要的CSV檔案格式**")
            st.image("app/static/example csv.png", caption="上傳CSV範例", use_container_width=True)

with col_upload:
    st.markdown("### Upload Data")
    st.write("Please select a method to upload data:")
    
    # Upload options with reset-capable keys
    uploaded_image = st.file_uploader(
        "🩻 Upload your CXR image file (jpg):",
        accept_multiple_files=False,
        type=["jpg", "jpeg"],
        key=f"image_{st.session_state.reset_counter}"
    )
    uploaded_file = st.file_uploader(
        "📤 Upload your report CSV file",
        type=["csv"],
        key=f"csv_{st.session_state.reset_counter}"
    )
    selected_example = st.selectbox(
        "📂 Select an example CSV:",
        [""] + list(example_files.keys()),
        key=f"example_{st.session_state.reset_counter}"
    )

    # Process selected data source
    json_data = None
    data_name = "Unknown"
    
    if uploaded_image:
        data_name = uploaded_image.name
        st.write(f"Selected image: {uploaded_image.name}")
    elif uploaded_file:
        data_name = uploaded_file.name
        json_data = preview_and_process_csv(uploaded_file, uploaded_file.name)
    elif selected_example:
        data_name = selected_example
        try:
            with open(example_files[selected_example], "rb") as example_file:
                json_data = preview_and_process_csv(example_file, selected_example)
        except Exception as e:
            st.error(f"Error loading example file: {exception_message(e)}")
            logging.error(f"[APP] Error loading example file: {exception_message(e)}")

    # Submit and Clear buttons side by side
    col_submit, col_clear = st.columns(2)
    with col_submit:
        if st.button("Submit"):
            if can_submit():
                sources = sum([bool(uploaded_image), bool(uploaded_file), bool(selected_example)])
                if sources > 1:
                    st.error("Please select only one data source.")
                elif uploaded_image or uploaded_file or selected_example:
                    try:
                        if uploaded_image:
                            report_content = process_and_generate_report(image_file=uploaded_image)
                        elif uploaded_file:
                            report_content = process_and_generate_report(csv_file=uploaded_file)
                        elif selected_example:
                            with open(example_files[selected_example], "rb") as example_file:
                                report_content = process_and_generate_report(csv_file=example_file)
                                
                        # Update UI and save report
                        st.session_state.response_content = report_content
                        if report_content:
                            try:
                                # Use file service to save the report
                                individual_path, master_path = save_report(data_name, report_content)
                                st.success("Report saved successfully!")
                                logging.info(f"[APP] Report saved to {individual_path}")
                            except Exception as e:
                                st.warning(f"Report generated but could not be saved: {exception_message(e)}")
                                logging.error(f"[APP] Error saving report: {exception_message(e)}")
                    except Exception as e:
                        st.error(f"An error occurred: {exception_message(e)}")
                        logging.error(f"[APP] Error during processing: {exception_message(e)}")
                else:
                    st.warning("Please upload or select a file.")
    
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
                        if st.button(f"View: view_report_{idx}"):
                            st.session_state.response_content = report.get('report_content', '')
                            st.experimental_rerun()
                    
                    st.divider()
            else:
                st.write("No previous reports found.")
        except Exception as e:
            st.write(f"Could not load recent reports: {exception_message(e)}")
            logging.error(f"[APP] Error loading recent reports: {exception_message(e)}")
