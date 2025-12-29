import os
from huggingface_hub import InferenceClient

def test_raw_hf():
    token = "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"
    model = "google/flan-t5-large"
    client = InferenceClient(model=model, token=token)
    
    prompt = "delay_mentioned: true / false\nquantity_changed: true / false\neta_changed: true / false\n\nEmail: The shipment will be late.\nOutput:"
    
    try:
        print(f"Testing {model} with raw prompt...")
        response = client.text_generation(prompt, max_new_tokens=50)
        print(f"Response: '{response}'")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_raw_hf()
