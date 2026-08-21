import base64
import json
import logging
from abc import ABC, abstractmethod
from typing import Any, Optional, Type, TypeVar
from pydantic import BaseModel
from app.config import settings

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class BaseAIProvider(ABC):
    @abstractmethod
    async def generate_text(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        pass

    @abstractmethod
    async def generate_structured(
        self, prompt: str, schema: Type[T], system_prompt: Optional[str] = None
    ) -> T:
        pass

    @abstractmethod
    async def analyze_image(
        self, image_bytes: bytes, prompt: str, schema: Optional[Type[T]] = None, mime_type: str = "image/jpeg"
    ) -> Any:
        pass

    @abstractmethod
    async def transcribe_audio(
        self, audio_bytes: bytes, filename: str = "recording.m4a", mime_type: str = "audio/m4a"
    ) -> str:
        pass


class OpenAIProvider(BaseAIProvider):
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.openai.com/v1",
        model: str = "gpt-4o-mini",
        vision_model: str = "gpt-4o-mini",
        transcription_model: str = "whisper-1",
    ):
        self.api_key = api_key
        self.base_url = base_url
        self.model_name = model
        self.vision_model_name = vision_model
        self.transcription_model_name = transcription_model

        try:
            from langchain_openai import ChatOpenAI
            self.llm = ChatOpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                model=self.model_name,
                temperature=0.2,
            )
            self.vision_llm = ChatOpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                model=self.vision_model_name,
                temperature=0.2,
            )
        except Exception as e:
            logger.warning(f"Could not initialize ChatOpenAI: {e}")
            self.llm = None
            self.vision_llm = None

    async def generate_text(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        from langchain_core.messages import HumanMessage, SystemMessage
        messages = []
        if system_prompt:
            messages.append(SystemMessage(content=system_prompt))
        messages.append(HumanMessage(content=prompt))
        response = await self.llm.ainvoke(messages)
        return response.content if isinstance(response.content, str) else str(response.content)

    async def generate_structured(
        self, prompt: str, schema: Type[T], system_prompt: Optional[str] = None
    ) -> T:
        structured_llm = self.llm.with_structured_output(schema)
        from langchain_core.messages import HumanMessage, SystemMessage
        messages = []
        if system_prompt:
            messages.append(SystemMessage(content=system_prompt))
        messages.append(HumanMessage(content=prompt))
        result = await structured_llm.ainvoke(messages)
        return result

    async def analyze_image(
        self, image_bytes: bytes, prompt: str, schema: Optional[Type[T]] = None, mime_type: str = "image/jpeg"
    ) -> Any:
        import httpx
        b64_image = base64.b64encode(image_bytes).decode("utf-8")
        image_url = f"data:{mime_type};base64,{b64_image}"

        if schema:
            structured_vision = self.vision_llm.with_structured_output(schema)
            from langchain_core.messages import HumanMessage
            content = [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": image_url}},
            ]
            message = HumanMessage(content=content)
            return await structured_vision.ainvoke([message])
        else:
            from langchain_core.messages import HumanMessage
            content = [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": image_url}},
            ]
            message = HumanMessage(content=content)
            res = await self.vision_llm.ainvoke([message])
            return res.content

    async def transcribe_audio(
        self, audio_bytes: bytes, filename: str = "recording.m4a", mime_type: str = "audio/m4a"
    ) -> str:
        import httpx
        headers = {"Authorization": f"Bearer {self.api_key}"}
        url = f"{self.base_url.rstrip('/')}/audio/transcriptions"
        files = {"file": (filename, audio_bytes, mime_type)}
        data = {"model": self.transcription_model_name}

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(url, headers=headers, files=files, data=data)
            response.raise_for_status()
            res_json = response.json()
            return res_json.get("text", "")


class MockAIProvider(BaseAIProvider):
    """
    High-fidelity mock AI provider for offline testing and development
    without requiring active OpenAI credentials.
    """

    async def generate_text(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        if "generate instructions" in prompt.lower() or "instruction" in (system_prompt or "").lower():
            return (
                "Execute the task diligently.\n"
                "1. Review the input thoroughly.\n"
                "2. Apply domain analysis and verify factual correctness.\n"
                "3. Structure the output clearly with key takeaways for the next workflow agent."
            )
        if "improve" in prompt.lower():
            return f"Enhanced instructions:\n- Validate input parameters.\n- Provide detailed synthesis.\n- Ensure structured clarity."
        return f"Synthesized output based on:\n{prompt[:200]}...\n\nResult:\n- Step completed successfully.\n- Key insights synthesized."

    async def generate_structured(
        self, prompt: str, schema: Type[T], system_prompt: Optional[str] = None
    ) -> T:
        from app.models.workflow import Workflow, WorkflowNode, WorkflowEdge
        # Check if schema is for Workflow or Workflow generation
        schema_name = getattr(schema, "__name__", "")
        
        # Simple intelligent parsing of prompt
        lower = prompt.lower()
        if "restaurant" in lower:
            wf = Workflow(
                name="Restaurant Finder Workflow",
                description="Find, compare, and recommend the best restaurants based on preferences",
                nodes=[
                    WorkflowNode(id="node_1", type="agent", name="Restaurant Researcher", description="Search for top rated restaurants", instructions="Search for top rated dining venues matching user constraints."),
                    WorkflowNode(id="node_2", type="agent", name="Comparison Agent", description="Compare prices and reviews", instructions="Analyze and rank restaurants based on user reviews, ambiance, and price."),
                    WorkflowNode(id="node_3", type="agent", name="Recommendation Agent", description="Recommend top 3 options", instructions="Format the top 3 best restaurant recommendations with reasons.")
                ],
                edges=[
                    WorkflowEdge(id="edge_1", source="node_1", target="node_2"),
                    WorkflowEdge(id="edge_2", source="node_2", target="node_3")
                ]
            )
        elif "news" in lower or "linkedin" in lower or "post" in lower:
            wf = Workflow(
                name="News Summarizer & Post Creator",
                description="Researches trending news stories, synthesizes key highlights, and writes an engaging post",
                nodes=[
                    WorkflowNode(id="node_1", type="agent", name="News Researcher", description="Gathers current headlines", instructions="Find the top 5 most important news articles on the requested topic."),
                    WorkflowNode(id="node_2", type="agent", name="Synthesizer", description="Extracts key facts", instructions="Summarize the core takeaways and impact points concisely."),
                    WorkflowNode(id="node_3", type="agent", name="Content Writer", description="Drafts engaging post", instructions="Write a polished post ready for publication.")
                ],
                edges=[
                    WorkflowEdge(id="edge_1", source="node_1", target="node_2"),
                    WorkflowEdge(id="edge_2", source="node_2", target="node_3")
                ]
            )
        elif "travel" in lower or "trip" in lower:
            wf = Workflow(
                name="Travel Planner Workflow",
                description="Plan destination activities, compare lodging, and build an itinerary",
                nodes=[
                    WorkflowNode(id="node_1", type="agent", name="Destination Researcher", description="Explore attractions", instructions="Identify top attractions and local experiences."),
                    WorkflowNode(id="node_2", type="agent", name="Budget & Lodging Planner", description="Compare options", instructions="Compare neighborhood stays and transit convenience."),
                    WorkflowNode(id="node_3", type="agent", name="Itinerary Builder", description="Construct daily schedule", instructions="Generate a complete day-by-day travel itinerary.")
                ],
                edges=[
                    WorkflowEdge(id="edge_1", source="node_1", target="node_2"),
                    WorkflowEdge(id="edge_2", source="node_2", target="node_3")
                ]
            )
        else:
            # Generic workflow from prompt
            wf = Workflow(
                name="Custom Agent Pipeline",
                description=f"Generated workflow for: {prompt[:40]}...",
                nodes=[
                    WorkflowNode(id="node_1", type="agent", name="Primary Analyzer", description="Analyze input context", instructions=f"Analyze input: {prompt}"),
                    WorkflowNode(id="node_2", type="agent", name="Processor & Evaluator", description="Process information", instructions="Evaluate data and apply decision rules."),
                    WorkflowNode(id="node_3", type="agent", name="Final Publisher", description="Format final output", instructions="Deliver clear, actionable results.")
                ],
                edges=[
                    WorkflowEdge(id="edge_1", source="node_1", target="node_2"),
                    WorkflowEdge(id="edge_2", source="node_2", target="node_3")
                ]
            )

        if schema == Workflow:
            return wf  # type: ignore

        # If schema is a container like GeneratedWorkflow
        try:
            return schema.model_validate(wf.model_dump())
        except Exception:
            return wf  # type: ignore

    async def analyze_image(
        self, image_bytes: bytes, prompt: str, schema: Optional[Type[T]] = None, mime_type: str = "image/jpeg"
    ) -> Any:
        from app.models.workflow import Workflow, WorkflowNode, WorkflowEdge
        wf = Workflow(
            name="Hand-Drawn Workflow",
            description="Workflow extracted from diagram photograph",
            nodes=[
                WorkflowNode(id="node_1", type="agent", name="Researcher", description="Conducts initial research", instructions="Research topic and collect relevant facts."),
                WorkflowNode(id="node_2", type="agent", name="Writer", description="Drafts content based on research", instructions="Synthesize findings into draft content."),
                WorkflowNode(id="node_3", type="agent", name="Reviewer", description="Checks quality and accuracy", instructions="Review draft for accuracy, clarity, and tone.")
            ],
            edges=[
                WorkflowEdge(id="edge_1", source="node_1", target="node_2"),
                WorkflowEdge(id="edge_2", source="node_2", target="node_3")
            ]
        )
        if schema:
            try:
                return schema.model_validate(wf.model_dump())
            except Exception:
                return wf
        return wf

    async def transcribe_audio(
        self, audio_bytes: bytes, filename: str = "recording.m4a", mime_type: str = "audio/m4a"
    ) -> str:
        return "I want one agent to research restaurants in Dubai, then another agent should compare them based on reviews and price, and finally another agent should recommend the best three."


def get_ai_provider() -> BaseAIProvider:
    if settings.LLM_API_KEY and settings.LLM_API_KEY.strip():
        try:
            return OpenAIProvider(
                api_key=settings.LLM_API_KEY,
                base_url=settings.LLM_BASE_URL,
                model=settings.LLM_MODEL,
                vision_model=settings.VISION_MODEL,
                transcription_model=settings.TRANSCRIPTION_MODEL,
            )
        except Exception as e:
            logger.warning(f"Falling back to MockAIProvider due to: {e}")
            return MockAIProvider()
    return MockAIProvider()
