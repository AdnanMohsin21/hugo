"""
Test and example for Hugo Operations QA module.

Demonstrates how to use answer_operational_question() for analytical queries.
"""

from services.operations_qa import answer_operational_question, OperationalAnswer


def test_operational_questions():
    """Test the operations QA module with realistic scenarios."""
    
    # Sample operational data
    erp_data = {
        "production_capacity_weekly": 500,
        "lead_time_weeks": 2,
        "current_production_rate": 350,
        "working_days_per_week": 5
    }
    
    orders = [
        {
            "order_id": "O-2025-001",
            "product_model": "X-Series",
            "quantity": 150,
            "due_date": "2025-01-20",
            "status": "confirmed"
        },
        {
            "order_id": "O-2025-002",
            "product_model": "Y-Series",
            "quantity": 100,
            "due_date": "2025-01-27",
            "status": "confirmed"
        },
        {
            "order_id": "O-2025-003",
            "product_model": "X-Series",
            "quantity": 75,
            "due_date": "2025-02-03",
            "status": "pending"
        }
    ]
    
    inventory = {
        "MOTOR-A": 450,
        "MOTOR-B": 200,
        "FRAME-X": 250,
        "FRAME-Y": 180,
        "BATTERY-PACK": 120,
        "CONTROLLER": 380,
        "WHEEL-SET": 320,
        "TIRE-KIT": 280,
        "CABLE-ASM": 500,
        "PAINT-KIT": 100
    }
    
    bom_data = {
        "X-Series": {
            "MOTOR-A": 1,
            "FRAME-X": 1,
            "BATTERY-PACK": 1,
            "CONTROLLER": 1,
            "WHEEL-SET": 1,
            "TIRE-KIT": 1,
            "CABLE-ASM": 2,
            "PAINT-KIT": 1
        },
        "Y-Series": {
            "MOTOR-B": 1,
            "FRAME-Y": 1,
            "BATTERY-PACK": 1,
            "CONTROLLER": 1,
            "WHEEL-SET": 1,
            "TIRE-KIT": 1,
            "CABLE-ASM": 2,
            "PAINT-KIT": 1
        }
    }
    
    # Test questions
    questions = [
        "How many X-Series scooters can we build next week with current inventory?",
        "Which parts are current bottlenecks for production?",
        "What happens if demand increases by 20%?",
        "Which suppliers should we prioritize for expedited delivery?"
    ]
    
    print("=" * 70)
    print("HUGO OPERATIONS QA - TEST SUITE")
    print("=" * 70)
    print()
    
    for i, question in enumerate(questions, 1):
        print(f"Question {i}/{len(questions)}: {question}")
        print("-" * 70)
        
        try:
            result = answer_operational_question(
                question=question,
                erp_data=erp_data,
                orders=orders,
                inventory=inventory,
                bom_data=bom_data,
                ollama_url="http://localhost:11434",
                model="gemma:2b"
            )
            
            if result.is_error:
                print(f"ERROR: {result.error}")
            else:
                # Display in formatted way
                print(result)
            
            print()
        
        except Exception as e:
            print(f"ERROR: {e}")
            print()


def example_single_question():
    """Example of answering a single operational question."""
    
    print("\n" + "=" * 70)
    print("SINGLE QUESTION EXAMPLE")
    print("=" * 70 + "\n")
    
    # Minimal data
    orders = [
        {"order_id": "O-001", "product_model": "Model-A", "quantity": 100, "due_date": "2025-01-31"}
    ]
    
    inventory = {
        "Component-X": 150,
        "Component-Y": 80,
        "Component-Z": 200
    }
    
    bom_data = {
        "Model-A": {
            "Component-X": 1,
            "Component-Y": 2,
            "Component-Z": 1
        }
    }
    
    question = "Can we fulfill the order for Model-A?"
    
    print(f"Question: {question}\n")
    
    result = answer_operational_question(
        question=question,
        orders=orders,
        inventory=inventory,
        bom_data=bom_data
    )
    
    print(result)
    print()
    
    # Show as dict for programmatic use
    print("\nAs dictionary:")
    print(result.to_dict())


if __name__ == "__main__":
    print("\nNOTE: This test requires Ollama running on localhost:11434")
    print("Start Ollama with: ollama run gemma:2b\n")
    
    # Run tests (comment out if Ollama not available)
    try:
        test_operational_questions()
        example_single_question()
    except Exception as e:
        print(f"Test failed (Ollama likely not running): {e}")
        print("\nTo run tests, start Ollama first:")
        print("  $ ollama run gemma:2b")
