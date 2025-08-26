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
from .checkpoints import get_checkpoints

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
        self.checkpoints = get_checkpoints()

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

    def _create_conversation_config(self, user_id: str, conversation_id: str) -> dict:
        """Create a standardized config for a conversation."""
        user_scoped_conversation_id = create_user_scoped_conversation_id(
            user_id, conversation_id
        )
        return {"configurable": {"thread_id": user_scoped_conversation_id}}

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

    def _ensure_config_structure(self, config: dict, conversation_id: str) -> dict:
        """Ensure config has proper structure for LangGraph operations."""
        if "configurable" not in config:
            config["configurable"] = {}

        # Ensure thread_id is set
        if "thread_id" not in config["configurable"]:
            user_id = self._extract_user_id_from_config(config)
            user_scoped_conversation_id = create_user_scoped_conversation_id(
                user_id, conversation_id
            )
            config["configurable"]["thread_id"] = user_scoped_conversation_id

        return config

    def _validate_conversation_id_format(self, conversation_id: str) -> None:
        """Validate conversation_id is a valid UUID."""
        try:
            uuid.UUID(conversation_id)
        except ValueError as e:
            raise ValidationError(f"Invalid conversation ID format: {e}") from e

    def _extract_audit_context(self, config: dict) -> dict:
        """Extract audit context from config."""
        configurable = config.get("configurable", {})
        return {
            "ip_address": configurable.get("ip_address"),
            "user_agent": configurable.get("user_agent"),
            "session_id": configurable.get("session_id"),
            "request_id": configurable.get("request_id"),
        }

    async def _audit_event(
        self,
        user_id: str,
        conversation_id: str,
        action: str,
        success: bool,
        config: dict,
        metadata: dict | None = None,
        checkpoint_id: str | None = None,
    ):
        """Lean audit event logging with configurable failure handling."""
        try:
            audit_context = self._extract_audit_context(config)

            # Use generic audit utility for easy future refactoring
            from ..services.audit_utils import log_conversation_access_event

            await log_conversation_access_event(
                user_id=user_id,
                conversation_id=conversation_id,
                action=action,
                success=success,
                metadata=metadata,
                ip_address=audit_context.get("ip_address"),
                user_agent=audit_context.get("user_agent"),
                session_id=audit_context.get("session_id"),
                request_id=audit_context.get("request_id"),
            )
        except Exception as e:
            # Configurable behavior: log failure and continue operation
            logger.warning(f"Audit logging failed for {action}: {e}")
            # TODO: Make this configurable via settings

    async def _validate_and_audit_access(
        self, user_id: str, conversation_id: str, action: str, config: dict
    ) -> None:
        """Validate user access and audit the attempt."""
        # Validate conversation_id format if provided
        if conversation_id:
            self._validate_conversation_id_format(conversation_id)

        # Validate access
        has_access = await self.checkpoints.validate_user_access(
            user_id, conversation_id
        )

        # Audit access attempt
        await self._audit_event(user_id, conversation_id, action, has_access, config)

        if not has_access:
            raise AccessDeniedError()

    async def _create_new_conversation(
        self, user_id: str, config: dict
    ) -> tuple[str, dict]:
        """Create a new conversation and return conversation_id and updated config."""
        conversation_id = str(uuid.uuid4())
        await self.checkpoints.create_conversation(user_id, conversation_id)

        # Audit conversation creation
        await self._audit_event(user_id, conversation_id, "created", True, config)

        # Update config with new conversation_id
        updated_config = self._update_config_with_conversation_id(
            config, conversation_id
        )
        return conversation_id, updated_config

    def _create_conversation_info_from_metadata(
        self,
        conversation_id: str,
        metadata: dict,
        status: str = "active",
        preview: str | None = None,
    ) -> ConversationInfo:
        """Create ConversationInfo from metadata."""
        return ConversationInfo(
            conversation_id=conversation_id,
            created_at=metadata.get("created_at"),
            last_accessed=metadata.get("last_accessed"),
            status=status,
            preview=preview,
        )

    def _extract_preview_from_messages(self, messages: list[BaseMessage]) -> str | None:
        """Extract preview text from messages."""
        if not messages:
            return None

        # Get the first message with content
        for msg in messages:
            if hasattr(msg, "content") and msg.content:
                content = str(msg.content)
                return content[:256] + "..." if len(content) > 256 else content

        return None

    async def _get_conversation_info(
        self, conversation_id: str, config: dict
    ) -> ConversationInfo:
        """Get conversation info for a conversation."""
        try:
            user_id = self._extract_user_id_from_config(config)

            # Get conversation metadata using checkpoint operations
            metadata = await self.checkpoints.get_conversation_metadata(
                user_id, conversation_id
            )

            # Get conversation preview and status
            user_scoped_id = create_user_scoped_conversation_id(
                user_id, conversation_id
            )
            checkpoint_config = {"configurable": {"thread_id": user_scoped_id}}
            preview, status, _ = await self.checkpoints.get_metadata(checkpoint_config)

            # Create conversation info using shared method
            return self._create_conversation_info_from_metadata(
                conversation_id, metadata, status=status, preview=preview
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

    async def chat(
        self,
        messages: list[BaseMessage],
        conversation_id: str | None,
        config: dict,
        previous_response_id: str | None = None,
    ) -> tuple[list[BaseMessage], ConversationInfo]:
        """Start a new conversation or continue an existing one based on conversation_id."""
        user_id = self._extract_user_id_from_config(config)

        if previous_response_id:
            # For response-level branching: load the previous response and continue from there
            # This is different from conversation-level continuation
            # TODO: Implement response-level branching logic
            # For now, we'll treat it like a new conversation but with the previous response context
            conversation_id, updated_config = await self._create_new_conversation(
                user_id, config
            )
            # TODO: Load previous response and merge context
        elif conversation_id:
            # For existing conversations: validate access
            await self._validate_and_audit_access(
                user_id, conversation_id, "access_validation", config
            )
            updated_config = config
        else:
            # For new conversations: create new UUID and conversation
            conversation_id, updated_config = await self._create_new_conversation(
                user_id, config
            )

        # Invoke agent
        try:
            agent_input = {"messages": messages}
            result = await self.agent.ainvoke(agent_input, config=updated_config)
        except Exception as e:
            logger.error(f"Agent invocation failed: {e}")

            # Check if this is a client error (4xx) that should be bubbled up
            if self._is_client_error(e):
                from .agent import ClientError

                # Extract status code and message from the original error
                status_code, error_message = self._extract_client_error_info(e)
                raise ClientError(
                    message=error_message,
                    http_status=status_code,
                    context={"conversation_id": conversation_id},
                ) from e

            # For server errors (5xx) or unknown errors, use InvocationError
            from .agent import InvocationError

            raise InvocationError(
                context={"conversation_id": conversation_id}, original_exception=e
            ) from e

        # Extract conversation data from the result
        result_messages = (
            result.get("messages", messages) if isinstance(result, dict) else messages
        )

        # Check for interrupts in the result
        interrupt_info = None
        if isinstance(result, dict) and "__interrupt__" in result:
            interrupt_data = result["__interrupt__"]
            if interrupt_data:
                # Handle multiple interrupts - convert list to list of interrupt info
                interrupts_list = (
                    interrupt_data
                    if isinstance(interrupt_data, list)
                    else [interrupt_data]
                )

                # Extract tool call IDs from the last assistant message
                tool_call_ids = []
                for message in reversed(result_messages):
                    if hasattr(message, "tool_calls") and message.tool_calls:
                        # Handle both object and dict formats
                        for tc in message.tool_calls:
                            if hasattr(tc, "id"):
                                tool_call_ids.append(tc.id)
                            elif isinstance(tc, dict) and "id" in tc:
                                tool_call_ids.append(tc["id"])
                        break

                interrupt_infos = []
                for i, interrupt_obj in enumerate(interrupts_list):
                    # Use the corresponding tool call ID, or "unknown" if not available
                    tool_call_id = (
                        tool_call_ids[i] if i < len(tool_call_ids) else "unknown"
                    )

                    single_interrupt_info = {
                        "type": "tool_call",
                        "tool_call_id": tool_call_id,
                        "action": "pending",
                        "args": {
                            "value": getattr(
                                interrupt_obj, "value", "Interrupt occurred"
                            )
                        },
                    }
                    interrupt_infos.append(single_interrupt_info)

                interrupt_info = {"interrupts": interrupt_infos}
                logger.info(
                    f"Interrupts detected: {len(interrupt_infos)} interrupts with tool call IDs: {[info['tool_call_id'] for info in interrupt_infos]}"
                )

        # Get conversation info
        conversation_info = await self._get_conversation_info(
            conversation_id, updated_config
        )

        # Set interrupt info if present
        if interrupt_info:
            conversation_info.interrupt_info = interrupt_info

        return result_messages, conversation_info

    async def chat_streaming(
        self,
        messages: list[BaseMessage],
        conversation_id: str | None,
        config: dict,
        previous_response_id: str | None = None,
    ) -> tuple[AsyncGenerator[str, None], ConversationInfo]:
        """Stream conversation events."""
        user_id = self._extract_user_id_from_config(config)

        if previous_response_id:
            # For response-level branching: load the previous response and continue from there
            # TODO: Implement response-level branching logic
            # For now, we'll treat it like a new conversation but with the previous response context
            conversation_id, config = await self._create_new_conversation(
                user_id, config
            )
            # TODO: Load previous response and merge context
        elif conversation_id:
            # For existing conversations: validate access
            await self._validate_and_audit_access(
                user_id, conversation_id, "access_validation", config
            )
        else:
            # For new conversations: create new UUID and conversation
            conversation_id, config = await self._create_new_conversation(
                user_id, config
            )

        # Ensure config has proper structure for LangGraph
        config = self._ensure_config_structure(config, conversation_id)

        # Get conversation info
        conversation_info = await self._get_conversation_info(conversation_id, config)

        # Create streaming generator with filtering
        async def stream_generator():
            agent_input = {"messages": messages}
            async for chunk in self.agent.astream(
                agent_input, config, stream_mode=["updates", "messages"]
            ):
                # Filter out sensitive LangGraph details and add conversation context
                filtered_chunk = self._filter_streaming_chunk(chunk, conversation_id)
                if filtered_chunk:
                    serialized_chunk = serialize_event(filtered_chunk)
                    if serialized_chunk:
                        yield serialized_chunk

        return stream_generator(), conversation_info

    def _filter_streaming_chunk(self, chunk, conversation_id: str):
        """
        Filter out sensitive LangGraph details from streaming chunks.

        Args:
            chunk: The raw LangGraph chunk
            conversation_id: The conversation ID to add to filtered chunks

        Returns:
            Filtered chunk with conversation context, or None if should be skipped
        """
        # LangGraph events come in the format ["messages", [...]] or ["updates", {...}]
        # We need to preserve this format but filter the content within

        # For message chunks with content, always preserve them and filter sensitive fields
        if hasattr(chunk, "content") and hasattr(chunk, "type"):
            # Create a clean message object with conversation context
            filtered_message = {
                "content": chunk.content,
                "type": chunk.type,
                "id": getattr(chunk, "id", None),
                "conversation": conversation_id,
            }

            # Add tool calls if present
            if hasattr(chunk, "tool_calls") and chunk.tool_calls:
                filtered_message["tool_calls"] = chunk.tool_calls

            # Add tool call chunks if present
            if hasattr(chunk, "tool_call_chunks") and chunk.tool_call_chunks:
                filtered_message["tool_call_chunks"] = chunk.tool_call_chunks

            # Add invalid tool calls if present
            if hasattr(chunk, "invalid_tool_calls") and chunk.invalid_tool_calls:
                filtered_message["invalid_tool_calls"] = chunk.invalid_tool_calls

            # Add response metadata if present
            if hasattr(chunk, "response_metadata") and chunk.response_metadata:
                filtered_message["response_metadata"] = chunk.response_metadata

            return filtered_message

        # For update chunks with meaningful data, preserve them and filter sensitive fields
        if hasattr(chunk, "__dict__"):
            # Check if this chunk has meaningful content (not just internal state)
            meaningful_fields = ["messages", "selected_apis", "cache_miss", "updates"]
            has_meaningful_content = any(
                hasattr(chunk, field) and getattr(chunk, field) is not None
                for field in meaningful_fields
            )

            if has_meaningful_content:
                filtered_dict = {}
                for key, value in chunk.__dict__.items():
                    # Skip sensitive fields but preserve meaningful content
                    if key in [
                        "auth_token",
                        "user_id",
                        "user_email",
                        "org_unit_id",
                        "langgraph_step",
                        "langgraph_node",
                        "langgraph_triggers",
                        "langgraph_path",
                        "langgraph_checkpoint_ns",
                        "checkpoint_ns",
                        "ls_provider",
                        "ls_model_name",
                        "ls_model_type",
                        "ls_temperature",
                        "thread_id",
                        "cache_disabled",
                        "disable_cache",
                    ]:
                        continue

                    # Add conversation context
                    if key == "conversation":
                        filtered_dict[key] = conversation_id
                    else:
                        filtered_dict[key] = value

                if filtered_dict:
                    filtered_dict["conversation"] = conversation_id
                    return filtered_dict
            else:
                # Skip chunks that are purely internal state
                if (
                    hasattr(chunk, "auth_token")
                    or hasattr(chunk, "user_id")
                    or hasattr(chunk, "user_email")
                    or hasattr(chunk, "org_unit_id")
                    or hasattr(chunk, "langgraph_step")
                    or hasattr(chunk, "langgraph_node")
                    or hasattr(chunk, "langgraph_triggers")
                    or hasattr(chunk, "langgraph_path")
                    or hasattr(chunk, "langgraph_checkpoint_ns")
                    or hasattr(chunk, "checkpoint_ns")
                    or hasattr(chunk, "ls_provider")
                    or hasattr(chunk, "ls_model_name")
                    or hasattr(chunk, "ls_model_type")
                    or hasattr(chunk, "ls_temperature")
                    or hasattr(chunk, "thread_id")
                ):
                    return None

        # For dictionary chunks, preserve meaningful content and filter sensitive fields
        if isinstance(chunk, dict):
            # Check if this dict has meaningful content
            meaningful_keys = ["messages", "selected_apis", "cache_miss", "updates"]
            has_meaningful_content = any(key in chunk for key in meaningful_keys)

            if has_meaningful_content:
                filtered_dict = {}
                for key, value in chunk.items():
                    # Skip sensitive fields but preserve meaningful content
                    if key in [
                        "auth_token",
                        "user_id",
                        "user_email",
                        "org_unit_id",
                        "langgraph_step",
                        "langgraph_node",
                        "langgraph_triggers",
                        "langgraph_path",
                        "langgraph_checkpoint_ns",
                        "checkpoint_ns",
                        "ls_provider",
                        "ls_model_name",
                        "ls_model_type",
                        "ls_temperature",
                        "thread_id",
                        "cache_disabled",
                        "disable_cache",
                    ]:
                        continue

                    filtered_dict[key] = value

                if filtered_dict:
                    filtered_dict["conversation"] = conversation_id
                    return filtered_dict
            else:
                # Skip dicts that are purely internal state
                sensitive_keys = [
                    "auth_token",
                    "user_id",
                    "user_email",
                    "org_unit_id",
                    "langgraph_step",
                    "langgraph_node",
                    "langgraph_triggers",
                    "langgraph_path",
                    "langgraph_checkpoint_ns",
                    "checkpoint_ns",
                    "ls_provider",
                    "ls_model_name",
                    "ls_model_type",
                    "ls_temperature",
                    "thread_id",
                ]
                if any(key in chunk for key in sensitive_keys):
                    return None

        # For other objects, try to add conversation context if they have meaningful content
        if hasattr(chunk, "__dict__"):
            # Check if this object has meaningful content
            meaningful_fields = [
                "messages",
                "selected_apis",
                "cache_miss",
                "updates",
                "content",
            ]
            has_meaningful_content = any(
                hasattr(chunk, field) and getattr(chunk, field) is not None
                for field in meaningful_fields
            )

            if has_meaningful_content:
                # Create a copy with conversation context
                filtered_chunk = type(chunk)()
                for key, value in chunk.__dict__.items():
                    if key in [
                        "auth_token",
                        "user_id",
                        "user_email",
                        "org_unit_id",
                        "langgraph_step",
                        "langgraph_node",
                        "langgraph_triggers",
                        "langgraph_path",
                        "langgraph_checkpoint_ns",
                        "checkpoint_ns",
                        "ls_provider",
                        "ls_model_name",
                        "ls_model_type",
                        "ls_temperature",
                        "thread_id",
                        "cache_disabled",
                        "disable_cache",
                    ]:
                        continue
                    setattr(filtered_chunk, key, value)

                # Add conversation context
                filtered_chunk.conversation = conversation_id
                return filtered_chunk
            else:
                # Skip objects that are purely internal state
                if (
                    hasattr(chunk, "auth_token")
                    or hasattr(chunk, "user_id")
                    or hasattr(chunk, "user_email")
                    or hasattr(chunk, "org_unit_id")
                    or hasattr(chunk, "langgraph_step")
                    or hasattr(chunk, "langgraph_node")
                    or hasattr(chunk, "langgraph_triggers")
                    or hasattr(chunk, "langgraph_path")
                    or hasattr(chunk, "langgraph_checkpoint_ns")
                    or hasattr(chunk, "checkpoint_ns")
                    or hasattr(chunk, "ls_provider")
                    or hasattr(chunk, "ls_model_name")
                    or hasattr(chunk, "ls_model_type")
                    or hasattr(chunk, "ls_temperature")
                    or hasattr(chunk, "thread_id")
                ):
                    return None

        return None

    async def list_conversations(
        self,
        config: dict,
    ) -> list[ConversationInfo]:
        """List user's conversations using checkpoint operations."""
        user_id = self._extract_user_id_from_config(config)

        # Audit conversation list access
        await self._audit_event(
            user_id, "conversation_list", "list_conversations", True, config
        )

        try:
            # Get all conversations for the user
            conversation_ids = await self.checkpoints.list_user_conversations(user_id)
            conversations = []

            for conversation_id in conversation_ids:
                # Get conversation metadata
                metadata = await self.checkpoints.get_conversation_metadata(
                    user_id, conversation_id
                )

                # Extract preview from messages if available
                preview = None
                if metadata.get("message_count", 0) > 0:
                    # Get conversation state to extract preview
                    user_scoped_id = create_user_scoped_conversation_id(
                        user_id, conversation_id
                    )
                    checkpoint_config = {"configurable": {"thread_id": user_scoped_id}}
                    checkpoint_state = await self.checkpoints.get(checkpoint_config)
                    if checkpoint_state:
                        messages = self.checkpoints.extract_messages(checkpoint_state)
                        preview = self._extract_preview_from_messages(messages)

                # Create conversation info
                conversation_info = self._create_conversation_info_from_metadata(
                    conversation_id,
                    metadata,
                    status="active",
                    preview=preview,
                )

                conversations.append(conversation_info)

            # Audit successful conversation list retrieval
            await self._audit_event(
                user_id, "conversation_list", "list_conversations_success", True, config
            )

            return conversations

        except Exception as e:
            # Audit failed conversation list retrieval
            await self._audit_event(
                user_id, "conversation_list", "list_conversations_failed", False, config
            )
            logger.error(f"Failed to list conversations: {e}")
            raise InvocationError("Failed to list conversations") from e

    async def load_conversation(
        self,
        conversation_id: str,
        config: dict,
    ) -> tuple[list[BaseMessage], ConversationInfo]:
        """Load conversation state using checkpoint operations."""
        user_id = self._extract_user_id_from_config(config)

        # Validate access
        await self._validate_and_audit_access(
            user_id, conversation_id, "access_validation", config
        )

        try:
            # Get conversation state using checkpoint operations
            user_scoped_id = create_user_scoped_conversation_id(
                user_id, conversation_id
            )
            checkpoint_config = {"configurable": {"thread_id": user_scoped_id}}
            checkpoint_state = await self.checkpoints.get(checkpoint_config)

            if not checkpoint_state:
                await self._audit_event(
                    user_id,
                    conversation_id,
                    "access_denied",
                    False,
                    config,
                )
                raise ConversationNotFoundError()

            # Check if conversation has been deleted (empty state indicates deletion)
            if not checkpoint_state or checkpoint_state == {}:
                await self._audit_event(
                    user_id,
                    conversation_id,
                    "access_denied",
                    False,
                    config,
                )
                raise ConversationNotFoundError()

            # Extract messages using checkpoint operations
            messages = self.checkpoints.extract_messages(checkpoint_state)

            # Get conversation info
            conversation_info = await self._get_conversation_info(
                conversation_id, config
            )

            return messages, conversation_info

        except (AccessDeniedError, ConversationNotFoundError, ValidationError):
            raise
        except Exception as e:
            logger.error(f"Failed to load conversation {conversation_id}: {e}")
            raise InvocationError(
                "Failed to load conversation",
                context={"conversation_id": conversation_id},
            ) from e

    async def delete_conversation(
        self,
        conversation_id: str,
        config: dict,
    ) -> bool:
        """Delete a conversation using checkpoint operations."""
        user_id = self._extract_user_id_from_config(config)

        # Validate access
        await self._validate_and_audit_access(
            user_id, conversation_id, "access_validation", config
        )

        try:
            # Delete conversation using checkpoint operations
            deleted = await self.checkpoints.delete_conversation(
                user_id, conversation_id
            )

            if deleted:
                # Audit successful deletion
                await self._audit_event(
                    user_id, conversation_id, "deleted", True, config
                )
                logger.info(
                    f"Successfully deleted conversation {conversation_id} for user {user_id}"
                )
            else:
                # Audit failed deletion
                await self._audit_event(
                    user_id, conversation_id, "deletion_failed", False, config
                )
                raise ConversationNotFoundError()

            return True

        except (AccessDeniedError, ConversationNotFoundError, ValidationError):
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
        user_id = self._extract_user_id_from_config(config)

        # Validate access
        await self._validate_and_audit_access(
            user_id, conversation_id, "access_validation", config
        )

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
        user_id = self._extract_user_id_from_config(config)

        # Validate access
        await self._validate_and_audit_access(
            user_id, conversation_id, "access_validation", config
        )

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
                # Filter out sensitive LangGraph details and add conversation context
                filtered_chunk = self._filter_streaming_chunk(chunk, conversation_id)
                if filtered_chunk:
                    serialized_chunk = serialize_event(filtered_chunk)
                    if serialized_chunk:
                        yield serialized_chunk

        return stream_generator(), conversation_info

    async def resume_from_checkpoint(
        self,
        conversation_id: str,
        checkpoint_id: str,
        config: dict,
    ) -> tuple[list[BaseMessage], ConversationInfo]:
        """
        Resume conversation from a specific checkpoint.

        This allows restarting from any point in the conversation history,
        potentially after editing messages.
        """
        user_id = self._extract_user_id_from_config(config)

        # Validate access
        await self._validate_and_audit_access(
            user_id, conversation_id, "access_validation", config
        )

        try:
            # Get checkpoint state using checkpoint operations
            user_scoped_id = create_user_scoped_conversation_id(
                user_id, conversation_id
            )
            checkpoint_config = {"configurable": {"thread_id": user_scoped_id}}
            checkpoint_state = await self.checkpoints.get_by_id(
                checkpoint_config, checkpoint_id
            )

            if not checkpoint_state:
                await self._audit_event(
                    user_id,
                    conversation_id,
                    "access_denied",
                    False,
                    config,
                )
                raise ConversationNotFoundError(f"Checkpoint {checkpoint_id} not found")

            # Extract messages using checkpoint operations
            messages = self.checkpoints.extract_messages(checkpoint_state)

            # Get conversation info
            conversation_info = await self._get_conversation_info(
                conversation_id, config
            )

            return messages, conversation_info

        except (AccessDeniedError, ConversationNotFoundError):
            raise
        except Exception as e:
            logger.error(f"Failed to resume from checkpoint {checkpoint_id}: {e}")
            raise InvocationError(
                "Failed to resume from checkpoint",
                context={
                    "conversation_id": conversation_id,
                    "checkpoint_id": checkpoint_id,
                },
            ) from e

    async def list_conversation_checkpoints(
        self,
        conversation_id: str,
        config: dict,
    ) -> list[dict]:
        """
        List all checkpoints for a conversation.

        This enables users to see the conversation history and choose
        which checkpoint to resume from.
        """
        user_id = self._extract_user_id_from_config(config)

        # Validate access
        await self._validate_and_audit_access(
            user_id, conversation_id, "access_validation", config
        )

        try:
            # List checkpoints using checkpoint operations
            user_scoped_id = create_user_scoped_conversation_id(
                user_id, conversation_id
            )
            checkpoint_config = {"configurable": {"thread_id": user_scoped_id}}
            checkpoints = await self.checkpoints.list(checkpoint_config)

            # Convert to list and add conversation context
            checkpoint_list = []
            for checkpoint in checkpoints:
                checkpoint_info = {
                    "checkpoint_id": checkpoint["id"],
                    "timestamp": checkpoint.get("ts"),
                    "version": checkpoint.get("v"),
                    "conversation_id": conversation_id,
                }
                checkpoint_list.append(checkpoint_info)

            return checkpoint_list

        except Exception as e:
            logger.error(
                f"Failed to list checkpoints for conversation {conversation_id}: {e}"
            )
            raise InvocationError(
                "Failed to list checkpoints",
                context={"conversation_id": conversation_id},
            ) from e

    async def edit_conversation_checkpoint(
        self,
        conversation_id: str,
        checkpoint_id: str,
        edited_messages: list[BaseMessage],
        config: dict,
    ) -> bool:
        """
        Edit a specific checkpoint with new messages.

        This allows users to modify conversation history and resume
        from the edited state.
        """
        user_id = self._extract_user_id_from_config(config)

        # Validate access
        await self._validate_and_audit_access(
            user_id, conversation_id, "access_validation", config
        )

        try:
            # Edit checkpoint using checkpoint operations
            user_scoped_id = create_user_scoped_conversation_id(
                user_id, conversation_id
            )
            checkpoint_config = {"configurable": {"thread_id": user_scoped_id}}
            success = await self.checkpoints.edit_messages(
                checkpoint_config, checkpoint_id, edited_messages
            )

            if success:
                # Audit successful edit
                await self._audit_event(
                    user_id,
                    conversation_id,
                    "checkpoint_edited",
                    True,
                    config,
                    metadata={"checkpoint_id": checkpoint_id},
                )
                logger.info(
                    f"Successfully edited checkpoint {checkpoint_id} for conversation {conversation_id}"
                )

            return success

        except (AccessDeniedError, ConversationNotFoundError):
            raise
        except Exception as e:
            logger.error(f"Failed to edit checkpoint {checkpoint_id}: {e}")
            raise InvocationError(
                "Failed to edit checkpoint",
                context={
                    "conversation_id": conversation_id,
                    "checkpoint_id": checkpoint_id,
                },
            ) from e

    def _is_client_error(self, exception: Exception) -> bool:
        """Check if the exception represents a client error (4xx)."""
        # Check for OpenAI BadRequestError (status code 400)
        if hasattr(exception, "status_code"):
            return 400 <= exception.status_code < 500

        # Check for OpenAI API errors by checking the error message patterns
        error_str = str(exception).lower()

        # Common OpenAI 400 error patterns
        client_error_patterns = [
            "error code: 400",
            "badrequest",
            "invalid_request_error",
            "must be followed by tool messages",
            "tool_call_ids did not have response messages",
            "maximum context length",
            "invalid input",
        ]

        return any(pattern in error_str for pattern in client_error_patterns)

    def _extract_client_error_info(self, exception: Exception) -> tuple[int, str]:
        """Extract HTTP status code and error message from client error."""
        # Default to 400 Bad Request
        status_code = 400
        error_message = str(exception)

        # Try to extract status code if available
        if hasattr(exception, "status_code"):
            status_code = exception.status_code
        elif "error code: 400" in error_message.lower():
            status_code = 400
        elif "error code: 401" in error_message.lower():
            status_code = 401
        elif "error code: 403" in error_message.lower():
            status_code = 403
        elif "error code: 404" in error_message.lower():
            status_code = 404
        elif "error code: 429" in error_message.lower():
            status_code = 429

        # Try to extract the actual error message from OpenAI format
        try:
            # OpenAI errors often have the format: "Error code: 400 - {'error': {'message': '...'}}"
            import re

            pattern = r"Error code: \d+ - \{'error': \{'message': '([^']+)'"
            match = re.search(pattern, error_message)
            if match:
                error_message = match.group(1)
        except Exception:
            # If extraction fails, use the original message
            pass

        return status_code, error_message
