"""Enumeraciones compartidas entre modelos, esquemas y servicios."""

from __future__ import annotations

from enum import StrEnum


class ServerType(StrEnum):
    VANILLA = "vanilla"
    PAPER = "paper"
    PURPUR = "purpur"
    SPIGOT = "spigot"
    FABRIC = "fabric"
    FORGE = "forge"
    NEOFORGE = "neoforge"

    @property
    def supports_plugins(self) -> bool:
        return self in {ServerType.PAPER, ServerType.PURPUR, ServerType.SPIGOT}

    @property
    def supports_mods(self) -> bool:
        return self in {ServerType.FABRIC, ServerType.FORGE, ServerType.NEOFORGE}


class ServerStatus(StrEnum):
    STOPPED = "stopped"
    STARTING = "starting"
    ONLINE = "online"
    STOPPING = "stopping"
    RESTARTING = "restarting"
    SAVING = "saving"
    INSTALLING = "installing"
    ERROR = "error"

    @property
    def is_active(self) -> bool:
        """El servidor está en uso: no se puede borrar ni reconfigurar en caliente."""
        return self not in {ServerStatus.STOPPED, ServerStatus.ERROR}


class Difficulty(StrEnum):
    PEACEFUL = "peaceful"
    EASY = "easy"
    NORMAL = "normal"
    HARD = "hard"


class GameMode(StrEnum):
    SURVIVAL = "survival"
    CREATIVE = "creative"
    ADVENTURE = "adventure"
    SPECTATOR = "spectator"


class BackupStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
