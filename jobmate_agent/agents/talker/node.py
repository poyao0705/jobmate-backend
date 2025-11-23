from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from jobmate_agent.agents.schema import AgentState

# The Talker's job is to be the "Face" and decide if the "Brain" is needed.
TALKER_SYSTEM_PROMPT = """
You are 'JobMate', a helpful AI career assistant.
Your goal is to chat with the user naturally.

DECISION LOGIC:
1. If the user says "Hi", "Thanks", or engages in small talk -> REPLY directly.
2. If the user asks to DO something (Find jobs, Analyze resume, Learn skill) -> DELEGATE to the Reasoner.

OUTPUT FORMAT:
Return JSON with two fields:
- "response": (String) The text to show the user (if replying directly).
- "action": (String) Either "REPLY" or "CALL_REASONER".
"""

def talker_node(state: AgentState):
    # Use a Fast Model (Mini) for speed/cost
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.5)
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", TALKER_SYSTEM_PROMPT),
        ("placeholder", "{messages}"),
    ])
    
    # Structured output to force a binary decision
    chain = prompt | llm.with_structured_output(
        schema={
            "type": "object",
            "properties": {
                "response": {"type": "string"},
                "action": {"type": "string", "enum": ["REPLY", "CALL_REASONER"]}
            }
        }
    )
    
    result = chain.invoke({"messages": state["messages"]})
    
    # If replying, we append the response to messages so the user sees it.
    # If calling reasoner, we might not want to append a response yet, or maybe a "Thinking..." message.
    # For now, we'll store the response in a separate key or just append it if it exists.
    
    updates = {
        "next_step": result["action"]
    }
    
    if result["action"] == "REPLY" and result["response"]:
         updates["messages"] = [result["response"]]
         
    return updates
