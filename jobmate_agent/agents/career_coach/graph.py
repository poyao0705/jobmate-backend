from langgraph.graph import StateGraph, START, END
from jobmate_agent.agents.career_coach.state import CareerCoachState
from jobmate_agent.agents.career_coach.nodes import (
    router_node,
    retrieval_node,
    grader_node,
    web_search_node,
    generate_node
)

def create_career_coach_graph():
    workflow = StateGraph(CareerCoachState)

    # 1. Add Nodes
    workflow.add_node("router", router_node)
    workflow.add_node("retriever", retrieval_node)
    workflow.add_node("grader", grader_node)
    workflow.add_node("web_search", web_search_node)
    workflow.add_node("generate", generate_node)

    # 2. Entry Point
    workflow.set_entry_point("router")

    # 3. Router Logic (Adaptive RAG)
    workflow.add_conditional_edges(
        "router",
        lambda x: x["source"],
        {
            "vectorstore": "retriever",
            "web_search": "web_search",
            "chat": "generate",
        },
    )

    # 4. Retriever -> Grader
    workflow.add_edge("retriever", "grader")

    # 5. Grader Logic (CRAG)
    workflow.add_conditional_edges(
        "grader",
        lambda x: x["grade"],
        {
            "yes": "generate",      # Good docs? Answer.
            "no": "web_search",     # Bad docs? Fallback to Web.
        },
    )

    # 6. Web Search -> Generate
    workflow.add_edge("web_search", "generate")

    # 7. Generate -> End
    workflow.add_edge("generate", END)

    return workflow.compile()

career_coach_graph = create_career_coach_graph()
