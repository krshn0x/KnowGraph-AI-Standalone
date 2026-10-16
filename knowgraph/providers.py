"""Wire-format adapters; retrieval and citation validation stay in the agent."""

import json
from dataclasses import dataclass

from knowgraph.config import Settings
from knowgraph.models import AskRequest, DraftAnswer


@dataclass(frozen=True)
class FunctionCall:
    name: str
    arguments: str
    call_id: str


@dataclass(frozen=True)
class ModelTurn:
    text: str
    calls: list[FunctionCall]


class ModelSession:
    """One request's conversation, with no state shared between concurrent questions."""

    def __init__(self, client, settings: Settings, instructions: str, request: AskRequest):
        self.client, self.settings, self.instructions = client, settings, instructions
        self.messages = [{"role": m.role, "content": m.content} for m in request.history]
        self.messages.append({"role": "user", "content": request.question})
        self.schema = DraftAnswer.model_json_schema()
        if settings.llm_provider != "openai":
            # Chat Completions providers use the same server-validated answer schema.
            self.messages.insert(
                0,
                {
                    "role": "system",
                    "content": instructions
                    + "\nWhen answering, return only a JSON object matching this schema:\n"
                    + json.dumps(self.schema),
                },
            )

    def next_turn(self, tools: list[dict], at_limit: bool, timeout: float) -> ModelTurn:
        if self.settings.llm_provider != "openai":
            return self._chat_turn(tools, at_limit, timeout)
        response = self.client.responses.create(
            model=self.settings.active_model,
            instructions=self.instructions,
            input=self.messages,
            tools=tools,
            tool_choice="none" if at_limit else "auto",
            parallel_tool_calls=False,
            text={
                "format": {
                    "type": "json_schema",
                    "name": "knowgraph_answer",
                    "strict": True,
                    "schema": self.schema,
                }
            },
            max_output_tokens=3000,
            timeout=timeout,
            store=False,
        )
        self.messages.extend(response.output)
        return ModelTurn(
            text=response.output_text,
            calls=[
                FunctionCall(o.name, o.arguments, o.call_id)
                for o in response.output
                if o.type == "function_call"
            ],
        )

    def _chat_turn(self, tools: list[dict], at_limit: bool, timeout: float) -> ModelTurn:
        parameters = {
            "model": self.settings.active_model,
            "messages": self.messages,
            "tools": [
                {
                    "type": "function",
                    "function": {k: v for k, v in tool.items() if k not in {"type", "strict"}},
                }
                for tool in tools
            ],
            "tool_choice": "none" if at_limit else "auto",
            "response_format": {"type": "json_object"},
            "max_tokens": 6000,
            "timeout": timeout,
        }
        if self.settings.llm_provider in {"gemini", "ollama"}:
            parameters["reasoning_effort"] = (
                "none" if self.settings.llm_provider == "ollama" else "low"
            )
            if at_limit:
                # Keep the final JSON-only request separate from function calling.
                parameters.pop("tools")
                parameters.pop("tool_choice")
            else:
                parameters.pop("response_format")
        response = self.client.chat.completions.create(**parameters)
        choice = response.choices[0]
        if choice.finish_reason not in {"stop", "tool_calls"}:
            raise ValueError("The provider did not complete the answer or tool call")
        message = choice.message
        calls = message.tool_calls or []
        serialized = {"role": "assistant", "content": message.content}
        if calls:
            serialized["tool_calls"] = [
                {
                    "id": call.id,
                    "type": "function",
                    "function": {
                        "name": call.function.name,
                        "arguments": call.function.arguments,
                    },
                }
                for call in calls
            ]
            if self.settings.llm_provider == "gemini":
                for original, replay in zip(calls, serialized["tool_calls"], strict=True):
                    # Google's opaque thought signatures must survive every tool turn.
                    # This metadata stays inside the backend provider conversation.
                    extra = getattr(original, "extra_content", None)
                    if extra is not None:
                        replay["extra_content"] = extra
            # DeepSeek thinking models require the reasoning content to be replayed
            # with tool calls. It remains server-side and is never shown as evidence.
            reasoning = getattr(message, "reasoning_content", None)
            if self.settings.llm_provider == "agentrouter" and reasoning is not None:
                serialized["reasoning_content"] = reasoning
        self.messages.append(serialized)
        return ModelTurn(
            text=message.content or "",
            calls=[FunctionCall(c.function.name, c.function.arguments, c.id) for c in calls],
        )

    def append_tool_result(self, call: FunctionCall, payload: dict) -> None:
        if self.settings.llm_provider != "openai":
            self.messages.append(
                {"role": "tool", "tool_call_id": call.call_id, "content": json.dumps(payload)}
            )
        else:
            self.messages.append(
                {
                    "type": "function_call_output",
                    "call_id": call.call_id,
                    "output": json.dumps(payload),
                }
            )
