from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from functools import lru_cache
from typing import Any, Type, TypeVar
from pydantic import BaseModel
from core.settings import settings
from libs.langchain.langfuse_client import langchain_config

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class BaseAIProvider(ABC):
    @abstractmethod
    async def generate_text(
        self, prompt: str, system_prompt: str | None = None, model_name: str | None = None
    ) -> str:
        """Generate unstructured text from prompt."""
        pass

    @abstractmethod
    async def generate_structured(
        self, prompt: str, schema: Type[T], system_prompt: str | None = None
    ) -> T:
        """Generate structured output validated against a Pydantic schema."""
        pass

    @abstractmethod
    async def analyze_image(
        self,
        image_bytes: bytes,
        prompt: str,
        schema: Type[T] | None = None,
        mime_type: str = "image/jpeg",
    ) -> Any:
        """Analyze an image using a vision model."""
        pass

    @abstractmethod
    async def transcribe_audio(
        self,
        audio_bytes: bytes,
        filename: str = "recording.m4a",
        mime_type: str = "audio/m4a",
    ) -> str:
        """Transcribe speech audio to text."""
        pass


class OpenAIProvider(BaseAIProvider):
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.openai.com/v1",
        model: str = "gpt-4o-mini",
        vision_model: str = "gpt-4o-mini",
        transcription_model: str = "whisper-1",
        temperature: float = 0.0,
        timeout: int = 120,
        max_retries: int = 2,
    ):
        self.api_key = api_key
        self.base_url = base_url
        self.model_name = model
        self.vision_model_name = vision_model
        self.transcription_model_name = transcription_model

        from langchain_openai import ChatOpenAI

        self.llm = ChatOpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            model=self.model_name,
            temperature=temperature,
            timeout=timeout,
            max_retries=max_retries,
        )
        self.vision_llm = ChatOpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            model=self.vision_model_name,
            temperature=temperature,
            timeout=timeout,
            max_retries=max_retries,
        )

    async def generate_text(
        self, prompt: str, system_prompt: str | None = None, model_name: str | None = None
    ) -> str:
        from langchain_core.messages import HumanMessage, SystemMessage

        messages = []
        if system_prompt:
            messages.append(SystemMessage(content=system_prompt))
        messages.append(HumanMessage(content=prompt))
        llm = self.llm if not model_name or model_name == self.model_name else self.llm.bind(model=model_name)
        response = await llm.ainvoke(
            messages,
            config=langchain_config(
                "llm.generate-text", metadata={"model": model_name or self.model_name}
            ),
        )
        return response.content if isinstance(response.content, str) else str(response.content)

    async def generate_structured(
        self, prompt: str, schema: Type[T], system_prompt: str | None = None
    ) -> T:
        structured_llm = self.llm.with_structured_output(schema)
        from langchain_core.messages import HumanMessage, SystemMessage

        messages = []
        if system_prompt:
            messages.append(SystemMessage(content=system_prompt))
        messages.append(HumanMessage(content=prompt))
        return await structured_llm.ainvoke(
            messages,
            config=langchain_config(
                f"llm.structured.{schema.__name__}", metadata={"model": self.model_name}
            ),
        )

    async def analyze_image(
        self,
        image_bytes: bytes,
        prompt: str,
        schema: Type[T] | None = None,
        mime_type: str = "image/jpeg",
    ) -> Any:
        from libs.langchain.chains.base_chain import bytes_to_base64, create_image_formated_prompt

        messages = create_image_formated_prompt(prompt, mime_type).format_messages(
            base64_image=bytes_to_base64(image_bytes)
        )

        if schema:
            structured_vision = self.vision_llm.with_structured_output(schema)
            return await structured_vision.ainvoke(
                messages,
                config=langchain_config(
                    f"vision.structured.{schema.__name__}",
                    metadata={"model": self.vision_model_name, "mime_type": mime_type},
                ),
            )
        else:
            res = await self.vision_llm.ainvoke(
                messages,
                config=langchain_config(
                    "vision.analyze",
                    metadata={"model": self.vision_model_name, "mime_type": mime_type},
                ),
            )
            return res.content

    async def transcribe_audio(
        self,
        audio_bytes: bytes,
        filename: str = "recording.m4a",
        mime_type: str = "audio/m4a",
    ) -> str:
        import httpx

        headers = {"Authorization": f"Bearer {self.api_key}"}
        url = f"{self.base_url.rstrip('/')}/audio/transcriptions"
        files = {"file": (filename, audio_bytes, mime_type)}
        data = {"model": self.transcription_model_name}

        from libs.langchain.langfuse_client import trace_scope

        with trace_scope(
            "audio.transcribe",
            input={"filename": filename, "mime_type": mime_type, "audio_bytes": len(audio_bytes)},
            tags=["audio", "transcription"],
            metadata={"model": self.transcription_model_name},
            as_type="generation",
        ) as trace:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(url, headers=headers, files=files, data=data)
                response.raise_for_status()
                text = response.json().get("text", "")
                trace.update(output={"character_count": len(text)})
                return text


