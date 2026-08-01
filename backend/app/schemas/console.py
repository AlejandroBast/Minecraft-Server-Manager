"""Esquemas de la consola de servidores."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ConsoleLine(BaseModel):
    index: int
    line: str


class ConsoleOutput(BaseModel):
    lines: list[ConsoleLine]
    next_index: int
    running: bool


class ConsoleCommand(BaseModel):
    command: str = Field(min_length=1, max_length=500)


class ConsoleCommandResult(BaseModel):
    sent: str
