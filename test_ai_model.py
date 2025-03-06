# test_ai_model.py - Place this in your project root
import asyncio
import sys
import os
from app.services.ai_model import extract_features, get_predictions

async def test_ai_model():
    # Test with a sample image
    image_path = "cxr_image.jpeg"  # Update with the path to a test image
    
    try:
        # Read the image
        with open(image_path, 'rb') as f:
            image_content = f.read()
        
        print(f"Testing with image: {image_path} ({len(image_content)} bytes)")
        
        # Test extract_features
        print("Testing extract_features...")
        features = await extract_features(image_content)
        print(f"Features extracted successfully: {len(features)} dimensions")
        
        # Test get_predictions
        print("Testing get_predictions...")
        predictions = await get_predictions(features)
        print(f"Predictions generated successfully: {len(predictions)} items")
        
        # Print first few predictions as sample
        print("\nSample predictions:")
        for i, pred in enumerate(predictions[:3]):
            print(f"Prediction {i+1}: {pred}")
        
        print("\nAll tests passed successfully!")
        
    except Exception as e:
        print(f"Error: {e}")
        return False
    
    return True

if __name__ == "__main__":
    success = asyncio.run(test_ai_model())
    sys.exit(0 if success else 1)