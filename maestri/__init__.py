# -*- coding: utf-8 -*-
"""
Pacote Maestri 2.0 — Pipeline em 9 Nós de Auditoria IA, Governança e Confiabilidade AQF
Integrado nativamente ao Portal Central PCM Cepêra (MAESTRI-PCM.html).
"""

from .dominio import (
    VERSAO_MAESTRI,
    CATEGORIAS,
    EQUIPES,
    SINAIS_VALIDOS,
    DIST_REFERENCIA,
    REGUA_OFICIAL,
    PARADAS_BIB,
    normalizar,
    evidencias,
    calcular_severidade,
    score_quebra,
    validar,
    fallback_deterministico,
    decidir_fast_path,
    calcular_score_qualidade_apontamento,
)
from .nos import MaestriPipeline, DEFINICAO_NOS

__all__ = [
    "VERSAO_MAESTRI",
    "CATEGORIAS",
    "EQUIPES",
    "SINAIS_VALIDOS",
    "DIST_REFERENCIA",
    "REGUA_OFICIAL",
    "PARADAS_BIB",
    "DEFINICAO_NOS",
    "MaestriPipeline",
    "normalizar",
    "evidencias",
    "calcular_severidade",
    "score_quebra",
    "validar",
    "fallback_deterministico",
    "decidir_fast_path",
    "calcular_score_qualidade_apontamento",
]
