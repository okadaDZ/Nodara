from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


NodeHint = Literal["trigger", "query_builder", "agent", "condition", "action", "output", "tool", "memory", "parser", "unknown"]
EdgeHint = Literal["flow", "conditional", "tool", "memory", "parser", "unknown"]


class DiagramNodeEvidence(BaseModel):
    ref: str = Field(description="Short unique reference such as n1. Use reading order, left-to-right then top-to-bottom.")
    visible_text: str = Field(default="", description="Only text visibly present inside or next to this node. Never invent text.")
    shape: str = Field(default="unknown", description="Visible shape: rectangle, diamond, circle, note, cylinder, or unknown.")
    node_type_hint: NodeHint = Field(default="unknown", description="Best visual classification. Use unknown when the image does not support a choice.")
    description_hint: str = Field(default="", description="Very short evidence-based purpose inferred from visible text; empty if uncertain.")
    confidence: float = Field(ge=0, le=1, description="Confidence that this node and its text were read correctly.")


class DiagramEdgeEvidence(BaseModel):
    source_ref: str = Field(description="Reference of the visible source node.")
    target_ref: str = Field(description="Reference of the visible target node.")
    label: str = Field(default="", description="Only the visible edge label, such as yes/no; empty when absent.")
    edge_kind_hint: EdgeHint = Field(default="unknown", description="Visual edge classification. Use conditional for labeled decision branches.")
    confidence: float = Field(ge=0, le=1, description="Confidence in arrow direction and endpoints.")


class DiagramObservation(BaseModel):
    diagram_title: str = Field(default="", description="Visible diagram title only; empty if no title is visible.")
    nodes: list[DiagramNodeEvidence] = Field(description="Every distinct visible workflow node, including isolated nodes.")
    edges: list[DiagramEdgeEvidence] = Field(description="Every visible directed connection. Do not create connections hidden by ambiguity.")
    unresolved_text: list[str] = Field(default_factory=list, description="Unreadable fragments or ambiguous labels that need user review.")
    warnings: list[str] = Field(default_factory=list, description="Concrete visual limitations such as cropped arrows or overlapping lines.")
    confidence: float = Field(ge=0, le=1, description="Overall transcription confidence for the diagram.")
