import anthropic
import os
from dotenv import load_dotenv

load_dotenv(override=True)

class BaseAgent:
    def __init__(self, name: str, role: str, system_prompt: str):
        self.name = name
        self.role = role
        self.system_prompt = system_prompt
        self.client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

    def think(self, user_message: str, max_tokens: int = 2048) -> str:
        response = self.client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=max_tokens,
            system=self.system_prompt,
            messages=[{"role": "user", "content": user_message}]
        )
        return response.content[0].text

    def think_with_tools(self, user_message: str, apps: list[str], max_tokens: int = 2048) -> str:
        """Like think(), but equips the agent with Composio tools for the given apps."""
        from connectors.composio_connector import get_tools, run_tool_loop

        tools = get_tools(apps)
        messages = [
            {"role": "user", "content": user_message}
        ]
        # Prepend system prompt via the system param — handled in run_tool_loop via client
        response = self.client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=max_tokens,
            system=self.system_prompt,
            tools=tools,
            messages=messages,
        )

        from composio_anthropic import ComposioToolSet
        toolset = ComposioToolSet(api_key=os.environ.get("COMPOSIO_API_KEY"))

        while True:
            if response.stop_reason == "end_turn":
                for block in response.content:
                    if hasattr(block, "text"):
                        return block.text
                return ""

            if response.stop_reason == "tool_use":
                messages.append({"role": "assistant", "content": response.content})
                tool_results = toolset.handle_tool_calls(response)
                messages.append({"role": "user", "content": tool_results})
                response = self.client.messages.create(
                    model="claude-sonnet-4-6",
                    max_tokens=max_tokens,
                    system=self.system_prompt,
                    tools=tools,
                    messages=messages,
                )
            else:
                break

        return ""

    def __repr__(self):
        return f"[{self.name}] — {self.role}"
