#!/usr/bin/env python
# -*- coding: utf-8 -*-

import aiohttp
import json
import logging
from typing import Dict, List, Any

from app.config.config import settings
from app.middleware.exception import exception_message
from app.middleware.logger import setup_logger

setup_logger()

async def extract_features(image_content: bytes) -> List[float]:
    """
    Extract CXR image features using AI API
    
    Args:
        image_content: Raw image bytes content
    
    Returns:
        List of extracted features as floats
        
    Raises:
        Exception: If feature extraction fails
    """
    try:
        logging.info(f"Extracting features from image ({len(image_content)} bytes)")

        # Create a new session for this request
        async with aiohttp.ClientSession() as session:
            auth = aiohttp.BasicAuth(settings.AUTH_USERNAME, settings.AUTH_PASSWORD)
            url = settings.BASE_URL_AI + settings.CXR_FEATURES_ENDPOINT
            
            # Prepare and send request
            form_data = aiohttp.FormData()
            form_data.add_field('file', image_content, filename='image.jpg', content_type='image/jpeg')
            
            async with session.post(url, auth=auth, data=form_data) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logging.error(f"Feature extraction failed: {response.status} - {error_text}")
                    raise Exception(f"Feature extraction failed: {response.status} - {error_text}")
                
                features = await response.json()
                logging.info(f"Features extracted successfully: {len(features)} dimensions")
                return features
    except Exception as e:
        logging.error(f"Error in extract_features: {exception_message(e)}")
        raise Exception(f"Feature extraction failed: {str(e)}")

async def get_predictions(features: List[float]) -> List[Dict[str, Any]]:
    """
    Get predictions from features using linear probe API
    
    Args:
        features: List of features extracted from CXR image
        
    Returns:
        List of prediction dictionaries with results
        
    Raises:
        Exception: If prediction generation fails
    """
    try:
        logging.info(f"Getting predictions for {len(features)} features")
        
        # Create a new session for this request
        async with aiohttp.ClientSession() as session:
            auth = aiohttp.BasicAuth(settings.AUTH_USERNAME, settings.AUTH_PASSWORD)
            url = settings.BASE_URL_AI + settings.CXR_LINEAR_PROBE_ENDPOINT
            
            # Convert features to JSON if needed
            features_json = json.dumps(features) if not isinstance(features, str) else features
            
            # Send request with proper headers
            headers = {'Content-Type': 'application/json'}
            async with session.post(url, auth=auth, data=features_json, headers=headers) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logging.error(f"Prediction failed: {response.status} - {error_text}")
                    raise Exception(f"Prediction failed: {response.status} - {error_text}")
                
                predictions = await response.json()
                logging.info(f"Predictions generated successfully: {len(predictions)} items")
                return predictions
    except Exception as e:
        logging.error(f"Error in get_predictions: {exception_message(e)}")
        raise Exception(f"Prediction generation failed: {str(e)}")

async def process_image_from_bytes(image_content: bytes) -> List[Dict[str, Any]]:
    """
    Process CXR image from bytes through feature extraction and prediction
    
    Args:
        image_content: Raw image bytes
        
    Returns:
        List of prediction dictionaries
    """
    # Step 1: Extract features
    features = await extract_features(image_content)
    
    # Step 2: Get predictions from features
    predictions = await get_predictions(features)
    
    return predictions

# Legacy function to keep backward compatibility
async def process_image(image_path: str) -> List[Dict[str, Any]]:
    """
    Process CXR image through feature extraction and prediction APIs
    
    Args:
        image_path: Path to the image file
        
    Returns:
        List of prediction dictionaries
    """
    try:
        with open(image_path, 'rb') as f:
            image_content = f.read()
        
        return await process_image_from_bytes(image_content)
    except Exception as e:
        logging.error(f"Error in process_image: {exception_message(e)}")
        raise Exception(f"Image processing failed: {str(e)}")