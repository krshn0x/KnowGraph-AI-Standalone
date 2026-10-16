"""Wire-format adapters; retrieval and citation validation stay in the agent."""

import json
import time
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
        self.native_call_ids: set[str] = set()
        if settings.llm_provider == "gemini":
            self.messages = [
                {
                    "role": "model" if m["role"] == "assistant" else "user",
                    "parts": [{"text": m["content"]}],
                }
                for m in self.messages
            ]
        elif settings.llm_provider != "openai":
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
        if self.settings.llm_provider == "gemini":
            return self._gemini_turn(tools, at_limit, timeout)
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
        if self.settings.llm_provider == "ollama":
            parameters["max_tokens"] = self.settings.ollama_max_output_tokens
            parameters["reasoning_effort"] = "none"
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
        if self.settings.llm_provider == "gemini":
            response = {"name": call.name, "response": payload}
            if call.call_id in self.native_call_ids:
                response["id"] = call.call_id
            part = {"functionResponse": response}
            if self.messages[-1]["role"] == "user" and any(
                "functionResponse" in p for p in self.messages[-1]["parts"]
            ):
                self.messages[-1]["parts"].append(part)
            else:
                self.messages.append({"role": "user", "parts": [part]})
        elif self.settings.llm_provider != "openai":
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

    def _gemini_turn(self, tools: list[dict], at_limit: bool, timeout: float) -> ModelTurn:
        started = time.monotonic()
        config = {"maxOutputTokens": 4096}
        if self.settings.active_model.startswith(("gemini-3", "gemini-4")):
            config["thinkingConfig"] = {"thinkingLevel": "LOW"}
        payload = {
            "systemInstruction": {
                "parts": [
                    {
                        "text": self.instructions
                        + "\nReturn final answers as JSON matching this schema:\n"
                        + json.dumps(self.schema)
                    }
                ]
            },
            "contents": self.messages,
            "generationConfig": config,
        }
        if at_limit:
            config["responseMimeType"] = "application/json"
            config["responseJsonSchema"] = self.schema
        else:
            payload["tools"] = [
                {
                    "functionDeclarations": [
                        {
                            "name": tool["name"],
                            "description": tool["description"],
                            "parametersJsonSchema": tool["parameters"],
                        }
                        for tool in tools
                    ]
                }
            ]
        response = self.client.generate(self.settings.active_model, payload, timeout)
        candidates = response.get("candidates", [])
        if not candidates or candidates[0].get("finishReason") != "STOP":
            raise ValueError("Gemini did not complete a usable answer")
        content = candidates[0]["content"]
        # Replay Google's entire content verbatim, including opaque signatures.
        self.messages.append(content)
        calls, texts = [], []
        for index, part in enumerate(content.get("parts", [])):
            if part.get("thought"):
                continue
            if "functionCall" in part:
                call = part["functionCall"]
                identifier = call.get("id") or f"gemini_{len(self.messages)}_{index}"
                if call.get("id"):
                    self.native_call_ids.add(identifier)
                calls.append(
                    FunctionCall(call["name"], json.dumps(call.get("args", {})), identifier)
                )
            elif "text" in part:
                texts.append(part["text"])
        if at_limit and calls:
            raise ValueError("Gemini requested tools during the final JSON answer")
        if not at_limit and not calls:
            # Function calling cannot guarantee a JSON answer. Once planning is
            # complete, request the final answer with Google's native schema.
            remaining = timeout - (time.monotonic() - started)
            if remaining <= 0:
                raise TimeoutError("Investigation deadline reached")
            self.messages.append(
                {
                    "role": "user",
                    "parts": [
                        {
                            "text": "Return the final answer now using the required JSON schema. Cite only the graph evidence retrieved in this investigation. Do not call more tools."
                        }
                    ],
                }
            )
            return self._gemini_turn(tools, True, remaining)
        return ModelTurn(text="".join(texts), calls=calls)
