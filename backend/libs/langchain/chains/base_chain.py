from __future__ import annotations

import base64

from langchain_core.language_models import BaseChatModel
from langchain_core.prompts import ChatPromptTemplate, HumanMessagePromptTemplate
from langchain_core.runnables import Runnable
from pydantic import BaseModel


def bytes_to_base64(image_bytes: bytes) -> str:
    return base64.b64encode(image_bytes).decode("utf-8") if image_bytes else ""


def create_image_formated_prompt(prompt: str, mime_type: str = "image/png") -> ChatPromptTemplate:
    """Falcon-eye compatible multimodal prompt shape.

    Keep the image and instructions in one human message because this shape is
    consistently understood by small OpenAI-compatible vision models.
    """
    return ChatPromptTemplate.from_messages(
        [
            HumanMessagePromptTemplate.from_template(
                [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime_type};base64,{{base64_image}}"},
                    },
                ]
            )
        ]
    )


def create_image_structured_output_chain(
    prompt: str,
    model: BaseChatModel,
    parser_class: type[BaseModel],
) -> Runnable:
    return create_image_formated_prompt(prompt) | model.with_structured_output(parser_class)
