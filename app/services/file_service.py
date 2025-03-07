#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import json
import logging
import datetime
from io import BytesIO
from typing import Dict, List, Tuple, Any

import pandas as pd
from fastapi import UploadFile

from app.middleware.exception import exception_message
from app.middleware.logger import setup_logger

# Initialize logging
setup_logger()

# Define constants
REPORTS_DIR = "reports"
ALLOWED_IMAGE_EXTENSIONS = [".jpg", ".jpeg", ".png"]
ALLOWED_CSV_EXTENSION = ".csv"
MAX_IMAGE_SIZE_MB = 10  # Maximum allowed image size in MB

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

async def read_upload_file(upload_file: UploadFile) -> bytes:
    """
    Read the contents of an uploaded file
    
    Args:
        upload_file: FastAPI UploadFile object
        
    Returns:
        File contents as bytes
        
    Raises:
        ValueError: If file is empty or too large
    """
    try:
        file_content = await upload_file.read()
        
        # Check if file is empty
        if not file_content or len(file_content) == 0:
            raise ValueError("The uploaded file is empty")
            
        # Check file size (for images)
        file_extension = os.path.splitext(upload_file.filename)[1].lower()
        if file_extension in ALLOWED_IMAGE_EXTENSIONS:
            file_size_mb = len(file_content) / (1024 * 1024)
            if file_size_mb > MAX_IMAGE_SIZE_MB:
                raise ValueError(f"Image file too large. Maximum allowed size is {MAX_IMAGE_SIZE_MB}MB")
        
        logging.info(f"[file_service] Successfully read file: {upload_file.filename} ({len(file_content)} bytes)")
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

def parse_csv_to_dataframe(file_content: bytes) -> pd.DataFrame:
    """
    Parse CSV file content to a pandas DataFrame
    
    Args:
        file_content: CSV file content as bytes
        
    Returns:
        Pandas DataFrame with the CSV data
        
    Raises:
        ValueError: If CSV parsing fails
    """
    try:
        df = pd.read_csv(BytesIO(file_content))
        logging.info(f"[file_service] CSV parsed successfully: {len(df)} rows, {len(df.columns)} columns")
        return df
    except Exception as e:
        error_msg = f"Error parsing CSV file: {exception_message(e)}"
        logging.error(f"[file_service] {error_msg}")
        raise ValueError(error_msg)

def dataframe_to_json(df: pd.DataFrame) -> str:
    """
    Convert a DataFrame to JSON string
    
    Args:
        df: Pandas DataFrame
        
    Returns:
        JSON string representation
        
    Raises:
        ValueError: If conversion fails
    """
    try:
        # Ensure we're converting to a list of records
        records = df.to_dict('records')
        json_data = json.dumps(records)
        logging.debug(f"[file_service] DataFrame converted to JSON: {len(json_data)} bytes")
        # Add extra debugging
        logging.debug(f"[file_service] First few records: {records[:2]}")
        return json_data
    except Exception as e:
        error_msg = f"Error converting DataFrame to JSON: {exception_message(e)}"
        logging.error(f"[file_service] {error_msg}")
        raise ValueError(error_msg)

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