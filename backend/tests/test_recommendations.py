"""Pruebas del motor de recomendaciones con hardware sintético."""

from __future__ import annotations

from app.models.enums import ServerType
from app.services.recommendations import HardwareSnapshot, recommend

EQUIPO_MODESTO = HardwareSnapshot(
    total_memory_mb=4096,
    available_memory_mb=2048,
    physical_cores=2,
    cpu_frequency_mhz=2400,
    free_disk_gb=40,
)
EQUIPO_POTENTE = HardwareSnapshot(
    total_memory_mb=32768,
    available_memory_mb=24576,
    physical_cores=8,
    cpu_frequency_mhz=4200,
    free_disk_gb=500,
)


def test_mas_hardware_permite_mas_jugadores() -> None:
    modesto = recommend(EQUIPO_MODESTO, ServerType.PAPER)
    potente = recommend(EQUIPO_POTENTE, ServerType.PAPER)
    assert potente.estimated_players > modesto.estimated_players


def test_paper_rinde_mas_que_vanilla_y_forge() -> None:
    paper = recommend(EQUIPO_POTENTE, ServerType.PAPER)
    vanilla = recommend(EQUIPO_POTENTE, ServerType.VANILLA)
    forge = recommend(EQUIPO_POTENTE, ServerType.FORGE)
    assert paper.estimated_players >= vanilla.estimated_players >= forge.estimated_players


def test_memoria_sugerida_coherente() -> None:
    for tipo in ServerType:
        resultado = recommend(EQUIPO_POTENTE, tipo)
        assert resultado.memory_min_mb <= resultado.memory_max_mb
        assert resultado.memory_max_mb <= 8192


def test_equipo_muy_limitado_avisa_pero_no_bloquea() -> None:
    minimo = HardwareSnapshot(
        total_memory_mb=2048,
        available_memory_mb=512,
        physical_cores=1,
        cpu_frequency_mhz=1600,
        free_disk_gb=2,
    )
    resultado = recommend(minimo, ServerType.VANILLA)
    assert resultado.estimated_players >= 0
    assert len(resultado.warnings) >= 3


def test_los_mods_siempre_avisan() -> None:
    resultado = recommend(EQUIPO_POTENTE, ServerType.FABRIC)
    assert any("mods" in aviso for aviso in resultado.warnings)
