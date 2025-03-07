import logging
from openai import OpenAI
import json
from typing import Union
from fastapi import FastAPI, HTTPException, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.middleware.exception import exception_message
from app.middleware.logger import setup_logger
from app.services.ai_model import extract_features, get_predictions
from app.services.report_generator import generate_complete_report
from app.services.file_service import read_upload_file, save_report

setup_logger()
client = OpenAI(api_key=settings.OPENAI_API_KEY)

app = FastAPI()

# CORS middleware setup to allow requests from specified origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost"],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*']
)

# Replace the /process_image/ endpoint implementation
@app.post("/process_image/")
async def process_image(file: UploadFile = File(...)) -> dict:
    """
    Process a CXR image directly, extracting features and generating analysis.
    
    Args:
        file: The uploaded CXR image file
        
    Returns:
        JSON response with analysis results
    """
    try:
        # Use file service to read and validate the uploaded file
        image_content = await read_upload_file(file)
        logging.info(f"Received image: {file.filename}, size: {len(image_content)} bytes")
        
        # Extract features using the AI model service
        features = await extract_features(image_content)
        logging.info(f"Features extracted successfully: {len(features)} dimensions")
        
        # Get predictions based on the features
        predictions = await get_predictions(features)
        logging.info(f"Predictions generated successfully: {len(predictions)} items")
        
        # Generate the report from predictions
        predictions_json = json.dumps(predictions)
        response = await generate_complete_report(predictions_json)
        logging.info("Report generated successfully")

        if response is None:
            raise HTTPException(status_code=500, detail="Failed to get response from ChatGPT API")
        
        # Use file service to save the report
        save_report(file.filename, response)

        return response
    
    except ValueError as e:
        # Handle validation errors
        logging.error(f"Validation error: {exception_message(e)}")
        raise HTTPException(status_code=400, detail=exception_message(e))
    except Exception as e:
        logging.error(exception_message(e))
        raise HTTPException(status_code=500, detail=f"Image processing failed: {exception_message(e)}")

@app.post("/extract_features/")
async def extract_features_endpoint(file: UploadFile = File(...)) -> dict:
    """
    Extract features from a CXR image without generating a full report.
    
    Args:
        file: The uploaded CXR image file
        
    Returns:
        JSON with the extracted feature vector
    """
    try:
        image_content = await file.read()
        features = await extract_features(image_content)
        return {"features": features, "dimensions": len(features)}
    except Exception as e:
        logging.error(exception_message(e))
        raise HTTPException(status_code=500, detail=f"Feature extraction failed: {exception_message(e)}")

@app.post("/generate_from_features/")
async def generate_from_features(features: list) -> dict:
    """
    Generate a report from a feature vector.
    
    Args:
        features: The feature vector extracted from a CXR image
        
    Returns:
        JSON with the generated report
    """
    try:
        predictions = await get_predictions(features)
        predictions_json = json.dumps(predictions)
        
        # Generate the report using the new service
        response = await generate_complete_report(predictions_json)
        
        if response is None:
            raise HTTPException(status_code=500, detail="Failed to get response from ChatGPT API")
        
        return response
    except Exception as e:
        logging.error(exception_message(e))
        raise HTTPException(status_code=500, detail=f"Report generation failed: {exception_message(e)}")

@app.post("/upload_csv/")
async def upload_csv(data: dict) -> Union[dict, str]:
    """Process JSON data from CSV and generate a report (legacy endpoint)"""
    # Keep your existing implementation, but perhaps add a deprecation warning in logs
    logging.info("Using legacy CSV upload endpoint")

    try:
        json_data = data['data']
        logging.info(f"Received file size: {len(json_data)} bytes")
        
        # Generate the report using the new service
        response = await generate_complete_report(json_data)
        
        if response is None:
            raise HTTPException(status_code=500, detail="Failed to get response from ChatGPT API")
        
        return response
    except Exception as e:
        logging.error(exception_message(e))
        raise HTTPException(status_code=500, detail=f"An error occurred while processing the file: {exception_message(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=7890,
        reload=True,
    )

    # import subprocess
    # import time

    # # Start FastAPI
    # fastapi_process = subprocess.Popen([
    #     "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "7890", "--reload"
    # ])

    # # Start Streamlit
    # streamlit_process = subprocess.Popen([
    #     "streamlit", "run", "app/app.py"
    # ])

    # # Keep the script running
    # try:
    #     while True:
    #         time.sleep(2)
    # except KeyboardInterrupt:
    #     fastapi_process.terminate()
    #     streamlit_process.terminate()