# app/agents/gap_analyst/nodes/agent.py
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from jobmate_agent.agents.schema import AgentState
from jobmate_agent.agents.gap_analyst.nodes.tool_node import analyst_tools

# --- THE SYSTEM PROMPT ---
# This determines how the agent interprets the data.

SYSTEM_PROMPT = """You are a Gap Analyst. Your job is to compare the user's resume against a job description.

INSTRUCTIONS:
1. If you have a 'current_job_id', FIRST call `get_job_details` to fetch the full job description.
2. Then, call `get_or_create_gap_report` to analyze the fit.
3. Present the findings clearly:
   - Match Score
   - Missing Skills
   - Actionable Advice
4. ALWAYS ask the user: "Would you like me to generate a personalized learning plan for these skills?"

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