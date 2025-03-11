import logging
from openai import OpenAI
import json
from fastapi import FastAPI, HTTPException, File, UploadFile, Body
from fastapi.middleware.cors import CORSMiddleware
import os

from app.config.config import settings
from app.middleware.exception import exception_message
from app.middleware.logger import setup_logger
from app.services.ai_model import extract_features, get_predictions
from app.services.report_generator import generate_complete_report
from app.services.file_service import save_report
from app.services import file_service

setup_logger()
client = OpenAI(api_key=settings.OPENAI_API_KEY)
app = FastAPI(debug=settings.DEBUG)

# CORS middleware setup to allow requests from specified origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*']
)

@app.post("/process_image_bytes/")
async def process_image_bytes(file_content: str = Body(...), filename: str = Body(...)):
    """
    Process CXR image provided as raw byte, extracting features and generating analysis.
    """
    try:
        # Convert the string back to bytes
        image_bytes = file_content.encode('latin1')
        logging.info(f"Received image bytes: {filename}, size: {len(image_bytes)} bytes")
        
        # Extract features using the AI model service
        features = await extract_features(image_bytes)
        logging.info(f"Features extracted successfully: {len(features)} dimensions")
        
        # Get predictions based on the features
        predictions = await get_predictions(features)
        logging.info(f"Predictions generated successfully: {len(predictions)} items")
        
        # Generate the report from predictions
        predictions_json = json.dumps(predictions)
        logging.info(f"Prediction JSON: {predictions_json}")

        logging.info("Generating report...")
        response = await generate_complete_report(predictions_json)
        logging.info("Report generated successfully")

        if response is None:
            raise HTTPException(status_code=500, detail="Failed to get response from ChatGPT API")

        # Parse the response JSON if it's a string
        if isinstance(response, str):
            try:
                response_dict = json.loads(response)
                report_content = response_dict['choices'][0]['message']['content']
                # Use file service to save the report
                save_report(filename, report_content)
                # Return a proper dictionary response
                return {"status": "success", "report": report_content, "features": features, "predictions": predictions}
            except json.JSONDecodeError as e:
                logging.error(f"JSON parsing error: {exception_message(e)}")
                raise HTTPException(status_code=500, detail=f"Error parsing response: {exception_message(e)}")
        else:
            # Use file service to save the report
            save_report(filename, response)
            return {"status": "success", "report": response, "features": features, "predictions": predictions}
    
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

@app.post("/api/save_case/")
async def save_case(case_data: dict):
    """Save complete case data including image, features, predictions and report"""
    try:
        case_id = file_service.save_case_data(
            image_path=case_data["image_path"],
            image_name=case_data["image_name"],
            features=case_data["features"],
            predictions=case_data["predictions"],
            report_content=case_data["report_content"]
        )
        return {"success": True, "case_id": case_id}
    except Exception as e:
        logging.error(f"Error saving case data: {exception_message(e)}")
        return {"success": False, "error": exception_message(e)}

@app.get("/api/cases/")
async def list_cases(limit: int = 10):
    """List recent cases"""
    try:
        cases = file_service.list_recent_cases(limit=limit)
        return {"success": True, "cases": cases}
    except Exception as e:
        logging.error(f"Error listing cases: {exception_message(e)}")
        return {"success": False, "error": exception_message(e)}

@app.get("/api/cases/{case_id}")
async def get_case(case_id: str):
    """Get case data by ID"""
    try:
        case_data = file_service.get_case_by_id(case_id)
        if case_data is None:
            return {"success": False, "error": "Case not found"}
        return {"success": True, "case_data": case_data}
    except Exception as e:
        logging.error(f"Error retrieving case data: {exception_message(e)}")
        return {"success": False, "error": exception_message(e)}

if __name__ == "__main__":
    import uvicorn
    
    # Log startup information
    logging.info(f"Starting application in {os.getenv('ENVIRONMENT', 'development')} mode")
    logging.info(f"Debug mode: {settings.DEBUG}")
    logging.info(f"Allowed origins: {settings.ALLOWED_ORIGINS}")
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.PORT,
        reload=settings.DEBUG,
    )

@app.post("/api/cases/{case_id}/verify")
async def verify_case(case_id: str, status: str, reason: str = None):
    """Mark a case as verified or flagged for review"""
    try:
        if status not in ["verified", "flagged", "pending"]:
            return {"success": False, "error": "Invalid status. Must be verified, flagged, or pending"}
            
        if status == "flagged" and not reason:
            return {"success": False, "error": "Reason required for flagged status"}
            
        success = file_service.update_case_verification(case_id, status, reason)
        
        if success:
            return {"success": True, "message": f"Case {case_id} marked as {status}"}
        else:
            return {"success": False, "error": "Failed to update case verification status"}
    except Exception as e:
        logging.error(f"Error verifying case: {exception_message(e)}")
        return {"success": False, "error": exception_message(e)}