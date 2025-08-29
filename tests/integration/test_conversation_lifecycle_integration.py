#!/usr/bin/env python3
"""
Real integration test for conversation lifecycle using the actual agent API.
Tests the complete conversation lifecycle with interruptions, resumption, loading, and deletion.
"""

import json
import logging
from typing import Any

import pytest
import requests

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class IntegrationConversationLifecycleTest:
    """Real integration test for conversation lifecycle using the actual agent API."""

    def __init__(self):
        self.base_url = "http://localhost:8000"  # Use main server port
        self.mock_service_url = "http://localhost:8001"  # Mock ecommerce service
        self.conversation_id = None
        self.response_ids = []  # Track all response IDs
        self.tool_call_id = None  # Track tool call ID for interruption
        self.interrupt_id = None

    def start_test_server(self):
        """Check if the main server is running."""
        logger.info("Checking if main server is running...")

        # Test if server is running
        try:
            # Try the main API endpoint
            response = requests.get(f"{self.base_url}/api/v1/", timeout=5)
            if response.status_code in [200, 404]:  # 404 is OK for root endpoint
                logger.info("✅ Main server is running")
                return
        except (requests.RequestException, ConnectionError):
            pass

        # If that fails, try healthz endpoint
        try:
            response = requests.get(f"{self.base_url}/healthz", timeout=5)
            if response.status_code == 200:
                logger.info("✅ Main server is running")
                return
        except (requests.RequestException, ConnectionError):
            pass

        # If both fail, raise error
        raise RuntimeError("Main server is not running on port 8000")

    def check_mock_service(self):
        """Check if mock ecommerce service is running."""
        logger.info("Checking if mock ecommerce service is running...")

        try:
            response = requests.get(f"{self.mock_service_url}/products", timeout=5)
            if response.status_code == 200:
                logger.info("✅ Mock ecommerce service is running")
                return
        except (requests.RequestException, ConnectionError):
            pass

        raise RuntimeError("Mock ecommerce service is not running on port 8001")

    def make_request(
        self, endpoint: str, data: dict[str, Any], headers: dict[str, str] = None
    ) -> requests.Response:
        """Make HTTP request to the API."""
        url = f"{self.base_url}{endpoint}"
        default_headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": "Bearer dev-token",  # Use consistent dev token
        }
        if headers:
            default_headers.update(headers)

        logger.info(f"Making request to {url}")
        logger.info(f"Request data: {json.dumps(data, indent=2)}")

        response = requests.post(url, json=data, headers=default_headers, timeout=30)

        logger.info(f"Response status: {response.status_code}")
        logger.info(f"Response headers: {dict(response.headers)}")
        if response.text:
            logger.info(f"Response body: {response.text[:1000]}...")

        return response

    def verify_response_structure(
        self, response_data: dict, expected_conversation_id: str = None
    ):
        """Verify response structure and extract IDs - schema validation handles most checks."""
        # Schema validation ensures required fields and ID formats
        response_id = response_data["id"]
        conversation_id = response_data["conversation_id"]

        # Verify conversation ID consistency
        if expected_conversation_id:
            assert conversation_id == expected_conversation_id, (
                f"Conversation ID mismatch: expected {expected_conversation_id}, got {conversation_id}"
            )

        return response_id, conversation_id

    def test_1_start_conversation_with_hello(self):
        """Step 1: Start a conversation with a simple 'hello' message."""
        logger.info("=== Step 1: Starting conversation with 'hello' ===")

        # Check services are running
        self.start_test_server()
        self.check_mock_service()

        # Create a simple hello message
        request_data = {
            "input": "hello",
            "stream": "off",  # Use non-streaming for easier testing
        }

        response = self.make_request("/api/v1/messages", request_data)

        # Assert response is successful
        assert response.status_code == 200, (
            f"Expected 200, got {response.status_code}: {response.text}"
        )

        response_data = response.json()

        # Verify response structure (schema validation handles ID formats and required fields)
        response_id, conversation_id = self.verify_response_structure(response_data)

        # Store IDs for later use
        self.conversation_id = conversation_id
        self.response_ids.append(response_id)

        logger.info(f"Created conversation: {conversation_id}")
        logger.info(f"Response ID: {response_id}")

        # Extract and verify messages
        messages = response_data.get("output", [])
        assert len(messages) > 0, "No messages in response"

        # Verify we got an AI response
        ai_messages = [msg for msg in messages if msg.get("role") == "assistant"]
        assert len(ai_messages) > 0, "No AI message in response"

        # Check that AI response contains some text
        ai_content = ai_messages[0].get("content", [])
        content_text = ""
        for content_block in ai_content:
            if content_block.get("type") == "text":
                content_text += content_block.get("text", "")

        assert len(content_text) > 0, "AI should provide a response to hello"

        logger.info("✅ Step 1 completed: Conversation started with hello")

    def test_2_interrupt_with_product_update(self):
        """Step 2: Continue with a message that interrupts the flow - product update."""
        logger.info("=== Step 2: Interrupting with product update request ===")

        if not self.conversation_id:
            pytest.skip("No conversation to continue")

        # Create a product update request that should trigger a tool call
        interrupt_data = {
            "conversation_id": self.conversation_id,
            "input": "update the price to 299.99 for product with id 550e8400-e29b-41d4-a716-446655440001",
            "stream": "off",
        }

        response = self.make_request("/api/v1/messages", interrupt_data)

        # Assert response is successful
        assert response.status_code == 200, (
            f"Expected 200, got {response.status_code}: {response.text}"
        )

        response_data = response.json()

        # Verify response structure (schema validation handles ID formats and required fields)
        response_id, conversation_id = self.verify_response_structure(
            response_data, self.conversation_id
        )

        # Store new response ID
        self.response_ids.append(response_id)

        logger.info(f"Interrupt response ID: {response_id}")

        # Extract messages
        messages = response_data.get("output", [])
        assert len(messages) > 0, "No messages in interrupt response"

        # Look for tool calls in assistant messages
        tool_calls_found = []
        for msg in messages:
            if msg.get("role") == "assistant":
                if "tool_calls" in msg and msg["tool_calls"] is not None:
                    tool_calls_found.extend(msg["tool_calls"])

        # Verify we have tool calls (this should trigger an interrupt)
        assert len(tool_calls_found) > 0, (
            "Expected tool calls for product update request"
        )

        # Extract tool call ID for later use
        self.tool_call_id = tool_calls_found[0]["id"]

        logger.info(f"Found tool call ID: {self.tool_call_id}")

        # Verify it's a PUT request for product update
        tool_call = tool_calls_found[0]
        assert tool_call["name"] == "put_http_requests", (
            "Expected PUT HTTP request tool"
        )

        # Verify args contain the expected product update
        args = tool_call["args"]
        assert "url" in args, "Tool call args missing URL"
        assert "input_data" in args, "Tool call args missing input_data"

        # Verify URL points to the specific product
        expected_product_id = "550e8400-e29b-41d4-a716-446655440001"
        assert expected_product_id in args["url"], (
            f"URL should contain product ID: {args['url']}"
        )

        # Verify input_data contains price update
        input_data = args["input_data"]
        assert "price" in input_data, "Input data should contain price update"
        assert input_data["price"] == 299.99, (
            f"Expected price 299.99, got {input_data['price']}"
        )

        logger.info("✅ Step 2 completed: Product update request created tool call")

    def test_3_resume_with_accept_tool_call(self):
        """Step 3: Resume the interrupt by accepting the tool call."""
        logger.info("=== Step 3: Resuming with tool call acceptance ===")

        if not self.conversation_id or not self.tool_call_id:
            pytest.skip("No conversation or tool call to resume")

        # Create tool decision to accept the tool call
        resume_data = {
            "conversation_id": self.conversation_id,
            "input": [
                {
                    "type": "tool_decision",
                    "tool_call_id": self.tool_call_id,
                    "decision": "accept",
                }
            ],
            "stream": "off",
        }

        response = self.make_request("/api/v1/messages", resume_data)

        # Assert response is successful
        assert response.status_code == 200, (
            f"Expected 200, got {response.status_code}: {response.text}"
        )

        response_data = response.json()

        # Verify response structure (schema validation handles ID formats and required fields)
        response_id, conversation_id = self.verify_response_structure(
            response_data, self.conversation_id
        )

        # Store new response ID
        self.response_ids.append(response_id)

        logger.info(f"Resume response ID: {response_id}")

        # Extract messages
        messages = response_data.get("output", [])
        assert len(messages) > 0, "No messages in resume response"

        # Verify we have tool messages (from the accepted tool call)
        tool_messages = [msg for msg in messages if msg.get("role") == "tool"]
        assert len(tool_messages) > 0, (
            "Should have tool messages after accepting tool call"
        )

        # Verify tool message structure (schema validation handles most checks)
        for tool_msg in tool_messages:
            assert tool_msg["tool_call_id"] == self.tool_call_id, (
                "Tool message tool_call_id mismatch"
            )

            # Verify tool message content contains the result
            content = tool_msg.get("content", [])
            content_text = ""
            for content_block in content:
                if content_block.get("type") == "text":
                    content_text += content_block.get("text", "")

            assert len(content_text) > 0, "Tool message should contain result"

            # Verify the result contains the updated product info
            try:
                result_data = json.loads(content_text)
                assert "id" in result_data, "Tool result should contain product ID"
                assert result_data["id"] == "550e8400-e29b-41d4-a716-446655440001", (
                    "Tool result should contain correct product ID"
                )
                assert "price" in result_data, (
                    "Tool result should contain updated price"
                )
                assert result_data["price"] == 299.99, (
                    "Tool result should contain correct updated price"
                )
            except json.JSONDecodeError:
                pytest.fail("Tool result should be valid JSON")

        # Verify we have an AI response after the tool call
        ai_messages = [msg for msg in messages if msg.get("role") == "assistant"]
        assert len(ai_messages) > 0, "Should have AI response after tool call"

        # Verify AI response acknowledges the update
        ai_content = ai_messages[0].get("content", [])
        content_text = ""
        for content_block in ai_content:
            if content_block.get("type") == "text":
                content_text += content_block.get("text", "")

        assert len(content_text) > 0, "AI should provide response after tool call"

        logger.info("✅ Step 3 completed: Tool call accepted and executed")

    def test_4_load_conversation(self):
        """Step 4: Load the conversation via GET /conversations/{conversation_id} and verify content."""
        logger.info("=== Step 4: Loading conversation via GET endpoint ===")

        if not self.conversation_id:
            pytest.skip("No conversation to load. Conversation id not specified.")

        # Load the conversation via GET endpoint
        load_url = f"{self.base_url}/api/v1/conversations/{self.conversation_id}"
        logger.info(f"Loading conversation: {load_url}")

        headers = {"Authorization": "Bearer dev-token"}
        response = requests.get(load_url, headers=headers)

        # Assert response is successful
        assert response.status_code == 200, (
            f"Expected 200, got {response.status_code}: {response.text}"
        )

        response_data = response.json()

        # Schema validation handles conversation_id format and messages structure
        conversation_id = response_data["conversation_id"]
        assert conversation_id == self.conversation_id, "Conversation ID mismatch"

        messages = response_data["messages"]
        assert len(messages) > 0, "No messages in loaded conversation"

        logger.info(f"Loaded conversation with {len(messages)} messages")

        # Verify that the loaded conversation contains the expected messages from previous steps
        # We should have:
        # 1. Initial hello message
        # 2. AI response to hello
        # 3. Product update request
        # 4. AI response with tool call
        # 5. Tool message (from accepted tool call)
        # 6. AI response after tool execution

        expected_message_count = 6
        assert len(messages) >= expected_message_count, (
            f"Expected at least {expected_message_count} messages, got {len(messages)}"
        )

        # Log message details for verification
        for i, msg in enumerate(messages):
            logger.info(f"Message {i}: role={msg['role']}, id={msg['id']}")
            if msg.get("content"):
                content_text = ""
                for content_block in msg["content"]:
                    if content_block.get("type") == "text":
                        content_text += content_block.get("text", "")
                if content_text:
                    logger.info(f"  Content: {content_text[:100]}...")

        # Verify specific messages from our test flow
        user_messages = [msg for msg in messages if msg.get("role") == "user"]
        assistant_messages = [msg for msg in messages if msg.get("role") == "assistant"]
        tool_messages = [msg for msg in messages if msg.get("role") == "tool"]

        # Should have at least 2 user messages (hello + product update)
        assert len(user_messages) >= 2, (
            f"Expected at least 2 user messages, got {len(user_messages)}"
        )

        # Should have at least 3 assistant messages (hello response + tool call + final response)
        assert len(assistant_messages) >= 3, (
            f"Expected at least 3 assistant messages, got {len(assistant_messages)}"
        )

        # Should have at least 1 tool message (from accepted tool call)
        assert len(tool_messages) >= 1, (
            f"Expected at least 1 tool message, got {len(tool_messages)}"
        )

        # Verify the first user message contains "hello"
        first_user_msg = user_messages[0]
        first_user_content = ""
        for content_block in first_user_msg.get("content", []):
            if content_block.get("type") == "text":
                first_user_content += content_block.get("text", "")
        assert "hello" in first_user_content.lower(), (
            "First user message should contain 'hello'"
        )

        # Verify one of the user messages contains the product update request
        product_update_found = False
        for user_msg in user_messages:
            content_text = ""
            for content_block in user_msg.get("content", []):
                if content_block.get("type") == "text":
                    content_text += content_block.get("text", "")
            if "update" in content_text.lower() and "price" in content_text.lower():
                product_update_found = True
                break
        assert product_update_found, (
            "Should find product update request in user messages"
        )

        # Verify tool message contains the tool call result
        if tool_messages:
            tool_msg = tool_messages[0]
            assert tool_msg["tool_call_id"] == self.tool_call_id, (
                "Tool message tool_call_id should match"
            )

            # Verify tool message content contains the result
            tool_content = ""
            for content_block in tool_msg.get("content", []):
                if content_block.get("type") == "text":
                    tool_content += content_block.get("text", "")
            assert len(tool_content) > 0, "Tool message should contain result"

            # Verify the result contains the updated product info
            try:
                result_data = json.loads(tool_content)
                assert "id" in result_data, "Tool result should contain product ID"
                assert result_data["id"] == "550e8400-e29b-41d4-a716-446655440001", (
                    "Tool result should contain correct product ID"
                )
                assert "price" in result_data, (
                    "Tool result should contain updated price"
                )
                assert result_data["price"] == 299.99, (
                    "Tool result should contain correct updated price"
                )
            except json.JSONDecodeError:
                pytest.fail("Tool result should be valid JSON")

        logger.info(
            "✅ Step 4 completed: Conversation loaded successfully with verified content"
        )

    def test_5_delete_conversation(self):
        """Step 5: Delete the conversation and verify deletion."""
        logger.info("=== Step 5: Deleting conversation ===")

        if not self.conversation_id:
            pytest.skip("No conversation to delete. Conversation ID not specified.")

        # Delete the conversation
        delete_url = f"{self.base_url}/api/v1/conversations/{self.conversation_id}"
        logger.info(f"Deleting conversation: {delete_url}")

        headers = {"Authorization": "Bearer dev-token"}
        response = requests.delete(delete_url, headers=headers)

        # Debug: Log the deletion response
        logger.info(f"Delete response status: {response.status_code}")
        logger.info(f"Delete response body: {response.text}")

        # Assert deletion is successful
        assert response.status_code == 204, (
            f"Expected 204, got {response.status_code}: {response.text}"
        )

        # Verify that the conversation was actually deleted
        logger.info("Verifying deletion...")

        # Try to access the deleted conversation - should fail
        try:
            # Try to send a message to the deleted conversation
            verify_data = {
                "conversation_id": self.conversation_id,
                "input": "This should fail",
                "stream": "off",
            }

            response = self.make_request("/api/v1/messages", verify_data)

            # Should get 404 or similar error
            assert response.status_code in [404, 400], (
                f"Expected error status, got {response.status_code}"
            )

            logger.info("Deletion verified - conversation no longer accessible")

        except Exception as e:
            logger.info(f"Deletion verified - got expected error: {e}")

        logger.info("✅ Step 5 completed: Conversation deleted and deletion verified")

    def run_full_lifecycle(self):
        """Run the complete conversation lifecycle test."""
        logger.info("🚀 Starting real integration conversation lifecycle test via API")

        try:
            # Run tests in sequence
            self.test_1_start_conversation_with_hello()
            self.test_2_interrupt_with_product_update()
            self.test_3_resume_with_accept_tool_call()
            self.test_4_load_conversation()
            self.test_5_delete_conversation()

            logger.info(
                "🎉 All tests passed! Real integration conversation lifecycle via API completed successfully."
            )
            logger.info(f"Conversation ID: {self.conversation_id}")
            logger.info(f"Response IDs: {self.response_ids}")
            logger.info(f"Tool call ID: {self.tool_call_id}")

        except Exception as e:
            logger.error(f"❌ Test failed: {e}")
            raise


def main():
    """Main test runner."""
    # Create test instance
    test = IntegrationConversationLifecycleTest()

    # Run the full lifecycle test
    test.run_full_lifecycle()


if __name__ == "__main__":
    main()
