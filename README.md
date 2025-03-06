# Demo Web App

[English](./README.md)    [中文](README_ZH.md)

This application allows users to submit a Linear Probe Result, analyzed through the [AI Model Website](https://aiotplatform.ndmctsgh.edu.tw/service-website). It automatically generates a corresponding CXR report, which users can copy, download, or print.

## Usage

### Step 1: Clone the Project

Clone this project to your local machine:

```bash
git clone <YOUR_CLONED_URL>
```

For example:

```bash
git clone https://github.com/shin13/AI-generated-CXR-report-assistant.git
```

If you need to specify a directory, add a path parameter:

```bash
git clone https://github.com/shin13/AI-generated-CXR-report-assistant.git <YOUR_FOLDER_NAME>
```

### Step 2: Install Required Packages

Install the necessary packages:

```bash
pip install -r requirements.txt
```

### Step 3: Set Up Environment Variables

Create a `.env` file and set the following environment variables:

- `AI_MODEL_URL`: URL of the AI model (OpenAI or DeepSeek)
- `API_KEY`: API key for the AI model (OpenAI or DeepSeek)
- `MODEL_NAME`: Name of the model (e.g., GPT-3, DeepSeek)

### Step 4: Launch the Application

Start the application:

```bash
python main.py
```

This will start the FastAPI and Streamlit applications.

### Step 5: Generate the AI Report

Select an example file and click the submit button to generate the AI report.
