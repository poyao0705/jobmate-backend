from langgraph.graph import StateGraph, START, END
from jobmate_agent.agents.schema import AgentState

# Placeholder for JobAgent
def job_agent_node(state: AgentState):
    return {"messages": ["JobAgent (Placeholder): I can help you find jobs, analyze your fit, and apply."]}

workflow = StateGraph(AgentState)
workflow.add_node("job_agent", job_agent_node)
workflow.add_edge(START, "job_agent")
workflow.add_edge("job_agent", END)

job_agent_graph = workflow.compile()
