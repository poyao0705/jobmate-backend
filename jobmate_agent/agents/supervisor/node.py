from typing import Literal
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from jobmate_agent.agents.schema import AgentState

# Define the valid workers.
# 'FINISH' means the system should stop and return the response to the user.
WORKER_OPTIONS = Literal["GapAnalyst", "JobHunter", "CareerCoach", "FINISH"]

# The System Prompt instructs the Supervisor on WHO handles WHAT.
SUPERVISOR_SYSTEM_PROMPT = """
You are the Supervisor for the 'JobMate' AI system.
Your job is to route the conversation to the correct specialized worker.

WORKER DESCRIPTIONS:
1. GapAnalyst:
   - Use for: Skill gap analysis, resume reviews, "Do I fit this job?", extracting skills.
   - Triggers: "Analyze my resume", "Compare me to this job", "What am I missing?".

2. JobHunter:
   - Use for: Searching for new jobs, saving jobs, filtering listings.
   - Triggers: "Find me python jobs", "Save this job", "Look for remote work".

3. CareerCoach:
   - Use for: General advice, soft skills, interview prep, motivation.
   - Triggers: "How do I negotiate salary?", "Mock interview", "I feel stuck".

RULES:
- If the specialized worker has just finished their task and responded, route to 'FINISH' to give control back to the user.
- If the user's request is ambiguous, default to 'CareerCoach'.
"""

def supervisor_node(state: AgentState) -> dict:
    """
    The Supervisor Node function.
    1. Looks at the conversation history.
    2. Decides which worker should act next.
    3. Updates the 'next_agent' field in the state.
    """
    
    # 1. Initialize LLM (Use a fast/cheap model for routing)
    # Ensure OPENAI_API_KEY is set in your environment
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

    # 2. Construct the Prompt
    prompt = ChatPromptTemplate.from_messages([
        ("system", SUPERVISOR_SYSTEM_PROMPT),
        ("placeholder", "{messages}"), # Inserts chat history automatically
        (
            "system", 
            "Given the conversation above, who should act next? "
            "Select one of: {options}"
        ),
    ]).partial(options=str(WORKER_OPTIONS.__args__))

    # 3. Force Structured Output
    # We use .with_structured_output to ensure the LLM returns valid JSON/Choice
    # instead of a random sentence.
    chain = prompt | llm.with_structured_output(schema={"type": "string", "enum": list(WORKER_OPTIONS.__args__)})

    # 4. Execute
    # We pass the messages from the state
    decision = chain.invoke({"messages": state["messages"]})

    # Handle edge case where LLM might return an object wrapper
    next_step = decision if isinstance(decision, str) else decision.get("next_agent", "FINISH")

    print(f"--- Supervisor Decision: {next_step} ---")
    return {"next_agent": next_step}