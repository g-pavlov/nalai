"""
Agent API implementation.

This module provides the concrete implementation of agent interactions,
handling conversation management, access control, and agent invocation.
"""

import logging
import uuid
from collections.abc import AsyncGenerator

from langchain_core.messages import BaseMessage
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command

from ..server.streaming import serialize_event
from ..services.checkpointing_service import get_checkpointer
from ..services.thread_access_control import get_thread_access_control
from .agent import (
    # Exceptions
    AccessDeniedError,
    Agent,
    ConversationInfo,
    ConversationNotFoundError,
    InvocationError,
    # Internal types
    ResumeDecision,
    ValidationError,
)

logger = logging.getLogger("nalai")


def create_user_scoped_conversation_id(user_id: str, conversation_id: str) -> str:
    """Create a user-scoped conversation ID for LangGraph checkpointing."""
    return f"user:{user_id}:{conversation_id}"


class LangGraphAgent(Agent):
    """Concrete implementation of agent interactions."""

    def __init__(
        self,
        workflow_graph: CompiledStateGraph,
    ):
        """Initialize the agent API."""
        self.agent = workflow_graph

    def _extract_user_id_from_config(self, config: dict) -> str:
        """Extract user_id from LangGraph config."""
        configurable = config.get("configurable", {})
        return configurable.get("user_id", "unknown")

    def _extract_conversation_id_from_config(self, config: dict) -> str:
        """Extract conversation_id from LangGraph config."""
        configurable = config.get("configurable", {})
        thread_id = configurable.get("thread_id", "")
        # Extract conversation_id from user-scoped thread_id: "user:{user_id}:{conversation_id}"
        if thread_id.startswith("user:"):
            parts = thread_id.split(":", 2)
            if len(parts) == 3:
                return parts[2]
        return thread_id

    def _update_config_with_conversation_id(
        self, config: dict, conversation_id: str
    ) -> dict:
        """Update config with a new conversation_id, creating user-scoped thread_id."""
        user_id = self._extract_user_id_from_config(config)
        user_scoped_conversation_id = create_user_scoped_conversation_id(
            user_id, conversation_id
        )

        updated_config = config.copy()
        if "configurable" not in updated_config:
            updated_config["configurable"] = {}
        updated_config["configurable"]["thread_id"] = user_scoped_conversation_id
        return updated_config

    def _create_config_for_conversation(
        self, user_id: str, conversation_id: str
    ) -> dict:
        """Create a new config for a specific conversation."""
        user_scoped_conversation_id = create_user_scoped_conversation_id(
            user_id, conversation_id
        )
        return {"configurable": {"thread_id": user_scoped_conversation_id}}

    async def _validate_conversation_access(
        self, conversation_id: str, config: dict
    ) -> None:
        """Validate conversation access for a user."""
        user_id = self._extract_user_id_from_config(config)

        # Validate that conversation_id is a UUID
        try:
            uuid.UUID(conversation_id)
        except ValueError as e:
            raise ValidationError(f"Invalid conversation ID format: {e}") from e

        # Validate access
        has_access = await get_thread_access_control().validate_thread_access(
            user_id, conversation_id
        )
        if not has_access:
            raise AccessDeniedError()

    def _create_conversation_info_from_thread_ownership(
        self,
        conversation_id: str,
        thread_ownership,
        status: str = "active",
        preview: str | None = None,
    ) -> ConversationInfo:
        """Create ConversationInfo from thread ownership data."""
        created_at = None
        last_accessed = None

        if thread_ownership:
            created_at = (
                thread_ownership.created_at.isoformat()
                if thread_ownership.created_at
                else None
            )
            last_accessed = (
                thread_ownership.last_accessed.isoformat()
                if thread_ownership.last_accessed
                else None
            )

        return ConversationInfo(
            conversation_id=conversation_id,
            created_at=created_at,
            last_accessed=last_accessed,
            status=status,
            preview=preview,
        )

    async def _get_conversation_status(self, config: dict) -> str:
        """Get conversation status from checkpoint state."""
        try:
            # Ensure config has proper structure for checkpointer
            checkpointer_config = config.copy()
            if "configurable" not in checkpointer_config:
                checkpointer_config["configurable"] = {}
            if "user_id" not in checkpointer_config["configurable"]:
                checkpointer_config["configurable"]["user_id"] = (
                    self._extract_user_id_from_config(config)
                )

            checkpoint_state = await get_checkpointer().aget(checkpointer_config)
            if checkpoint_state:
                if "interrupts" in checkpoint_state and checkpoint_state["interrupts"]:
                    return "interrupted"
                elif checkpoint_state.get("completed", False):
                    return "completed"
        except Exception as e:
            logger.warning(f"Failed to get conversation status: {e}")

        return "active"

    async def chat(
        self,
        messages: list[BaseMessage],
        conversation_id: str | None,
        config: dict,
    ) -> tuple[list[BaseMessage], ConversationInfo]:
        """Start a new conversation or continue an existing one based on conversation_id."""
        if conversation_id:
            # For existing conversations: validate access
            await self._validate_conversation_access(conversation_id, config)
            updated_config = config
        else:
            # For new conversations: create new UUID and thread ownership record
            conversation_id = str(uuid.uuid4())
            user_id = self._extract_user_id_from_config(config)

            await get_thread_access_control().create_thread(user_id, conversation_id)

            # Update config with new conversation_id
            updated_config = self._update_config_with_conversation_id(
                config, conversation_id
            )

        # Invoke agent
        try:
            agent_input = {"messages": messages}
            result = await self.agent.ainvoke(agent_input, config=updated_config)
        except Exception as e:
            logger.error(f"Agent invocation failed: {e}")
            raise InvocationError(context={"conversation_id": conversation_id}) from e

        # Extract conversation data from the result
        result_messages = (
            result.get("messages", messages) if isinstance(result, dict) else messages
        )

        # Get conversation info
        conversation_info = await self._get_conversation_info(
            conversation_id, updated_config
        )

        return result_messages, conversation_info

    async def chat_streaming(
        self,
        messages: list[BaseMessage],
        conversation_id: str | None,
        config: dict,
    ) -> tuple[AsyncGenerator[str, None], ConversationInfo]:
        """Stream conversation events."""
        if conversation_id:
            # For existing conversations: validate access
            await self._validate_conversation_access(conversation_id, config)
        else:
            # For new conversations: create new UUID and thread ownership record
            conversation_id = str(uuid.uuid4())
            user_id = self._extract_user_id_from_config(config)

            await get_thread_access_control().create_thread(user_id, conversation_id)

            # Update config with new conversation_id
            config = self._update_config_with_conversation_id(config, conversation_id)

        # Ensure config has proper structure for LangGraph
        if "configurable" not in config:
            config["configurable"] = {}

        # Ensure thread_id is set
        if "thread_id" not in config["configurable"]:
            user_id = self._extract_user_id_from_config(config)
            user_scoped_conversation_id = create_user_scoped_conversation_id(
                user_id, conversation_id
            )
            config["configurable"]["thread_id"] = user_scoped_conversation_id

        # Get conversation info
        conversation_info = await self._get_conversation_info(conversation_id, config)

        # Create streaming generator
        async def stream_generator():
            agent_input = {"messages": messages}
            async for chunk in self.agent.astream(
                agent_input, config, stream_mode=["updates", "messages"]
            ):
                serialized_chunk = serialize_event(chunk)
                if serialized_chunk:
                    yield serialized_chunk

        return stream_generator(), conversation_info

    async def load_conversation(
        self,
        conversation_id: str,
        config: dict,
    ) -> tuple[list[BaseMessage], ConversationInfo]:
        """Load conversation state."""
        # Validate access
        await self._validate_conversation_access(conversation_id, config)

        try:
            # Get the checkpoint state
            # Ensure config has proper structure for checkpointer
            checkpointer_config = config.copy()
            if "configurable" not in checkpointer_config:
                checkpointer_config["configurable"] = {}
            if "user_id" not in checkpointer_config["configurable"]:
                checkpointer_config["configurable"]["user_id"] = (
                    self._extract_user_id_from_config(config)
                )
            checkpoint_state = await get_checkpointer().aget(checkpointer_config)

            if not checkpoint_state:
                raise ConversationNotFoundError()

            # Extract messages (simplified - would need the full implementation)
            messages = self._extract_messages_from_checkpoint(checkpoint_state)

            # Get conversation info
            conversation_info = await self._get_conversation_info(
                conversation_id, config
            )

            return messages, conversation_info

        except (AccessDeniedError, ConversationNotFoundError):
            raise
        except Exception as e:
            logger.error(f"Failed to load conversation {conversation_id}: {e}")
            raise InvocationError(
                "Failed to load conversation",
                context={"conversation_id": conversation_id},
            ) from e

    def _extract_messages_from_checkpoint(
        self, checkpoint_state: dict
    ) -> list[BaseMessage]:
        """Extract messages from checkpoint state."""
        messages = []

        if checkpoint_state and "channel_values" in checkpoint_state:
            channel_values = checkpoint_state["channel_values"]
            if "messages" in channel_values:
                messages = channel_values["messages"]

        return messages

    async def list_conversations(
        self,
        config: dict,
    ) -> list[ConversationInfo]:
        """List user's conversations."""
        user_id = self._extract_user_id_from_config(config)

        try:
            # Get all threads owned by the user
            user_threads = await get_thread_access_control().list_user_threads(user_id)

            conversations = []

            for thread_ownership in user_threads:
                # The thread_id in ThreadOwnership is actually the conversation_id
                conversation_id = thread_ownership.thread_id

                # Create config for this conversation using the same structure as runtime config
                conversation_config = {
                    "configurable": {
                        "user_id": user_id,
                        "thread_id": create_user_scoped_conversation_id(
                            user_id, conversation_id
                        ),
                        "auth_token": "dev-token",  # Add auth token to match runtime config
                        "cache_disabled": False,  # Add cache setting to match runtime config
                    }
                }

                # Get the checkpoint state to extract preview
                checkpoint_state = await get_checkpointer().aget(conversation_config)

                if checkpoint_state is None:
                    # Still include the conversation even if no checkpoint state
                    # This allows conversations to be listed even if they don't have messages yet
                    pass

                # Extract preview from messages (simplified)
                preview = None
                if checkpoint_state and "channel_values" in checkpoint_state:
                    channel_values = checkpoint_state["channel_values"]
                    if "messages" in channel_values:
                        messages = channel_values["messages"]
                        if messages:
                            # Get the first message with content
                            for msg in messages:
                                if hasattr(msg, "content") and msg.content:
                                    preview = msg.content[:256]
                                    break

                # Create conversation summary using shared method
                conversation_info = (
                    self._create_conversation_info_from_thread_ownership(
                        conversation_id,
                        thread_ownership,
                        status="active",
                        preview=preview,
                    )
                )

                conversations.append(conversation_info)

            return conversations

        except Exception as e:
            logger.error(f"Failed to list conversations: {e}")
            raise InvocationError("Failed to list conversations") from e

    async def delete_conversation(
        self,
        conversation_id: str,
        config: dict,
    ) -> bool:
        """Delete a conversation."""
        # Validate access
        await self._validate_conversation_access(conversation_id, config)
        user_id = self._extract_user_id_from_config(config)

        try:
            # Delete the checkpoint state from LangGraph
            try:
                # Ensure config has proper structure for checkpointer
                checkpointer_config = config.copy()
                if "configurable" not in checkpointer_config:
                    checkpointer_config["configurable"] = {}
                if "user_id" not in checkpointer_config["configurable"]:
                    checkpointer_config["configurable"]["user_id"] = (
                        self._extract_user_id_from_config(config)
                    )
                await get_checkpointer().aput(checkpointer_config, None)
                logger.debug(
                    f"Cleared checkpoint state for conversation {conversation_id}"
                )
            except Exception as e:
                logger.warning(f"Failed to clear checkpoint state: {e}")

            # Delete the thread ownership record
            deleted = await get_thread_access_control().delete_thread(
                user_id, conversation_id
            )
            if not deleted:
                raise ConversationNotFoundError()

            logger.info(
                f"Successfully deleted conversation {conversation_id} for user {user_id}"
            )
            return True

        except (AccessDeniedError, ConversationNotFoundError):
            raise
        except Exception as e:
            logger.error(f"Failed to delete conversation {conversation_id}: {e}")
            raise InvocationError(
                "Failed to delete conversation",
                context={"conversation_id": conversation_id},
            ) from e

    async def resume_interrupted(
        self,
        resume_decision: ResumeDecision,
        conversation_id: str,
        config: dict,
    ) -> tuple[list[BaseMessage], ConversationInfo]:
        """Resume an interrupted conversation."""
        # Validate access
        await self._validate_conversation_access(conversation_id, config)

        # Invoke agent with resume command using ResumeDecision directly
        try:
            result = await self.agent.ainvoke(
                Command(resume=[resume_decision.model_dump()]), config=config
            )
        except Exception as e:
            logger.error(f"Agent resume invocation failed: {e}")
            raise InvocationError(
                "Failed to resume conversation",
                context={"conversation_id": conversation_id},
            ) from e

        # Extract conversation data from the result
        result_messages = result.get("messages", []) if isinstance(result, dict) else []

        # Get conversation info
        conversation_info = await self._get_conversation_info(conversation_id, config)

        return result_messages, conversation_info

    async def resume_interrupted_streaming(
        self,
        resume_decision: ResumeDecision,
        conversation_id: str,
        config: dict,
    ) -> tuple[AsyncGenerator[str, None], ConversationInfo]:
        """Stream resume conversation events."""
        # Validate access
        await self._validate_conversation_access(conversation_id, config)

        # Get conversation info
        conversation_info = await self._get_conversation_info(conversation_id, config)

        # Create streaming generator using ResumeDecision directly
        async def stream_generator():
            resume_command = [resume_decision.model_dump()]
            async for chunk in self.agent.astream(
                Command(resume=resume_command),
                config,
                stream_mode=["updates", "messages"],
            ):
                serialized_chunk = serialize_event(chunk)
                if serialized_chunk:
                    yield serialized_chunk

        return stream_generator(), conversation_info

    async def _get_conversation_info(
        self, conversation_id: str, config: dict
    ) -> ConversationInfo:
        """Get conversation info for a conversation."""
        try:
            # Get thread ownership information
            thread_ownership = await get_thread_access_control().get_thread_ownership(
                conversation_id
            )

            # Get conversation status
            status = await self._get_conversation_status(config)

            # Get the checkpoint state to extract preview
            # Ensure config has proper structure for checkpointer
            checkpointer_config = config.copy()
            if "configurable" not in checkpointer_config:
                checkpointer_config["configurable"] = {}
            if "user_id" not in checkpointer_config["configurable"]:
                checkpointer_config["configurable"]["user_id"] = (
                    self._extract_user_id_from_config(config)
                )
            checkpoint_state = await get_checkpointer().aget(checkpointer_config)

            # Extract preview from messages (same logic as list_conversations)
            preview = None
            if checkpoint_state and "channel_values" in checkpoint_state:
                channel_values = checkpoint_state["channel_values"]
                if "messages" in channel_values:
                    messages = channel_values["messages"]
                    if messages:
                        # Get the first message with content
                        for msg in messages:
                            if hasattr(msg, "content") and msg.content:
                                preview = msg.content[:256]
                                break

            # Create conversation info using shared method
            return self._create_conversation_info_from_thread_ownership(
                conversation_id, thread_ownership, status=status, preview=preview
            )

        except Exception as e:
            logger.error(f"Failed to get conversation info {conversation_id}: {e}")
            # Return basic info even if metadata retrieval fails
            return ConversationInfo(
                conversation_id=conversation_id,
                created_at=None,
                last_accessed=None,
                status="active",
                preview=None,
            )
