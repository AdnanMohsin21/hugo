
import unittest
from unittest.mock import patch, MagicMock
import json
import services.ollama_llm as ollama_llm
from services.ollama_llm import OllamaLLM

class TestOllamaJSONRepair(unittest.TestCase):
    
    @patch('services.ollama_llm.OllamaLLM.generate')
    @patch('services.ollama_llm.requests.post')
    def test_generate_json_success(self, mock_repair_post, mock_generate):
        # Scenario: First attempt succeeds
        mock_generate.return_value = '{"answer": 42}'
        
        client = OllamaLLM()
        result = client.generate_json("Test prompt")
        
        self.assertEqual(result, {"answer": 42})
        # Note: requests.post might be called by generate, but repair post is distinct
        # We assume repair uses requests.post directly in _call_ollama_for_repair

    @patch('services.ollama_llm.OllamaLLM.generate')
    @patch('services.json_repair.requests.post')
    def test_generate_json_repair_success(self, mock_repair_post, mock_generate):
        # Scenario: First attempt fails (bad JSON), repair succeeds
        mock_generate.return_value = 'INVALID JSON {answer: 42}'
        
        # Repair response
        mock_response = MagicMock()
        mock_response.json.return_value = {"response": '{"answer": 42}'}
        mock_response.status_code = 200
        mock_repair_post.return_value = mock_response
        
        client = OllamaLLM()
        result = client.generate_json("Test prompt")
        
        self.assertEqual(result, {"answer": 42})
        # Should call repair
        mock_repair_post.assert_called()
        
    @patch('services.ollama_llm.OllamaLLM.generate')
    @patch('services.json_repair.requests.post')
    def test_generate_json_repair_failure(self, mock_repair_post, mock_generate):
        # Scenario: First attempt fails, repair attempt also returns bad JSON
        mock_generate.return_value = 'INVALID JSON'
        
        # Repair response also bad
        mock_response = MagicMock()
        mock_response.json.return_value = {"response": 'STILL INVALID'}
        mock_response.status_code = 200
        mock_repair_post.return_value = mock_response
        
        client = OllamaLLM()
        
        # Should now return empty dict instead of raising
        result = client.generate_json("Test prompt")
        self.assertEqual(result, {})
            
        # Should be called 2 times now (2 retry attempts)
        self.assertEqual(mock_repair_post.call_count, 2)

if __name__ == '__main__':
    unittest.main()