class MockAIProvider(BaseAIProvider):
    """Fallback provider that generates realistic multi-agent workflows offline."""

    async def generate_text(
        self, prompt: str, system_prompt: str | None = None, model_name: str | None = None
    ) -> str:
        lower = prompt.lower()
        if "generate instructions" in lower or "what this agent should do" in lower:
            return (
                "1. Analyze incoming request and prior agent outputs.\n"
                "2. Perform domain synthesis according to specified constraints.\n"
                "3. Format clear output ready for the next agent."
            )
        if "improve" in lower or "feedback" in lower:
            return (
                "Refined Instructions:\n"
                "- Verify all input parameters carefully.\n"
                "- Produce structured, bullet-point summaries.\n"
                "- Guarantee high fidelity output."
            )
        return (
            f"Agent completed synthesis based on input:\n\n"
            f"- Evaluated core parameters\n"
            f"- Processed findings\n"
            f"- Summary: Step executed successfully."
        )

    async def generate_structured(
        self, prompt: str, schema: Type[T], system_prompt: str | None = None
    ) -> T:
        lower = prompt.lower()
        from libs.models.workflow import Workflow, WorkflowNode, WorkflowEdge

        if "restaurant" in lower or "food" in lower or "dubai" in lower:
            nodes = [
                {"id": "agent_1", "name": "Restaurant Researcher", "description": "Search top dining spots", "instructions": "Search and identify high-rated restaurants matching criteria."},
                {"id": "agent_2", "name": "Review & Price Comparator", "description": "Compare ratings and pricing", "instructions": "Compare options based on ratings, reviews, and average price."},
                {"id": "agent_3", "name": "Recommendation Agent", "description": "Recommend the top 3", "instructions": "Format top 3 recommendations with clear highlights."}
            ]
            edges = [
                {"source": "agent_1", "target": "agent_2"},
                {"source": "agent_2", "target": "agent_3"}
            ]
            name = "Restaurant Finder Workflow"
            desc = "Find, compare, and recommend top dining options"
        elif "news" in lower or "linkedin" in lower or "post" in lower:
            nodes = [
                {"id": "agent_1", "name": "News Researcher", "description": "Find top news stories", "instructions": "Find the top 5 most important news articles on the requested topic."},
                {"id": "agent_2", "name": "Summarizer", "description": "Summarize key highlights", "instructions": "Summarize the core takeaways concisely."},
                {"id": "agent_3", "name": "Post Writer", "description": "Draft social post", "instructions": "Write an engaging post ready for publication."}
            ]
            edges = [
                {"source": "agent_1", "target": "agent_2"},
                {"source": "agent_2", "target": "agent_3"}
            ]
            name = "News Summarizer & Post Creator"
            desc = "Researches trending stories and writes an engaging summary post"
        elif "travel" in lower or "trip" in lower:
            nodes = [
                {"id": "agent_1", "name": "Destination Explorer", "description": "Identify top attractions", "instructions": "Identify key landmarks and local experiences."},
                {"id": "agent_2", "name": "Lodging & Route Planner", "description": "Compare accommodations", "instructions": "Evaluate lodging and transit routes."},
                {"id": "agent_3", "name": "Itinerary Builder", "description": "Build day-by-day plan", "instructions": "Create a day-by-day travel schedule."}
            ]
            edges = [
                {"source": "agent_1", "target": "agent_2"},
                {"source": "agent_2", "target": "agent_3"}
            ]
            name = "Travel Itinerary Planner"
            desc = "Plan destination activities, lodging, and daily itineraries"
        else:
            nodes = [
                {"id": "agent_1", "name": "Primary Researcher", "description": "Gather context and facts", "instructions": "Research and gather context on user request."},
                {"id": "agent_2", "name": "Analysis & Synthesis Agent", "description": "Synthesize key data", "instructions": "Analyze facts and formulate insights."},
                {"id": "agent_3", "name": "Final Delivery Agent", "description": "Draft final output", "instructions": "Deliver structured and polished final output."}
            ]
            edges = [
                {"source": "agent_1", "target": "agent_2"},
                {"source": "agent_2", "target": "agent_3"}
            ]
            name = "Automated Agent Pipeline"
            desc = "Multi-agent workflow generated for requested task"

        data = {
            "name": name,
            "description": desc,
            "nodes": nodes,
            "edges": edges,
        }
        return schema.model_validate(data)

    async def analyze_image(
        self,
        image_bytes: bytes,
        prompt: str,
        schema: Type[T] | None = None,
        mime_type: str = "image/jpeg",
    ) -> Any:
        # The offline fallback intentionally exercises the full graph experience:
        # fan-out, parallel stages, multi-input merges, and bounded iterative agents.
        data = {
            "name": "Adaptive Launch Intelligence",
            "description": "A complex agent workflow extracted in offline demo mode",
            "nodes": [
                {"id": "intake", "type": "trigger", "name": "Image Received", "description": "Starts when a diagram is submitted", "instructions": "Normalize the request, identify constraints, and produce a concise execution brief."},
                {"id": "visual", "name": "Diagram Analyst", "description": "Reads visual structure and relationships", "instructions": "Extract visual evidence, labels, and relationships from the source diagram."},
                {"id": "research", "name": "Domain Researcher", "description": "Collects facts and external context", "instructions": "Research the domain and return sourced findings relevant to the execution brief."},
                {"id": "constraints", "type": "condition", "name": "Diagram Complete?", "description": "Routes complete and incomplete diagrams", "instructions": "Check whether the diagram contains readable nodes and connections. State either complete or incomplete."},
                {"id": "risks", "name": "Risk Scout", "description": "Finds failure modes independently", "instructions": "Identify operational, quality, and compliance risks in parallel with research."},
                {"id": "architecture", "name": "Solution Architect", "description": "Merges evidence into a coherent plan", "instructions": "Merge visual, research, and constraint outputs into a structured solution plan."},
                {"id": "risk_review", "name": "Risk Reviewer", "description": "Challenges and prioritizes identified risks", "instructions": "Review risks recursively for up to 2 passes, stopping early when no material gaps remain."},
                {"id": "draft", "name": "Draft Builder", "description": "Creates the primary deliverable", "instructions": "Build the first complete deliverable from the approved architecture."},
                {"id": "tests", "name": "Test Designer", "description": "Designs independent validation scenarios", "instructions": "Create success, edge-case, and failure tests for the proposed solution."},
                {"id": "critic", "name": "Iterative Critic", "description": "Reviews and improves the combined result", "instructions": "Evaluate the draft, tests, and risk review. Iterate internally for at most 3 passes or until every blocking issue is resolved."},
                {"id": "final", "type": "output", "name": "Quality Gate", "description": "Produces the final approved output", "instructions": "Verify completeness, accuracy, and clarity, then produce the final approved result."},
                {"id": "not_ready", "type": "output", "name": "Needs Better Image", "description": "Explains what must be recaptured", "instructions": "Explain which parts of the diagram are unreadable or disconnected."},
                {"id": "memory", "type": "memory", "name": "Workflow Memory", "description": "Keeps shared context across agent stages", "instructions": "Retain the normalized brief and important decisions."},
                {"id": "search_tool", "type": "tool", "name": "Research Tools", "description": "Provides external research capabilities", "instructions": "Search trusted sources required by the researcher."},
                {"id": "parser", "type": "parser", "name": "Structured Parser", "description": "Validates the final output schema", "instructions": "Parse and validate the final result into structured sections."},
            ],
            "edges": [
                {"source": "intake", "target": "visual"},
                {"source": "intake", "target": "research"},
                {"source": "intake", "target": "constraints", "kind": "flow", "label": "inspect"},
                {"source": "intake", "target": "risks"},
                {"source": "visual", "target": "architecture"},
                {"source": "research", "target": "architecture"},
                {"source": "constraints", "target": "architecture", "kind": "conditional", "label": "complete"},
                {"source": "constraints", "target": "not_ready", "kind": "conditional", "label": "incomplete"},
                {"source": "risks", "target": "risk_review"},
                {"source": "architecture", "target": "draft"},
                {"source": "architecture", "target": "tests"},
                {"source": "draft", "target": "critic"},
                {"source": "tests", "target": "critic"},
                {"source": "risk_review", "target": "critic"},
                {"source": "critic", "target": "final", "kind": "flow", "label": "approved"},
                {"source": "memory", "target": "architecture", "kind": "memory", "label": "context"},
                {"source": "search_tool", "target": "research", "kind": "tool", "label": "tools"},
                {"source": "parser", "target": "final", "kind": "parser", "label": "schema"},
            ],
        }
        if schema:
            return schema.model_validate(data)
        return data

    async def transcribe_audio(
        self,
        audio_bytes: bytes,
        filename: str = "recording.m4a",
        mime_type: str = "audio/m4a",
    ) -> str:
        return "I want one agent to research restaurants in Dubai, then another agent should compare them based on reviews and price, and finally another agent should recommend the best three."


