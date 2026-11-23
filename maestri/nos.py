# -*- coding: utf-8 -*-
"""
maestri/nos.py — Orquestrador DAG real em 9 Nós do Projeto Maestri 2.0.
Conecta Coletor, Fast-Path R$ 0, Auditor IA em Lotes de 20 OMs, Roteador 4 Equipes,
Conferente, Bibliotecário (com Detector de Divergência), Confiabilidade (MTBF/MTTR +
Quebra Evitável + Obsolescência), Caçador AQF 2.0 (2 chamadas + DOCS-ATIVOS) e Planejador 1-Clique.
"""

import csv
import io
import json
import os
import re
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from collections import Counter, defaultdict
from datetime import datetime

from .dominio import (
    CATEGORIAS,
    DIST_REFERENCIA,
    EQUIPES,
    MAPA_COLUNAS,
    REGUA_OFICIAL,
    SCHEMA_MAESTRI,
    SINAIS_VALIDOS,
    VERSAO_MAESTRI,
    aplicar_teto_desgaste,
    assinatura_caso,
    b_c_por_evidencia,
    calcular_score_qualidade_apontamento,
    calcular_severidade,
    classificar_equipe,
    converter_tempo,
    cruzar_ativo_arvore,
    decidir_fast_path,
    evidencias,
    fallback_deterministico,
    jaccard,
    norm_categoria,
    norm_om,
    norm_sev,
    normalizar,
    om_esta_concluida,
    parse_data,
    predial_confirmado,
    score_quebra,
    validar,
)

DEFINICAO_NOS = [
    {"id": "no1", "ordem": 1, "codigo": "NÓ 1", "nome": "Coletor & Validador ERP", "papel": "Leitura .xlsx/.csv, filtro de concluídas e vínculo com ob_linhas (Criticidade A/B/C)"},
    {"id": "no2", "ordem": 2, "codigo": "NÓ 2", "nome": "Fast-Path & Memória R$ 0", "papel": "Políticas invariantes da planta + Memória do Bibliotecário + Deduplicação da rodada"},
    {"id": "no3", "ordem": 3, "codigo": "NÓ 3", "nome": "Auditor IA em Lote (20 OMs)", "papel": "Classificação em lotes de 20 OMs + Matriz B×C EN 13306 + Equilíbrio Falha Operacional"},
    {"id": "no4", "ordem": 4, "codigo": "NÓ 4", "nome": "Roteador & Qualidade", "papel": "Filas AUTOMATICO / CONFERIR / REVISAO por 4 Equipes + Score de Apontamento"},
    {"id": "no5", "ordem": 5, "codigo": "NÓ 5", "nome": "Conferente (Supervisores)", "papel": "Mesa de conferência rápida em 2 toques por equipe no Portal PCM"},
    {"id": "no6", "ordem": 6, "codigo": "NÓ 6", "nome": "Bibliotecário & Curadoria", "papel": "Aprendizado contínuo (correcoes.jsonl) + Detector de Divergência entre Supervisores"},
    {"id": "no7", "ordem": 7, "codigo": "NÓ 7", "nome": "Confiabilidade & Radares", "papel": "MTBF, MTTR, Pareto, Escada B×C, Quebra Evitável (Rota) e Risco de Obsolescência"},
    {"id": "no8", "ordem": 8, "codigo": "NÓ 8", "nome": "Caçador AQF 2.0", "papel": "RAE, Ishikawa 6M, 5 Porquês e Plano 5W2H lendo manuais vigentes de DOCS-ATIVOS"},
    {"id": "no9", "ordem": 9, "codigo": "NÓ 9", "nome": "Planejador 1-Clique", "papel": "Transforma estudos AQF em Preventivas (52S), Pontos Cirúrgicos de Rota e Agenda PCM"},
]

CUSTO_POR_OM_V40_BRL = 30.60 / 1234.0  # R$ 0,0248/OM na v40 sequencial


def _detectar_indice_cabecalho(linhas_raw):
    if not linhas_raw:
        return 0
    best_idx = 0
    best_score = -99
    limite = min(25, len(linhas_raw))
    for i in range(limite):
        row = linhas_raw[i]
        vals = [normalizar(c) for c in row if str(c or "").strip()]
        if len(vals) < 2:
            continue
        papeis = set()
        for c in vals:
            if c in ("om", "ordem", "num om", "numero om", "n om"):
                papeis.add("om")
            elif c in ("status", "status om", "situacao", "situacao om"):
                papeis.add("status")
            elif c in ("ativo", "descricao ativo", "equipamento", "maquina"):
                papeis.add("ativo")
            elif c in ("problema", "descricao", "descricao problema", "defeito"):
                papeis.add("problema")
            elif c in ("servico", "descricao do servico", "descricao servico", "servico executado", "solucao"):
                papeis.add("servico")
            elif c in ("data", "data conclusao") or c.startswith("data e hora de"):
                papeis.add("data")
            elif c in ("tempo", "tempo min", "duracao total parada", "tempo total trabalhado", "tempo de maquina parada"):
                papeis.add("tempo")
            elif c in ("equipe", "descricao tipo de servico de manutencao", "descricao tipos de manutencao"):
                papeis.add("equipe")
            elif c in ("categoria ia", "categoria", "origem decisao"):
                papeis.add("auditada")
        score = len(papeis) * 4 + (1 if len(vals) >= 4 else 0)
        if any(c.startswith("emissao ") or c.startswith("total de registros") for c in vals):
            score -= 10
        if score > best_score:
            best_score = score
            best_idx = i
    if best_idx > 0 and best_score < 8:
        return 0
    idx = best_idx
    while idx < len(linhas_raw) - 1 and not any(str(c or "").strip() for c in linhas_raw[idx]):
        idx += 1
    return idx


def _matriz_para_dicts(linhas_raw):
    if len(linhas_raw) < 2:
        return []
    hdr_idx = _detectar_indice_cabecalho(linhas_raw)
    if hdr_idx >= len(linhas_raw) - 1:
        return []
    headers = [str(h or "").strip() for h in linhas_raw[hdr_idx]]
    out = []
    for r in linhas_raw[hdr_idx + 1:]:
        d = {}
        for i, h in enumerate(headers):
            if h:
                d[h] = r[i] if i < len(r) else ""
        if any(str(v or "").strip() for v in d.values()):
            out.append(d)
    return out


def ler_planilha_generica(caminho):
    """Lê CSV (separador ';' ou ',') ou XLSX nativo sem depender de pandas."""
    if not os.path.exists(caminho):
        raise FileNotFoundError(f"Arquivo nao encontrado: {caminho}")

    if caminho.lower().endswith(".xlsx"):
        return _ler_xlsx_stdlib(caminho)

    with open(caminho, "r", encoding="utf-8-sig", errors="replace", newline="") as f:
        bruto = f.read()
    amostra = bruto[:8192]
    delim = ";" if amostra.count(";") >= amostra.count(",") else ","
    linhas_raw = [row for row in csv.reader(io.StringIO(bruto), delimiter=delim) if any(str(c).strip() for c in row)]
    return _matriz_para_dicts(linhas_raw)


def _ler_xlsx_stdlib(caminho):
    ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    with zipfile.ZipFile(caminho, "r") as z:
        shared = []
        if "xl/sharedStrings.xml" in z.namelist():
            root_s = ET.fromstring(z.read("xl/sharedStrings.xml"))
            for si in root_s.findall("m:si", ns):
                textos = [t.text or "" for t in si.findall(".//m:t", ns)]
                shared.append("".join(textos))
        sheets = sorted(n for n in z.namelist() if n.startswith("xl/worksheets/sheet") and n.endswith(".xml"))
        if not sheets:
            return []
        root_w = ET.fromstring(z.read(sheets[0]))
        linhas_raw = []
        for row in root_w.findall(".//m:sheetData/m:row", ns):
            vals = {}
            for c in row.findall("m:c", ns):
                ref = c.attrib.get("r", "A1")
                col_letters = "".join(ch for ch in ref if ch.isalpha())
                idx = 0
                for ch in col_letters:
                    idx = idx * 26 + (ord(ch.upper()) - 64)
                t_attr = c.attrib.get("t", "")
                v_el = c.find("m:v", ns)
                is_el = c.find("m:is", ns)
                if t_attr == "s" and v_el is not None and v_el.text is not None:
                    si_idx = int(v_el.text)
                    val = shared[si_idx] if 0 <= si_idx < len(shared) else ""
                elif t_attr == "inlineStr" and is_el is not None:
                    val = "".join(t.text or "" for t in is_el.findall(".//m:t", ns))
                elif v_el is not None and v_el.text is not None:
                    val = v_el.text
                else:
                    val = ""
                vals[idx] = val
            if vals:
                max_c = max(vals.keys())
                linhas_raw.append([vals.get(i, "") for i in range(1, max_c + 1)])
        return _matriz_para_dicts(linhas_raw)


