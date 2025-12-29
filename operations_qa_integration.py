"""
Hugo Operations QA - Integration Guide

Shows how to integrate the operations question answering module into Hugo.
"""

from services.operations_qa import answer_operational_question


def example_integration_with_hugo_agent():
    """
    Example of integrating operations QA into the Hugo agent workflow.
    
    This shows how to add question-answering capabilities to the main agent.
    """
    
    # In the HugoAgent class, add this method:
    
    def answer_operational_question_interactive(self, question: str):
        """
        Answer an operational question using Ollama reasoning.
        
        Example questions:
        - "How many scooters can we build next week?"
        - "Which parts are bottlenecks?"
        - "What if demand increases by 20%?"
        
        Args:
            question: Operational analysis question
        
        Returns:
            OperationalAnswer with reasoning and constraints
        """
        from services.operations_qa import answer_operational_question
        
        # Gather current operational data
        erp_data = self._get_erp_data()
        orders = self._get_active_orders()
        inventory = self._get_inventory_levels()
        bom_data = self._get_bom_data()
        
        # Ask Ollama
        result = answer_operational_question(
            question=question,
            erp_data=erp_data,
            orders=orders,
            inventory=inventory,
            bom_data=bom_data
        )
        
        return result
    
    def _get_erp_data(self):
        """Fetch ERP data from system."""
        # Implementation depends on your ERP system
        return {
            "production_capacity_weekly": 500,
            "lead_time_weeks": 2,
            "current_production_rate": 350
        }
    
    def _get_active_orders(self):
        """Fetch active orders."""
        # Connect to order management system
        return []
    
    def _get_inventory_levels(self):
        """Fetch current inventory."""
        # Connect to warehouse management system
        return {}
    
    def _get_bom_data(self):
        """Fetch bill of materials."""
        # Connect to product database
        return {}


# USAGE EXAMPLES
# ==============

def example_1_production_capacity():
    """How many units can we produce?"""
    
    result = answer_operational_question(
        question="How many X-Series scooters can we build next week?",
        orders=[
            {"order_id": "O-001", "quantity": 100, "product": "X-Series"},
            {"order_id": "O-002", "quantity": 75, "product": "X-Series"}
        ],
        inventory={
            "MOTOR": 200,
            "FRAME-X": 150,
            "BATTERY": 180,
            "WHEEL-SET": 200
        },
        bom_data={
            "X-Series": {
                "MOTOR": 1,
                "FRAME-X": 1,
                "BATTERY": 1,
                "WHEEL-SET": 1
            }
        }
    )
    
    print("Production Capacity Question")
    print(result)
    # Output might be:
    # "We can build 150 X-Series scooters next week.
    #  Limited by FRAME-X inventory at 150 units.
    #  Constraints: Supply lead time for frames is 2 weeks
    #  Bottlenecks: Frame availability"


def example_2_bottleneck_analysis():
    """What's limiting production?"""
    
    result = answer_operational_question(
        question="Which parts are current bottlenecks for production?",
        inventory={
            "MOTOR-A": 450,
            "MOTOR-B": 200,
            "FRAME-X": 250,
            "FRAME-Y": 180,
            "BATTERY": 120,  # Low!
            "CONTROLLER": 380,
            "WHEEL-SET": 320
        },
        erp_data={
            "production_rate": 350,
            "lead_time_battery": 3,
            "lead_time_frame": 2
        }
    )
    
    print("\nBottleneck Analysis")
    print(result)
    # Output might identify BATTERY as bottleneck


def example_3_demand_impact():
    """What if demand increases?"""
    
    result = answer_operational_question(
        question="What happens if customer demand increases by 20%?",
        orders=[
            {"order_id": "O-1", "quantity": 100},
            {"order_id": "O-2", "quantity": 80}
        ],
        inventory={
            "PART-A": 300,
            "PART-B": 150,
            "PART-C": 200
        },
        erp_data={
            "production_capacity": 500,
            "current_demand": 180
        }
    )
    
    print("\nDemand Scenario")
    print(result)
    # Output discusses capacity impact, supply constraints


def example_4_supplier_risk():
    """Which suppliers to prioritize?"""
    
    result = answer_operational_question(
        question="Which suppliers should we expedite orders from to manage risk?",
        orders=[
            {"order_id": "O-1", "due_date": "2025-01-20", "priority": "high"},
            {"order_id": "O-2", "due_date": "2025-01-31", "priority": "high"}
        ],
        inventory={
            "CRITICAL-PART": 50,  # Very low
            "NORMAL-PART": 200
        },
        erp_data={
            "supplier_lead_times": {
                "SUPPLIER-A": 2,
                "SUPPLIER-B": 3,
                "SUPPLIER-C": 1
            }
        }
    )
    
    print("\nSupplier Risk Analysis")
    print(result)
    # Output identifies high-risk suppliers


# INTEGRATION PATTERNS
# ====================

"""
Pattern 1: Batch Analysis
=========================

for question in strategic_questions:
    result = answer_operational_question(question, erp_data, orders, inventory, bom)
    store_analysis_result(result)

Pattern 2: Real-time Alerts
===========================

if detected_delivery_delay:
    question = f"How does this delay impact production of {affected_product}?"
    result = answer_operational_question(question, ...)
    if result.bottlenecks:
        alert_operations_team(result.bottlenecks)

Pattern 3: What-If Scenario Analysis
======================================

for demand_increase in [10, 20, 30]:
    q = f"What if demand increases by {demand_increase}%?"
    result = answer_operational_question(q, ...)
    scenario_results[demand_increase] = result

Pattern 4: Dashboard Integration
=================================

@app.route("/api/operations/question", methods=["POST"])
def ask_operations_question(request):
    question = request.json["question"]
    result = answer_operational_question(
        question=question,
        erp_data=get_erp_data(),
        orders=get_orders(),
        inventory=get_inventory(),
        bom_data=get_bom()
    )
    return {
        "question": result.question,
        "answer": result.answer,
        "constraints": result.constraints,
        "bottlenecks": result.bottlenecks,
        "confidence": result.confidence
    }
"""

if __name__ == "__main__":
    print("Operations QA Integration Guide\n")
    print("Run with Ollama running on localhost:11434")
    print()
    
    try:
        example_1_production_capacity()
        example_2_bottleneck_analysis()
        example_3_demand_impact()
        example_4_supplier_risk()
    except Exception as e:
        print(f"\nNote: Examples require Ollama running")
        print(f"Error: {e}")
