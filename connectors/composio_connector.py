"""
Composio connector — wraps Composio toolsets for use with Anthropic agents.

Supported apps: GMAIL, GOOGLESHEETS, TELEGRAM, WHATSAPP

Usage:
    from connectors.composio_connector import get_tools, run_tool_loop

    tools = get_tools(["GMAIL", "GOOGLESHEETS"])
    result = run_tool_loop(client, messages, tools)
"""

import os
from typing import Optional
from dotenv import load_dotenv

load_dotenv(override=True)

try:
    from composio_anthropic import ComposioToolSet, App
    COMPOSIO_AVAILABLE = True
except ImportError:
    COMPOSIO_AVAILABLE = False

# Map friendly names to Composio App enums
APP_MAP = {
    "GMAIL": "GMAIL",
    "GOOGLESHEETS": "GOOGLESHEETS",
    "TELEGRAM": "TELEGRAM",
    "WHATSAPP": "WHATSAPP",
}


def get_toolset() -> Optional["ComposioToolSet"]:
    if not COMPOSIO_AVAILABLE:
        raise RuntimeError(
            "composio-anthropic is not installed. Run: pip install composio-anthropic"
        )
    api_key = os.environ.get("COMPOSIO_API_KEY")
    if not api_key:
        raise RuntimeError("COMPOSIO_API_KEY is not set in environment variables.")
    return ComposioToolSet(api_key=api_key)


def get_tools(apps: list[str]) -> list[dict]:
    """Return Anthropic-compatible tool definitions for the given Composio apps."""
    toolset = get_toolset()
    composio_apps = [App[name] for name in apps if name in APP_MAP]
    return toolset.get_tools(apps=composio_apps)


def run_tool_loop(client, messages: list[dict], tools: list[dict], model: str, max_tokens: int = 2048) -> str:
    """
    Agentic loop: sends messages to Claude with Composio tools,
    executes any tool calls, and returns the final text response.
    """
    toolset = get_toolset()

    while True:
        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            tools=tools,
            messages=messages,
        )

        if response.stop_reason == "end_turn":
            for block in response.content:
                if hasattr(block, "text"):
                    return block.text
            return ""

        if response.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": response.content})
            tool_results = toolset.handle_tool_calls(response)
            messages.append({"role": "user", "content": tool_results})
        else:
            break

    return ""
