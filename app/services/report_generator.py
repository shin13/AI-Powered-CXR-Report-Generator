#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import logging
import pandas as pd
from typing import Dict, List, Tuple, Union, Any
import os

from openai import OpenAI
from requests.exceptions import RequestException

from app.config import settings
from app.middleware.exception import exception_message
from app.middleware.logger import setup_logger

# Initialize logging and OpenAI client
setup_logger()
client = OpenAI(api_key=settings.OPENAI_API_KEY)

async def load_data(json_data: str, description_path: str) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Load JSON data and convert to dataframe with descriptions
    
    Args:
        json_data: JSON string containing the data
        description_path: Path to the CSV file with descriptions
        
    Returns:
        Tuple of (data DataFrame, description DataFrame)
        
    Raises:
        ValueError: If data loading fails
    """
    try:
        logging.info(f"[report_generator] Loading data of size: {len(json_data)} bytes")
        if not json_data:
            raise ValueError("The data is empty.")
        
        data_dict = json.loads(json_data)
        df = pd.DataFrame(data_dict)  # Construct the dataframe
        
        # Check if description file exists
        if not os.path.exists(description_path):
            raise ValueError(f"Description file not found: {description_path}")
            
        description = pd.read_csv(description_path)
        logging.info(f"[report_generator] Data loaded successfully: {len(df)} rows, {len(description)} descriptions")
        
        return df, description
    except Exception as e:
        error_msg = f"Error loading data: {exception_message(e)}"
        logging.error(f"[report_generator] {error_msg}")
        raise ValueError(error_msg) from e

def prepare_dataframe(df: pd.DataFrame, description: pd.DataFrame) -> pd.DataFrame:
    """
    Add descriptions to results and prepare the dataframe for report generation
    
    Args:
        df: DataFrame with analysis results
        description: DataFrame with feature descriptions
        
    Returns:
        Annotated DataFrame with combined information
    """
    try:
        logging.info(f"[report_generator] Preparing dataframe with {len(df)} rows and {len(description)} descriptions")
        # Add feature number to description for joining
        description['feature_number'] = range(1, len(description) + 1)
        
        # Concatenate dataframes
        df_annotated = pd.concat([df, description], axis=1)
        
        # Select and return only the needed columns
        result = df_annotated[['name', 'Result', 'feature_number']]
        logging.info(f"[report_generator] Dataframe prepared successfully: {len(result)} rows")
        
        return result
    except Exception as e:
        error_msg = f"Error preparing dataframe: {exception_message(e)}"
        logging.error(f"[report_generator] {error_msg}")
        raise ValueError(error_msg)

def _filter_and_sort(df: pd.DataFrame, features: List[int]) -> pd.DataFrame:
    """
    Filter and sort DataFrame based on feature numbers
    
    Args:
        df: DataFrame to filter
        features: List of feature numbers to include
        
    Returns:
        Filtered and sorted DataFrame
    """
    try:
        filtered_df = df[df['feature_number'].isin(features)].copy()
        
        # To keep features listed in desired order, use Categorical method
        filtered_df['feature_number'] = pd.Categorical(
            filtered_df['feature_number'], 
            categories=features, 
            ordered=True
        )
        
        return filtered_df.sort_values('feature_number').drop(columns='feature_number')
    except Exception as e:
        error_msg = f"Error filtering and sorting dataframe: {exception_message(e)}"
        logging.error(f"[report_generator] {error_msg}")
        raise ValueError(error_msg)

def generate_report(df: pd.DataFrame) -> str:
    """
    Generate a structured report from the annotated dataframe
    
    Args:
        df: Annotated DataFrame with analysis results
        
    Returns:
        Formatted report text
    """
    try:
        logging.info(f"[report_generator] Generating report from dataframe with {len(df)} rows")
        
        # Feature dictionary with organ/category mappings
        feature_dict = {
            "Lung": [8, 2, 3, 9, 10, 1, 5, 6],
            "Mediastinum": [15, 28, 13, 17, 72, 73],
            "Bone": [20, 116, 27, 42, 18, 19, 24, 23],
            "Cardiac Silhouette": [14],
            "Diagnosis": [7, 12, 16],
            "Catheter/Implant": [44, 43, 41, 34, 35, 40, 36, 32, 33, 37, 38, 39]
        }

        report_output = ""

        # Process each organ/category
        for organ, features in feature_dict.items():
            df_organ = _filter_and_sort(df, features)
            report_output += f"{organ}:\n{df_organ.to_string(index=False, header=False)}\n\n"
        
        logging.info(f"[report_generator] Report generated successfully: {len(report_output)} characters")
        return report_output
    except Exception as e:
        error_msg = f"Error generating report: {exception_message(e)}"
        logging.error(f"[report_generator] {error_msg}")
        raise ValueError(error_msg)

def generate_prompt(report_output: str) -> Dict[str, Any]:
    """
    Generate the prompt for the ChatGPT API
    
    Args:
        report_output: The structured report text
        
    Returns:
        Formatted prompt dictionary for the ChatGPT API
    """
    try:
        logging.info(f"[report_generator] Generating prompt from report output: {len(report_output)} characters")

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
        
        logging.info("[report_generator] Prompt generated successfully")
        return prompt
    except Exception as e:
        error_msg = f"Error generating prompt: {exception_message(e)}"
        logging.error(f"[report_generator] {error_msg}")
        raise ValueError(error_msg)

async def send_request(prompt: Dict[str, Any]) -> Union[Dict, None]:
    """
    Send a request to the ChatGPT API
    
    Args:
        prompt: The formatted prompt dictionary
        
    Returns:
        The API response as a dictionary or None if failed
    """
    try:
        logging.info("[report_generator] Sending request to ChatGPT API")
        
        response = client.chat.completions.create(
            model=prompt["model"],
            messages=prompt["messages"],
            temperature=prompt["temperature"],
            top_p=prompt["top_p"],
            stream=False
        )
        
        logging.info(f"[report_generator] Response received from ChatGPT API: {response}")
        logging.debug(f"[report_generator] Message Content: {response.choices[0].message.content}")
        
        return response.model_dump_json()
    except RequestException as e:
        error_msg = f"Error sending request to ChatGPT API: {exception_message(e)}"
        logging.error(f"[report_generator] {error_msg}")
        return None
    except Exception as e:
        error_msg = f"Unexpected error sending request: {exception_message(e)}"
        logging.error(f"[report_generator] {error_msg}")
        return None

async def generate_complete_report(predictions_json: str, description_path: str = "app/data/Linear_Probe_Description.csv") -> Dict[str, Any]:
    """
    Complete workflow to generate a report from predictions JSON
    
    Args:
        predictions_json: JSON string with predictions
        description_path: Path to the descriptions CSV file
        
    Returns:
        The complete ChatGPT report
        
    Raises:
        ValueError: If any part of the process fails
    """
    try:
        # Load data
        df, description = await load_data(predictions_json, description_path)
        
        # Prepare dataframe with annotations
        df_annotated = prepare_dataframe(df, description)
        
        # Generate structured report
        report_output = generate_report(df_annotated)
        
        # Generate prompt for ChatGPT
        prompt = generate_prompt(report_output)
        
        # Send request to ChatGPT
        response = await send_request(prompt)
        
        if response is None:
            raise ValueError("Failed to get response from ChatGPT API")
            
        return response
    except Exception as e:
        error_msg = f"Error generating complete report: {exception_message(e)}"
        logging.error(f"[report_generator] {error_msg}")
        raise ValueError(error_msg)