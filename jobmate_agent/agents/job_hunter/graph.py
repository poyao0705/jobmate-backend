from langgraph.graph import StateGraph, START, END
from jobmate_agent.agents.schema import AgentState

# Minimal placeholder for JobHunter
def job_hunter_node(state: AgentState):
    return {"messages": ["JobHunter: I am a placeholder agent."]}

workflow = StateGraph(AgentState)
workflow.add_node("job_hunter", job_hunter_node)
workflow.add_edge(START, "job_hunter")
workflow.add_edge("job_hunter", END)

job_hunter_graph = workflow.compile()
