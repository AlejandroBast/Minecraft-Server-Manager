"""Motor de recomendaciones de hardware.

Función pura: recibe números y devuelve una estimación. No consulta el sistema,
no toca disco y no bloquea nada — sólo aconseja, según la filosofía del
proyecto. Esto la hace comprobable con datos sintéticos.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.models.enums import ServerType

# RAM que se reserva para el sistema operativo y el resto de programas.
OS_RESERVED_MB = 2048
MIN_SERVER_MB = 1024

# Eficiencia relativa por tipo de servidor (1.0 = vanilla).
# Paper y Purpur optimizan el tick; Forge/NeoForge cargan mods pesados.
TYPE_EFFICIENCY: dict[ServerType, float] = {
    ServerType.VANILLA: 1.0,
    ServerType.SPIGOT: 1.15,
    ServerType.PAPER: 1.4,
    ServerType.PURPUR: 1.4,
    ServerType.FABRIC: 0.95,
    ServerType.FORGE: 0.7,
    ServerType.NEOFORGE: 0.7,
}

PLAYER_BUCKETS: tuple[int, ...] = (0, 5, 15, 30, 50, 100, 200)


@dataclass(frozen=True)
class HardwareSnapshot:
    """Datos mínimos del equipo necesarios para estimar."""

    total_memory_mb: int
    available_memory_mb: int
    physical_cores: int
    cpu_frequency_mhz: float
    free_disk_gb: float


@dataclass(frozen=True)
class Recommendation:
    server_type: ServerType
    estimated_players: int
    memory_min_mb: int
    memory_max_mb: int
    warnings: list[str] = field(default_factory=list)


def _bucket(value: float) -> int:
    """Redondea a la baja al tramo publicado más cercano."""
    result = PLAYER_BUCKETS[0]
    for bucket in PLAYER_BUCKETS:
        if value >= bucket:
            result = bucket
    return result


def recommend(hardware: HardwareSnapshot, server_type: ServerType) -> Recommendation:
    efficiency = TYPE_EFFICIENCY[server_type]
    warnings: list[str] = []

    usable_mb = max(hardware.total_memory_mb - OS_RESERVED_MB, 0)
    if usable_mb < MIN_SERVER_MB:
        warnings.append(
            "El equipo tiene muy poca RAM libre para el sistema y un servidor a la vez."
        )

    # Reparto habitual: la mitad de la RAM utilizable, entre 1 y 8 GB.
    memory_max_mb = int(min(max(usable_mb // 2, MIN_SERVER_MB), 8192))
    memory_min_mb = max(memory_max_mb // 2, MIN_SERVER_MB)
    if memory_min_mb > memory_max_mb:
        memory_min_mb = memory_max_mb

    # Estimaciones independientes: gana la más restrictiva.
    by_memory = max((memory_max_mb - 512) / 1024.0, 0) * 12 * efficiency
    ghz = max(hardware.cpu_frequency_mhz, 1000) / 1000.0
    by_cpu = max(hardware.physical_cores, 1) * 7 * ghz * efficiency

    estimated = _bucket(min(by_memory, by_cpu))

    if hardware.physical_cores <= 2:
        warnings.append(
            "Con 2 núcleos o menos el rendimiento cae rápido a partir de unos pocos jugadores."
        )
    if hardware.available_memory_mb < memory_max_mb:
        warnings.append(
            "Ahora mismo hay menos RAM libre que la asignada al servidor: "
            "cierra otros programas antes de arrancarlo."
        )
    if hardware.free_disk_gb < 5:
        warnings.append("Queda menos de 5 GB libres en disco; los mundos y backups crecen rápido.")
    if server_type.supports_mods:
        warnings.append("Los mods aumentan mucho el consumo: la estimación puede quedarse corta.")

    return Recommendation(
        server_type=server_type,
        estimated_players=estimated,
        memory_min_mb=memory_min_mb,
        memory_max_mb=memory_max_mb,
        warnings=warnings,
    )
