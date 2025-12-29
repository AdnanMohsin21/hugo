"""Ollama LLM service for local language model inference."""

import json
import logging
import os
import time
import requests
from typing import Any, Optional
from services.json_repair import attempt_json_repair, clean_json_text, normalize_json_output

logger = logging.getLogger("hugo.ollama")


class OllamaConnectionError(Exception):
    """Raised when Ollama cannot be reached after retries."""
    pass


def check_ollama_status(base_url: str = None) -> bool:
    """
    Check if Ollama is running and accessible.
    
    This function will NEVER crash the app - all exceptions are caught.
    
    Args:
        base_url: Ollama API base URL. If None, reads from OLLAMA_BASE_URL env var
                  or defaults to http://localhost:11434
    
    Returns:
        True if Ollama is reachable, False otherwise
    """
    if base_url is None:
        base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
    
    base_url = base_url.rstrip("/")
    
    try:
        response = requests.get(f"{base_url}/api/tags", timeout=5)
        if response.status_code == 200:
            logger.info("Ollama ready")
            return True
        else:
            logger.warning("Ollama not running, falling back")
            return False
    except requests.exceptions.Timeout:
        logger.warning("Ollama not running, falling back")
        return False
    except requests.exceptions.ConnectionError:
        logger.warning("Ollama not running, falling back")
        return False
    except Exception:
        # Catch-all to ensure we NEVER crash
        logger.warning("Ollama not running, falling back")
        return False


class OllamaLLM:
    """Client for interacting with Ollama's local LLM API."""

    def __init__(self, model: str = "gemma:2b", base_url: str = "http://localhost:11434"):
        """
        Initialize the Ollama LLM client.

        Args:
            model: The model to use for generation (default: "gemma:2b")
            base_url: The base URL for the Ollama API (default: "http://localhost:11434")
        """
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.ollama_url = self.base_url

    def _request_with_retry(self, url: str, payload: dict) -> dict:
        """
        Execute request with exponential backoff circuit breaker.
        
        Retries: 1s -> 2s -> 4s
        """
        backoffs = [1, 2, 4]
        last_error = None
        
        for attempt, backoff in enumerate(backoffs):
            try:
                response = requests.post(url, json=payload, timeout=120)
                response.raise_for_status()
                return response.json()
            except requests.exceptions.RequestException as e:
                last_error = e
                logger.warning(
                    f"Ollama request failed (attempt {attempt + 1}/3). "
                    f"Retrying in {backoff}s. Error: {str(e)[:100]}"
                )
                time.sleep(backoff)
        
        # If we get here, all retries failed
        logger.error("Ollama circuit breaker tripped. Service unavailable.")
        raise OllamaConnectionError(f"Failed to connect to Ollama after {len(backoffs)} retries: {last_error}")

    def generate(self, prompt: str) -> str:
        """
        Generate a response from the LLM given a prompt.

        Args:
            prompt: The input prompt to send to the model

        Returns:
            The generated response text

        Raises:
            OllamaConnectionError: If API fails after retries
        """
        url = f"{self.base_url}/api/generate"
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False
        }

        try:
            response_json = self._request_with_retry(url, payload)
            if "response" not in response_json:
                raise KeyError("Missing 'response' field in Ollama output")
            return response_json["response"]
        except KeyError as e:
            raise RuntimeError(f"Unexpected response format from Ollama API: {e}")
        except OllamaConnectionError:
            raise
        except Exception as e:
            raise RuntimeError(f"Unexpected error while calling Ollama: {str(e)}")

    def generate_json(self, prompt: str) -> dict:
        """
        Generate a JSON response from the LLM given a prompt.
        
        Features:
        - Automatic JSON repair (2 retries)
        - Output normalization (handling nulls)
        - Circuit breaker for connection issues
        
        Args:
            prompt: The input prompt to send to the model
            
        Returns:
            Parsed JSON dictionary
            
        Raises:
            OllamaConnectionError: If API fails
        """
        # Get raw response
        response = self.generate(prompt)
        
        # Clean potential formatting issues
        cleaned_response = clean_json_text(response)
        
        try:
            # Parse initial response
            result = json.loads(cleaned_response)
            # Normalize successful parse
            return normalize_json_output(result)
            
        except json.JSONDecodeError as e:
            logger.warning(f"Initial JSON parsing failed: {e}. Attempting repair...")
            
            # Attempt repair
            repaired = attempt_json_repair(
                raw_response=response,
                parse_error=e,
                ollama_url=self.base_url,
                model=self.model
            )
            
            # Use strict check since attempt_json_repair now returns {} on failure
            if repaired:
                logger.info("JSON repair successful")
                return repaired  # attempt_json_repair already normalizes
            
            # If repair returned empty dict or failed
            logger.error("JSON repair failed or returned empty")
            return {}  # Return safe empty object per requirements


# Module-level client for convenience function
_client: OllamaLLM = None


def generate_text(prompt: str) -> str:
    """
    Generate text using Ollama LLM.
    
    Reads configuration from environment variables:
    - OLLAMA_MODEL: Model to use (default: gemma:2b)
    - OLLAMA_BASE_URL: Ollama server URL (default: http://localhost:11434)
    
    Args:
        prompt: The input prompt to send to the model
    
    Returns:
        The generated response text (clean text only)
    
    Example:
        >>> response = generate_text("Summarize this email: ...")
        >>> print(response)
    """
    global _client
    
    if _client is None:
        model = os.environ.get("OLLAMA_MODEL", "gemma:2b")
        base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
        _client = OllamaLLM(model=model, base_url=base_url)
        logger.info(f"Initialized Ollama client (model: {model}, url: {base_url})")
    
    try:
        response = _client.generate(prompt)
        return response.strip()
    except OllamaConnectionError:
        logger.error("Ollama connection failed in generate_text")
        return ""  # Graceful failure
    except Exception as e:
        logger.error(f"Unexpected error in generate_text: {e}")
        return ""


def generate_json(prompt: str) -> dict[str, Any]:
    """
    Generate JSON using Ollama LLM with automatic repair and normalization.
    
    Args:
        prompt: The input prompt to send to the model
    
    Returns:
        Parsed JSON dictionary (or empty dict on failure)
    """
    global _client
    
    if _client is None:
        model = os.environ.get("OLLAMA_MODEL", "gemma:2b")
        base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
        _client = OllamaLLM(model=model, base_url=base_url)
        logger.info(f"Initialized Ollama client (model: {model}, url: {base_url})")
    
    try:
        return _client.generate_json(prompt)
    except Exception as e:
        logger.error(f"Error in generate_json: {e}")
        return {}  # Return safe empty object



# Export public API
__all__ = [
    "OllamaLLM",
    "check_ollama_status",
    "generate_text",
    "generate_json",
]

