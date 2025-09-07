import logging

from fastapi import FastAPI
from langgraph.graph.state import StateGraph

from nalai.config import settings
from nalai.core.factory import create_agent
from nalai.server.api_agent import create_agent_api
from nalai.server.api_conversations import create_conversations_api

logger = logging.getLogger("nalai")


def create_agent_routes(app: FastAPI, workflow: StateGraph) -> None:
    agent = create_agent(workflow)
    create_agent_api(app, agent)
    logger.info("Agent API endpoint enabled")

    if settings.conversations_endpoint_enabled:
        create_conversations_api(app, agent)
        logger.info("Conversations API endpoint enabled")

    logger.info("Agent routes created")
