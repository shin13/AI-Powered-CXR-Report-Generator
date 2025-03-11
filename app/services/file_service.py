#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import json
import uuid
import shutil
import logging
import datetime
from typing import Dict, List, Tuple, Any, Union, Optional
import hashlib

from fastapi import UploadFile

from app.config.config import settings
from app.middleware.exception import exception_message
from app.middleware.logger import setup_logger

# Initialize logging
setup_logger()

# Define constants
REPORTS_DIR = settings.REPORTS_DIR
MAX_IMAGE_SIZE_MB = settings.MAX_IMAGE_SIZE_MB
ALLOWED_IMAGE_EXTENSIONS = [".jpg", ".jpeg", ".png"]

def ensure_directory_exists(directory_path: str) -> None:
    """
    Ensure a directory exists, creating it if necessary
    
    Args:
        directory_path: Path to the directory
    """
    try:
        os.makedirs(directory_path, exist_ok=True)
        logging.debug(f"[file_service] Ensured directory exists: {directory_path}")
    except Exception as e:
        error_msg = f"Failed to create directory {directory_path}: {exception_message(e)}"
        logging.error(f"[file_service] {error_msg}")
        raise IOError(error_msg)

async def read_upload_file(upload_file: Union[UploadFile, Any]) -> bytes:
    """
    Read the contents of an uploaded file from either FastAPI or Streamlit
    
    Args:
        upload_file: FastAPI UploadFile or Streamlit UploadedFile object
        
    Returns:
        File contents as bytes
        
    Raises:
        ValueError: If file is empty or too large
    """
    try:
        # Different handling based on the file type
        # Check if it's a FastAPI UploadFile (which has an async read method)
        if hasattr(upload_file, 'read') and hasattr(upload_file, 'file'):
            # FastAPI's UploadFile - asynchronous read
            logging.info("FastAPI's UploadFile - asynchronous read")
            file_content = await upload_file.read()

        elif hasattr(upload_file, 'read'):
            # Streamlit's UploadedFile - synchronous read
            logging.info("Streamlit's UploadedFile - synchronous read")
            file_content = upload_file.read()
        else:
            raise ValueError("Unsupported file object type")
            
        # Check if file is empty
        if not file_content or len(file_content) == 0:
            raise ValueError("The uploaded file is empty")
            
        # Check file size (for images)
        file_extension = os.path.splitext(upload_file.name if hasattr(upload_file, 'name') else upload_file.filename)[1].lower()
        if file_extension in ALLOWED_IMAGE_EXTENSIONS:
            file_size_mb = len(file_content) / (1024 * 1024)
            if file_size_mb > MAX_IMAGE_SIZE_MB:
                raise ValueError(f"Image file too large. Maximum allowed size is {MAX_IMAGE_SIZE_MB} MB")
        
        logging.info(f"[file_service] Successfully read file: {getattr(upload_file, 'name', None) or upload_file.filename} ({len(file_content)} bytes)")
        return file_content
        
    except Exception as e:
        if isinstance(e, ValueError):
            # Re-raise validation errors
            raise
        error_msg = f"Error reading uploaded file: {exception_message(e)}"
        logging.error(f"[file_service] {error_msg}")
        raise IOError(error_msg)

def validate_image_file(filename: str, file_content: bytes) -> None:
    """
    Validate an image file
    
    Args:
        filename: Name of the file
        file_content: Contents of the file
        
    Raises:
        ValueError: If file is invalid
    """
    # Check file extension
    file_extension = os.path.splitext(filename)[1].lower()
    if file_extension not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValueError(f"Invalid image format. Supported formats: {', '.join(ALLOWED_IMAGE_EXTENSIONS)}")
        
    # Basic validation - check for minimum viable image size
    if len(file_content) < 100:  # Arbitrary small size that's definitely not a valid image
        raise ValueError("The file does not appear to be a valid image")
    
    logging.debug(f"[file_service] Image file validated: {filename}")