@lru_cache
def get_ai_provider() -> BaseAIProvider:
    """Factory to retrieve configured AI Provider."""
    if settings.llm_api_key and settings.llm_api_key.strip():
        try:
            return OpenAIProvider(
                api_key=settings.llm_api_key,
                base_url=settings.llm_base_url,
                model=settings.llm_model,
                vision_model=settings.vision_model,
                transcription_model=settings.transcription_model,
                temperature=settings.llm_temperature,
                timeout=settings.llm_request_timeout_seconds,
                max_retries=settings.llm_max_retries,
            )
        except Exception as exc:
            if settings.use_mock_ai_fallback:
                logger.warning("Could not initialize OpenAIProvider, falling back to POC demo: %s", exc)
                return MockAIProvider()
            raise
    if settings.use_mock_ai_fallback:
        logger.info("No LLM_API_KEY configured; using the explicit POC demo workflow")
        return MockAIProvider()
    raise RuntimeError("LLM_API_KEY is required when USE_MOCK_AI_FALLBACK=false")


def create_request_provider(
    api_key: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
) -> BaseAIProvider:
    """Create a request-scoped provider, falling back to backend configuration."""
    if not any((api_key, base_url, model)):
        return get_ai_provider()
    resolved_key = (api_key or settings.llm_api_key).strip()
    if not resolved_key:
        if settings.use_mock_ai_fallback:
            return MockAIProvider()
        raise RuntimeError("An API key is required for a custom LLM provider")
    resolved_model = model or settings.llm_model
    return OpenAIProvider(
        api_key=resolved_key,
        base_url=base_url or settings.llm_base_url,
        model=resolved_model,
        vision_model=resolved_model,
        transcription_model=settings.transcription_model,
        temperature=settings.llm_temperature,
        timeout=settings.llm_request_timeout_seconds,
        max_retries=settings.llm_max_retries,
    )
