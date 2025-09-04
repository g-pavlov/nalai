from .agent import Agent
from .services import (
    APIService,
    AuditService,
    CacheService,
    CheckpointingService,
    ModelService,
)


def create_agent(
    checkpointing_service: CheckpointingService | None = None,
    cache_service: CacheService | None = None,
    model_service: ModelService | None = None,
    api_service: APIService | None = None,
    audit_service: AuditService | None = None,
) -> Agent:
    """
    Create and return an agent.

    Args:
        checkpointing_service: Checkpointing service
        cache_service: Cache service
        model_service: Model service
        api_service: API service
        audit_service: Audit service

    Returns:
        Agent: Agent for business operations
    """
    # Import implementation details only when needed
    from .internal.lc_agent import LangGraphAgent
    from .internal.workflow import create_and_compile_workflow
    from .internal.workflow_nodes import WorkflowNodes

    # Resolve dependencies with fallback to default services
    if checkpointing_service is None:
        from ..services.factory import get_checkpointing_service

        checkpointing_service = get_checkpointing_service()

    if cache_service is None:
        from ..services.factory import get_cache_service

        cache_service = get_cache_service()

    if model_service is None:
        from ..services.factory import get_model_service

        model_service = get_model_service()

    if api_service is None:
        from ..services.factory import get_api_service

        api_service = get_api_service()

    if audit_service is None:
        from ..services.factory import get_audit_service

        audit_service = get_audit_service()

    # Create workflow nodes with injected services
    workflow_nodes = WorkflowNodes()

    # Get memory store from checkpointing service
    memory_store = checkpointing_service.get_checkpointer()

    # Create and compile workflow
    workflow = create_and_compile_workflow(
        workflow_nodes=workflow_nodes, memory_store=memory_store
    )

    # Create and return the agent
    return LangGraphAgent(workflow_graph=workflow, audit_service=audit_service)
