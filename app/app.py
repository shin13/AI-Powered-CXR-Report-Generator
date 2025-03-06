# ./app/app.py
import os
import json
import time
import logging
import datetime
from io import StringIO, BytesIO

import streamlit as st
import pandas as pd
import aiohttp
import asyncio
from icecream import ic

from config import settings
from middleware.exception import exception_message
from middleware.logger import setup_logger


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

# --- Asynchronous Functions ---

async def get_image_features(image_bytes: bytes) -> dict:
    """Send image to CXR_FEATURES_URL and return a 512-dimensional feature array."""
    async with aiohttp.ClientSession() as session:
        form = aiohttp.FormData()
        form.add_field('file', image_bytes, filename='image.jpg', content_type='image/jpeg')
        async with session.post(settings.CXR_FEATURES_URL, data=form) as response:
            if response.status == 200:
                features = await response.json()
                logging.info(f"[APP] Features retrieved: {len(features)} dimensions")
                logging.info(f"[APP] Features: \n{features}")
                return features
            else:
                error_msg = f"Failed to get features: {response.status}"
                logging.error(f"[APP] {error_msg}")
                raise Exception(error_msg)

async def get_image_analysis(features: dict) -> dict:
    """Send feature array to CXR_AI_MODEL_URL and return JSON analysis result."""
    async with aiohttp.ClientSession() as session:
        async with session.post(settings.CXR_AI_MODEL_URL, json=features) as response:
            logging.info(f"[APP] Analysis response: {response.text}")
            if response.status == 200:
                analysis = await response.json()
                logging.info(f"[APP] Analysis result: {analysis}")
                return analysis
            else:
                error_msg = f"Failed to get analysis: {response.status}"
                logging.error(f"[APP] {error_msg}")
                raise Exception(error_msg)

async def generate_report(json_data: str) -> str:
    """Send JSON data to the backend API and retrieve the generated report."""
    async with aiohttp.ClientSession() as session:
        payload = {'data': json_data}
        async with session.post(settings.BACKEND_URL, json=payload) as response:
            logging.info(f"[APP] Response from backend API: {response}")
            if response.status == 200:
                response_data = await response.json()
                logging.info(f"[APP] Response data (STRING): {response_data}")
                response_data = json.loads(response_data)
                logging.info(f"[APP] Response data (JSON): {response_data}")
                report_content = response_data["choices"][0]["message"]["content"]
                logging.info(f"[APP] Report content: {report_content}")
                return report_content
            else:
                error_detail = await response.text()
                error_msg = f"Failed to generate report: {response.status} - {error_detail}"
                logging.error(f"[APP] {error_msg}")
                raise Exception(error_msg)

# --- Synchronous Wrapper Function ---

def process_and_generate_report(image_file=None, csv_file=None) -> str:
    """
    Process an image or CSV file and generate a report asynchronously.
    Handles both image (via feature extraction and analysis) and CSV inputs.
    """
    try:
        async def async_process():
            if image_file:
                with st.spinner("Processing image..."):
                    image_bytes = image_file.read()
                    features = await get_image_features(image_bytes)
                    analysis = await get_image_analysis(features)
                    json_data = json.dumps(analysis)  # Convert analysis JSON to string
            elif csv_file:
                bytes_data = csv_file.read()
                df = pd.read_csv(BytesIO(bytes_data))
                json_data = json.dumps(df.to_dict('records'))
            else:
                raise ValueError("No file provided")

            with st.spinner("Generating report..."):
                report_content = await generate_report(json_data)
            return report_content

        return asyncio.run(async_process())
    except Exception as e:
        logging.error(f"[APP] Error in process_and_generate_report: {exception_message(e)}")
        raise

# --- Helper Functions ---

