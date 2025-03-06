from fastapi import FastAPI, HTTPException, File, UploadFile
from fastapi.responses import JSONResponse
import pandas as pd
import logging
from typing import Union
from fastapi.middleware.cors import CORSMiddleware
from requests import post
from requests.exceptions import RequestException
from app.middleware.exception import exception_message
import json
from typing import Union
import io

import os
from openai import OpenAI
import subprocess
import time

from app.config import settings
from app.middleware.exception import exception_message
from app.middleware.logger import setup_logger
from app.services.ai_model import extract_features, get_predictions

from icecream import ic

client = OpenAI(api_key=settings.OPENAI_API_KEY)

setup_logger()

app = FastAPI()

# CORS middleware setup to allow requests from specified origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost"],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*']
)

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
        # Read the uploaded file content
        image_content = await file.read()
        logging.info(f"Received image: {file.filename}, size: {len(image_content)} bytes")
        
        # Extract features using the AI model service
        features = await extract_features(image_content)
        logging.info(f"Features extracted successfully: {len(features)} dimensions")
        
        # Get predictions based on the features
        predictions = await get_predictions(features)
        logging.info(f"Predictions generated successfully: {len(predictions)} items")
        
        # Generate the report from predictions
        df, description = load_data(json.dumps(predictions), "app/data/Linear_Probe_Description.csv")
        df_annotated = prepare_dataframe(df, description)
        report_output = generate_report(df_annotated)
        
        # Generate prompt and get response from ChatGPT
        prompt = generate_prompt(report_output)
        response = await send_request(prompt)
        
        if response is None:
            raise HTTPException(status_code=500, detail="Failed to get response from ChatGPT API")
        
        return response
    except Exception as e:
        logging.error(exception_message(e))
        raise HTTPException(status_code=500, detail=f"Image processing failed: {str(e)}")

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
        raise HTTPException(status_code=500, detail=f"Feature extraction failed: {str(e)}")

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
        
        # Generate the report from predictions
        df, description = load_data(json.dumps(predictions), "app/data/Linear_Probe_Description.csv")
        df_annotated = prepare_dataframe(df, description)
        report_output = generate_report(df_annotated)
        
        # Generate prompt and get response from ChatGPT
        prompt = generate_prompt(report_output)
        response = await send_request(prompt)
        
        if response is None:
            raise HTTPException(status_code=500, detail="Failed to get response from ChatGPT API")
        
        return response
    except Exception as e:
        logging.error(exception_message(e))
        raise HTTPException(status_code=500, detail=f"Report generation failed: {str(e)}")

@app.post("/upload_csv/")
async def upload_csv(data: dict) -> Union[dict, str]:
    """Process JSON data from CSV and generate a report (legacy endpoint)"""
    # Keep your existing implementation, but perhaps add a deprecation warning in logs
    logging.info("Using legacy CSV upload endpoint")

    try:
        json_data = data['data']
        logging.info(f"Received file size: {len(json_data)} bytes")
        logging.info(f"Received data: \n{json_data}...")

        df, description = load_data(json_data, "app/data/Linear_Probe_Description.csv")  # Handle json
        logging.info(f"Loaded data: \n{df}...")
        logging.info(f"Loaded description: \n{description}...")

        df_annotated = prepare_dataframe(df, description)
        logging.info(f"Prepared dataframe: \n{df_annotated}...")

        report_output = generate_report(df_annotated)
        logging.info(f"Generated report output: \nType of report output: {type(report_output)} \n{report_output}")

        prompt = generate_prompt(report_output)
        logging.info(f"Generated prompt: \n{prompt}")

        response = await send_request(prompt)
        logging.info(f"Received response from ChatGPT API: \n{response}")
        if response is None:
            raise HTTPException(status_code=500, detail="Failed to get a response from the ChatGPT API.")
        try:
            return response
        except:
            error_msg = "An error occurred while processing the file."
            return error_msg
    except Exception as e:
        logging.error(exception_message(e))
        raise HTTPException(status_code=500, detail=f"An error occurred while processing the file: {str(e)}")


async def send_request(prompt: dict) -> Union[dict, str]:
    """Send a request to the ChatGPT API with the given input text."""
    ic(prompt)
    ic(type(prompt))
    ic(prompt["model"])
    ic(prompt["messages"])
    ic(prompt["messages"][0])
    ic(prompt["temperature"])
    ic(prompt["top_p"])
    try:
        response = client.chat.completions.create(
            model=prompt["model"],
            messages=prompt["messages"],
            temperature=prompt["temperature"],
            top_p=prompt["top_p"],
            stream=False
        )
        ic(response)
        logging.info(f"Response received: \n{response}")
        ic(response.choices[0].message.content)
        logging.info(f"Message Content: \n{response.choices[0].message.content}")
        ic(response.model_dump_json())
        logging.info(f"Response -> Model Dump JSON: \n{response.model_dump_json()}")
        return response.model_dump_json()
    except RequestException as e:
        logging.error(exception_message(e))
        return None


