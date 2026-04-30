from typing import TypedDict, Optional, List, Dict, Any
from src.schema.user_schema import CurrentUser
from src.Database.connection_manager import ConnectionManager
from src.services.vector_db_service import VectorDBService

class AgentState(TypedDict, total=False):
    user_id: str
    client_id: str
    current_user: CurrentUser
    
    user_query: str
    
    connection_manager: ConnectionManager
    vectordb: VectorDBService

    execution_plan: List[Dict[str, Any]]
    execution_index: int
    execution_trace: List[str]
    
    rag_agent_results: List[Dict[str, Any]]
    sql_agent_results: List[Dict[str, Any]]
    nosql_agent_results: List[Dict[str, Any]]

    final_response: Optional[str]