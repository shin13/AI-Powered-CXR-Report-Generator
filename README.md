# AI-Powered CXR Report Generator

[English](./README.md) | [中文](README_ZH.md)

A web application that automatically generates structured radiological reports from chest X-ray (CXR) images using AI analysis. The application provides a simple interface for uploading images and receiving detailed, medically accurate reports.

## Features

- **Direct Image Analysis**: Upload chest X-ray images in JPG/JPEG format for immediate processing
- **AI-Powered Report Generation**: Advanced AI models analyze images and generate structured reports
- **Medical Terminology**: Reports use standard radiological terminology and formatting
- **Save & Export**: Save generated reports for future reference
- **Responsive Design**: User-friendly interface that works on desktop and tablet devices

## Getting Started

### Prerequisites

- Python 3.8 or higher
- pip (Python package installer)

### Installation

1. **Clone the Repository**

   ```bash
   git clone https://github.com/shin13/AI-Powered-CXR-Report-Generator.git
   cd AI-Powered-CXR-Report-Generator
   ```

2. **Install Required Packages**

   ```bash
   pip install -r requirements.txt
   ```

3. **Configure Environment Variables**

   Create a `.env` file in the project root with the following variables:

   ```bash
   # API Settings
   OPENAI_API_KEY=your-openai-key-here
   CHATGPT_MODEL=gpt-4o-mini
   
   # Backend Settings
   BACKEND_URL=http://localhost:7890
   
   # AI Service Settings
   BASE_URL_AI=https://your-ai-service-url.com/api
   CXR_FEATURES_ENDPOINT=/v1/cxr/features
   CXR_LINEAR_PROBE_ENDPOINT=/v1/cxr/linear-probe
   AUTH_USERNAME=your_username
   AUTH_PASSWORD=your_password
   ```

### Running the Application

Launch the application with a single command:

```bash
python main.py
```

This will start both the FastAPI backend server and the Streamlit frontend application. The application will be accessible at:

- **Frontend**: http://localhost:8501
- **Backend API**: http://localhost:7890

## Usage Guide

1. **Access the Application**
   - Open your browser and navigate to http://localhost:8501

2. **Upload an Image**
   - Click the "Upload your CXR image file (jpg)" button
   - Select a valid chest X-ray image from your device

3. **Generate Report**
   - Click the "Submit" button to process the image
   - Wait for the AI to analyze the image and generate a report

4. **View and Save Report**
   - The generated report will appear in the "Report (draft)" section
   - View the report in Markdown or Text format
   - Previous reports can be accessed through the "Recent Reports" dropdown

## Project Structure

```bash
AI-Powered-CXR-Report-Generator/
├── app/                    # Frontend and service components
│   ├── app.py              # Streamlit frontend application
│   ├── config.py           # Configuration settings
│   ├── data/               # Data and model information
│   ├── middleware/         # Error handling and logging
│   ├── services/           # Service layer components
│   └── static/             # Static assets
├── logs/                   # Application logs
├── reports/                # Generated reports
├── main.py                 # FastAPI backend application
├── requirements.txt        # Python dependencies
└── README.md               # Project documentation
```

## License

[MIT License](LICENSE)

## Acknowledgments

- This project uses the OpenAI API for language processing
- Streamlit and FastAPI for the application framework