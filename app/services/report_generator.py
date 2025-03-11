#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import logging
import pandas as pd
from typing import Dict, List, Tuple, Union, Any
import os

from openai import OpenAI
from requests.exceptions import RequestException

from app.config.config import settings
from app.middleware.exception import exception_message
from app.middleware.logger import setup_logger

# Initialize logging and OpenAI client
setup_logger()
client = OpenAI(api_key=settings.OPENAI_API_KEY)

async def load_data(json_data: str) -> pd.DataFrame:
    """
    Load JSON data and convert to dataframe
    
    Args:
        json_data: JSON string containing the data
        
    Returns:
        data DataFrame
        
    Raises:
        ValueError: If data loading fails
    """
    try:
        logging.info(f"[report_generator] Loading data of size: {len(json_data)} bytes")
        if not json_data:
            raise ValueError("The data is empty.")
        
        data_dict = json.loads(json_data)
        df = pd.DataFrame(data_dict)  # Construct the dataframe

        return df
    except Exception as e:
        error_msg = f"Error loading data: {exception_message(e)}"
        logging.error(f"[report_generator] {error_msg}")
        raise ValueError(error_msg) from e

def validate_prediction_json(data: pd.DataFrame) -> None:
    """Validate the prediction dataframe has required columns"""
    required_columns = ['uid', 'item', 'value', 'risk', 'category']
    missing_columns = [col for col in required_columns if col not in data.columns]
    if missing_columns:
        raise ValueError(f"Missing required columns in prediction data: {missing_columns}")
      
def _filter_and_sort(df: pd.DataFrame, features: List[int]) -> pd.DataFrame:
    try:
        filtered_df = df[df['uid'].isin(features)].copy()
        
        # To keep features listed in desired order, use Categorical method
        filtered_df['uid'] = pd.Categorical(
            filtered_df['uid'], 
            categories=features, 
            ordered=True
        )
        
        return filtered_df.sort_values('uid').drop(columns='uid')
    except Exception as e:
        error_msg = f"Error filtering and sorting dataframe: {exception_message(e)}"
        logging.error(f"[report_generator] {error_msg}")
        raise ValueError(error_msg)

def load_feature_mapping(config_path: str = "app/config/mapping/feature_mapping.json") -> Dict[str, List[int]]:
    """
    Load feature mapping configuration from JSON file
    
    Args:
        config_path: Path to the feature mapping configuration file
        
    Returns:
        Dictionary mapping sections to feature IDs
        
    Raises:
        ValueError: If config file cannot be loaded
    """
    try:
        logging.info(f"[report_generator] Loading feature mapping from {config_path}")
        with open(config_path, 'r') as f:
            feature_dict = json.load(f)
        logging.info(f"[report_generator] Successfully loaded mapping with {len(feature_dict)} sections")
        return feature_dict
    except Exception as e:
        error_msg = f"Error loading feature mapping: {exception_message(e)}"
        logging.error(f"[report_generator] {error_msg}")
        # Fall back to default mapping if available
        logging.warning("[report_generator] Using default feature mapping")
        # Default mapping as fallback
        default_mapping = {
            "Lung": [8, 193, 2, 131, 194, 195],
            "Mediastinum": [15, 307, 308, 309],
            "Bone": [20, 116, 27, 42],
            "Cardiac silhouette": [22, 23, 24, 25],
            "Diagnosis": [6, 7, 9, 10, 11, 161],
            "Catheter and Implant": [31, 33, 34, 35]
        }
        return default_mapping

def generate_report(df: pd.DataFrame, config_path: str = "app/config/feature_mapping.json") -> str:
    """
    Generate a structured report from the annotated dataframe
    
    Args:
        df: Annotated DataFrame with analysis results
        config_path: Path to the feature mapping configuration file
        
    Returns:
        Formatted report text
    """
    try:
        logging.info(f"[report_generator] Generating report from dataframe with {len(df)} rows")
        
        # Load feature mapping from configuration file
        feature_dict = load_feature_mapping(config_path)
        
        report_output = ""

        # Process each organ/category
        for section, features in feature_dict.items():
            df_section = _filter_and_sort(df, features)
            report_output += f"{section}:\n{df_section[['item', 'risk']].to_string(index=False, header=False)}\n\n"

        logging.info(f"Report generated successfully: {len(report_output)} characters")
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
            f"""Given: AI-analyzed report with risk levels (low, middle, high) for various features.
            [AI analyzed CXR report] 
            {report_output}

            Instructions:
            1. Read and understand the each feature section of the AI-analyzed report before writing the corresponding section of your report.
            2. Use typical CXR terminology and follow the feature order in the report.
            3. Write one short, clear sentence per line for better readability.
            4. Do not use the terms 'low risk', 'middle risk', or 'high risk' in the report.
            5. For every low-risk item, skip it.
            6. For every middle-risk item, describe it in report and suggest further investigation.
            7. For every high-risk item, describe it in report and use definitive language.
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

                S/P {{high risk feature}}"""
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
            "temperature": 0.2,
            "top_p": 0.2,
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

async def generate_complete_report(predictions_json: str) -> Dict[str, Any]:
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
        df = await load_data(predictions_json)
        logging.info(f"Data Frame: {df}")
        
        # Generate structured report
        report_output = generate_report(df)
        logging.info(f"Report Output: {report_output}")
        
        # Generate prompt for ChatGPT
        prompt = generate_prompt(report_output)
        logging.info(f"Prompt: {prompt}")
        
        # Send request to ChatGPT
        response = await send_request(prompt)
        logging.info(f"Response: {response}")
        
        if response is None:
            raise ValueError("Failed to get response from ChatGPT API")
            
        return response
    except Exception as e:
        error_msg = f"Error generating complete report: {exception_message(e)}"
        logging.error(f"[report_generator] {error_msg}")
        raise ValueError(error_msg)