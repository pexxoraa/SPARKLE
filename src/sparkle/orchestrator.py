from __future__ import annotations

from collections.abc import Iterable

from sparkle.agents import AgentRegistry, AgentRouter, AgentSpec
from sparkle.context import ContextBuilder
from sparkle.contracts import AgentResult, Message, ModelRequest, TokenUsage
from sparkle.model import ModelError
from sparkle.registry import ModelRouter
from sparkle.tooling import ToolError, ToolRegistry, safe_tool_result
from sparkle.trace import TraceStore


class Orchestrator:
    def __init__(
        self,
        *,
        models: ModelRouter,
        agents: AgentRegistry,
        agent_router: AgentRouter,
        context: ContextBuilder,
        tools: ToolRegistry,
        traces: TraceStore,
        max_tool_rounds: int = 4,
    ):
        self.models = models
        self.agents = agents
        self.agent_router = agent_router
        self.context = context
        self.tools = tools
        self.traces = traces
        self.max_tool_rounds = max(0, max_tool_rounds)

    def run(
        self,
        text: str,
        *,
        agent_name: str | None = None,
        history: Iterable[Message] | None = None,
        user_id: str | None = None,
        additional_context: str | None = None,
        input_source: str = "text",
    ) -> AgentResult:
        if not text.strip():
            raise ValueError("Request text cannot be empty")
        spec = self.agents.get(agent_name) if agent_name else self.agent_router.select(text)
        trace_id, started = self.traces.start(input_source=input_source, agent=spec.name)
        adapter = None
        executed: list[str] = []
        data_accessed = ["memory_environment", "knowledge_environment"]
        try:
            bundle = self.context.build(text)
            rendered_context = bundle.render()
            system_parts = [spec.system_prompt()]
            if rendered_context:
                system_parts.append(rendered_context)
            if additional_context:
                system_parts.append(f"Other agent work:\n{additional_context}")
            messages = list(history or []) + [Message(role="user", content=text)]
            adapter = self.models.select(spec.capability)
            response = None
            for round_number in range(self.max_tool_rounds + 1):
                response = adapter.complete(ModelRequest(
                    messages=messages,
                    system="\n\n".join(system_parts),
                    tools=self.tools.definitions(set(spec.tools)),
                    max_output_tokens=4096,
                    temperature=1.0,
                    thinking=True,
                    metadata={"user_id": user_id} if user_id else {},
                ))
                if not response.tool_calls:
                    break
                if round_number >= self.max_tool_rounds:
                    raise RuntimeError("Model exceeded the configured tool-call round limit")
                messages.append(Message(
                    role="assistant", content=response.text, tool_calls=response.tool_calls,
                    provider_state=response.raw_assistant_content,
                ))
                for call in response.tool_calls:
                    try:
                        result = self.tools.execute(call.name, call.arguments, allowed=set(spec.tools))
                    except (ToolError, ValueError, TypeError) as exc:
                        result = {"ok": False, "error": str(exc), "error_type": type(exc).__name__}
                    executed.append(call.name)
                    messages.append(Message(role="tool", content=safe_tool_result(result), tool_call_id=call.id, name=call.name))
            if response is None:
                raise RuntimeError("Model execution produced no response")
            result = AgentResult(
                agent=spec.name, text=response.text, model=response.model, provider=response.provider,
                trace_id=trace_id, finish_reason=response.finish_reason, usage=response.usage,
                tool_calls_executed=executed,
            )
            self.traces.finish(
                trace_id, started, status="success", agent=spec.name, model=response.model,
                provider=response.provider, tools=executed, data_accessed=data_accessed,
                transformations=["context_retrieval", "agent_reasoning", "tool_loop" if executed else "direct_completion"],
                storage_destinations=["trace_environment"], result_summary=response.text,
            )
            return result
        except Exception as exc:
            self.traces.finish(
                trace_id, started, status="failure", agent=spec.name,
                model=getattr(adapter, "model_id", None), provider=getattr(adapter, "provider", None),
                tools=executed, data_accessed=data_accessed, storage_destinations=["trace_environment"],
                error_type=type(exc).__name__, result_summary=str(exc),
            )
            if isinstance(exc, ModelError):
                raise
            raise

    def run_multi(
        self,
        text: str,
        *,
        agent_names: list[str] | None = None,
        user_id: str | None = None,
        input_source: str = "text",
    ) -> AgentResult:
        specs = [self.agents.get(name) for name in agent_names] if agent_names else self.agent_router.select_many(text)
        if len(specs) == 1:
            return self.run(
                text, agent_name=specs[0].name, user_id=user_id,
                input_source=input_source,
            )
        peer_outputs: list[str] = []
        for spec in specs:
            output = self.run(
                text, agent_name=spec.name, user_id=user_id,
                input_source=input_source,
            )
            peer_outputs.append(f"[{spec.name}]\n{output.text}")
        return self.run(
            "Synthesize the specialist analyses into one verified, actionable answer for the original request:\n\n" + text,
            agent_name="personal", user_id=user_id,
            additional_context="\n\n".join(peer_outputs), input_source=input_source,
        )
