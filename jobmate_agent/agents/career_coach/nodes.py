from typing import Literal
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langchain_core.pydantic_v1 import BaseModel, Field
from jobmate_agent.agents.career_coach.state import CareerCoachState
from jobmate_agent.tools.skill_tools import search_skill_knowledge
from jobmate_agent.tools.web_tools import web_search
from jobmate_agent.tools.learning_tools import generate_learning_path

# --- 1. ROUTER NODE ---
class RouteQuery(BaseModel):
    """Route a user query to the most relevant datasource."""
    datasource: Literal["vectorstore", "web_search", "chat"] = Field(
        ...,
        description="Given a user question choose to route it to web search, vectorstore, or just chat."
    )

def router_node(state: CareerCoachState):
    """
    Determines where to route the user's question.
    """
    print("---ROUTER---")
    question = state["messages"][-1].content
    
    system = """You are an expert at routing a user question to a vectorstore or web search.
    The vectorstore contains documents related to technical skills (Python, React, etc).
    Use the web search for questions about current events, job market trends, or specific learning courses.
    Use 'chat' for general conversation OR for generating learning plans/paths."""
    
    route_prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system),
            ("human", "{question}"),
        ]
    )
    
    llm = ChatOpenAI(model="gpt-4o", temperature=0)
    structured_llm_router = llm.with_structured_output(RouteQuery)
    router = route_prompt | structured_llm_router
    
    source = router.invoke({"question": question})
    
    return {"source": source.datasource, "question": question}

# --- 2. RETRIEVER NODE ---
def retrieval_node(state: CareerCoachState):
    """
    Retrieve documents from the vector store.
    """
    print("---RETRIEVE---")
    question = state["question"]
    
    # We use the tool directly here for simplicity, but in a real node we might want more control
    # The tool returns a string, we want to store it as a list of docs or a single string doc
    documents = search_skill_knowledge.invoke(question)
    
    return {"documents": [documents], "question": question}

# --- 3. GRADER NODE (CRAG) ---
class GradeDocuments(BaseModel):
    """Binary score for relevance check on retrieved documents."""
    binary_score: str = Field(description="Documents are relevant to the question, 'yes' or 'no'")

def grader_node(state: CareerCoachState):
    """
    Determines whether the retrieved documents are relevant to the question.
    """
    print("---CHECK RELEVANCE---")
    question = state["question"]
    documents = state["documents"]
    
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    structured_llm_grader = llm.with_structured_output(GradeDocuments)
    
    system = """You are a grader assessing relevance of a retrieved document to a user question. \n 
    If the document contains keyword(s) or semantic meaning related to the user question, grade it as relevant. \n
    Give a binary score 'yes' or 'no' score to indicate whether the document is relevant to the question."""
    
    grade_prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system),
            ("human", "Retrieved document: \n\n {document} \n\n User question: {question}"),
        ]
    )
    
    grader = grade_prompt | structured_llm_grader
    
    # We grade the combined documents string
    score = grader.invoke({"question": question, "document": documents[0]})
    
    return {"grade": score.binary_score}

# --- 4. WEB SEARCH NODE ---
def web_search_node(state: CareerCoachState):
    """
    Web search based on the re-phrased question.
    """
    print("---WEB SEARCH---")
    question = state["question"]
    
    docs = web_search.invoke(question)
    
    # We format the web result as a "document"
    return {"documents": [docs], "question": question}

# --- 5. GENERATE NODE ---
def generate_node(state: CareerCoachState):
    """
    Generate answer.
    """
    print("---GENERATE---")
    question = state["question"]
    documents = state.get("documents", [])
    
    # If we have documents, use them. If not (Chat mode), just chat.
    context = documents[0] if documents else "No context provided."
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a helpful Career Coach. Use the following context to answer the user's question. If the context is empty or irrelevant, answer from your own knowledge but mention that you didn't find specific internal data.\n\nIf the user asks for a learning path or curriculum, use the `generate_learning_path` tool.\nIf the user asks to save a learning path, use the `save_learning_path` tool."),
        ("human", "Context: {context} \n\n Question: {question}"),
    ])
    
    # Bind the learning path tool
    from jobmate_agent.tools.learning_tools import generate_learning_path, save_learning_path
    llm = ChatOpenAI(model="gpt-4o", temperature=0)
    llm_with_tools = llm.bind_tools([generate_learning_path, save_learning_path])
    
    chain = prompt | llm_with_tools
    
    response = chain.invoke({"question": question, "context": context})
    
    return {"messages": [response]}
