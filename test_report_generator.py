# test_report_generator.py - Place this in your project root
import asyncio
import sys
import json
import os
from app.services.report_generator import generate_complete_report

async def test_report_generator():
    # Test with sample predictions data
    sample_path = "app/data/sample_predictions.json"
    
    try:
        # Check if sample file exists, otherwise create mock data
        if os.path.exists(sample_path):
            with open(sample_path, 'r') as f:
                predictions_json = f.read()
        else:
            # Create mock predictions for testing
            print("Sample file not found, creating mock data:")
            mock_predictions = [
                {"name": "Atelectasis", "Result": "low risk"},
                {"name": "Cardiomegaly", "Result": "middle risk"},
                {"name": "Consolidation", "Result": "low risk"},
                {"name": "Pneumothorax", "Result": "low risk"}
            ]
            
            predictions_json = json.dumps(mock_predictions)
            print(predictions_json)
            
            # Save mock data for future use
            os.makedirs(os.path.dirname(sample_path), exist_ok=True)
            with open(sample_path, 'w') as f:
                f.write(predictions_json)
        
        print(f"Testing with predictions data: {len(predictions_json)} bytes")
        
        # Generate complete report
        report_response = await generate_complete_report(predictions_json)
        
        # Parse and display the report content
        report_json = json.loads(report_response)
        print("\nReport generated successfully!")
        print(f"Model: {report_json['model']}")
        print(f"Content length: {len(report_json['choices'][0]['message']['content'])} characters")
        print("\nSample of generated report:")
        print(report_json['choices'][0]['message']['content'][:200] + "...")
        
        return True
        
    except Exception as e:
        print(f"Error: {e}")
        return False

if __name__ == "__main__":
    success = asyncio.run(test_report_generator())
    sys.exit(0 if success else 1)