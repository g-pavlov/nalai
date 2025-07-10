"""
Command-line interface for API Assistant.

Provides an interactive CLI for testing and debugging the API Assistant
agent. Supports conversation history, human-in-the-loop review,
and streaming responses for development and testing workflows.
"""

import asyncio

from dotenv import load_dotenv
from langgraph.checkpoint.memory import MemorySaver

from api_assistant.core.agent import APIAssistant
from api_assistant.core.workflow import create_and_compile_workflow
from api_assistant.utils.cli_print import stream_events_with_interruptions

CLI_PROMPT = "\nPrompt: "
EXIT_COMMANDS = {"quit", "exit", "q"}

load_dotenv()


def main():
    """Main CLI entry point for interactive API Assistant testing.
    Initializes agent with memory store and provides interactive
    conversation interface with streaming responses and human review.
    """
    memory_store = MemorySaver()
    agent = APIAssistant()
    agent_workflow = create_and_compile_workflow(agent, memory_store)

    agent_config = {
        "configurable": {
            "thread_id": "thread-1",
            "auth_token": "abcdefg123456789",
            "model": {
                "name": "llama3.1:8b",
                "platform": "ollama",
            },
        }
    }

    try:
        print(agent_workflow.get_graph().draw_ascii())
    except ImportError:
        print("Note: Install 'grandalf' to see the workflow diagram")
        print("pip install grandalf")

    print("API Assistant CLI - Type 'quit', 'exit', or 'q' to exit")

    while True:
        user_input = input(CLI_PROMPT)
        if user_input.lower() in EXIT_COMMANDS:
            print("Goodbye!")
            break
        try:
            print("\n")
            asyncio.run(
                stream_events_with_interruptions(
                    agent_workflow, agent_config, user_input
                )
            )
        except ValueError as error:
            print(f"Error: {error}")


if __name__ == "__main__":
    main()
