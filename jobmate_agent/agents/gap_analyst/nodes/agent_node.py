# app/agents/gap_analyst/nodes/agent.py
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from jobmate_agent.agents.schema import AgentState
from jobmate_agent.agents.gap_analyst.nodes.tool_node import analyst_tools

# --- THE SYSTEM PROMPT ---
# This determines how the agent interprets the data.
SYSTEM_PROMPT = """
You are an expert Technical Recruiter and Career Gap Analyst.
Your goal is to help the user understand how well they fit a specific job description.

PRIMARY INSTRUCTIONS:
1. If the user asks "Do I fit this job?" or similar, call the 'get_or_create_gap_report' tool first.
2. Do not guess. You must rely on the data returned by the tool.
3. When explaining the report:
   - Be encouraging but honest.
   - Highlight the 'Critical Missing Skills' first.
   - Suggest specific learning actions for the missing skills.
4. If the user asks about a skill you didn't find, trust the tool's output over the user's claim, but be polite (e.g., "I didn't see that in the parsed resume data...").

CONTEXT:
Current User ID: {user_id}
Current Resume ID: {resume_id}
Target Job ID: {current_job_id}
"""

def agent_node(state: AgentState):
    """
    The Brain of the Gap Analyst.
    """
    # 0. Check for Missing Context (Conversational Logic)
    # If we don't have a job to analyze, ask for it instead of calling tools.
    current_job_id = state.get("current_job_id")
    if not current_job_id or current_job_id == "None":
        return {
            "messages": [
                "I'm ready to analyze your fit, but I need to know which job you're targeting. "
                "Please provide a Job ID or paste the job description."
            ]
        }

    # 1. Initialize LLM
    llm = ChatOpenAI(model="gpt-4o", temperature=0)
    
    # 2. Bind Tools
    # This tells the LLM: "Here are the functions you can call."
    llm_with_tools = llm.bind_tools(analyst_tools)

    # 3. Format Prompt with State Data
    # We inject the IDs from the state so the prompt knows context
    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        ("placeholder", "{messages}"),
    ])
    
    # 4. Run the Chain
    chain = prompt | llm_with_tools
    
    result = chain.invoke({
        "messages": state["messages"],
        "user_id": state.get("user_id", "unknown"),
        "resume_id": state.get("resume_id", "unknown"),
        "current_job_id": state.get("current_job_id", "unknown")
    })

    return {"messages": [result]}