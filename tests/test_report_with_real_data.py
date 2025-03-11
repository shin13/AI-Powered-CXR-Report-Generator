#!/usr/bin/env python
# -*- coding: utf-8 -*-

import asyncio
import sys
import json
import os
import pandas as pd
from app.services.report_generator import generate_complete_report, load_data, generate_report
from app.middleware.exception import exception_message
from app.middleware.logger import setup_logger
import logging

setup_logger()

async def test_with_real_data():
    """Test report generator with real prediction data CSV"""
    try:
        # Path to the real prediction data
        csv_path = "prediction_data.csv"
        
        # Step 1: Verify the CSV exists
        if not os.path.exists(csv_path):
            logging.error(f"Error: Could not find {csv_path}")
            return False
            
        # Step 2: Load CSV data
        df = pd.read_csv(csv_path)
        logging.info(f"Loaded {len(df)} records from CSV")
        
        # Step 3: Convert to JSON format expected by the generator
        json_data = df.to_json(orient='records')
        
        # Step 4: Generate a report using each component separately
        logging.info("\nTesting load_data function...")
        loaded_df = await load_data(json_data)
        logging.info(f"Successfully loaded dataframe with {len(loaded_df)} rows")
        
        logging.info("\nTesting generate_report function...")
        # Test the core report generation (filtering and structuring)
        report_output = generate_report(loaded_df)
        logging.info(f"Successfully generated report with {len(report_output)} characters")
        logging.info("\nSample of report:")
        logging.info(report_output[:500] + "...")
        
        # Step 5: Test the full pipeline
        logging.info("\nTesting full report generation pipeline...")
        response = await generate_complete_report(json_data)
        logging.info(f"Successfully generated complete report response:\n{response}")
        
        # Parse and display the results
        response_obj = json.loads(response)
        logging.info(f"Model used: {response_obj['model']}")
        report_content = response_obj['choices'][0]['message']['content']
        logging.info(f"Report length: {len(report_content)} characters")
        logging.info("\nSample of final report:")
        logging.info(report_content[:500] + "...")
        
        # Save the output to a file for manual inspection
        with open("test_report_output.txt", "w") as f:
            f.write(report_content)
        logging.info("\nFull report saved to test_report_output.txt")
        
        return True
        
    except Exception as e:
        logging.error(f"Error in test: {exception_message(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_with_real_data())
    sys.exit(0 if success else 1)