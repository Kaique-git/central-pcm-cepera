#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
maestri/cli.py — CLI do Orquestrador em 9 Nós do Projeto Maestri 2.0.
Exemplo:
  python3 -m maestri.cli --entrada dados_brutos_para_ia.csv --saida-portal maestri_portal_sync.json
"""

import argparse
import sys
from .nos import MaestriPipeline


def main(argv=None):
    parser = argparse.ArgumentParser(description="Maestri 2.0 — Pipeline de 9 Nós (Auditoria IA & Confiabilidade AQF)")
    parser.add_argument("--entrada", "-e", default="dados_brutos_para_ia.csv", help="Planilha .csv ou .xlsx do ERP")
    parser.add_argument("--saida-csv", default="OMs_Auditadas.csv", help="Arquivo CSV auditado de saída")
    parser.add_argument("--saida-portal", default="maestri_portal_sync.json", help="Pacote JSON para sincronizar com MAESTRI-PCM.html")
    parser.add_argument("--biblioteca", default="correcoes.jsonl", help="Caminho da biblioteca correcoes.jsonl")
    parser.add_argument("--custo", default="custo_acumulado.json", help="Caminho do arquivo custo_acumulado.json")
    parser.add_argument("--lote", type=int, default=20, help="Quantidade de OMs por chamada de IA (padrão: 20)")
    parser.add_argument("--modo-ia", choices=["auto", "gemini", "deterministico"], default="auto")
    parser.add_argument("--max-estudos", type=int, default=3, help="Quantidade de estudos AQF do Caçador a gerar")
    args = parser.parse_args(argv)

    pipeline = MaestriPipeline(
        caminho_biblioteca=args.biblioteca,
        caminho_custo=args.custo,
        lote_size=args.lote,
        modo_ia=args.modo_ia,
    )
    pacote = pipeline.executar_pipeline_completo(args.entrada, max_estudos=args.max_estudos)
    pipeline.exportar_arquivos(
        caminho_csv=args.saida_csv,
        caminho_portal_sync=args.saida_portal,
    )

    print("=" * 74)
    print(f"MAESTRI 2.0 ({pacote['versao']}) — PIPELINE DE 9 NÓS CONCLUÍDO")
    print("=" * 74)
    for n in pacote["nos"]:
        print(f"  [{n['codigo']}] {n['nome']:<30} | {n['status'].upper():<10} | {n['tempo_s']:>5.2f}s | {n['resumo']}")
    print("-" * 74)
    c = pacote["custo"]
    print(
        f"  ECONOMIA: R$ {c['custo_sem_otimizacao_brl']:.2f} (v40) -> R$ {c['custo_brl']:.2f} "
        f"(Maestri 2.0) | Poupança: R$ {c['economia_brl']:.2f} (-{c['economia_pct']}%)"
    )
    print(f"  PACOTE PORTAL GERADO EM: {args.saida_portal}")
    print("=" * 74)
    return 0


if __name__ == "__main__":
    sys.exit(main())