def generate_prompt(report_output: str) -> dict:
    """
    Generate the input text for the ChatGPT API based on the linear probing report.
    Property keys must be doublequoted.
    Use singlequote in prompt text if necessary.
    """

    logging.info(f"Generating prompt from report output: \n{report_output}")

    system_prompt = (
        "You are an experienced and detail-oriented radiologist interpreting chest X-ray (CXR) images based on the AI-analyzed results. "
        "Produce a concise, objective CXR report using short sentences and standard reporting conventions. "
        "Read and digest the content of the AI-analyzed CXR report section by section before writing the corresponding section of your report. "
    )
    user_prompt = (
        f"""
        Given: AI-analyzed report with risk levels (low, middle, high) for various features.
        [AI analyzed CXR report] {report_output}

        Instructions:
        1. Read and understand the each feature section of the AI-analyzed report before writing the corresponding section of your report.
        2. Use typical CXR terminology and follow the feature order in the report.
        3. Write one short, clear sentence per line for better readability.
        4. Do not use the terms 'low risk', 'middle risk', or 'high risk' in the report.
        5. For low-risk items, only mention them if clinically relevant.
        6. For middle-risk items, mention the item in report and suggest further investigation.
        7. For high-risk items, mention the item in report and use definitive language.
        8. When items in a categories are all low risk, use only the provided standard sentence.
        9. Omit 'patient' as a subject, omit the report title, and omit explanations.
        10. Use 'No' for negative findings.
        11. If Lung section contains middle risk or high risk features, directly report these features and omit the summary sentence (e.g., "No significant abnormality...").

        Reporting guidelines:
        - If there is a mix of risk levels across the categories, summarize and report the findings according to the instructions for low-risk, middle-risk, and high-risk items.
        - Lung features: If all low risk, use 'No significant abnormality (no focal nodule/mass or consolidation) in both lungs could be seen.'
        - Mediastinum: If all low risk, use 'The mediastinum shows normal appearance without evidence of focal bulging or widening.'
        - Bones: If all low risk, use 'No definite fracture line or focal nodule in bone structures could be seen.'
        - Cardiac silhouette: If low risk, use 'The cardiovascular silhouette is within normal limit.'
        - Diagnosis: If all low risk, use 'No evidence of pleural effusion or pneumothorax.'
        - Catheter and Implant: If all low risk, use 'No iatrogenic catheter or implant is noted.'
        - If all items across all categories are low risk, write only 'No significant abnormality of the chest radiography could be identified.'
        - 
        Report Template 1 (all items across all categories are low risk):
        No significant abnormality of the chest radiography could be identified.

        1. **Organ**


            **Lung:**
            No significant abnormality (no focal nodule/mass or consolidation) in both lungs could be seen.

            **Mediastinum:**
            The mediastinum shows normal appearance without evidence of focal bulging or widening.

            **Bones:**
            No definite fracture line or focal nodule in bone structures could be seen.

            **Cardiac silhouette:**
            The cardiovascular silhouette is within normal limit.

        2. **Diagnosis**

            No evidence of pleural effusion or pneumothorax.

        3. **Catheter and Implant**

            No iatrogenic catheter or implant is noted.

        Report Template 2 (mix of risk levels across the categories):
        1. **Organ**

            **Lung:**
            Minimal {{middle risk feature}} in {{right/left/bilateral}} lungs.
            Mild {{middle risk feature}} over {{right/left/bilateral}} {{upper/middle/lower}} lung.
            {{middle risk feature}} is suspected.
            {{high risk feature}} in {{right/left/bilateral}} lungs.
            {{high risk feature}} over {{right/left/bilateral}} {{upper/middle/lower}} lung.
            {{high risk feature}} is noted.

            **Mediastinum**
            {{middle risk feature}} is suspected.
            {{high risk feature}} is noted.

            **Bones:**
            {{middle risk feature}} is suspected.
            {{high risk feature}} is noted.

            **Cardiac silhouette:**
            {{high risk feature}}.
            {{middle risk feature}}.

        2. **Diagnosis**

            {{high risk feature}} is identified.
            {{middle risk feature}} is suspected.

        3. **Catheter and Implant**

            S/P {{high risk feature}}
        """
    )
    prompt = {
        "model": settings.CHATGPT_MODEL,
        "messages": [
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": user_prompt
            }
        ],
        "temperature": 0.15,
        "top_p": 0.15,
        "max_tokens": 1000,
        "stream": False
    }
    print("Prompt Prepared!")
    return prompt

# Function to load json and convert to dataframe
def load_data(json_data, description_path: str):
    try:
        logging.info(f"[Function: load_data] Received file size: {len(json_data)} bytes")
        if not json_data:
            raise ValueError("The uploaded file is empty.")
        data_dict = json.loads(json_data)
        df = pd.DataFrame(data_dict) # Construct the dataframe
        description = pd.read_csv(description_path)
        return df, description
    except Exception as e:
        raise ValueError(f"Error loading data: {e}") from e

# Function to concat descriptions to result
def prepare_dataframe(df, description):
    description['feature_number'] = range(1, len(description) + 1)
    df_annotated = pd.concat([df, description], axis=1)
    return df_annotated[['name', 'Result', 'feature_number']]

# Function to filter and sort DataFrame based on feature dictionary
def _filter_and_sort(df, features):
    """ Filters and sorts DataFrame based on feature numbers. """
    filtered_df = df[df['feature_number'].isin(features)].copy()
    # To keep features listed in desired order, use Categorical method
    filtered_df['feature_number'] = pd.Categorical(filtered_df['feature_number'], categories=features, ordered=True)
    return filtered_df.sort_values('feature_number').drop(columns='feature_number')

# Function to generate report output
def generate_report(df):
    feature_dict = {
        "Lung": [8, 2, 3, 9, 10, 1, 5, 6],
        "Mediastinum": [15, 28, 13, 17, 72, 73],
        "Bone": [20, 116, 27, 42, 18, 19, 24, 23],
        "Cardiac Silhouette": [14],
        "Diagnosis": [7, 12, 16],
        "Catheter/Implant": [44, 43, 41, 34, 35, 40, 36, 32, 33, 37, 38, 39]
    }

    report_output = ""

    for organ, features in feature_dict.items():
        df_organ = _filter_and_sort(df, features)
        report_output += f"{organ}:\n{df_organ.to_string(index=False, header=False)}\n\n"
    ic(report_output)
    logging.info(f" Report output generated successfully.\n{report_output}")
    return report_output


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