def save_report(data_name: str, report_content: str) -> Tuple[str, str]:
    """
    Save a report to disk
    
    Args:
        data_name: Name of the data source
        report_content: Content of the report
        
    Returns:
        Tuple of (individual report path, reports list path)
        
    Raises:
        IOError: If saving fails
    """
    try:
        # Ensure reports directory exists
        ensure_directory_exists(REPORTS_DIR)
        
        # Create report data structure
        now = datetime.datetime.now()
        timestamp_now = int(now.timestamp())
        formatted_time = now.strftime('%Y%m%d%H%M%S')
        
        report_data = {
            "data_name": data_name,
            "report_content": report_content,
            "created_at": timestamp_now,
            "created_at_str": now.strftime('%Y-%m-%d %H:%M:%S')
        }

        # Save individual report
        individual_report_path = f"{REPORTS_DIR}/report_{formatted_time}.json"
        with open(individual_report_path, "w") as f:
            json.dump(report_data, f, indent=4)

        # Update master reports list
        master_reports_path = f"{REPORTS_DIR}/reports.json"
        reports_list = []
        
        if os.path.exists(master_reports_path):
            with open(master_reports_path, "r") as f:
                try:
                    reports_list = json.load(f)
                    if not isinstance(reports_list, list):
                        reports_list = [reports_list]
                except json.JSONDecodeError:
                    reports_list = []
                    
        reports_list.append(report_data)
        
        with open(master_reports_path, "w") as f:
            json.dump(reports_list, f, indent=4)
            
        logging.info(f"[file_service] Report saved to both {master_reports_path} and {individual_report_path}")
        return individual_report_path, master_reports_path
        
    except Exception as e:
        error_msg = f"Error saving report: {exception_message(e)}"
        logging.error(f"[file_service] {error_msg}")
        raise IOError(error_msg)

def load_report(report_path: str) -> Dict[str, Any]:
    """
    Load a report from disk
    
    Args:
        report_path: Path to the report file
        
    Returns:
        Report data as dictionary
        
    Raises:
        IOError: If loading fails
    """
    try:
        if not os.path.exists(report_path):
            raise FileNotFoundError(f"Report file not found: {report_path}")
            
        with open(report_path, "r") as f:
            report_data = json.load(f)
            
        logging.info(f"[file_service] Report loaded: {report_path}")
        return report_data
        
    except Exception as e:
        error_msg = f"Error loading report: {exception_message(e)}"
        logging.error(f"[file_service] {error_msg}")
        raise IOError(error_msg)

def get_recent_reports(limit: int = 10) -> List[Dict[str, Any]]:
    """
    Get a list of recent reports
    
    Args:
        limit: Maximum number of reports to return
        
    Returns:
        List of report data dictionaries, ordered by creation time (newest first)
        
    Raises:
        IOError: If loading fails
    """
    try:
        master_reports_path = f"{REPORTS_DIR}/reports.json"
        
        if not os.path.exists(master_reports_path):
            return []
            
        with open(master_reports_path, "r") as f:
            try:
                reports_list = json.load(f)
                if not isinstance(reports_list, list):
                    reports_list = [reports_list]
            except json.JSONDecodeError:
                return []
                
        # Sort by creation time (newest first) and limit results
        sorted_reports = sorted(
            reports_list, 
            key=lambda x: x.get("created_at", 0), 
            reverse=True
        )[:limit]
        
        logging.info(f"[file_service] Retrieved {len(sorted_reports)} recent reports")
        return sorted_reports
        
    except Exception as e:
        error_msg = f"Error getting recent reports: {exception_message(e)}"
        logging.error(f"[file_service] {error_msg}")
        raise IOError(error_msg)
    
