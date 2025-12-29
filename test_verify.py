import os
import logging
from main import HugoAgent

# Setup logging
logging.basicConfig(level=logging.INFO)

def test_hf_llm():
    print("Testing Hugging Face LLM integration...")
    os.environ["HF_TOKEN"] = "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"
    
    agent = HugoAgent()
    
    # This sender exists in the mock ERP data
    sender = "logistics@acme-supplies.com"
    subject = "Urgent: Delivery Delay for PO-2024-0892"
    body = "Hi, we are experiencing a delay. The new delivery date for PO-2024-0892 is January 12th."
    
    print(f"\nProcessing test email from {sender}...")
    alert = agent.process_single_email_from_text(sender, subject, body)
    
    if alert and alert.delivery_change.detected:
        print("\nSUCCESS: Delivery change detected!")
        print(f"Change Type: {alert.delivery_change.change_type}")
        print(f"Delay Days: {alert.delivery_change.delay_days}")
        if alert.risk_assessment:
            print(f"Risk Level: {alert.risk_assessment.risk_level}")
    else:
        print("\nFAILURE: No delivery change detected or PO mismatch.")

if __name__ == "__main__":
    test_hf_llm()
