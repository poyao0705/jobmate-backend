# app/agents/gap_analyst/nodes/tools.py
from langgraph.prebuilt import ToolNode
from jobmate_agent.tools.report_tools import get_or_create_gap_report
from jobmate_agent.tools.job_tools import get_job_details

# 1. Define the list of tools for THIS agent
analyst_tools = [
    get_or_create_gap_report,
    get_job_details
]

# 2. Create the Node
# This prebuilt node will execute the function when the LLM requests it.
tool_node = ToolNode(analyst_tools)