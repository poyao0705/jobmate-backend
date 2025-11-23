from langgraph.graph import StateGraph, START, END
from jobmate_agent.agents.schema import AgentState

# Placeholder for CareerCoach
def career_coach_node(state: AgentState):
    return {"messages": ["CareerCoach (Placeholder): I can help you learn skills and prepare for interviews."]}

workflow = StateGraph(AgentState)
workflow.add_node("career_coach", career_coach_node)
workflow.add_edge(START, "career_coach")
workflow.add_edge("career_coach", END)

career_coach_graph = workflow.compile()
