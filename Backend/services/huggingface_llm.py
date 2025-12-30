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
        self.api_url = f"https://router.huggingface.co/models/{model}"
        self.headers = {"Authorization": f"Bearer {self.token}"}
        # Keep client for other hub-related utilities if needed
        self.client = InferenceClient(model=model, token=self.token)

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
                    "max_new_tokens": 150,
                    "temperature": 0.2,
                    "do_sample": True,
                    "return_full_text": False
                }
            }
            
            response = requests.post(
                self.api_url,
                headers=self.headers,
                json=payload,
                timeout=30
            )
            
            if response.status_code == 429:
                # Rate limited - wait and retry once
                import time
                time.sleep(2)
                response = requests.post(
                    self.api_url,
                    headers=self.headers,
                    json=payload,
                    timeout=30
                )
            
            response.raise_for_status()
            
            result = response.json()
            
            # Handle different response formats
            if isinstance(result, list) and len(result) > 0:
                # Standard HF API format
                generated_text = result[0].get("generated_text", "")
            elif isinstance(result, dict):
                # Alternative format
                generated_text = result.get("generated_text", "")
            else:
                logger.warning(f"Unexpected response format: {type(result)}")
                generated_text = str(result)
            
            # Clean up the response
            if generated_text:
                generated_text = generated_text.strip()
                # Remove common artifacts
                artifacts = ["'", '"', '`', '\n\n', '\n\t']
                for artifact in artifacts:
                    generated_text = generated_text.replace(artifact, '')
                
                return generated_text
            else:
                logger.warning("Empty response from Hugging Face API")
                return ""
                
        except requests.exceptions.RequestException as e:
            error_msg = f"HF API error ({response.status_code if 'response' in locals() else 'Unknown'}): {str(e)}"
            logger.error(f"Hugging Face call failed: RuntimeError: {error_msg}")
            raise RuntimeError(error_msg) from e
            
        except Exception as e:
            logger.error(f"Unexpected error in HuggingFace LLM: {e}")
            raise RuntimeError(f"HF Inference API error: {str(e)}") from e
    
    def generate_json(self, prompt: str, schema: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Generate JSON output using the LLM with automatic repair.
        
        Args:
            prompt: Input prompt that should result in JSON
            schema: Optional JSON schema for validation
            
        Returns:
            Parsed JSON dictionary
        """
        try:
            response = self.generate(prompt)
            
            if not response:
                return {}
            
            # Clean and parse JSON
            cleaned_text = clean_json_text(response)
            
            try:
                parsed = json.loads(cleaned_text)
                return parsed
            except json.JSONDecodeError as e:
                logger.warning(f"JSON parsing failed, attempting repair: {e}")
                
                # Try to repair using our repair service
                repaired = attempt_json_repair(response, e, self.api_url, self.model)
                
                if repaired is not None:
                    logger.info("JSON repair successful")
                    return repaired
                else:
                    logger.error("JSON repair failed")
                    return {}
                    
        except Exception as e:
            logger.error(f"JSON generation failed: {e}")
            return {}
    
    def is_available(self) -> bool:
        """
        Check if the Hugging Face service is available.
        
        Returns:
            True if service is available, False otherwise
        """
        try:
            # Simple test with minimal prompt
            test_response = self.generate("Test")
            return True
        except Exception as e:
            logger.warning(f"Hugging Face service unavailable: {e}")
            return False