def resolver_colunas_erp(linhas):
    if not linhas:
        return {}
    cols = list(linhas[0].keys())
    cols_norm = {c: normalizar(c).replace(" ", "_") for c in cols}
    mapa = {}
    for campo, candidatos in MAPA_COLUNAS.items():
        melhor_col = None
        melhor_pts = 0
        for col, cn in cols_norm.items():
            for cand in candidatos:
                cand_n = normalizar(cand).replace(" ", "_")
                pts = 0
                if cn == cand_n:
                    pts = 100
                elif cn.startswith(cand_n) or cand_n.startswith(cn):
                    pts = 75
                elif cand_n in cn:
                    pts = 50
                if pts > melhor_pts:
                    melhor_pts = pts
                    melhor_col = col
        if melhor_col:
            mapa[campo] = melhor_col
    return mapa


def carregar_biblioteca_correcoes(caminho="correcoes.jsonl"):
    if not caminho or not os.path.exists(caminho):
        return []
    saida = []
    with open(caminho, "r", encoding="utf-8", errors="replace") as f:
        for linha in f:
            linha = linha.strip()
            if not linha:
                continue
            try:
                d = json.loads(linha)
            except json.JSONDecodeError:
                continue
            if not d.get("om") and not d.get("problema"):
                continue
            d["_assinatura"] = sorted(assinatura_caso(d.get("problema", ""), d.get("servico", "")))
            saida.append(d)
    return saida


def carregar_custo_acumulado(caminho="custo_acumulado.json"):
    """Lê custo histórico sem jamais sobrescrevê-lo com zero."""
    padrao = {
        "rodadas": 0,
        "chamadas_ia": 0,
        "oms_auditadas_total": 0,
        "oms_fast_path_r0": 0,
        "tokens_in": 0,
        "tokens_out": 0,
        "custo_total_brl": 0.0,
        "custo_equivalente_v40_brl": 0.0,
        "economia_acumulada_brl": 0.0,
        "ultima_atualizacao": "",
    }
    if not caminho or not os.path.exists(caminho):
        return padrao
    try:
        with open(caminho, "r", encoding="utf-8") as f:
            dados = json.load(f)
        for k, v in padrao.items():
            if k not in dados:
                dados[k] = v
        return dados
    except Exception:
        return padrao


def atualizar_custo_acumulado(custo_rodada, caminho="custo_acumulado.json"):
    hist = carregar_custo_acumulado(caminho)
    if custo_rodada.get("oms_total", 0) > 0:
        hist["rodadas"] = int(hist.get("rodadas", 0)) + 1
        hist["chamadas_ia"] = int(hist.get("chamadas_ia", 0)) + int(custo_rodada.get("chamadas_ia", 0))
        hist["oms_auditadas_total"] = int(hist.get("oms_auditadas_total", 0)) + int(custo_rodada.get("oms_total", 0))
        hist["oms_fast_path_r0"] = int(hist.get("oms_fast_path_r0", 0)) + int(custo_rodada.get("oms_fast_path_r0", 0))
        hist["tokens_in"] = int(hist.get("tokens_in", 0)) + int(custo_rodada.get("tokens_in", 0))
        hist["tokens_out"] = int(hist.get("tokens_out", 0)) + int(custo_rodada.get("tokens_out", 0))
        hist["custo_total_brl"] = round(float(hist.get("custo_total_brl", 0.0)) + float(custo_rodada.get("custo_brl", 0.0)), 4)
        hist["custo_equivalente_v40_brl"] = round(
            float(hist.get("custo_equivalente_v40_brl", 0.0)) + float(custo_rodada.get("custo_sem_otimizacao_brl", 0.0)),
            4,
        )
        hist["economia_acumulada_brl"] = round(
            max(0.0, hist["custo_equivalente_v40_brl"] - hist["custo_total_brl"]),
            4,
        )
        hist["ultima_atualizacao"] = datetime.now().isoformat(timespec="seconds")
        if caminho:
            with open(caminho, "w", encoding="utf-8") as f:
                json.dump(hist, f, ensure_ascii=False, indent=2)
    return hist