def save_case_data(
    image_path: str, 
    image_name: str,
    features: List[Dict],
    predictions: List[Dict],
    report_content: str,
    storage_dir: str = "./storage"
) -> str:
    """
    Save complete case data including image, features, predictions and report.
    
    Args:
        image_path: Path to the uploaded image
        image_name: Original filename of the image
        features: Extracted features from the image
        predictions: AI predictions based on features
        report_content: Final generated report text
        storage_dir: Base storage directory
        
    Returns:
        case_id: Unique identifier for the saved case
    """
    # Generate unique ID for case
    case_id = str(uuid.uuid4())
    timestamp = datetime.datetime.now().isoformat()
    
    # Create image hash for verification
    with open(image_path, "rb") as f:
        image_hash = hashlib.sha256(f.read()).hexdigest()
    
    # Copy image to storage
    images_dir = os.path.join(storage_dir, "images")
    os.makedirs(images_dir, exist_ok=True)
    image_ext = os.path.splitext(image_name)[1]
    stored_image_path = os.path.join(images_dir, f"{case_id}{image_ext}")
    shutil.copy2(image_path, stored_image_path)
    
    # Create case data object
    case_data = {
        "case_id": case_id,
        "timestamp": timestamp,
        "image": {
            "name": image_name,
            "path": os.path.relpath(stored_image_path, storage_dir),
            "hash": image_hash
        },
        "features": features,
        "predictions": predictions,
        "report": {
            "content": report_content
        }
    }
    
    # Save case data to JSON file
    cases_dir = os.path.join(storage_dir, "cases")
    os.makedirs(cases_dir, exist_ok=True)
    case_file = os.path.join(cases_dir, f"{case_id}.json")
    with open(case_file, "w") as f:
        json.dump(case_data, f, indent=2)
    
    return case_id

def get_case_by_id(case_id: str, storage_dir: str = "./storage") -> Optional[Dict]:
    """Retrieve case data by ID"""
    case_file = os.path.join(storage_dir, "cases", f"{case_id}.json")
    if not os.path.exists(case_file):
        return None
    
    with open(case_file, "r") as f:
        case_data = json.load(f)
    
    return case_data

def list_recent_cases(limit: int = 10, storage_dir: str = "./storage") -> List[Dict]:
    """List recent cases with basic information"""
    cases_dir = os.path.join(storage_dir, "cases")
    if not os.path.exists(cases_dir):
        return []
    
    cases = []
    for filename in os.listdir(cases_dir):
        if filename.endswith(".json"):
            with open(os.path.join(cases_dir, filename), "r") as f:
                case_data = json.load(f)
                cases.append({
                    "case_id": case_data["case_id"],
                    "timestamp": case_data["timestamp"],
                    "image_name": case_data["image"]["name"]
                })
    
    # Sort by timestamp (newest first) and limit results
    cases.sort(key=lambda x: x["timestamp"], reverse=True)
    return cases[:limit]

def update_case_verification(
    case_id: str, 
    status: str, 
    reason: str = None,
    storage_dir: str = "./storage"
) -> bool:
    """
    Update verification status of a case
    
    Args:
        case_id: Unique identifier for the case
        status: Verification status ("verified", "flagged", "pending")
        reason: Reason for flagging (required when status is "flagged")
        storage_dir: Base storage directory
        
    Returns:
        success: Whether update was successful
    """
    try:
        case_file = os.path.join(storage_dir, "cases", f"{case_id}.json")
        if not os.path.exists(case_file):
            logging.error(f"[file_service] Case not found: {case_id}")
            return False
        
        # Validate status
        valid_statuses = ["verified", "flagged", "pending"]
        if status not in valid_statuses:
            logging.error(f"[file_service] Invalid verification status: {status}")
            return False
            
        # Require reason for flagged status
        if status == "flagged" and not reason:
            logging.error("[file_service] Reason required for flagged status")
            return False
            
        # Load existing case data
        with open(case_file, "r") as f:
            case_data = json.load(f)
            
        # Update verification data
        if "verification" not in case_data:
            case_data["verification"] = {}
            
        case_data["verification"]["status"] = status
        case_data["verification"]["timestamp"] = datetime.datetime.now().isoformat()
        
        if status == "flagged" and reason:
            case_data["verification"]["reason"] = reason
        elif "reason" in case_data["verification"]:
            # Remove reason if not flagged
            del case_data["verification"]["reason"]
            
        # Save updated case data
        with open(case_file, "w") as f:
            json.dump(case_data, f, indent=2)
            
        logging.info(f"[file_service] Case verification updated: {case_id} -> {status}")
        return True
        
    except Exception as e:
        error_msg = f"Error updating case verification: {exception_message(e)}"
        logging.error(f"[file_service] {error_msg}")
        return False
