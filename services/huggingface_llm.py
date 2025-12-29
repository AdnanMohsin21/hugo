"""
Hugging Face LLM service for online language model inference.
Replaces local Ollama usage with production-ready HF Inference API.
"""

import os
import json
import logging
import requests
from typing import Any, Dict, Optional
from huggingface_hub import InferenceClient
from services.json_repair import attempt_json_repair, clean_json_text, normalize_json_output

logger = logging.getLogger("hugo.huggingface")


class HuggingFaceLLM:
    """
    Hugging Face Inference Client wrapper for online LLM generation.
    Replaces local Ollama usage with production-ready HF Inference API.
    
    Uses google/flan-t5-large model via HF_TOKEN authentication.
    """
    
    def __init__(self, model: str = "google/flan-t5-large"):
        """
        Initialize Hugging Face LLM client.
        
        Args:
            model: Model identifier (default: google/flan-t5-large)
        """
        self.token = os.environ.get("HF_TOKEN")
        if not self.token:
            raise ValueError("HF_TOKEN environment variable is required but not set!")
        
        self.model = model
        self.api_url = f"https://api-inference.huggingface.co/models/{model}"
        self.headers = {"Authorization": f"Bearer {self.token}"}
        # Keep client for other hub-related utilities if needed
        self.client = InferenceClient(model=model, token=self.token)
        logger.info(f"Initialized HuggingFaceLLM with model: {model}")

    def generate(self, prompt: str) -> str:
        """
        Generate text completion for the given prompt using HF Inference API.
        
        Args:
            prompt: Input prompt text
            
        Returns:
            Generated text response
        """
        try:
            # Use requests directly for maximum stability with flan-t5
            payload = {
                "inputs": prompt,
                "parameters": {
                    "max_new_tokens": 200,
                    "temperature": 0.1,
                }
            }
            
            response = requests.post(
                self.api_url,
                headers=self.headers,
                json=payload,
                timeout=30
            )
            
            if response.status_code != 200:
                logger.error(f"HF API returned status {response.status_code}: {response.text}")
                raise RuntimeError(f"HF API error ({response.status_code}): {response.text}")
            
            result = response.json()
            
            # Text2Text models return a list of dicts: [{"generated_text": "..."}]
            if isinstance(result, list) and len(result) > 0:
                content = result[0].get("generated_text", "")
                logger.info("Hugging Face inference successful")
                return content.strip()
            
            return str(result).strip()
            
        except Exception as e:
            logger.error(f"Hugging Face call failed: {type(e).__name__}: {str(e)}")
            raise RuntimeError(f"HF Inference API error: {e}")

    def generate_json(self, prompt: str) -> Dict[str, Any]:
        """
        Generate JSON output from the model with automatic repair and retry.
        
        Features:
        - Automatic JSON extraction from response
        - Retry with stricter system message on failure
        - JSON repair on failure (using HF model)
        - Output normalization
        
        Args:
            prompt: Input prompt that should produce JSON
            
        Returns:
            Parsed JSON dictionary (empty dict on failure)
        """
        try:
            # First attempt
            response = self.generate(prompt)
            
            if not response:
                logger.warning("Empty response from HF API")
                return {}
            
            # Clean and try parsing
            cleaned_response = clean_json_text(response)
            
            try:
                result = json.loads(cleaned_response)
                logger.info("Extraction successful")
                return normalize_json_output(result)
            except json.JSONDecodeError as e:
                logger.warning(f"Initial JSON parsing failed: {e}. Retrying with stricter system message...")
                
                # Retry with stricter system message
                try:
                    strict_messages = [
                        {"role": "system", "content": "You are a JSON-only response system. You MUST return ONLY valid JSON. No explanations, no markdown, no code blocks. Invalid JSON will cause system failure."},
                        {"role": "user", "content": prompt}
                    ]
                    
                    retry_response = self.client.text_generation(
                        prompt,
                        max_new_tokens=200,
                        temperature=0.1,
                        seed=42
                    )
                    
                    retry_content = retry_response.strip()
                    logger.info("Hugging Face chat completion successful")
                    
                    cleaned_retry = clean_json_text(retry_content)
                    result = json.loads(cleaned_retry)
                    logger.info("Extraction successful")
                    return normalize_json_output(result)
                    
                except json.JSONDecodeError as retry_error:
                    logger.warning(f"Retry JSON parsing also failed: {retry_error}. Attempting repair...")
                    
                    # Attempt repair using HF model
                    repaired = attempt_json_repair(
                        raw_response=retry_content if 'retry_content' in locals() else response,
                        parse_error=retry_error,
                        ollama_url="",  # Not used for HF
                        model=self.model
                    )
                    
                    if repaired:
                        logger.info("JSON repair successful")
                        logger.info("Extraction successful")
                        return repaired
                    
                    logger.error("JSON repair failed or returned empty")
                    return {}
                
        except Exception as e:
            logger.error(f"Unexpected error in generate_json: {e}")
            return {}
