from langgraph.graph import StateGraph, END
from jobmate_agent.agents.schema import AgentState
from jobmate_agent.agents.supervisor.node import supervisor_node
from jobmate_agent.agents.talker.node import talker_node
from jobmate_agent.agents.gap_analyst.graph import gap_analyst_graph
from jobmate_agent.agents.job_hunter.graph import job_hunter_graph
from jobmate_agent.agents.career_coach.graph import career_coach_graph

def create_master_graph():
    workflow = StateGraph(AgentState)

    # 1. Add Nodes
    workflow.add_node("Talker", talker_node)
    workflow.add_node("Reasoner_Supervisor", supervisor_node)
    
    # Add the specialists (The Reasoners)
    workflow.add_node("GapAnalyst", gap_analyst_graph)
    workflow.add_node("JobHunter", job_hunter_graph)
    workflow.add_node("CareerCoach", career_coach_graph)

    # 2. Entry Point
    workflow.set_entry_point("Talker")

    # 3. The "Brain Check" Edge
    def check_talker_decision(state):
        if state.get("next_step") == "CALL_REASONER":
            return "Reasoner_Supervisor"
        return END # If "REPLY", we are done! Talker handled it.

    workflow.add_conditional_edges(
        "Talker",
        check_talker_decision,
        {
            "Reasoner_Supervisor": "Reasoner_Supervisor",
            END: END
        }
    )

    # 4. The Reasoner Logic (Standard Supervisor Routing)
    # Note: We need to ensure the supervisor node returns "GapAnalyst", "JobHunter", etc.
    # The routing map matches the output of the supervisor LLM.
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

# --- EXAMPLE: How to run with stream_events (for real-time UI updates) ---
# async def demo_run():
#     inputs = {
#         "messages": [("user", "Analyze my resume for this python job")],
#         "user_id": "test_user",
#         "resume_id": "resume_123",
#         "current_job_id": "job_456"
#     }
#     
#     print("--- Starting Stream ---")
#     async for event in master_graph.astream_events(inputs, version="v2"):
#         kind = event["event"]
#         
#         # 1. Stream Tokens from LLMs
#         if kind == "on_chat_model_stream":
#             content = event["data"]["chunk"].content
#             if content:
#                 print(content, end="", flush=True)
#                 
#         # 2. Detect Tool Usage
#         elif kind == "on_tool_start":
#             print(f"\n[TOOL START] {event['name']}...")
#             
#         elif kind == "on_tool_end":
#             print(f"\n[TOOL END] {event['name']} -> {event['data'].get('output')}")
#             
#         # 3. Detect Agent Switches (Graph Node Changes)
#         elif kind == "on_chain_end":
#             # This helps visualize which node just finished (Supervisor vs GapAnalyst)
#             node_name = event["name"]
#             if node_name in ["supervisor", "GapAnalyst", "JobHunter", "CareerCoach"]:
#                 print(f"\n[NODE FINISHED] {node_name}")



