#!/usr/bin/env python
# -*- coding: utf-8 -*-

import asyncio
import aiohttp
import aiofiles
import json
import logging
import sys
from typing import Dict, List, Any
from app.config import settings
from app.middleware import logger

# Set up logging
logger.setup_logger()

async def extract_features(session: aiohttp.ClientSession, image_path: str) -> List[float]:
    """Extract CXR image features using AI API"""
    auth = aiohttp.BasicAuth(settings.AUTH_USERNAME, settings.AUTH_PASSWORD)
    url = settings.BASE_URL_AI + settings.CXR_FEATURES_ENDPOINT
    
    # Read image file
    async with aiofiles.open(image_path, 'rb') as f:
        image_data = await f.read()
        image_name = image_path.split('/')[-1].split('.')[0]
        logging.info(f"Extracting features from {image_name} ({len(image_data)} bytes)")
    
    # Prepare and send request
    form_data = aiohttp.FormData()
    form_data.add_field('file', image_data, filename=image_name)
    
    async with session.post(url, auth=auth, data=form_data) as response:
        if response.status != 200:
            raise Exception(f"Feature extraction failed: {response.status} - {await response.text()}")
        
        return await response.json()

async def get_predictions(session: aiohttp.ClientSession, features: List[float]) -> List[Dict[str, Any]]:
    """Get predictions from features using linear probe API"""
    auth = aiohttp.BasicAuth(settings.AUTH_USERNAME, settings.AUTH_PASSWORD)
    url = settings.BASE_URL_AI + settings.CXR_LINEAR_PROBE_ENDPOINT
    
    # Convert features to JSON if needed
    features_json = json.dumps(features) if not isinstance(features, str) else features
    
    # Send request with proper headers
    headers = {'Content-Type': 'application/json'}
    async with session.post(url, auth=auth, data=features_json, headers=headers) as response:
        if response.status != 200:
            raise Exception(f"Prediction failed: {response.status} - {await response.text()}")
        
        return await response.json()
    
async def process_image(image_path: str) -> List[Dict[str, Any]]:
    """Process CXR image through feature extraction and prediction APIs"""
    async with aiohttp.ClientSession() as session:
        # Step 1: Extract features
        features = await extract_features(session, image_path)
        logging.info(f"Features extracted: {len(features)} dimensions")
        
        # Step 2: Get predictions from features
        results = await get_predictions(session, features)
        logging.info(f"Received {len(results)} predictions")
        
        return results

async def main():
    """Main function to run the script"""
    if len(sys.argv) != 2:
        print("Usage: python script.py <image_path>")
        return
    
    try:
        results = await process_image(sys.argv[1])
        print(json.dumps(results, indent=2))
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
    
# Usage: python test_model_api.py /path/to/cxr_image.jpeg
# Example: $ python test_model_api.py /Users/shin/Projects/CXR自動打報告/AI-Powered-CXR-Report-Generator/cxr_image.jpeg