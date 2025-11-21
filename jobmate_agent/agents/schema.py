# The global state of the agent
import operator
from typing import TypedDict, Annotated, List, Optional, Union
from langchain_core.messages import AnyMessage

class AgentState(TypedDict):
    """
    The Global State Object.
    This dictionary is passed between the Supervisor and all Sub-Agents.
    """

    # --- Chat History ---
    # 'operator.add' ensures that new messages are appended to the history
    # rather than overwriting it.
    messages: Annotated[List[AnyMessage], operator.add]

    # --- Routing Logic ---
    # The Supervisor writes to this field to decide who goes next.
    # Options: "GapAnalyst", "JobHunter", "CareerCoach", "FINISH"
    next_agent: str

    # --- Shared Business Context ---
    # These fields allow agents to be "Context Aware" without asking the user again.
    # Populated by the Frontend (Next.js) or extracted by agents.
    user_id: str
    resume_id: Optional[int]      # The resume currently being discussed
    current_job_id: Optional[int] # The job the user is looking at