# AI-Powered CXR Report Generator

[English](./README.md) | [中文](README_ZH.md)

A web application that analyzes chest X-ray (CXR) images and generates structured radiological reports.

## Features

- Upload and analyze chest X-ray images
- Generate structured radiological reports using AI
- Store and manage case histories
- Review and verify generated reports

## Architecture

The project follows a three-tier architecture:

- **Frontend**: Streamlit application for user interface
- **Backend**: FastAPI application for processing and API endpoints
- **Services**: Core business logic components

## Setup Instructions

### Prerequisites

- Python 3.8+
- pip
- Virtual environment (recommended)

### Installation

1. Clone the repository:
   ```
   git clone https://github.com/shin13/AI-Powered-CXR-Report-Generator.git
   cd AI-Powered-CXR-Report-Generator
   ```

2. Create and activate a virtual environment:
   ```
   python -m venv .venv
   source .venv/bin/activate  
   # On Windows, use .venv\Scripts\activate
   ```

3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

4. Configure environment variables:
   ```
   cp .env.example .env
   # Edit .env file with your configuration
   ```

### Running the Application

1. Start the Backend API:
   ```
   python main.py
   ```

2. Start the Frontend (in a new terminal):
   ```
   cd app
   streamlit run app.py
   ```

## Usage

1. Open your browser and navigate to http://localhost:8501
2. Log in using the configured credentials
3. Upload a chest X-ray image
4. Click "Submit" to analyze the image and generate a report
5. View the generated report

## API Documentation

The API documentation is available at http://localhost:7890/docs when the backend is running.

## Development

### Project Structure

```bash
/
├── app/                  # Application code
│   ├── config/           # Configuration files
│   ├── middleware/       # Middleware components
│   ├── services/         # Core business logic
│   └── app.py            # Streamlit frontend
├── main.py               # FastAPI backend
├── tests/                # Tests
├── storage/              # Data storage
├── reports/              # Generated reports
└── examples/             # Example files
```

### Running Tests

```bash
pytest tests/
```

## License

[MIT License](LICENSE)

## Acknowledgments

- This project uses the OpenAI API for language processing
- Streamlit and FastAPI for the application framework