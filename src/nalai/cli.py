"""
Command-line interface for nalAI.

Provides an interactive CLI for testing and debugging the nalAI
agent. Supports conversation history, human-in-the-loop review,
and streaming responses for development and testing workflows.
"""

import asyncio

from dotenv import load_dotenv

from nalai.core import create_agent
from nalai.utils.cli_print import stream_events_with_interruptions

CLI_PROMPT = "\nPrompt: "
EXIT_COMMANDS = {"quit", "exit", "q"}

load_dotenv()


def main():
    """Main CLI entry point for interactive API Assistant testing.
    Initializes agent and provides interactive conversation interface
    with streaming responses and human review.
    """
    agent = create_agent()

    agent_config = {
        "configurable": {
            "thread_id": "thread-1",
            "auth_token": "dev-token",
            # "model": {
            #     "name": "gpt-4.1",
            #     "platform": "openai",
            # },
        }
    }

    print("nalAI CLI - Type 'quit', 'exit', or 'q' to exit")

    while True:
        user_input = input(CLI_PROMPT)
        if user_input.lower() in EXIT_COMMANDS:
            print("Goodbye!")
            break
        try:
            print("\n")
            asyncio.run(
                stream_events_with_interruptions(agent, agent_config, user_input)
            )
        except ValueError as error:
            print(f"Error: {error}")


if __name__ == "__main__":
    main()