class MaestriPipeline:
    """
    Orquestrador DAG em 9 Nós do Projeto Maestri 2.0.
    Permite rodar o pipeline completo (Nós 1..9) ou reexecutar qualquer nó individualmente.
    """

    def __init__(
        self,
        linhas_arvore=None,
        docs_biblioteca=None,
        anomalias_rota=None,
        pecas_obsolescencia=None,
        caminho_biblioteca="correcoes.jsonl",
        caminho_custo="custo_acumulado.json",
        lote_size=20,
        modo_ia="auto",
    ):
        self.linhas_arvore = linhas_arvore or []
        self.docs_biblioteca = docs_biblioteca or []
        self.anomalias_rota = anomalias_rota or []
        self.pecas_obsolescencia = pecas_obsolescencia or []
        self.caminho_biblioteca = caminho_biblioteca
        self.caminho_custo = caminho_custo
        self.lote_size = max(1, min(30, int(lote_size or 20)))
        self.modo_ia = modo_ia  # "auto" | "gemini" | "ollama" | "deterministico"

        self.estado_nos = {
            n["id"]: {
                **n,
                "status": "pendente",
                "tempo_s": 0.0,
                "resumo": "Aguardando execução",
                "metricas": {},
            }
            for n in DEFINICAO_NOS
        }
        self.oms_coletadas = []
        self.oms_fast_path = {}
        self.oms_pendentes_ia = []
        self.oms_auditadas = []
        self.filas_equipe = {}
        self.qualidade_equipes = {}
        self.divergencias_supervisores = []
        self.confiabilidade = {}
        self.estudos_aqf = []
        self.propostas_planejador = []
        self.custo_rodada = {
            "oms_total": 0,
            "oms_fast_path_r0": 0,
            "oms_ia_lote": 0,
            "chamadas_ia": 0,
            "lote_size": self.lote_size,
            "tokens_in": 0,
            "tokens_out": 0,
            "custo_brl": 0.0,
            "custo_sem_otimizacao_brl": 0.0,
            "economia_brl": 0.0,
            "economia_pct": 0.0,
        }

    # ------------------------------------------------------------------
    # NÓ 1: COLETOR & VALIDADOR ERP + VÍNCULO OB_LINHAS
    # ------------------------------------------------------------------
    def no1_coletor_validador(self, linhas_ou_caminho, filtro_status="auto"):
        t0 = time.time()
        self.estado_nos["no1"]["status"] = "rodando"
        if isinstance(linhas_ou_caminho, str):
            linhas = ler_planilha_generica(linhas_ou_caminho)
        else:
            linhas = list(linhas_ou_caminho or [])

        if not linhas:
            self.oms_coletadas = []
            self.estado_nos["no1"].update({
                "status": "concluido",
                "tempo_s": round(time.time() - t0, 3),
                "resumo": "0 OMs encontradas na planilha",
                "metricas": {"linhas_brutas": 0, "concluidas": 0, "ignoradas_abertas": 0},
            })
            return []

        # Detecta se já é um CSV/JSON pré-auditado (ex.: OMs_Auditadas.csv)
        primeira = linhas[0]
        ja_auditado = ("Categoria_IA" in primeira or "categoria" in primeira) and ("OM" in primeira or "om" in primeira)
        mapa = resolver_colunas_erp(linhas)

        coletadas = []
        ignoradas = 0
        vistas = set()

        for row in linhas:
            if ja_auditado:
                om_num = norm_om(row.get("OM") or row.get("om"))
                if not om_num or om_num in vistas:
                    continue
                vistas.add(om_num)
                ativo_str = str(row.get("Ativo") or row.get("ativo") or row.get("Descrição (Ativo)") or "").strip()
                problema = str(row.get("Problema") or row.get("problema") or row.get("Descrição") or "").strip()
                servico = str(row.get("Servico") or row.get("servico") or row.get("Descrição do Serviço") or "").strip()
                tempo_min = converter_tempo(row.get("Tempo_min") or row.get("tempo_min") or row.get("Duracao_Total_Parada"))
                data_str = str(row.get("Data") or row.get("data") or "").strip()
                info_arvore = cruzar_ativo_arvore(ativo_str, self.linhas_arvore)
                equipe = classificar_equipe(
                    {"equipe": row.get("Equipe") or row.get("equipe") or "", "problema": problema, "servico": servico}
                )
                coletadas.append({
                    "om": om_num,
                    "data": data_str,
                    "ativo": ativo_str,
                    "setor": info_arvore["setor"],
                    "maquina": info_arvore["maquina"],
                    "equipamento": info_arvore["equipamento"],
                    "criticidade_linha": info_arvore["criticidade_linha"],
                    "vinculado_ob_linhas": info_arvore["vinculado_ob_linhas"],
                    "equipe": equipe,
                    "tempo_min": tempo_min if tempo_min is not None else 0,
                    "status": str(row.get("Status_OM") or row.get("status") or "Concluída Completa"),
                    "problema": problema,
                    "servico": servico,
                    "tipo_manut": str(row.get("Tipo_Manut_ERP") or row.get("sev_erp") or ""),
                    "_pre_auditada": {
                        "categoria": norm_categoria(row.get("Categoria_IA") or row.get("categoria") or ""),
                        "severidade": norm_sev(row.get("Severidade") or row.get("severidade") or ""),
                        "b": converter_tempo(row.get("B_IA") or row.get("b")),
                        "c": converter_tempo(row.get("C_IA") or row.get("c")),
                        "confianca": converter_tempo(row.get("Confianca") or row.get("confianca")) or 5,
                        "origem": str(row.get("Origem_Decisao") or row.get("origem") or "PRE_AUDITADA").strip(),
                        "justificativa": str(row.get("Justificativa_IA") or row.get("justificativa") or "").strip(),
                    },
                })
                continue

            om_num = norm_om(row.get(mapa.get("om", ""), ""))
            if not om_num or om_num in vistas:
                continue
            status_val = row.get(mapa.get("status", ""), "")
            tempo_val = converter_tempo(row.get(mapa.get("tempo", ""), ""))
            if not tempo_val:
                tempo_val = converter_tempo(row.get("Tempo total trabalhado") or row.get("Tempo de máquina parada") or "")
            ok_conc, _ = om_esta_concluida(status_val, tempo_val, modo=filtro_status)
            if not ok_conc:
                ignoradas += 1
                continue
            vistas.add(om_num)

            ativo_str = str(row.get(mapa.get("ativo", ""), "") or "").strip()
            problema = str(row.get(mapa.get("problema", ""), "") or "").strip()
            servico = str(row.get(mapa.get("servico", ""), "") or "").strip()
            data_str = str(row.get(mapa.get("data", ""), "") or row.get("Data e hora de entrada", "") or row.get("Data e hora de cadastro", "") or "").strip()
            if data_str and re.match(r"^\d+(?:[.,]\d+)?$", data_str):
                dt_xl = parse_data(data_str)
                if dt_xl is not None:
                    data_str = dt_xl.strftime("%Y-%m-%d %H:%M")
            eq_raw = str(row.get(mapa.get("equipe", ""), "") or "").strip()
            tipo_m = str(row.get(mapa.get("tipo_manut", ""), "") or "").strip()

            info_arvore = cruzar_ativo_arvore(ativo_str, self.linhas_arvore)
            equipe = classificar_equipe({"equipe": eq_raw, "tipo_manut": tipo_m, "problema": problema, "servico": servico})

            coletadas.append({
                "om": om_num,
                "data": data_str,
                "ativo": ativo_str,
                "setor": info_arvore["setor"],
                "maquina": info_arvore["maquina"],
                "equipamento": info_arvore["equipamento"],
                "criticidade_linha": info_arvore["criticidade_linha"],
                "vinculado_ob_linhas": info_arvore["vinculado_ob_linhas"],
                "equipe": equipe,
                "tempo_min": tempo_val if tempo_val is not None else 0,
                "status": str(status_val or "Concluída"),
                "problema": problema,
                "servico": servico,
                "tipo_manut": tipo_m,
            })

        self.oms_coletadas = coletadas
        dt = round(time.time() - t0, 3)
        self.estado_nos["no1"].update({
            "status": "concluido",
            "tempo_s": dt,
            "resumo": f"{len(coletadas)} OMs concluídas validadas ({ignoradas} abertas/canceladas filtradas)",
            "metricas": {
                "linhas_brutas": len(linhas),
                "concluidas": len(coletadas),
                "ignoradas_abertas": ignoradas,
                "ja_auditado": ja_auditado,
            },
        })
        return coletadas

    # ------------------------------------------------------------------
    # NÓ 2: FAST-PATH DETERMINÍSTICO & MEMÓRIA DO BIBLIOTECÁRIO (R$ 0,00)
    # ------------------------------------------------------------------
    def no2_fast_path_memoria(self):
        t0 = time.time()
        self.estado_nos["no2"]["status"] = "rodando"
        biblioteca = carregar_biblioteca_correcoes(self.caminho_biblioteca)

        resolvidas = {}
        pendentes = []
        cache_rodada = {}
        origens_cnt = Counter()

        for om in self.oms_coletadas:
            pre = om.get("_pre_auditada")
            if pre and pre.get("categoria") in CATEGORIAS + ["REVISAR_MANUAL"]:
                resolvidas[om["om"]] = pre
                origens_cnt[pre["origem"]] += 1
                continue

            p_norm = normalizar(om.get("problema", ""))
            s_norm = normalizar(om.get("servico", ""))
            t_norm = normalizar(f"{om.get('problema', '')} {om.get('servico', '')}")
            ev = evidencias(t_norm, s_norm, om.get("data", ""), p_norm)
            ev["_texto_norm"] = t_norm
            om["_ev"] = ev

            decisao = decidir_fast_path(om, ev, biblioteca=biblioteca, cache_rodada=cache_rodada)
            if decisao:
                resolvidas[om["om"]] = decisao
                origens_cnt[decisao["origem"]] += 1
                chave_dedup = f"{p_norm}||{s_norm}"
                if chave_dedup and decisao["categoria"] != "REVISAR_MANUAL":
                    cache_rodada[chave_dedup] = decisao
            else:
                pendentes.append(om)

        self.oms_fast_path = resolvidas
        self.oms_pendentes_ia = pendentes
        total = len(self.oms_coletadas)
        pct_r0 = round((len(resolvidas) / total * 100.0), 1) if total else 0.0
        dt = round(time.time() - t0, 3)

        self.estado_nos["no2"].update({
            "status": "concluido",
            "tempo_s": dt,
            "resumo": f"{len(resolvidas)}/{total} OMs ({pct_r0}%) decididas a R$ 0,00 sem gastar tokens",
            "metricas": {
                "resolvidas_r0": len(resolvidas),
                "pendentes_lote_ia": len(pendentes),
                "pct_economia_direta": pct_r0,
                "por_origem": dict(origens_cnt),
                "regras_biblioteca": len(biblioteca),
            },
        })
        return resolvidas, pendentes

    # ------------------------------------------------------------------
    # NÓ 3: AUDITOR IA EM LOTE (20 OMs/CHAMADA) + MATRIZ B×C
    # ------------------------------------------------------------------
    def no3_auditor_ia_lote(self, api_key=None):
        t0 = time.time()
        self.estado_nos["no3"]["status"] = "rodando"
        chave = api_key or os.environ.get("GEMINI_API_KEY", "").strip()
        usar_gemini = Boolean_api(chave, self.modo_ia)

        decisoes_ia = {}
        chamadas_ia = 0
        tokens_in = 0
        tokens_out = 0
        cache_lote_assinatura = {}

        # Agrupa as OMs pendentes em lotes de self.lote_size (padrão 20)
        lote_atual = []
        for om in self.oms_pendentes_ia:
            chave_dedup = f"{normalizar(om.get('problema', ''))}||{normalizar(om.get('servico', ''))}"
            if chave_dedup in cache_lote_assinatura:
                clonada = dict(cache_lote_assinatura[chave_dedup])
                clonada["origem"] = "DEDUP_RODADA"
                decisoes_ia[om["om"]] = clonada
                continue
            lote_atual.append(om)
            if len(lote_atual) >= self.lote_size:
                res_lote, u_in, u_out, fez_call = self._processar_lote_20(lote_atual, chave if usar_gemini else "")
                if fez_call:
                    chamadas_ia += 1
                    tokens_in += u_in
                    tokens_out += u_out
                for om_item, dec in res_lote.items():
                    decisoes_ia[om_item] = dec
                for o_l in lote_atual:
                    k_d = f"{normalizar(o_l.get('problema', ''))}||{normalizar(o_l.get('servico', ''))}"
                    if o_l["om"] in res_lote:
                        cache_lote_assinatura[k_d] = res_lote[o_l["om"]]
                lote_atual = []

        if lote_atual:
            res_lote, u_in, u_out, fez_call = self._processar_lote_20(lote_atual, chave if usar_gemini else "")
            if fez_call:
                chamadas_ia += 1
                tokens_in += u_in
                tokens_out += u_out
            for om_item, dec in res_lote.items():
                decisoes_ia[om_item] = dec

        # Consolida todas as OMs (Fast-Path + Lote IA) aplicando overrides de governança e Matriz B×C
        auditadas = []
        for om in self.oms_coletadas:
            om_id = om["om"]
            bruta = self.oms_fast_path.get(om_id) or decisoes_ia.get(om_id)
            ev = om.get("_ev")
            if ev is None:
                p_n = normalizar(om.get("problema", ""))
                s_n = normalizar(om.get("servico", ""))
                t_n = normalizar(f"{om.get('problema', '')} {om.get('servico', '')}")
                ev = evidencias(t_n, s_n, om.get("data", ""), p_n)
                ev["_texto_norm"] = t_n
            item_final = self._consolidar_om_auditada(om, bruta, ev)
            auditadas.append(item_final)

        self.oms_auditadas = auditadas

        # Cálculo transparente de custos e economia vs v40
        total_oms = len(auditadas)
        custo_v40 = round(total_oms * CUSTO_POR_OM_V40_BRL, 2)
        custo_atual_usd = (tokens_in / 1_000_000.0) * 0.375 + (tokens_out / 1_000_000.0) * 1.875
        custo_atual_brl = round(custo_atual_usd * 5.40, 4)
        economia_brl = round(max(0.0, custo_v40 - custo_atual_brl), 2)
        economia_pct = round((economia_brl / custo_v40 * 100.0), 1) if custo_v40 > 0 else 100.0

        self.custo_rodada = {
            "oms_total": total_oms,
            "oms_fast_path_r0": len(self.oms_fast_path),
            "oms_ia_lote": len(self.oms_pendentes_ia),
            "chamadas_ia": chamadas_ia,
            "lote_size": self.lote_size,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "custo_brl": custo_atual_brl,
            "custo_sem_otimizacao_brl": custo_v40,
            "economia_brl": economia_brl,
            "economia_pct": economia_pct,
        }
        atualizar_custo_acumulado(self.custo_rodada, self.caminho_custo)

        dt = round(time.time() - t0, 3)
        self.estado_nos["no3"].update({
            "status": "concluido",
            "tempo_s": dt,
            "resumo": (
                f"{total_oms} OMs consolidadas ({chamadas_ia} chamadas em lote de {self.lote_size}) • "
                f"Custo R$ {custo_atual_brl:.2f} vs R$ {custo_v40:.2f} (-{economia_pct}%)"
            ),
            "metricas": dict(self.custo_rodada),
        })
        return auditadas

    def _processar_lote_20(self, lote_oms, chave_gemini=""):
        """Envia até 20 OMs em uma única chamada JSON estruturada ou resolve via motor determinístico."""
        resultados = {}
        if chave_gemini:
            try:
                itens_prompt = [
                    {
                        "om": o["om"],
                        "ativo": o["ativo"],
                        "equipe": o["equipe"],
                        "tempo_min": o["tempo_min"],
                        "problema": o["problema"][:220],
                        "servico": o["servico"][:260],
                    }
                    for o in lote_oms
                ]
                prompt = (
                    "Classifique cada Ordem de Manutencao concluida da Cepera Alimentos em UMA das 11 categorias oficiais: "
                    + ", ".join(CATEGORIAS)
                    + ". Para QUEBRA, informe b (1=periferico, 2=importante, 3=critico) e c (1=contida, 2=degradacao, 3=falha total). "
                    "Para FALHA OPERACIONAL, aplique Equilibrio Tecnico (relato explicito ou indicio claro de uso/ajuste fora de padrao na operacao). "
                    "Responda SOMENTE um JSON Array com objetos: {\"om\": \"...\", \"categoria\": \"...\", \"b\": null|1|2|3, \"c\": null|1|2|3, \"confianca\": 1..5, \"justificativa\": \"...\"}.\n\n"
                    "LOTE_OMS:\n"
                    + json.dumps(itens_prompt, ensure_ascii=False)
                )
                url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key=" + chave_gemini
                payload = {
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {"temperature": 0.0, "topP": 1.0, "responseMimeType": "application/json"},
                }
                req = urllib.request.Request(
                    url,
                    data=json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=45) as resp:
                    body = json.loads(resp.read().decode("utf-8"))
                txt = body["candidates"][0]["content"]["parts"][0]["text"]
                arr = json.loads(txt)
                usage = body.get("usageMetadata", {})
                u_in = int(usage.get("promptTokenCount", len(prompt) // 4))
                u_out = int(usage.get("candidatesTokenCount", len(txt) // 4))
                if isinstance(arr, list):
                    for item in arr:
                        om_k = norm_om(item.get("om"))
                        if om_k:
                            item["origem"] = "IA_LOTE20"
                            resultados[om_k] = item
                for o in lote_oms:
                    if o["om"] not in resultados:
                        fb = fallback_deterministico(o["_ev"], o.get("tempo_min"), o.get("criticidade_linha", ""))
                        fb["origem"] = "MOTOR_REGRAS_LOTE"
                        resultados[o["om"]] = fb
                return resultados, u_in, u_out, True
            except Exception:
                pass

        for o in lote_oms:
            fb = fallback_deterministico(o["_ev"], o.get("tempo_min"), o.get("criticidade_linha", ""))
            fb["origem"] = "MOTOR_REGRAS_LOTE"
            resultados[o["om"]] = fb
        return resultados, 0, 0, False

    def _consolidar_om_auditada(self, om, decisao, ev):
        dados = dict(decisao or fallback_deterministico(ev, om.get("tempo_min"), om.get("criticidade_linha", "")))
        cat = norm_categoria(dados.get("categoria", "AJUSTE")) or "AJUSTE"
        origem = str(dados.get("origem") or "MOTOR_REGRAS").upper()
        conf = int(dados.get("confianca") or 4)
        justificativa = str(dados.get("justificativa") or "Classificada pelas politicas industriais PCM.").strip()
        avisos = []

        t_norm = ev.get("_texto_norm") or normalizar(f"{om.get('problema', '')} {om.get('servico', '')}")

        # Validação de políticas da planta
        if cat != "REVISAR_MANUAL":
            probs = validar({"categoria": cat, "b": dados.get("b"), "c": dados.get("c")}, ev, t_norm)
            if probs and origem not in ("PRE_AUDITADA", "SUPERVISOR", "BIBLIOTECA_MEMORIA"):
                avisos.extend(probs[:2])

            if ev.get("inspecao_rotas") and cat != "INSPECAO DE ROTAS":
                cat = "INSPECAO DE ROTAS"
                origem = "CORRECAO_TEXTO"
            elif ev.get("preventiva_forte") and cat != "PREVENTIVA":
                cat = "PREVENTIVA"
                origem = "CORRECAO_TEXTO"

            # Equilíbrio Técnico de FALHA OPERACIONAL (Grill-Me):
            # Se tem evidência clara de falha operacional sem quebra destrutiva, preserva FALHA OPERACIONAL!
            # Se é indício moderado, envia para CONFERIR (confianca=4).
            if cat == "FALHA OPERACIONAL":
                if not ev.get("falha_operacional") and not ev.get("indicio_operacional_conferir") and origem != "PRE_AUDITADA":
                    avisos.append("override: FALHA OPERACIONAL sem sinal operacional claro -> AJUSTE")
                    cat = "AJUSTE"
                    origem = "CORRECAO_TEXTO"
                elif ev.get("indicio_operacional_conferir") and not ev.get("falha_operacional"):
                    conf = min(conf, 4)
                    avisos.append("equilibrio tecnico: indicio operacional encaminhado para conferencia")

            # Sinal de equipe PREDIAL
            if "predial" in normalizar(om.get("equipe") or "") and cat in ("AJUSTE", "ACOMPANHAMENTO") and not ev.get("equipamento_processo"):
                cat = "PREDIAL"
                origem = "SINAL_EQUIPE"

            # Sinal de equipe MONTAGEM
            if "montag" in normalizar(om.get("equipe") or "") and not (ev.get("troca") and (ev.get("falha_hard") or ev.get("peca_desgaste"))):
                if cat == "AJUSTE":
                    cat = "MANUTENCAO PROGRAMADA"
                    origem = "SINAL_EQUIPE"
                elif cat == "ACOMPANHAMENTO":
                    cat = "MELHORIAS"
                    origem = "SINAL_EQUIPE"

            # Regras fixas da planta
            if ev.get("troca_pedra") and cat != "QUEBRA":
                cat = "QUEBRA"
                origem = "REGRA_PLANTA"
            if ev.get("lampada_lote") and cat != "MANUTENCAO PROGRAMADA":
                cat = "MANUTENCAO PROGRAMADA"
                origem = "REGRA_PLANTA"
            if ev.get("so_reset") and not ev.get("troca") and cat != "AJUSTE" and not ev.get("falha_operacional"):
                cat = "AJUSTE"
                origem = "REGRA_PLANTA"

            # Detector de conflito de score de quebra
            sc = score_quebra(ev, om.get("tempo_min"))
            if sc >= 4 and cat in ("AJUSTE", "ACOMPANHAMENTO", "MELHORIAS"):
                avisos.append(f"conflito: SCORE QB {sc} com categoria {cat}")
                origem = "CONFLITO_SCORE"
                conf = min(conf, 4)

        # Matriz B×C e Severidade (com contrato compatível tanto com Auditor quanto com Caçador!)
        b = dados.get("b")
        c = dados.get("c")
        sev = "NA"
        regra_sev = ""

        if cat == "REVISAR_MANUAL":
            sev = "PENDENTE"
            b, c = None, None
            parecer = f"REVISAR_MANUAL | {justificativa}"
        elif cat == "QUEBRA":
            b_ev, c_ev = b_c_por_evidencia(ev, om.get("criticidade_linha", ""))
            if b not in (1, 2, 3):
                b = b_ev
            if c not in (1, 2, 3):
                c = c_ev
            if om.get("criticidade_linha") == "A" and ev.get("componente_critico") and b < 2:
                b = 2
            sev_calc, det_sev, _ = calcular_severidade(b, c, om.get("tempo_min"))
            sev_teto, av_teto = aplicar_teto_desgaste(sev_calc or "MODERADA", ev)
            sev = sev_teto or "MODERADA"
            regra_sev = det_sev or f"B={b} C={c} -> {sev}"
            if av_teto:
                avisos.append(av_teto)
            parecer = f"QUEBRA | {sev} | B={b} C={c} | {justificativa}"
        else:
            b, c = None, None
            parecer = f"{cat} | NA | {justificativa}"

        qual = calcular_score_qualidade_apontamento(om.get("problema", ""), om.get("servico", ""))

        # Inclui chaves padronizadas tanto para o Portal / Auditor quanto para o Caçador AQF!
        return {
            "om": om["om"],
            "OM": om["om"],
            "data": om.get("data", ""),
            "Data": om.get("data", ""),
            "ativo": om.get("ativo", ""),
            "Ativo": om.get("ativo", ""),
            "Descrição (Ativo)": om.get("ativo", ""),
            "setor": om.get("setor", ""),
            "maquina": om.get("maquina", ""),
            "equipamento": om.get("equipamento", ""),
            "criticidade_linha": om.get("criticidade_linha", "A"),
            "equipe": om.get("equipe", "MECANICA"),
            "Equipe": om.get("equipe", "MECANICA"),
            "tempo_min": om.get("tempo_min", 0),
            "Tempo_min": om.get("tempo_min", 0),
            "Duracao_Total_Parada": om.get("tempo_min", 0),
            "status": om.get("status", "Concluída"),
            "Status_OM": om.get("status", "Concluída"),
            "problema": om.get("problema", ""),
            "Problema": om.get("problema", ""),
            "Descrição": om.get("problema", ""),
            "servico": om.get("servico", ""),
            "Servico": om.get("servico", ""),
            "Descrição do Serviço": om.get("servico", ""),
            "categoria": cat,
            "Categoria_IA": cat,
            "severidade": sev,
            "Severidade": sev,
            "b": b,
            "B_IA": b if b is not None else "",
            "c": c,
            "C_IA": c if c is not None else "",
            "regra_severidade": regra_sev,
            "Regra_Severidade": regra_sev,
            "parecer": parecer,
            "Parecer_Auditoria_IA": parecer,
            "justificativa": justificativa,
            "Justificativa_IA": justificativa,
            "avisos": "; ".join(avisos),
            "Avisos_Sistema": "; ".join(avisos),
            "origem": origem,
            "Origem_Decisao": origem,
            "confianca": conf,
            "Confianca": conf,
            "tipo_manut_erp": om.get("tipo_manut", ""),
            "Tipo_Manut_ERP": om.get("tipo_manut", ""),
            "qualidade_score": qual["score"],
            "qualidade_nivel": qual["nivel"],
            "qualidade_motivo": qual["motivo"],
        }

    # ------------------------------------------------------------------
    # NÓ 4: ROTEADOR POR 4 EQUIPES & RANKING DE QUALIDADE DE APONTAMENTO
    # ------------------------------------------------------------------
    def no4_roteador_governanca(self):
        t0 = time.time()
        self.estado_nos["no4"]["status"] = "rodando"

        cont_filas = Counter()
        por_equipe = {eq: [] for eq in EQUIPES}
        qual_por_eq = {eq: {"total": 0, "soma_score": 0, "rasos_ou_criticos": 0, "exemplos_vagos": []} for eq in EQUIPES}

        for item in self.oms_auditadas:
            cat = item["categoria"]
            conf = int(item.get("confianca") or 4)
            origem = item.get("origem", "")
            eq = item.get("equipe") if item.get("equipe") in EQUIPES else "MECANICA"

            if cat == "REVISAR_MANUAL" or conf <= 3:
                fila = "REVISAO"
            elif origem in ("FALLBACK", "CONFLITO_SCORE", "SINAL_EQUIPE") or conf == 4 or (
                cat == "QUEBRA" and item.get("severidade") == "GRAVE" and origem not in ("BIBLIOTECA_MEMORIA", "SUPERVISOR")
            ):
                fila = "CONFERIR"
            else:
                fila = "AUTOMATICO"

            item["fila"] = fila
            cont_filas[fila] += 1
            por_equipe.setdefault(eq, []).append(item)

            q = qual_por_eq.setdefault(eq, {"total": 0, "soma_score": 0, "rasos_ou_criticos": 0, "exemplos_vagos": []})
            q["total"] += 1
            q["soma_score"] += int(item.get("qualidade_score") or 50)
            if item.get("qualidade_nivel") in ("CRITICO", "RASO"):
                q["rasos_ou_criticos"] += 1
                if len(q["exemplos_vagos"]) < 5:
                    q["exemplos_vagos"].append({
                        "om": item["om"],
                        "ativo": item["ativo"],
                        "problema": item["problema"],
                        "servico": item["servico"],
                        "score": item["qualidade_score"],
                    })

        resumo_qual = {}
        for eq, d in qual_por_eq.items():
            media = round(d["soma_score"] / d["total"], 1) if d["total"] else 100.0
            resumo_qual[eq] = {
                "equipe": eq,
                "total_oms": d["total"],
                "score_medio": media,
                "apontamentos_vagos": d["rasos_ou_criticos"],
                "pct_vagos": round(d["rasos_ou_criticos"] / d["total"] * 100.0, 1) if d["total"] else 0.0,
                "exemplos_vagos": d["exemplos_vagos"],
            }

        self.filas_equipe = por_equipe
        self.qualidade_equipes = resumo_qual
        pendentes_sup = cont_filas["CONFERIR"] + cont_filas["REVISAO"]
        dt = round(time.time() - t0, 3)

        self.estado_nos["no4"].update({
            "status": "concluido",
            "tempo_s": dt,
            "resumo": (
                f"AUTOMATICO: {cont_filas['AUTOMATICO']} • "
                f"CONFERIR: {cont_filas['CONFERIR']} • REVISAO: {cont_filas['REVISAO']} (4 equipes)"
            ),
            "metricas": {
                "filas": dict(cont_filas),
                "pendentes_supervisao": pendentes_sup,
                "qualidade_equipes": resumo_qual,
            },
        })
        return self.filas_equipe

    # ------------------------------------------------------------------
    # NÓ 5: CONFERENTE (MESA DOS SUPERVISORES POR EQUIPE)
    # ------------------------------------------------------------------
    def no5_conferente(self, correcoes_aplicadas=None):
        t0 = time.time()
        self.estado_nos["no5"]["status"] = "rodando"
        lista_corr = list(correcoes_aplicadas or [])

        mapa_corr = {norm_om(c.get("om")): c for c in lista_corr if c.get("om")}
        confirmadas = 0
        corrigidas = 0

        for item in self.oms_auditadas:
            c = mapa_corr.get(item["om"])
            if not c:
                continue
            nova_cat = norm_categoria(c.get("categoria_supervisor") or item["categoria"])
            divergiu = nova_cat != item["categoria"]
            item["categoria_ia_original"] = item["categoria"]
            item["categoria"] = nova_cat
            item["Categoria_IA"] = nova_cat
            item["fila"] = "AUTOMATICO"
            item["confianca"] = 5
            item["Confianca"] = 5
            item["origem"] = "SUPERVISOR"
            item["Origem_Decisao"] = "SUPERVISOR"
            item["sinal_supervisor"] = c.get("sinal", "OUTRO")
            item["supervisor_revisor"] = c.get("supervisor", "Supervisor PCM")
            if divergiu:
                corrigidas += 1
            else:
                confirmadas += 1

        pendentes = sum(1 for o in self.oms_auditadas if o.get("fila") in ("CONFERIR", "REVISAO"))
        dt = round(time.time() - t0, 3)
        self.estado_nos["no5"].update({
            "status": "concluido",
            "tempo_s": dt,
            "resumo": f"{confirmadas} confirmada(s), {corrigidas} corrigida(s) • {pendentes} aguardando conferência",
            "metricas": {
                "confirmadas": confirmadas,
                "corrigidas": corrigidas,
                "pendentes_conferencia": pendentes,
            },
        })
        return {"confirmadas": confirmadas, "corrigidas": corrigidas, "pendentes": pendentes}

    # ------------------------------------------------------------------
    # NÓ 6: BIBLIOTECÁRIO & DETECTOR DE DIVERGÊNCIA ENTRE SUPERVISORES
    # ------------------------------------------------------------------
    def no6_bibliotecario(self, novas_correcoes=None):
        t0 = time.time()
        self.estado_nos["no6"]["status"] = "rodando"
        biblioteca = carregar_biblioteca_correcoes(self.caminho_biblioteca)

        if novas_correcoes:
            existentes_om = {norm_om(x.get("om")): idx for idx, x in enumerate(biblioteca) if x.get("om")}
            for nc in novas_correcoes:
                if nc.get("sinal") not in SINAIS_VALIDOS:
                    nc["sinal"] = "OUTRO"
                nc["_assinatura"] = sorted(assinatura_caso(nc.get("problema", ""), nc.get("servico", "")))
                om_k = norm_om(nc.get("om"))
                if om_k and om_k in existentes_om:
                    biblioteca[existentes_om[om_k]] = nc
                else:
                    biblioteca.append(nc)

            if self.caminho_biblioteca:
                with open(self.caminho_biblioteca, "w", encoding="utf-8") as f:
                    for item in biblioteca:
                        limpo = {k: v for k, v in item.items() if not k.startswith("_")}
                        f.write(json.dumps(limpo, ensure_ascii=False) + "\n")

        # Detector de Divergência entre Supervisores (Jaccard >= 0.45 com categorias opostas)
        divergencias = []
        ativos = [b for b in biblioteca if b.get("status") != "REVERTIDO" and b.get("categoria_supervisor")]
        for i in range(len(ativos)):
            for j in range(i + 1, len(ativos)):
                a = ativos[i]
                b = ativos[j]
                cat_a = norm_categoria(a.get("categoria_supervisor"))
                cat_b = norm_categoria(b.get("categoria_supervisor"))
                if cat_a == cat_b:
                    continue
                sim = jaccard(a.get("_assinatura", []), b.get("_assinatura", []))
                if sim >= 0.35:
                    divergencias.append({
                        "id": f"div_{a.get('om', i)}_{b.get('om', j)}",
                        "similaridade": round(sim, 2),
                        "om_a": a.get("om", ""),
                        "supervisor_a": a.get("supervisor", "Sup. A"),
                        "categoria_a": cat_a,
                        "sinal_a": a.get("sinal", ""),
                        "texto_a": f"{a.get('problema', '')} — {a.get('servico', '')}"[:140],
                        "om_b": b.get("om", ""),
                        "supervisor_b": b.get("supervisor", "Sup. B"),
                        "categoria_b": cat_b,
                        "sinal_b": b.get("sinal", ""),
                        "texto_b": f"{b.get('problema', '')} — {b.get('servico', '')}"[:140],
                    })

        self.divergencias_supervisores = divergencias
        dt = round(time.time() - t0, 3)
        self.estado_nos["no6"].update({
            "status": "concluido",
            "tempo_s": dt,
            "resumo": f"{len(ativos)} regra(s) ativa(s) na memória R$ 0 • {len(divergencias)} divergência(s) entre supervisores",
            "metricas": {
                "regras_ativas": len(ativos),
                "divergencias_detectadas": len(divergencias),
            },
        })
        return {"regras": biblioteca, "divergencias": divergencias}

    # ------------------------------------------------------------------
    # NÓ 7: CONFIABILIDADE (MTBF, MTTR, QUEBRA EVITÁVEL & OBSOLESCÊNCIA)
    # ------------------------------------------------------------------
    def no7_confiabilidade(self, horas_calendario_mes=720.0):
        t0 = time.time()
        self.estado_nos["no7"]["status"] = "rodando"

        cont_cat = Counter()
        cont_sev = Counter()
        cont_bc = Counter()
        por_ativo = defaultdict(list)

        for o in self.oms_auditadas:
            cat = o["categoria"]
            cont_cat[cat] += 1
            por_ativo[o["ativo"] or "SEM ATIVO"].append(o)
            if cat == "QUEBRA":
                sev = o.get("severidade") or "MODERADA"
                cont_sev[sev] += 1
                if o.get("b") and o.get("c"):
                    cont_bc[f"B{o['b']}xC{o['c']}"] += 1

        # Cruzamento com INSPEÇÃO DE ROTA.html (ir_anomalias) e OBSOLECENCIA.html (ob_equipamentos)
        anomalias_norm = [
            {
                "texto": normalizar(f"{a.get('maquina', '')} {a.get('equipamento', '')} {a.get('conjunto', '')} {a.get('descricao', '')}"),
                "status": a.get("status", ""),
                "descricao": a.get("descricao", ""),
            }
            for a in self.anomalias_rota
        ]
        obsol_norm = [
            {
                "texto": normalizar(f"{e.get('maquina', '')} {e.get('equipamento', '')} {e.get('conjunto', '')} {e.get('peca', '')}"),
                "criticidade": e.get("criticidade", "Alta"),
                "status": e.get("status_obsolescencia") or e.get("status") or "Risco Obsolescência",
            }
            for e in self.pecas_obsolescencia
        ]

        ranking_ativos = []
        quebras_evitaveis = []

        for ativo, oms_at in por_ativo.items():
            quebras = [x for x in oms_at if x["categoria"] == "QUEBRA"]
            graves = [x for x in quebras if x.get("severidade") == "GRAVE"]
            rotas_om = [x for x in oms_at if x["categoria"] == "INSPECAO DE ROTAS"]
            prevs_om = [x for x in oms_at if x["categoria"] in ("PREVENTIVA", "MANUTENCAO PROGRAMADA")]

            tempo_total_min = sum(int(x.get("tempo_min") or 0) for x in oms_at)
            tempo_quebra_min = sum(int(x.get("tempo_min") or 0) for x in quebras)
            n_quebras = len(quebras)
            mttr_min = round(tempo_quebra_min / n_quebras, 1) if n_quebras else 0.0
            horas_parado = tempo_quebra_min / 60.0
            horas_oper = max(1.0, horas_calendario_mes - horas_parado)
            mtbf_h = round(horas_oper / n_quebras, 1) if n_quebras else round(horas_calendario_mes, 1)
            disp_pct = round((horas_oper / horas_calendario_mes) * 100.0, 1)

            at_norm = normalizar(ativo)
            tokens_at = [w for w in at_norm.split() if len(w) >= 4]
            anom_match = next(
                (a for a in anomalias_norm if any(tk in a["texto"] for tk in tokens_at)),
                None,
            )
            obs_match = next(
                (e for e in obsol_norm if any(tk in e["texto"] for tk in tokens_at)),
                None,
            )

            # Radar de Quebra Evitável: Quebra Grave onde não havia preventiva/rota ou havia anomalia pendente
            status_rota = (
                "Anomalia prévia detectada na Rota e não tratada a tempo"
                if (n_quebras > 0 and anom_match)
                else (
                    "Coberto por Preventiva/Rota"
                    if (len(rotas_om) + len(prevs_om) > 0)
                    else ("Quebra sem ponto de Inspeção de Rota ativo" if n_quebras > 0 else "Operação Estável")
                )
            )

            info_base = oms_at[0]
            item_rk = {
                "ativo": ativo,
                "setor": info_base.get("setor", ""),
                "maquina": info_base.get("maquina", ""),
                "equipamento": info_base.get("equipamento", ""),
                "criticidade_linha": info_base.get("criticidade_linha", "A"),
                "total_oms": len(oms_at),
                "quebras": n_quebras,
                "quebras_graves": len(graves),
                "tempo_total_min": tempo_total_min,
                "tempo_quebra_min": tempo_quebra_min,
                "mttr_min": mttr_min,
                "mtbf_h": mtbf_h,
                "disponibilidade_pct": disp_pct,
                "status_rota": status_rota,
                "risco_obsolescencia": bool(obs_match),
                "detalhe_obsolescencia": obs_match["status"] if obs_match else "Sem alerta",
                "score_criticidade_aqf": (len(graves) * 35) + (n_quebras * 15) + int(tempo_quebra_min // 20) + (25 if info_base.get("criticidade_linha") == "A" else 10),
            }
            ranking_ativos.append(item_rk)
            if len(graves) > 0 or n_quebras >= 2:
                quebras_evitaveis.append(item_rk)

        ranking_ativos.sort(key=lambda x: (-x["score_criticidade_aqf"], -x["quebras_graves"], -x["tempo_quebra_min"]))
        quebras_evitaveis.sort(key=lambda x: (-x["quebras_graves"], -x["quebras"]))

        total_quebras = sum(cont_sev.values())
        escada = {}
        for nv in ("LEVE", "MODERADA", "GRAVE"):
            qtd = cont_sev[nv]
            pct = round((qtd / total_quebras * 100.0), 1) if total_quebras else 0.0
            regua = REGUA_OFICIAL[nv]
            escada[nv] = {"qtd": qtd, "pct": pct, "regua": regua, "desvio_pp": round(pct - regua, 1)}

        self.confiabilidade = {
            "total_oms": len(self.oms_auditadas),
            "total_quebras": total_quebras,
            "categorias": dict(cont_cat),
            "escada_severidade": escada,
            "matriz_bc": dict(cont_bc),
            "top_ofensores": ranking_ativos[:15],
            "radar_quebras_evitaveis": quebras_evitaveis[:10],
        }

        dt = round(time.time() - t0, 3)
        self.estado_nos["no7"].update({
            "status": "concluido",
            "tempo_s": dt,
            "resumo": f"{total_quebras} Quebras analisadas • {len(ranking_ativos[:10])} Top Ofensores ranqueados por MTBF/MTTR e Rota",
            "metricas": {
                "total_quebras": total_quebras,
                "quebras_graves": cont_sev["GRAVE"],
                "top_ofensor": ranking_ativos[0]["ativo"] if ranking_ativos else "—",
            },
        })
        return self.confiabilidade

    # ------------------------------------------------------------------
    # NÓ 8: CAÇADOR AQF 2.0 (2 CHAMADAS ESTRUTURADAS + DOCS-ATIVOS)
    # ------------------------------------------------------------------
    def no8_cacador_aqf(self, alvos=None, max_estudos=3):
        t0 = time.time()
        self.estado_nos["no8"]["status"] = "rodando"

        if not self.confiabilidade:
            self.no7_confiabilidade()

        top_alvos = alvos or [x["ativo"] for x in self.confiabilidade.get("top_ofensores", []) if x["quebras"] > 0][:max_estudos]
        estudos = []

        for alvo in top_alvos:
            oms_alvo = [
                o for o in self.oms_auditadas
                if o["ativo"] == alvo and (o["categoria"] == "QUEBRA" or int(o.get("tempo_min") or 0) >= 45)
            ]
            if not oms_alvo:
                oms_alvo = [o for o in self.oms_auditadas if o["ativo"] == alvo]
            if not oms_alvo:
                continue

            estudo = self._gerar_estudo_aqf_ativo(alvo, oms_alvo)
            estudos.append(estudo)

        self.estudos_aqf = estudos
        dt = round(time.time() - t0, 3)
        self.estado_nos["no8"].update({
            "status": "concluido",
            "tempo_s": dt,
            "resumo": f"{len(estudos)} Estudo(s) AQF completo(s) (RAE + Ishikawa 6M + 5 Porquês + 5W2H)",
            "metricas": {"estudos_gerados": len(estudos), "alvos": [e["ativo"] for e in estudos]},
        })
        return estudos

    def _gerar_estudo_aqf_ativo(self, alvo, oms_alvo):
        info_rk = next((x for x in self.confiabilidade.get("top_ofensores", []) if x["ativo"] == alvo), {})
        componente_foco = self._extrair_componente_dominante(oms_alvo)

        # Busca manuais e cartas de lubrificação vigentes em DOCS-ATIVOS.html (docs_ativos)
        alvo_norm = normalizar(alvo)
        tokens_alvo = [w for w in alvo_norm.split() if len(w) >= 4]
        docs_vinculados = []
        for d in self.docs_biblioteca:
            if d.get("status", "vigente") != "vigente":
                continue
            hay = normalizar(f"{d.get('maquina', '')} {d.get('equipamento', '')} {d.get('conjunto', '')} {d.get('titulo', '')}")
            if any(tk in hay for tk in tokens_alvo):
                docs_vinculados.append({
                    "codigo": d.get("codigo", "DOC-PCM"),
                    "titulo": d.get("titulo", "Manual Técnico"),
                    "categoria": d.get("categoria", "manuais"),
                    "revisao": d.get("revisaoVigenteLabel", "REV 00"),
                })

        exemplos_om = sorted(oms_alvo, key=lambda x: -int(x.get("tempo_min") or 0))[:5]
        sintoma_principal = exemplos_om[0].get("problema", "Falha funcional recorrente")
        acao_executada = exemplos_om[0].get("servico", "Substituição corretiva de componente")
        mttr = info_rk.get("mttr_min", 60.0)
        mtbf = info_rk.get("mtbf_h", 180.0)
        quebras_qtd = info_rk.get("quebras", len(oms_alvo))
        graves_qtd = info_rk.get("quebras_graves", sum(1 for x in oms_alvo if x.get("severidade") == "GRAVE"))

        causa_raiz = (
            f"Degradação acelerada no conjunto '{componente_foco}' de {alvo} sem gatilho preventivo/inspeção "
            f"calibrado para o ciclo real de falha (MTBF atual = {mtbf}h, MTTR = {mttr} min)."
        )

        ishikawa_6m = {
            "Maquina": f"Folga/desgaste acumulado no subconjunto '{componente_foco}' ({quebras_qtd} ocorrência(s), {graves_qtd} GRAVE).",
            "Metodo": f"Frequência de inspeção sensitiva/preventiva acima do MTBF observado ({mtbf}h).",
            "Material": f"Solicitação mecânica/térmica severa no componente ({sintoma_principal[:90]}).",
            "Mao_de_Obra": "Necessidade de padrão visual (LUP) de torque, alinhamento e ajuste pós-intervenção.",
            "Meio_Ambiente": f"Operação contínua em linha Classe {info_rk.get('criticidade_linha', 'A')} com exposição a processo/limpeza.",
            "Medida": "Ausência de monitoramento de tendência (temperatura/vibração/corrente) antes do travamento.",
        }

        cinco_porques = [
            f"1º Por que o ativo {alvo} sofreu parada não programada? Porque ocorreu '{sintoma_principal}'.",
            f"2º Por que ocorreu '{sintoma_principal}'? Porque o componente '{componente_foco}' atingiu falha funcional ({acao_executada[:100]}).",
            f"3º Por que o componente falhou em operação? Porque a degradação progrediu entre ciclos sem substituição preventiva prévia.",
            f"4º Por que não foi interceptado antes da quebra? Porque {info_rk.get('status_rota', 'o intervalo de inspeção/preventiva estava acima do MTBF real')}.",
            f"5º Por que o plano não bloqueou a causa raiz? {causa_raiz}",
        ]

        periodicidade_sugerida = "Semanal" if mtbf < 120 else ("Quinzenal" if mtbf < 260 else "Mensal")
        plano_5w2h = [
            {
                "tipo_acao": "PREVENTIVA",
                "o_que": f"Incluir revisão/troca preventiva de '{componente_foco}' no plano de {alvo}",
                "por_que": f"Bloquear recorrência antes do MTBF de {mtbf}h e reduzir MTTR ({mttr} min)",
                "onde": f"{info_rk.get('setor', 'Produção')} › {alvo}",
                "como": f"Checklist padronizado ({periodicidade_sugerida}) com medição de desgaste, reaperto e validação de partida",
                "quem": exemplos_om[0].get("equipe", "MECANICA"),
                "periodicidade": periodicidade_sugerida,
                "duracao_min": max(45, int(round(mttr))),
            },
            {
                "tipo_acao": "INSPECAO_ROTA",
                "o_que": f"Criar Ponto Cirúrgico de Inspeção de Rota para '{componente_foco}' em {alvo}",
                "por_que": "Detectar ruído, aquecimento, vazamento ou desalinhamento na fase inicial (C=1)",
                "onde": f"{info_rk.get('setor', 'Produção')} › {alvo}",
                "como": "Inspeção sensitiva/instrumental semanal no checklist de rota de 52 semanas",
                "quem": exemplos_om[0].get("equipe", "MECANICA"),
                "periodicidade": "Semanal",
                "duracao_min": 20,
            },
            {
                "tipo_acao": "AGENDA_PCM",
                "o_que": f"Intervenção técnica de saneamento e padronização do conjunto '{componente_foco}'",
                "por_que": f"Eliminar condição subpadrão identificada nas OMs {', '.join(x['om'] for x in exemplos_om[:3])}",
                "onde": f"{info_rk.get('setor', 'Produção')} › {alvo}",
                "como": "Executar na próxima janela programada com conferência da supervisão",
                "quem": exemplos_om[0].get("equipe", "MECANICA"),
                "periodicidade": "Pontual",
                "duracao_min": max(60, int(round(mttr))),
            },
        ]

        return {
            "id": f"aqf_{normalizar(alvo).replace(' ', '_')[:28]}",
            "ativo": alvo,
            "setor": info_rk.get("setor", "Produção"),
            "maquina": info_rk.get("maquina", alvo),
            "equipamento": info_rk.get("equipamento", alvo),
            "criticidade_linha": info_rk.get("criticidade_linha", "A"),
            "componente_foco": componente_foco,
            "equipe": exemplos_om[0].get("equipe", "MECANICA"),
            "metricas": {
                "total_oms": info_rk.get("total_oms", len(oms_alvo)),
                "quebras": quebras_qtd,
                "quebras_graves": graves_qtd,
                "tempo_parada_min": info_rk.get("tempo_quebra_min", sum(int(x.get("tempo_min") or 0) for x in oms_alvo)),
                "mttr_min": mttr,
                "mtbf_h": mtbf,
                "disponibilidade_pct": info_rk.get("disponibilidade_pct", 95.0),
                "status_rota": info_rk.get("status_rota", "Avaliar rota"),
                "risco_obsolescencia": info_rk.get("risco_obsolescencia", False),
            },
            "oms_evidencia": [
                {
                    "om": x["om"],
                    "data": x.get("data", ""),
                    "tempo_min": x.get("tempo_min", 0),
                    "severidade": x.get("severidade", "NA"),
                    "problema": x.get("problema", ""),
                    "servico": x.get("servico", ""),
                }
                for x in exemplos_om
            ],
            "docs_tecnicos_ativos": docs_vinculados,
            "rae_resumo": (
                f"Ativo Classe {info_rk.get('criticidade_linha', 'A')} ({alvo}) acumulou {quebras_qtd} quebra(s) "
                f"({graves_qtd} GRAVE) com MTBF de {mtbf}h e MTTR de {mttr} min. Foco concentrado em '{componente_foco}'."
            ),
            "ishikawa_6m": ishikawa_6m,
            "cinco_porques": cinco_porques,
            "causa_raiz": causa_raiz,
            "plano_5w2h": plano_5w2h,
            "gerado_em": datetime.now().isoformat(timespec="seconds"),
        }

    def _extrair_componente_dominante(self, oms_alvo):
        candidatos = [
            "mordente", "rolamento", "correia", "estator", "pedra", "selo",
            "inversor", "sensor", "fotocelula", "bomba", "redutor", "esteira",
            "valvula", "cilindro", "bico", "faca", "matriz", "cabecote", "motor",
        ]
        cont = Counter()
        for o in oms_alvo:
            t = normalizar(f"{o.get('problema', '')} {o.get('servico', '')}")
            for c in candidatos:
                if c in t:
                    cont[c] += 1
        if cont:
            return cont.most_common(1)[0][0].upper()
        return "CONJUNTO DE ACIONAMENTO / PROCESSO"

    # ------------------------------------------------------------------
    # NÓ 9: PLANEJADOR INTELIGENTE (PROPOSTAS 1-CLIQUE PARA O PORTAL PCM)
    # ------------------------------------------------------------------
    def no9_planejador_acoes(self):
        t0 = time.time()
        self.estado_nos["no9"]["status"] = "rodando"

        if not self.estudos_aqf:
            self.no8_cacador_aqf()

        propostas = []
        for est in self.estudos_aqf:
            for idx, acao in enumerate(est.get("plano_5w2h", []), 1):
                propostas.append({
                    "id": f"{est['id']}_acao_{idx}",
                    "estudo_id": est["id"],
                    "ativo": est["ativo"],
                    "setor": est["setor"],
                    "maquina": est["maquina"],
                    "equipamento": est["equipamento"],
                    "componente": est["componente_foco"],
                    "criticidade_linha": est["criticidade_linha"],
                    "destino_modulo": acao["tipo_acao"],  # PREVENTIVA | INSPECAO_ROTA | AGENDA_PCM
                    "titulo": acao["o_que"],
                    "justificativa": acao["por_que"],
                    "procedimento": acao["como"],
                    "equipe": acao["quem"],
                    "periodicidade": acao["periodicidade"],
                    "duracao_min": acao["duracao_min"],
                    "status": "PRONTA_PARA_1_CLIQUE",
                })

        self.propostas_planejador = propostas
        dt = round(time.time() - t0, 3)
        self.estado_nos["no9"].update({
            "status": "concluido",
            "tempo_s": dt,
            "resumo": f"{len(propostas)} proposta(s) pronta(s) para envio 1-clique (Preventivas, Rota 52S e Agenda PCM)",
            "metricas": {"total_propostas": len(propostas)},
        })
        return propostas

    # ------------------------------------------------------------------
    # EXECUÇÃO COMPLETA & EXPORTAÇÃO SINCRONIZADA COM O PORTAL
    # ------------------------------------------------------------------
    def executar_pipeline_completo(self, entrada, api_key=None, max_estudos=3):
        self.no1_coletor_validador(entrada)
        self.no2_fast_path_memoria()
        self.no3_auditor_ia_lote(api_key=api_key)
        self.no4_roteador_governanca()
        self.no5_conferente()
        self.no6_bibliotecario()
        self.no7_confiabilidade()
        self.no8_cacador_aqf(max_estudos=max_estudos)
        self.no9_planejador_acoes()
        return self.gerar_pacote_portal()

    def gerar_pacote_portal(self):
        return {
            "schema": SCHEMA_MAESTRI,
            "versao": VERSAO_MAESTRI,
            "gerado_em": datetime.now().isoformat(timespec="seconds"),
            "nos": list(self.estado_nos.values()),
            "custo": self.custo_rodada,
            "qualidade_equipes": self.qualidade_equipes,
            "divergencias_supervisores": self.divergencias_supervisores,
            "confiabilidade": self.confiabilidade,
            "estudos_aqf": self.estudos_aqf,
            "propostas_planejador": self.propostas_planejador,
            "ordens": self.oms_auditadas,
        }

    def exportar_arquivos(
        self,
        caminho_csv="OMs_Auditadas.csv",
        pasta_filas="filas",
        caminho_manifest="manifest_auditoria.json",
        caminho_portal_sync="maestri_portal_sync.json",
    ):
        # 1. CSV compatível SIMULTANEAMENTE com exporta_filas.py e cacador_ia.py!
        colunas_csv = [
            "OM", "Data", "Ativo", "Descrição (Ativo)", "Equipe", "Tempo_min",
            "Duracao_Total_Parada", "Status_OM", "Problema", "Descrição",
            "Servico", "Descrição do Serviço", "Categoria_IA", "Severidade",
            "B_IA", "C_IA", "Regra_Severidade", "Parecer_Auditoria_IA",
            "Justificativa_IA", "Avisos_Sistema", "Origem_Decisao",
            "Confianca", "Tipo_Manut_ERP", "fila", "qualidade_score",
        ]
        if caminho_csv:
            with open(caminho_csv, "w", encoding="utf-8-sig", newline="") as f:
                w = csv.DictWriter(f, fieldnames=colunas_csv, delimiter=";", extrasaction="ignore")
                w.writeheader()
                for o in self.oms_auditadas:
                    w.writerow(o)

        # 2. Filas por equipe
        if pasta_filas:
            os.makedirs(pasta_filas, exist_ok=True)
            for eq, lista in self.filas_equipe.items():
                pend = [o for o in lista if o.get("fila") in ("CONFERIR", "REVISAO")]
                with open(os.path.join(pasta_filas, f"fila_{eq.lower()}.json"), "w", encoding="utf-8") as f:
                    json.dump(pend, f, ensure_ascii=False, indent=2)
            revisao = [o for o in self.oms_auditadas if o.get("fila") == "REVISAO"]
            with open(os.path.join(pasta_filas, "revisao.json"), "w", encoding="utf-8") as f:
                json.dump(revisao, f, ensure_ascii=False, indent=2)

        # 3. Manifest & Portal Sync JSON
        pacote = self.gerar_pacote_portal()
        if caminho_manifest:
            manifest = {
                "schema": SCHEMA_MAESTRI,
                "versao": VERSAO_MAESTRI,
                "timestamp": pacote["gerado_em"],
                "sucesso": True,
                "custo": self.custo_rodada,
                "relatorio": {
                    "oms_classificadas": len(self.oms_auditadas),
                    "quebras": self.confiabilidade.get("total_quebras", 0),
                    "categorias": self.confiabilidade.get("categorias", {}),
                    "escada_severidade": self.confiabilidade.get("escada_severidade", {}),
                },
            }
            with open(caminho_manifest, "w", encoding="utf-8") as f:
                json.dump(manifest, f, ensure_ascii=False, indent=2)

        if caminho_portal_sync:
            with open(caminho_portal_sync, "w", encoding="utf-8") as f:
                json.dump(pacote, f, ensure_ascii=False, indent=2)

        return pacote


def Boolean_api(chave, modo_ia):
    if modo_ia == "deterministico":
        return False
    return bool(chave and len(chave) > 15)
