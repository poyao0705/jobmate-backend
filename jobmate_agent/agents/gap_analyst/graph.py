# Agent graph for langgraph.
# app/agents/gap_analyst/graph.py
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import tools_condition

from jobmate_agent.agents.schema import AgentState
from jobmate_agent.agents.gap_analyst.nodes.agent_node import agent_node
from jobmate_agent.agents.gap_analyst.nodes.tool_node import tool_node

# 1. Initialize Graph
workflow = StateGraph(AgentState)

# 2. Add Nodes
workflow.add_node("analyst_brain", agent_node)
workflow.add_node("analyst_tools", tool_node)

# 3. Define Flow
# Start at the Brain
workflow.add_edge(START, "analyst_brain")

# 4. Conditional Logic (The Loop)
# If the Brain calls a tool -> Go to Tools
# If the Brain replies with text -> Go to END (back to Supervisor)
workflow.add_conditional_edges(
    "analyst_brain",
    tools_condition,
    {
        "tools": "analyst_tools",
        "__end__": END
    }
)

# 5. Close the Loop
# After tools finish, always go back to Brain to interpret results
workflow.add_edge("analyst_tools", "analyst_brain")

# 6. Compile
gap_analyst_graph = workflow.compile()