def preview_and_process(file, file_label) -> dict:
    """Preview the uploaded CSV file and convert it to JSON for API processing."""
    logging.info(f"[APP] Processing file_label: \n{file_label}")
    logging.info(f"[APP] File Type: {type(file)}")
    logging.info(f"[APP] File: \n{file}")
    st.write(f"Preview of {file_label}:")
    try:
        bytes_data = file.read()
        df = pd.read_csv(StringIO(bytes_data.decode("utf-8")))
        st.write(f"File size: {len(bytes_data)} bytes")
        st.write(f"File length: {len(df)} rows")
        st.write(df.head())
        logging.info(f"Dict of dataframe: \n{df.to_dict('records')}")
        json_data = json.dumps(df.to_dict('records'))  # Convert to list of dictionaries
        logging.info(f"[APP] Converted JSON data: \n{json_data}")
        return json_data
    except Exception as e:
        st.write(f"Unable to show file content or data table: {e}")
        logging.error(f"[APP] Error processing file: \n{exception_message(e)}")
        return None  

def can_submit() -> bool:
    """Check if enough time has passed since the last submission to prevent spam."""
    current_time = time.time()
    last_submit_time = st.session_state.get('last_submit_time', 0)
    cooldown_period = 10  # 10 seconds cooldown
    if current_time - last_submit_time >= cooldown_period:
        st.session_state['last_submit_time'] = current_time
        return True
    remaining_time = cooldown_period - (current_time - last_submit_time)
    st.warning(f"Please wait {remaining_time:.1f} seconds before submitting again.")
    logging.warning(f"[APP] Submission blocked; last submit was {last_submit_time:.1f}s ago.")
    return False

def save_report(data_name: str, report_content: str) -> None:
    """Save the report content, data name, and timestamp to a JSON file."""
    now = datetime.datetime.now()
    timestamp_now = int(now.timestamp())
    formatted_time = now.strftime('%Y%m%d%H%M%S')
    report_data = {
        "data_name": data_name,
        "report_content": report_content,
        "created_at": timestamp_now,
        "created_at_str": now.strftime('%Y-%m-%d %H:%M:%S')
    }

    os.makedirs("reports", exist_ok=True)
    filename = f"reports/report_{formatted_time}.json"
    with open(filename, "w") as f:
        json.dump(report_data, f, indent=4)

    path = "reports/reports.json"
    reports_list = []
    if os.path.exists(path):
        with open(path, "r") as f:
            try:
                reports_list = json.load(f)
                if not isinstance(reports_list, list):
                    reports_list = [reports_list]
            except json.JSONDecodeError:
                reports_list = []
    reports_list.append(report_data)
    with open(path, "w") as f:
        json.dump(reports_list, f, indent=4)
    logging.info(f"[APP] Report saved to both {path} and {filename}")

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
        type=["jpg"],
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
    elif uploaded_file:
        data_name = uploaded_file.name
        json_data = preview_and_process(uploaded_file, uploaded_file.name)
    elif selected_example:
        data_name = selected_example
        with open(example_files[selected_example], "rb") as example_file:
            json_data = preview_and_process(example_file, selected_example)

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
                        st.session_state.response_content = report_content
                        if report_content:
                            save_report(data_name, report_content)
                    except Exception as e:
                        st.error(f"An error occurred: {e}")
                        logging.error(f"[APP] Error during processing: {exception_message(e)}")
                else:
                    st.warning("Please upload or select a file.")
    with col_clear:
        if st.button("Clear"):
            st.session_state.reset_counter += 1
            st.session_state.response_content = None
            logging.info("[APP] Cleared uploaded data and report.")
       
with col_report:
    st.markdown("### Report (draft)")
    if st.session_state.response_content:
        logging.info(f"[APP] Displaying report: {st.session_state.response_content}")
        tab_markdown, tab_text = st.tabs(["Markdown", "Text"])
        with tab_markdown:
            st.markdown(st.session_state.response_content)
        with tab_text:
            st.text_area("Generated Report", st.session_state.response_content, height=300)
