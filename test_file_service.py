# test_file_service.py - Place this in your project root
import os
import sys
import asyncio
import tempfile
from fastapi import UploadFile
import pandas as pd
from io import BytesIO
import json

from app.services.file_service import (
    read_upload_file, 
    validate_image_file,
    parse_csv_to_dataframe,
    dataframe_to_json,
    save_report,
    load_report,
    get_recent_reports
)

class MockUploadFile:
    """Mock FastAPI UploadFile for testing"""
    def __init__(self, filename, content):
        self.filename = filename
        self._content = content
        
    async def read(self):
        return self._content

async def test_file_service():
    print("Testing file service...")
    
    # Test image validation
    print("\n1. Testing image validation")
    try:
        # Create a mock image file (just a few bytes to pass basic validation)
        mock_image_content = b'\xff\xd8\xff' + os.urandom(1000)  # JPEG signature + random data
        validate_image_file("test.jpg", mock_image_content)
        print("✓ Image validation passed")
        
        try:
            validate_image_file("test.txt", mock_image_content)
            print("✗ Failed to catch invalid image extension")
            return False
        except ValueError:
            print("✓ Successfully caught invalid image extension")
    except Exception as e:
        print(f"✗ Image validation test failed: {e}")
        return False
    
    # Test CSV processing
    print("\n2. Testing CSV processing")
    try:
        # Create a mock CSV
        mock_df = pd.DataFrame({
            'name': ['Atelectasis', 'Cardiomegaly', 'Consolidation'],
            'Result': ['low risk', 'middle risk', 'high risk']
        })
        csv_content = mock_df.to_csv(index=False).encode('utf-8')
        
        # Test parsing
        mock_upload = MockUploadFile("test.csv", csv_content)
        file_content = await read_upload_file(mock_upload)
        parsed_df = parse_csv_to_dataframe(file_content)
        
        if len(parsed_df) == len(mock_df) and list(parsed_df.columns) == list(mock_df.columns):
            print("✓ CSV parsing passed")
        else:
            print("✗ CSV parsing returned unexpected data")
            return False
            
        # Test DataFrame to JSON conversion
        # Add this debugging code right after the dataframe_to_json call
        # Parse and check JSON properly:
        json_data = dataframe_to_json(parsed_df)
        print(f"DEBUG - JSON output: {json_data}")

        # Parse the JSON into Python objects
        try:
            parsed_json = json.loads(json_data)
            
            # Check for the expected values in the data
            atelectasis_found = False
            middle_risk_found = False
            
            for item in parsed_json:
                if item.get('name') == 'Atelectasis':
                    atelectasis_found = True
                if item.get('Result') == 'middle risk':
                    middle_risk_found = True
            
            if atelectasis_found and middle_risk_found:
                print("✓ DataFrame to JSON conversion passed")
            else:
                print("✗ DataFrame to JSON conversion failed")
                print(f"  - Atelectasis found: {atelectasis_found}")
                print(f"  - Middle risk found: {middle_risk_found}")
                return False
                
        except json.JSONDecodeError as e:
            print(f"✗ DataFrame to JSON conversion failed - invalid JSON: {e}")
            return False


    except Exception as e:
        print(f"✗ CSV processing test failed: {e}")
        return False
    
    # Test report saving and loading
    print("\n3. Testing report saving and loading")
    try:
        # Create a temporary report
        test_content = "This is a test report content"
        individual_path, master_path = save_report("test_data", test_content)
        print(f"✓ Report saved to {individual_path}")
        
        # Load the report
        loaded_report = load_report(individual_path)
        if loaded_report["report_content"] == test_content:
            print("✓ Report loading passed")
        else:
            print("✗ Report loading returned unexpected content")
            return False
            
        # Get recent reports
        recent_reports = get_recent_reports()
        if len(recent_reports) > 0 and "test_data" in [r.get("data_name") for r in recent_reports]:
            print("✓ Recent reports retrieval passed")
        else:
            print("✗ Recent reports retrieval failed")
            return False
            
        # Clean up test files
        os.remove(individual_path)
        print(f"✓ Cleaned up test report file at {individual_path}")
    except Exception as e:
        print(f"✗ Report handling test failed: {e}")
        return False
    
    print("\nAll tests passed successfully!")
    return True

if __name__ == "__main__":
    success = asyncio.run(test_file_service())
    sys.exit(0 if success else 1)