from langgraph.graph import StateGraph, END
from .schema import AgentState
from .supervisor import supervisor_node

# --- IMPORT SUB-AGENTS ---
from jobmate_agent.agents.gap_analyst.graph import gap_analyst_graph
from jobmate_agent.agents.job_hunter.graph import job_hunter_graph
from jobmate_agent.agents.career_coach.graph import career_coach_graph

def create_master_graph():
    """
    Constructs the top-level Supervisor Graph.
    """
    workflow = StateGraph(AgentState)

    # --- 1. Add The Supervisor Node ---
    workflow.add_node("supervisor", supervisor_node)

    # --- 2. Add Worker Nodes ---
    # In LangGraph, a compiled graph can be a node in another graph!
    
    workflow.add_node("GapAnalyst", gap_analyst_graph)
    workflow.add_node("JobHunter", job_hunter_graph)
    workflow.add_node("CareerCoach", career_coach_graph)

    # --- 3. Define Entry Point ---
    # The conversation always starts with the Supervisor deciding who goes first.
    workflow.set_entry_point("supervisor")

    # --- 4. Define Routing Logic (The Switch) ---
    # This map matches the 'next_agent' string to the Node Name.
    routing_map = {
        "GapAnalyst": "GapAnalyst",
        "JobHunter": "JobHunter",
        "CareerCoach": "CareerCoach",
        "FINISH": END
    }

    workflow.add_conditional_edges(
        "supervisor",                # Start at Supervisor
        lambda x: x["next_agent"],   # Read this field
        routing_map                  # Go to matching node
    )

    # --- 5. Define Return Logic (The Loop) ---
    # After a worker finishes, ALWAYS go back to Supervisor.
    # The Supervisor checks if the job is done or if another worker is needed.
    
    workflow.add_edge("GapAnalyst", "supervisor")
    workflow.add_edge("JobHunter", "supervisor")
    workflow.add_edge("CareerCoach", "supervisor")

    return workflow.compile()

# Initialize the runnable graph
master_graph = create_master_graph()