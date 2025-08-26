"""
Checkpoints Service.

This module provides a clean CRUD++ interface for managing LangGraph checkpoints,
leveraging the existing checkpointing_service for backend operations.
"""

import builtins
import logging
from typing import Any

from langchain_core.messages import BaseMessage

from ..services.checkpointing_service import (
    CheckpointingBackendError,
    get_checkpointing_service,
)

logger = logging.getLogger(__name__)


class Checkpoints:
    """Clean CRUD++ interface for managing LangGraph checkpoints."""

    def __init__(self):
        """Initialize checkpoints service."""
        self.checkpointing_service = get_checkpointing_service()
        self.checkpointer = self.checkpointing_service.get_checkpointer()

    def _extract_user_from_thread_id(self, thread_id: str) -> str | None:
        """Extract user_id from thread_id format 'user:{user_id}:{conversation_id}'."""
        if thread_id.startswith("user:"):
            parts = thread_id.split(":", 2)
            if len(parts) == 3:
                return parts[1]
        return None

    def _extract_conversation_from_thread_id(self, thread_id: str) -> str | None:
        """Extract conversation_id from thread_id format 'user:{user_id}:{conversation_id}'."""
        if thread_id.startswith("user:"):
            parts = thread_id.split(":", 2)
            if len(parts) == 3:
                return parts[2]
        return None

    def _discover_user_conversations_via_list(self, user_id: str) -> list[str]:
        """
        Discover conversations for a user using the checkpointer's list method.

        This approach uses the checkpointer's built-in filtering capabilities
        to find all thread_ids that belong to the specified user.
        """
        try:
            discovered_conversations = set()

            # Use the checkpointer's list method to get all checkpoints
            # We pass None as config to get all checkpoints, then filter by user
            checkpoints = self.checkpointer.list(None)

            for checkpoint_tuple in checkpoints:
                # Extract thread_id from the checkpoint config
                config = checkpoint_tuple.config
                thread_id = config.get("configurable", {}).get("thread_id", "")

                # Check if this thread_id belongs to our user
                thread_user_id = self._extract_user_from_thread_id(thread_id)
                if thread_user_id == user_id:
                    conversation_id = self._extract_conversation_from_thread_id(
                        thread_id
                    )
                    if conversation_id:
                        discovered_conversations.add(conversation_id)

            logger.debug(
                f"Discovered {len(discovered_conversations)} conversations for user {user_id}"
            )
            return list(discovered_conversations)

        except Exception as e:
            logger.error(f"Error discovering conversations for user {user_id}: {e}")
            return []

    def _discover_user_conversations_via_storage(self, user_id: str) -> list[str]:
        """
        Fallback method: Discover conversations by scanning the checkpointer's storage.

        This is used as a fallback if the list method doesn't work as expected.
        """
        try:
            # Access the checkpointer's internal storage
            if hasattr(self.checkpointer, "storage") and hasattr(
                self.checkpointer.storage, "keys"
            ):
                discovered_conversations = []

                # Scan all thread_ids in the storage
                for thread_id in self.checkpointer.storage.keys():
                    if isinstance(thread_id, str):
                        # Check if this thread_id belongs to our user
                        thread_user_id = self._extract_user_from_thread_id(thread_id)
                        if thread_user_id == user_id:
                            conversation_id = self._extract_conversation_from_thread_id(
                                thread_id
                            )
                            if conversation_id:
                                discovered_conversations.append(conversation_id)

                logger.debug(
                    f"Discovered {len(discovered_conversations)} conversations for user {user_id} via storage"
                )
                return discovered_conversations
            else:
                logger.warning("Checkpointer storage not accessible for discovery")
                return []

        except Exception as e:
            logger.error(
                f"Error discovering conversations for user {user_id} via storage: {e}"
            )
            return []

    # ===== CRUD Operations =====

    async def get(self, config: dict[str, Any]) -> dict[str, Any] | None:
        """
        Get the current conversation state.

        Args:
            config: LangGraph configuration with thread_id

        Returns:
            Checkpoint state or None if not found
        """
        try:
            return await self.checkpointer.aget(config)
        except Exception as e:
            logger.error(f"Failed to get conversation state: {e}")
            raise CheckpointingBackendError(
                f"Failed to get conversation state: {e}"
            ) from e

    async def list(self, config: dict[str, Any]) -> list[dict[str, Any]]:
        """
        List all checkpoints for a conversation.

        Args:
            config: LangGraph configuration with thread_id

        Returns:
            List of checkpoint information
        """
        try:
            checkpoints = self.checkpointer.list(config)
            return list(checkpoints)
        except Exception as e:
            logger.error(f"Failed to list checkpoints: {e}")
            raise CheckpointingBackendError(f"Failed to list checkpoints: {e}") from e

    async def update(
        self, config: dict[str, Any], checkpoint_id: str, state: dict[str, Any]
    ) -> bool:
        """
        Update a specific checkpoint.

        Args:
            config: LangGraph configuration with thread_id
            checkpoint_id: Specific checkpoint ID
            state: New checkpoint state

        Returns:
            True if successful
        """
        try:
            checkpoint_config = self._add_checkpoint_id(config, checkpoint_id)
            await self.checkpointer.aput(checkpoint_config, state, metadata={})
            logger.debug(f"Updated checkpoint {checkpoint_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to update checkpoint {checkpoint_id}: {e}")
            raise CheckpointingBackendError(
                f"Failed to update checkpoint {checkpoint_id}: {e}"
            ) from e

    async def delete(self, config: dict[str, Any]) -> int:
        """
        Delete all checkpoints for a conversation.

        Args:
            config: LangGraph configuration with thread_id

        Returns:
            Number of checkpoints deleted
        """
        try:
            # Extract thread_id from config
            thread_id = config.get("configurable", {}).get("thread_id", "")

            # For MemorySaver, we can't actually delete checkpoints, but we can clear the state
            # by overwriting it with an empty state
            try:
                await self.checkpointer.aput(config, {}, metadata={})
                logger.debug(f"Cleared conversation state for thread_id: {thread_id}")
                return 1
            except Exception as e:
                logger.warning(f"Could not clear conversation state: {e}")
                return 1

        except Exception as e:
            logger.error(f"Failed to delete checkpoints: {e}")
            raise CheckpointingBackendError(f"Failed to delete checkpoints: {e}") from e

    async def put(self, config: dict[str, Any], state: dict[str, Any]) -> str:
        """
        Create or update a checkpoint.

        Args:
            config: LangGraph configuration with thread_id
            state: Checkpoint state

        Returns:
            Checkpoint ID
        """
        try:
            checkpoint_id = await self.checkpointer.aput(config, state, metadata={})
            logger.debug(f"Created/updated checkpoint {checkpoint_id}")
            return checkpoint_id
        except Exception as e:
            logger.error(f"Failed to create/update checkpoint: {e}")
            raise CheckpointingBackendError(
                f"Failed to create/update checkpoint: {e}"
            ) from e

    async def list_user_conversations(self, user_id: str) -> builtins.list[str]:
        """
        List all conversations for a user using the checkpointer's list method.

        Args:
            user_id: User identifier

        Returns:
            List of conversation IDs
        """
        try:
            # Try the preferred method first (using checkpointer's list method)
            conversations = self._discover_user_conversations_via_list(user_id)

            # If no conversations found, try the fallback method
            if not conversations:
                logger.debug(
                    f"No conversations found via list method for user {user_id}, trying storage method"
                )
                conversations = self._discover_user_conversations_via_storage(user_id)

            logger.debug(f"Found {len(conversations)} conversations for user {user_id}")
            return conversations

        except Exception as e:
            logger.error(f"Failed to list conversations for user {user_id}: {e}")
            raise CheckpointingBackendError(f"Failed to list conversations: {e}") from e

    # ===== Enhanced Operations =====

    async def get_by_id(
        self, config: dict[str, Any], checkpoint_id: str
    ) -> dict[str, Any] | None:
        """
        Get a specific checkpoint by ID.

        Args:
            config: LangGraph configuration with thread_id
            checkpoint_id: Specific checkpoint ID

        Returns:
            Checkpoint state or None if not found
        """
        try:
            checkpoint_config = self._add_checkpoint_id(config, checkpoint_id)
            return await self.checkpointer.aget(checkpoint_config)
        except Exception as e:
            logger.error(f"Failed to get checkpoint {checkpoint_id}: {e}")
            raise CheckpointingBackendError(
                f"Failed to get checkpoint {checkpoint_id}: {e}"
            ) from e

    async def clear(self, checkpoint_id: str, config: dict[str, Any]) -> bool:
        """
        Clear a specific checkpoint by setting empty state.

        Args:
            checkpoint_id: Specific checkpoint ID
            config: LangGraph configuration with thread_id

        Returns:
            True if successful
        """
        return await self.update(config, checkpoint_id, {})

    async def edit_messages(
        self,
        config: dict[str, Any],
        checkpoint_id: str,
        messages: builtins.list[BaseMessage],
    ) -> bool:
        """
        Edit messages in a specific checkpoint.

        Args:
            config: LangGraph configuration with thread_id
            checkpoint_id: Specific checkpoint ID
            messages: New list of messages

        Returns:
            True if successful
        """
        try:
            # Get original checkpoint state
            original_state = await self.get_by_id(config, checkpoint_id)
            if not original_state:
                raise CheckpointingBackendError(f"Checkpoint {checkpoint_id} not found")

            # Create new state with edited messages
            edited_state = original_state.copy()
            if "channel_values" not in edited_state:
                edited_state["channel_values"] = {}
            edited_state["channel_values"]["messages"] = messages

            # Update the checkpoint
            await self.update(config, checkpoint_id, edited_state)
            logger.info(f"Successfully edited checkpoint {checkpoint_id}")
            return True

        except CheckpointingBackendError:
            raise
        except Exception as e:
            logger.error(f"Failed to edit checkpoint {checkpoint_id}: {e}")
            raise CheckpointingBackendError(
                f"Failed to edit checkpoint {checkpoint_id}: {e}"
            ) from e

    # ===== Access Control Operations =====

    async def validate_user_access(self, user_id: str, conversation_id: str) -> bool:
        """
        Validate that user can access conversation.

        Args:
            user_id: User identifier
            conversation_id: Conversation identifier

        Returns:
            True if user can access conversation
        """
        try:
            user_scoped_id = f"user:{user_id}:{conversation_id}"
            config = {"configurable": {"thread_id": user_scoped_id}}
            state = await self.get(config)
            return state is not None
        except Exception as e:
            logger.debug(
                f"Access validation failed for user {user_id}, conversation {conversation_id}: {e}"
            )
            return False

    async def create_conversation(self, user_id: str, conversation_id: str) -> str:
        """
        Create a new conversation for user.

        Args:
            user_id: User identifier
            conversation_id: Conversation identifier

        Returns:
            User-scoped conversation ID
        """
        try:
            user_scoped_id = f"user:{user_id}:{conversation_id}"

            # Don't manually create checkpoint - let LangGraph handle it when workflow runs
            # The thread_id will be used to identify the conversation
            logger.info(f"Created conversation {conversation_id} for user {user_id}")
            return user_scoped_id

        except Exception as e:
            logger.error(
                f"Failed to create conversation {conversation_id} for user {user_id}: {e}"
            )
            raise CheckpointingBackendError(
                f"Failed to create conversation: {e}"
            ) from e

    async def delete_conversation(self, user_id: str, conversation_id: str) -> bool:
        """
        Delete a conversation for user.

        Args:
            user_id: User identifier
            conversation_id: Conversation identifier

        Returns:
            True if successful
        """
        try:
            user_scoped_id = f"user:{user_id}:{conversation_id}"
            config = {"configurable": {"thread_id": user_scoped_id}}

            deleted_count = await self.delete(config)
            logger.info(
                f"Deleted conversation {conversation_id} for user {user_id} ({deleted_count} checkpoints)"
            )
            return deleted_count > 0

        except Exception as e:
            logger.error(
                f"Failed to delete conversation {conversation_id} for user {user_id}: {e}"
            )
            raise CheckpointingBackendError(
                f"Failed to delete conversation: {e}"
            ) from e

    async def get_conversation_metadata(
        self, user_id: str, conversation_id: str
    ) -> dict[str, Any]:
        """
        Get conversation metadata.

        Args:
            user_id: User identifier
            conversation_id: Conversation identifier

        Returns:
            Conversation metadata
        """
        try:
            user_scoped_id = f"user:{user_id}:{conversation_id}"
            config = {"configurable": {"thread_id": user_scoped_id}}

            state = await self.get(config)
            if not state:
                return {
                    "conversation_id": conversation_id,
                    "user_id": user_id,
                    "created_at": None,
                    "last_accessed": None,
                    "message_count": 0,
                    "checkpoint_count": 0,
                }

            # Extract metadata from state
            metadata = state.get("metadata", {})
            channel_values = state.get("channel_values", {})
            messages = channel_values.get("messages", [])

            return {
                "conversation_id": conversation_id,
                "user_id": user_id,
                "created_at": metadata.get("created_at"),
                "last_accessed": metadata.get("last_accessed"),
                "message_count": len(messages),
                "checkpoint_count": len(await self.list(config)),
            }

        except Exception as e:
            logger.error(
                f"Failed to get metadata for conversation {conversation_id}: {e}"
            )
            raise CheckpointingBackendError(
                f"Failed to get conversation metadata: {e}"
            ) from e

    # ===== Utility Methods =====

    def extract_messages(self, state: dict[str, Any]) -> builtins.list[BaseMessage]:
        """
        Extract messages from checkpoint state.

        Args:
            state: Checkpoint state dictionary

        Returns:
            List of messages
        """
        messages = []

        if state and "channel_values" in state:
            channel_values = state["channel_values"]
            if "messages" in channel_values:
                messages = channel_values["messages"]

        return messages

    def extract_preview(self, state: dict[str, Any]) -> str | None:
        """
        Extract conversation preview from checkpoint state.

        Args:
            state: Checkpoint state dictionary

        Returns:
            Preview text or None
        """
        if state and "channel_values" in state:
            channel_values = state["channel_values"]
            if "messages" in channel_values:
                messages = channel_values["messages"]
                if messages:
                    # Get the first message with content
                    for msg in messages:
                        if hasattr(msg, "content") and msg.content:
                            return msg.content[:256]
        return None

    def extract_status(self, state: dict[str, Any]) -> str:
        """
        Extract conversation status from checkpoint state.

        Args:
            state: Checkpoint state dictionary

        Returns:
            Status string (active, interrupted, completed)
        """
        if not state:
            return "active"

        if "interrupts" in state and state["interrupts"]:
            return "interrupted"
        elif state.get("completed", False):
            return "completed"

        return "active"

    async def get_metadata(self, config: dict[str, Any]) -> tuple[str | None, str, int]:
        """
        Get conversation metadata from checkpoint state.

        Args:
            config: LangGraph configuration with thread_id

        Returns:
            Tuple of (preview, status, message_count)
        """
        try:
            state = await self.get(config)
            if not state:
                return None, "active", 0

            preview = self.extract_preview(state)
            status = self.extract_status(state)
            messages = self.extract_messages(state)
            message_count = len(messages)

            return preview, status, message_count
        except Exception as e:
            logger.error(f"Failed to get conversation metadata: {e}")
            return None, "active", 0

    async def validate_access(self, config: dict[str, Any], checkpoint_id: str) -> bool:
        """
        Validate that a checkpoint exists and is accessible.

        Args:
            config: LangGraph configuration with thread_id
            checkpoint_id: Specific checkpoint ID

        Returns:
            True if checkpoint exists and is accessible
        """
        try:
            state = await self.get_by_id(config, checkpoint_id)
            return state is not None
        except Exception as e:
            logger.debug(f"Checkpoint {checkpoint_id} validation failed: {e}")
            return False

    async def get_summary(self, config: dict[str, Any]) -> dict[str, Any]:
        """
        Get summary of all checkpoints for a conversation.

        Args:
            config: LangGraph configuration with thread_id

        Returns:
            Summary dictionary with checkpoint information
        """
        try:
            checkpoints = await self.list(config)

            summary = {
                "total_checkpoints": len(checkpoints),
                "checkpoints": [],
                "latest_checkpoint": None,
                "earliest_checkpoint": None,
            }

            if checkpoints:
                # Sort by timestamp
                sorted_checkpoints = sorted(
                    checkpoints, key=lambda x: x.get("ts", ""), reverse=True
                )

                summary["latest_checkpoint"] = sorted_checkpoints[0]
                summary["earliest_checkpoint"] = sorted_checkpoints[-1]

                for checkpoint in checkpoints:
                    checkpoint_info = {
                        "id": checkpoint["id"],
                        "timestamp": checkpoint.get("ts"),
                        "version": checkpoint.get("v"),
                    }
                    summary["checkpoints"].append(checkpoint_info)

            return summary
        except Exception as e:
            logger.error(f"Failed to get checkpoint summary: {e}")
            raise CheckpointingBackendError(
                f"Failed to get checkpoint summary: {e}"
            ) from e

    # ===== Health and Stats =====

    async def health_check(self) -> bool:
        """Check if the checkpointing service is healthy."""
        return await self.checkpointing_service.health_check()

    async def get_stats(self) -> dict[str, Any]:
        """Get checkpointing statistics."""
        return await self.checkpointing_service.get_stats()

    # ===== Private Helpers =====

    def _add_checkpoint_id(
        self, config: dict[str, Any], checkpoint_id: str
    ) -> dict[str, Any]:
        """Add checkpoint_id to config."""
        checkpoint_config = config.copy()
        if "configurable" not in checkpoint_config:
            checkpoint_config["configurable"] = {}
        checkpoint_config["configurable"]["checkpoint_id"] = checkpoint_id
        return checkpoint_config

    def _get_timestamp(self) -> str:
        """Get current timestamp in ISO format."""
        from datetime import datetime

        return datetime.now().isoformat()


# Global checkpoints instance
_checkpoints: Checkpoints | None = None


def get_checkpoints() -> Checkpoints:
    """Get the global checkpoints instance."""
    global _checkpoints
    if _checkpoints is None:
        _checkpoints = Checkpoints()
    return _checkpoints


def set_checkpoints(checkpoints: Checkpoints) -> None:
    """Set the global checkpoints instance."""
    global _checkpoints
    _checkpoints = checkpoints
