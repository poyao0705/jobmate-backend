from langchain_core.tools import tool

@tool
def generate_learning_path(skill: str):
    """
    Generates a structured, recursive dependency tree for learning a specific skill.
    Returns a JSON object with 'topic' and 'prerequisites'.
    """
    # Placeholder implementation
    return {
        "topic": skill,
        "prerequisites": [
            {"topic": "Placeholder Prerequisite 1", "prerequisites": []},
            {"topic": "Placeholder Prerequisite 2", "prerequisites": []}
        ]
    }
