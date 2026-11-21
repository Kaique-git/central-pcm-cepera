# -*- coding: utf-8 -*-
"""
maestri/dominio.py — Domínio industrial PCM Cepêra (Políticas, Evidências, Matriz B×C EN 13306,
Fast-Path R$ 0,00, Equilíbrio Técnico de Falha Operacional e Qualidade de Apontamento).
Compatível com Python 3.8 a 3.13.
"""

import re
import unicodedata
from datetime import datetime

VERSAO_MAESTRI = "v41.0-Maestri-2.0"
SCHEMA_MAESTRI = "maestri_pcm/v41"

CATEGORIAS = [
    "ACOMPANHAMENTO",
    "AJUSTE",
    "AJUSTE POS SETUP",
    "FALHA OPERACIONAL",
    "INSPECAO DE ROTAS",
    "MANUTENCAO PROGRAMADA",
    "MELHORIAS",
    "PREDIAL",
    "PREVENTIVA",
    "QUEBRA",
    "SETUP PROGRAMADO",
]

EQUIPES = ("MECANICA", "ELETRICA", "MONTAGEM", "PREDIAL")

SINAIS_VALIDOS = {
    "FUNCAO_MANTIDA",
    "FUNCAO_PERDIDA",
    "JANELA_PLANEJADA",
    "SINAL_OPERACIONAL",
    "TROCA_SEM_FALHA",
    "FORMATO",
    "EDIFICACAO",
    "ROTINA_DECLARADA",
    "OUTRO",
}

# Correção do bug crítico da v40 (onde PARADAS_BIB = 3 quebrava assinatura_caso com TypeError)
PARADAS_BIB = {
    "para", "com", "sem", "dos", "das", "que", "foi", "pela", "pelo",
    "esta", "estava", "apos", "sobre", "mais", "menos", "muito",
    "pouco", "tambem", "fazer", "feito", "realizado", "realizada",
    "maquina", "equipamento", "servico", "ordem", "linha", "setor",
}

DIST_REFERENCIA = {
    "AJUSTE": 64.4,
    "MANUTENCAO PROGRAMADA": 13.2,
    "QUEBRA": 11.3,
    "SETUP PROGRAMADO": 4.9,
    "ACOMPANHAMENTO": 2.5,
    "FALHA OPERACIONAL": 1.8,
    "PREDIAL": 1.1,
    "MELHORIAS": 0.7,
    "AJUSTE POS SETUP": 0.5,
    "PREVENTIVA": 0.3,
    "INSPECAO DE ROTAS": 0.3,
}

REGUA_OFICIAL = {"LEVE": 47.1, "MODERADA": 30.5, "GRAVE": 22.3}

TEMPO_CURTO = 30
TEMPO_LONGO = 180
ESCOPO_VERBOS_MIN = 4
ESCOPO_CARACTERES = 280
B_SEM_CRITICO_MAX = 2
TETO_DESGASTE_MAX = "MODERADA"
TETO_LAMPADA_MAX = "LEVE"

MAPA_COLUNAS = {
    "om": ["om", "ordem", "num_om", "numero_om", "n_om", "no_os", "num_os",
           "ordem_manutencao", "id", "codigo_om", "numero"],
    "problema": ["descricao", "problema", "descricao_problema", "desc_problema",
                 "defeito", "descricao_do_problema", "sintoma"],
    "servico": ["servico", "descricao_servico", "desc_servico", "solucao",
                "atividade", "descricao_do_servico", "servico_realizado",
                "servico_executado", "acao"],
    "tempo": ["tempo", "tempo_total", "tempo_trabalhado", "duracao", "horas",
              "tempo_min", "minutos", "mttr", "tempo_parada",
              "duracao_total_parada"],
    "ativo": ["ativo", "descricao_ativo", "equipamento", "maquina", "linha", "tag"],
    "data": ["data", "data_manutencao", "data_de_manutencao", "data_om",
             "data_abertura", "data_conclusao", "data_e_hora_de_conclusao",
             "data_hora_conclusao", "data_servico", "data_execucao",
             "data_fim", "data_termino", "data_encerramento",
             "data_fechamento", "data_realizacao", "dt"],
    "status": ["status", "situacao", "situacao_om", "estado", "fase",
               "status_om", "fl_status", "status_ordem", "statusestudo"],
    "equipe": ["equipe", "time", "setor", "area", "disciplina",
               "descricao_tipo_de_servico_de_manutencao",
               "descricao (tipo de servico de manutencao)",
               "tipo_de_servico_de_manutencao"],
    "tipo_manut": ["descricao_tipos_de_manutencao", "tipos_de_manutencao",
                   "tipo_manutencao", "tipo_de_manutencao", "tipo_manut",
                   "tipos_manutencao", "tipo_manut_erp"],
}

STATUS_CONCLUIDA = (
    "concluid", "encerrad", "finalizad", "fechad", "realizad",
    "completed", "closed", "finished", "done", "atendid", "executad",
    "baixad", "apontad",
)

STATUS_ABERTA = (
    "abert", "solicitad", "pendent", "andamento", "liberad", "aguardand",
    "em execucao", "executando", "planejad", "programad", "aprovad",
    "nao iniciad", "backlog", "em aberto", "em espera", "cancelad",
    "reprovad", "aguardando", "em analise", "em aprovacao", "orcament",
)


def normalizar(t):
    if t is None:
        return ""
    t = str(t).strip().lower()
    t = unicodedata.normalize("NFKD", t)
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = re.sub(r"[^a-z0-9\s]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def norm_om(v):
    if v is None:
        return ""
    s = str(v).strip()
    if s.endswith(".0"):
        s = s[:-2]
    m = re.search(r"\d+", s)
    return m.group(0) if m else s.upper()


def norm_categoria(v):
    t = normalizar(v).replace(" ", "_").upper()
    if not t:
        return ""
    mapa = {
        "ACOMPANHAMENTO": "ACOMPANHAMENTO",
        "AJUSTE": "AJUSTE",
        "AJUSTE_POS_SETUP": "AJUSTE POS SETUP",
        "FALHA_OPERACIONAL": "FALHA OPERACIONAL",
        "INSPECAO_DE_ROTAS": "INSPECAO DE ROTAS",
        "INSPECAO_ROTAS": "INSPECAO DE ROTAS",
        "MANUTENCAO_PROGRAMADA": "MANUTENCAO PROGRAMADA",
        "MELHORIAS": "MELHORIAS",
        "MELHORIA": "MELHORIAS",
        "PREDIAL": "PREDIAL",
        "PREVENTIVA": "PREVENTIVA",
        "QUEBRA": "QUEBRA",
        "SETUP_PROGRAMADO": "SETUP PROGRAMADO",
        "SETUP": "SETUP PROGRAMADO",
        "REVISAR_MANUAL": "REVISAR_MANUAL",
    }
    if t in mapa:
        return mapa[t]
    for k, v2 in mapa.items():
        if t.startswith(k):
            return v2
    return t


def norm_sev(v):
    t = normalizar(v).upper()
    if "GRAV" in t:
        return "GRAVE"
    if "MODER" in t:
        return "MODERADA"
    if "LEV" in t:
        return "LEVE"
    if "PEND" in t:
        return "PENDENTE"
    return "NA"


def converter_tempo(valor):
    if valor is None:
        return None
    s = str(valor).strip()
    if not s:
        return None
    m_hhmm = re.match(r"^(\d{1,3}):(\d{2})(?::(\d{2}))?$", s)
    if m_hhmm:
        h = int(m_hhmm.group(1))
        mi = int(m_hhmm.group(2))
        return h * 60 + mi
    s_num = s.replace(",", ".")
    try:
        v = float(s_num)
        return int(round(v)) if v >= 0 else None
    except ValueError:
        return None


_DIAS_PT = ["segunda", "terca", "quarta", "quinta", "sexta", "sabado", "domingo"]
_DIAS_ABREV = ["SEG", "TER", "QUA", "QUI", "SEX", "SAB", "DOM"]


def parse_data(v):
    if not v:
        return None
    s = str(v).strip()
    if not s:
        return None
    s = s.split(" ")[0].split("T")[0]
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d", "%d.%m.%Y"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def dia_semana_info(data_str):
    dt = parse_data(data_str)
    if dt is None:
        return None, None, False, False
    i = dt.weekday()
    return (_DIAS_PT[i], _DIAS_ABREV[i], i == 5, i == 6)


def classificar_status(valor):
    t = normalizar(valor)
    if not t:
        return "desconhecido"
    if re.match(r"^(?:nao|sem)\s", t):
        return "aberta"
    for p in STATUS_CONCLUIDA:
        if t.startswith(p):
            return "concluida"
    for p in STATUS_ABERTA:
        if t.startswith(p) or p in t:
            return "aberta"
    if t in ("3", "4", "c", "f", "ok", "sim"):
        return "concluida"
    if t in ("1", "2", "a", "p"):
        return "aberta"
    return "desconhecido"


def om_esta_concluida(status_valor, tempo, modo="auto"):
    if modo == "todos":
        return True, "filtro desativado"
    st = classificar_status(status_valor)
    if modo == "status":
        return (st == "concluida"), f"status={st}"
    if modo == "tempo":
        ok = tempo is not None and tempo > 0
        return ok, f"tempo={'positivo' if ok else 'zero/ausente'}"
    if st == "concluida":
        return True, "status concluida"
    if st == "aberta":
        return False, "status aberta"
    ok = tempo is not None and tempo > 0
    return ok, f"status desconhecido, tempo={'positivo' if ok else 'zero/ausente'}"


# ================= CAMADAS DE DETECÇÃO REGEX =================
RE_TROCA_FORTE = re.compile(
    r"\b(?:trocad[oa]s?|trocou|trocamos|trocand[oa]|"
    r"su\w{0,2}titu\w*|repost[oa]s?|reposta|permutad[oa]s?|permutou|"
    r"colocad[oa]\s+(?:nov[oa]s?|outr[oa])|"
    r"instalad[oa]\s+(?:nov[oa]s?|outr[oa])|troc\w*)\b"
)
RE_TROCA_FRACA = re.compile(
    r"\b(?:troc\w*|su\w{0,2}titu\w*|repost[oa]s?|reposicao|reposicoes|permut\w*|"
    r"su\w{0,2}bstitu\w*)\b"
)
RE_NEGACAO_TROCA = re.compile(r"\bsem\s+(?:troc\w*|substitu\w*|repos\w*|permut\w*)")
RE_CONFIRMA_ADICIONAL = re.compile(r"\badiciona\w*|\bextra\b|\balem\s+dess|\boutr[ao]\b")

RE_FALHA_HARD = re.compile(
    r"\b(?:queim\w*|queimou|quebr\w*|quebrou|trinc\w*|trincou|rompe\w*|rompeu|"
    r"rasg\w*|rasgou|fur\w*|furou|furo|furad[oa]|"
    r"emperr\w*|emperrou|trav\w*|travou|solt\w*|soltou|"
    r"empen\w*|empenou|derret\w*|derreteu|estour\w*|estourou|"
    r"arrebent\w*|arrebentou|estuf\w*|estufou|"
    r"fund\w*|fundiu|oxidad\w*|oxidou|corro\w*|corroeu|"
    r"entup\w*|entupiu|incrustac\w*|incrustou|"
    r"vaz\w*|vazou|vazamento|falh\w*|falha|defeit\w*|defeito|"
    r"parou|danific\w*|danificou|avari\w*|avariou|"
    r"contamin\w*|contaminou|desalinh\w*|desalinhou|"
    r"desbalance\w*|desbalanceou|descalibr\w*|descalibrou|"
    r"fadiga|fadigad[oa]|corros\w*|abras\w*|curto)\b"
)

RE_FALHA = re.compile(
    r"\b(?:queim\w*|queimou|quebr\w*|quebrou|trinc\w*|trincou|rompe\w*|rompeu|"
    r"rasg\w*|rasgou|fur\w*|furou|furo|furad[oa]|"
    r"desgast\w*|emperr\w*|emperrou|trav\w*|travou|solt\w*|soltou|"
    r"empen\w*|empenou|derret\w*|derreteu|estour\w*|estourou|"
    r"arrebent\w*|arrebentou|estuf\w*|estufou|"
    r"fund\w*|fundiu|oxidad\w*|oxidou|corro\w*|corroeu|"
    r"entup\w*|entupiu|incrustac\w*|incrustou|"
    r"vaz\w*|vazou|vazamento|falh\w*|falha|defeit\w*|defeito|"
    r"parou|danific\w*|danificou|avari\w*|avariou|"
    r"contamin\w*|contaminou|desalinh\w*|desalinhou|"
    r"desbalance\w*|desbalanceou|descalibr\w*|descalibrou|"
    r"fadiga|fadigad[oa]|corros\w*|abras\w*|curto)\b"
)

RE_DESGASTE_NATURAL = re.compile(
    r"\b(?:gast[oa]s?|desgastad[oa]s?|vencid[oa]s?|consumid[oa]s?|"
    r"no\s+limite|fim\s+de\s+vida\s+util|vida\s+util|"
    r"por\s+uso|pelo\s+uso|uso\s+normal|"
    r"ja\s+estava\s+gast[oa]|estava\s+gast[oa])\b"
)

RE_NEUTRALIZA_FALHA = re.compile(
    r"\bsem\s+(?:falha|falhas|defeito|defeitos|problema|problemas|"
    r"vazamento|vazamentos|ruido|ruidos|anormalidade)\w*"
)

RE_SEM_FUNCAO = re.compile(
    r"\b(?:nao\s+(?:liga|ligou|parte|partiu|funciona|funcionou|aciona|acionou|"
    r"abre|abriu|fecha|fechou|gira|girou|puxa|puxou|sobe|subiu|desce|desceu|"
    r"segura|segurou|solda|soldou|dosou|dosando|enche|encheu|mantem|manteve|"
    r"sai|saiu|reconhece|reconheceu|responde|respondeu|le|leu|detecta|detectou|"
    r"inicia|iniciou|completa|completou|retorna|retornou|reseta|resetou)|"
    r"parou\s+de\s+(?:funcionar|operar|dosar|soldar|girar|acionar|responder|bater|cortar)|"
    r"deixou\s+de\s+(?:funcionar|operar|dosar|soldar|girar|acionar)|"
    r"em\s+alarme|travad[oa]|travando|bloquead[oa]|em\s+falha|"
    r"sem\s+(?:funcionamento|funcionar|resposta|acao|forca)|"
    r"perdeu\s+(?:forca|rendimento|pressao|vacuo|torque|velocidade|referencia))\b"
)

RE_PARADA_PRODUCAO = re.compile(
    r"\b(?:parou\s+a\s+(?:producao|linha|maquina|maquinas)|"
    r"a\s+linha\s+parou|a\s+maquina\s+parou|o\s+equipamento\s+parou|"
    r"linha\s+parada|maquina\s+parada|equipamento\s+parado|"
    r"parada\s+de\s+producao|parada\s+nao\s+programada|parada\s+forcada|paralisac\w*|"
    r"producao\s+(?:parada|interrompida|comprometida|prejudicada|afetada)|"
    r"interrompeu\s+a\s+(?:producao|linha)|"
    r"perda\s+de\s+(?:lote|batelada|producao|produto|embalagem|material)|"
    r"perdemos\s+(?:lote|batelada|producao|material|a\s+esterilizacao)|"
    r"batelada\s+perdida|lote\s+perdido|refugo|"
    r"ficou\s+sem\s+produzir|deixou\s+de\s+produzir|sem\s+producao|"
    r"fiquei\s+parad[oa]|ficamos\s+parad[oa]|paramos\s+a|"
    r"nao\s+produziu|nao\s+conseguiu\s+produzir)\b"
)

RE_CONSEQUENCIA = re.compile(
    r"\b(?:ruido\w*|barulh\w*|vibra\w*|trepidac\w*|"
    r"superaquec\w*|aqueciment\w*\s+excessiv\w*|esquent\w*|"
    r"cheiro\s+de\s+queimad\w*|fumac\w*|fumaca|"
    r"refug\w*|perda\s+de\s+(?:produto|producao|batelada|lote|material|"
    r"rendimento|embalagem|sache|pacote|vinagre|goma|esterilizacao)|"
    r"parada\s+nao\s+programada|parada\s+forcada)\b"
)

RE_PENDENTE = re.compile(
    r"\b(?:necessit\w*|precis\w*|aguard\w*|pendent\w*|solicitad\w*|"
    r"providenci\w*|agendad\w*|"
    r"sera\s+(?:trocad|reparad|substitu|soldad|feito|executad|instalad)\w*|"
    r"a\s+ser\s+(?:trocad|reparad|substitu|soldad|feito|executad)\w*|"
    r"ficou\s+de|deixad\w*\s+(?:para|pendente)|"
    r"orcament\w*|pedid\w*\s+de\s+compra|sem\s+condic\w*|"
    r"nao\s+foi\s+(?:possivel|executad|realizad)\w*|"
    r"impossibilitad\w*|passad[oa]\s+para\s+manutenc\w*)\b"
)

RE_SETUP = re.compile(
    r"\b(?:setup|set\s*up|"
    r"troca\s+de\s+(?:produto|formato|ferrament\w*|molde|matriz|faca|facas|"
    r"mordente|mordentes|bico|bicos|dosador|dosadores|selagem|rotulo|"
    r"embalagem|sabor|receita|peca\s+de\s+formato)|"
    r"mudanc\w*\s+de\s+(?:produto|formato|sabor|receita|rotulo|embalagem|"
    r"ferrament\w*|molde|matriz)|"
    r"preparac\w*\s+de\s+maquina|regulagem\s+(?:de|para)\s+maquina|"
    r"inicio\s+de\s+(?:turno|producao|batelada|ordem|rodada)|"
    r"(?:final|fim)\s+de\s+(?:turno|producao|batelada|ordem|rodada))\b"
)

RE_POS_SETUP = re.compile(
    r"\b(?:pos\s*setup|apos\s+(?:o\s+)?setup|depois\s+d[oa]\s+setup|"
    r"apos\s+(?:a\s+)?troca\s+de\s+(?:produto|formato|sabor|rotulo|embalagem)|"
    r"depois\s+d[ao]\s+troca\s+de\s+(?:produto|formato|sabor)|"
    r"ajuste\s+(?:fino\s+)?apos|regulagem\s+apos|"
    r"pos\s+setap|apos\s+setap|setap\s+para)\b"
)

# Equilíbrio Técnico de FALHA OPERACIONAL (Calibrado pelo Grill-Me com os 15 casos reais do CSV):
# Cobre atribuição humana explícita (operador, facilitador, colaborador, encarregado)
# E indícios técnicos claros de operação fora de padrão (colisão de paleteira, botão/chave em manual ou
# fora do automático, registro/válvula fechado pela operação, orientação operacional de uso correto,
# receita/setpoint/parâmetro alterado indevidamente na troca de turno).
RE_FALHA_OPERACIONAL = re.compile(
    r"\b(?:erro\s+(?:de\s+)?operac\w*|erro\s+humano|falha\s+humana|falha\s+operacional|"
    r"mau\s+uso|uso\s+indevid\w*|acionament\w*\s+indevid\w*|operacao\s+indevida|"
    r"(?:operador\w*|operadora\w*|facilitador\w*|facilidador\w*|colaborador\w*|funcionari\w*|encarregad\w*)"
    r"[^.;]{0,95}?"
    r"(?:mexeu|mexeram|fucou|fucaram|prendeu|ligou|desligou|alterou|carregou|deixou|esqueceu|"
    r"nao\s+quis|errou|inverteu|forcou|colocou|misturou|bateu|atingiu)|"
    r"falha\s+d[oa]\s+(?:operador\w*|facilitador\w*|facilidador\w*|colaborador\w*)|"
    r"(?:explicad[oa]|ensinad[oa]|orientad[oa])\s+(?:e\s+\w+\s+)?(?:para\s+o\s+|ao\s+|o\s+)?"
    r"(?:operador\w*|facilitador\w*|facilidador\w*|colaborador\w*)|"
    r"atingid[oa]\s+pel[oa]\s+(?:paleteira|empilhadeira|carrinho)|"
    r"batid[oa]\s+de\s+(?:paleteira|empilhadeira)|"
    r"nao\s+estava\s+no\s+automatico|estava\s+ligad[oa]\s+em\s+manual|"
    r"chave\s+seletora[^.;]{0,60}?(?:estava\s+em|errad\w*|invertid\w*)|"
    r"registro\s+fechado|valvula\s+fechada\s+pel[oa]|"
    r"chave\s+(?:na\s+)?posic\w*\s+errad\w*|"
    r"(?:setpoint|receita|parametr\w*)\s+(?:errad\w*|incorret\w*|invertid\w*|irregular\w*)|"
    r"parametr\w*\s+d[aeo]\s+\w+\s+tinha\s+sido\s+alterad\w*|"
    r"esqueceu\s+(?:a\s+|o\s+)?(?:bomba|maquina|chave|valvula|registro)\s+ligad[oa]|"
    r"nao\s+seguiu\s+(?:o\s+)?procediment\w*|"
    r"deixou\s+(?:a\s+|o\s+)?(?:chave|valvula|registro|bomba|canhao)\s+"
    r"(?:em|abert[oa]|fechad[oa]|ligad[oa]|desligad[oa]|virad[oa]))\b",
    re.I,
)

# Indício operacional moderado (vai para fila CONFERIR quando não há troca de peça destrutiva)
RE_INDICIO_OPERACIONAL_CONFERIR = re.compile(
    r"\b(?:fora\s+de\s+comando\s+desde|ajuste\s+operacional|troca\s+da\s+receita|"
    r"orientamos\s+realizar\s+a\s+troca\s+do\s+lote|problema\s+nas\s+tampas\s+do\s+lote)\b",
    re.I,
)

RE_ATRIBUICAO_HUMANA = RE_FALHA_OPERACIONAL

RE_PECA_DESGASTE = re.compile(
    r"\b(?:correia|correias|mola|molas|lampada|lampadas|faca|facas|"
    r"mordente|mordentes|vedacao|vedacoes|oring|gaxeta|gaxetas|"
    r"retentor|retentores|filtro|filtros|mangueira|mangueiras|"
    r"selo|selos|junta|juntas|rolo|rolos|escova|escovas|"
    r"resistencia|resistencias|termopar|termopares|fusivel|fusiveis|"
    r"bucha|buchas|pino|pinos|parafuso|parafusos|porca|porcas|"
    r"arruela|arruelas|abracadeira|presilha|presilhas|graxa|oleo|anel|"
    r"pedra|pedras|conector|conectores|trava\s+elastic\w*|batoque|batoques|"
    r"rolament\w*|mancal|mancais)\b"
)

RE_MELHORIA = re.compile(
    r"\b(?:prolongament\w*|benfeitoria\w*|"
    r"confecc\w*\s+d[eao]?\s*(?:protecao|base|bandeja|cocho|abrigo|plataforma|"
    r"corrimao|guarda\s*corpo)|"
    r"instalac\w*\s+de\s+(?:nova|novo)\s+(?:suporte|base|protecao|guarda|"
    r"cocho|bandeja|plataforma|escada|corrimao|estrutura|abrigo)|"
    r"para\s+facilitar\s+(?:a\s+)?(?:operac\w*|limpez\w*|acesso)|"
    r"para\s+evitar\s+(?:acidente|risco|queda))\b"
)

RE_SO_OBSERVACAO = re.compile(
    r"\b(?:acompanhament\w*|monitora\w*|observac\w*|"
    r"auxili\w*\s+(?:o|a)\s+operador|liberac\w*\s+(?:de|do|da))\b"
)

RE_PLANEJADO = re.compile(
    r"\b(?:apos\s+(?:o\s+)?(?:horari|hora|producao|expediente|turno|janta|almoco)\w*|"
    r"fora\s+do\s+(?:horari|turno|expediente)\w*|"
    r"programad\w*|agendad\w*|"
    r"passad[oa]\s+para\s+manutenc\w*|"
    r"no\s+final\s+do\s+(?:turno|expediente)|"
    r"quando\s+(?:parar|desligar)|na\s+parada|sabado|domingo|\bobs\b)\b"
)

RE_PARADA_PROGRAMADA = re.compile(
    r"\b(?:parada\s+programad[ao]|parada\s+de\s+manutenc\w*|"
    r"manutenc\w*\s+programad[ao]|preventiva\s+programad[ao]|"
    r"durante\s+a\s+parada|aproveitand\w*\s+a\s+parada|"
    r"ja\s+que\s+estava\s+parad[ao]|"
    r"lubrificac\w*\s+programad[ao]|inspec\w*\s+programad[ao]|"
    r"troca\s+programad[ao]|servico\s+programad[ao]|"
    r"rotina\s+de\s+manutenc\w*|plano\s+de\s+manutenc\w*)\b"
)

RE_PREVENTIVA = re.compile(
    r"\b(?:preventiva|preventivas|"
    r"manutencao\s+preventiva|plano\s+de\s+manutencao\s+preventiva|"
    r"preventiva\s+(?:diaria|semanal|mensal|bimestral|trimestral|semestral|anual)|"
    r"preventiva\s+(?:de|n)\s*\d+|rotina\s+preventiva|"
    r"checklist\s+preventivo|pm\s*\d{1,3})\b"
)
RE_PREVENTIVA_FORTE = RE_PREVENTIVA

RE_PLANO_FRACO = re.compile(
    r"\b(?:conforme\s+plano|conforme\s+cronograma|plano\s+de\s+manutencao|"
    r"periodicidade|cronograma\s+de\s+manutencao)\b"
)

RE_INSPECAO_ROTAS = re.compile(
    r"\b(?:inspec\w*\s+de\s+rotas?|inspec\w*\s+de\s+rota|"
    r"ronda|rondas|conforme\s+roteiro|conforme\s+a\s+rota|"
    r"checklist\s+de\s+rota|checklist\s+de\s+inspec\w*|"
    r"rota\s+de\s+inspec\w*|roteiro\s+de\s+inspec\w*|"
    r"inspecao\s+sensitiva|rota\s+preventiva)\b"
)

RE_PREDIAL = re.compile(
    r"\b(?:telhad\w*|telha\w*|calha\w*|rufo|alvenaria|"
    r"esgoto\s+predial|vaso\s+sanitari\w*|"
    r"caixa\s+d\s*agua|caixa\s+de\s+agua|cisterna|"
    r"portao|fechadura|janela\w*|"
    r"forro\s+(?:da|do)\s+|gesso|muro|calcada|bueiro|ralo\s+predial|"
    r"banheiro\w*|vestiari\w*|refeitori\w*|"
    r"ar\s+condicionad\w*\s+(?:da|do)\s+(?:sala|escritorio|refeitorio|vestiario))\b"
)

RE_PREDIAL_NUCLEO = re.compile(
    r"\b(?:telhad\w*|telha\w*|calha\w*|rufo|alvenaria|"
    r"esgoto\s+predial|vaso\s+sanitari\w*|cisterna|"
    r"caixa\s+d\s*agua|caixa\s+de\s+agua|portao|fechadura|janela\w*|"
    r"gesso|muro|calcada|bueiro|ralo\s+predial|banheiro\w*|"
    r"vestiari\w*|refeitori\w*|infiltrac\w*|goteira)\b"
)

RE_EQUIPAMENTO_PROCESSO = re.compile(
    r"\b(?:esteira|motor|bomba|forno|enchedor\w*|enchedeira|rotuladeira|"
    r"tampadeira|seladora|paletizador\w*|dosador\w*|compressor|redutor|"
    r"inversor|mancal|rolament\w*|cabecote|molde|matriz|silo|tanque|"
    r"posicionador|soprador\w*|empurrador|rosqueadeira|pinca|garr\w*|"
    r"serac|posimec|boatopack|comitrol|buller|batedor\w*|dmon|fryma|multipet|systempack|volpack)\b"
)

RE_OBJETO_ESTRANHO = re.compile(
    r"\b(?:pre\s*forma|preforma|pre\s*formas|"
    r"objeto\s+estranh\w*|corpo\s+estranh\w*|material\s+estranh\w*|"
    r"saco\s+plastic\w*|sacola|papel\s+pres[oa]|plastico\s+pres[oa]|"
    r"residuo|rebarba|sobra\s+de\s+material|pedaco\s+de|"
    r"tampa\s+enroscad\w*|tampa\s+pres[oa]|tampa\s+caid[oa]|"
    r"fita\s+pres[oa]|filme\s+pres[oa]|material\s+na\s+esteira)\b"
)
RE_RETIRADA = re.compile(r"\b(?:retir\w*|removid\w*|remov\w*|retirad\w*|liberad\w*)\b")

RE_COMPONENTE_CRITICO = re.compile(
    r"\b(?:rolament\w*|mancal|mancais|motor|motores|redutor|redutores|"
    r"inversor|inversores|plc|clp|ihm|servomotor|encoder|atuador|"
    r"cilindro|valvula|valvulas|compressor|caldeira|trocador|bomba|bombas|"
    r"disjuntor|contator|transformador|paletizador|esteira|cabecote|"
    r"estator|eixo|engrenagem|dosador|dosadores|seladora|pedra|pedras)\b"
)

RE_FERRAMENTAL = re.compile(
    r"\b(?:cabecote|cabecotes|molde|moldes|matriz|matrizes|ferrament\w*|"
    r"torque|estator\s+de\s+motor|faca\s+de\s+formato|"
    r"posicionador|formatador|mordente\s+de\s+selagem)\b"
)

RE_LAMPADA_LOTE = re.compile(
    r"\blampad\w*\b[^.;]{0,40}\b(?:lote|todas|todos|geral|armadilha)\b"
    r"|\b(?:troc\w*|substitu\w*)[^.;]{0,25}\b(?:[2-9]|\d{2,})\s*(?:lampad|lamp)"
    r"|\b(?:[2-9]|\d{2,})\s*(?:lampad|lamp)\w*\b[^.;]{0,30}\b(?:troc|substitu)"
)

RE_SO_RESET = re.compile(
    r"\b(?:rearm\w*|reset\w*|relig\w*|destrav\w*|reinici\w*|reinci\w*)\b"
)

RE_PEDRA = re.compile(r"\b(?:pedra|pedras|conjunto\s+de\s+moagem|rebolo)\b")

RE_C3_EVIDENCIA = re.compile(
    r"\b(?:parou|parada|parado|paralis\w*|interromp\w*|"
    r"nao\s+(?:funciona|liga|opera|parte|aciona|dosou|soldou)|"
    r"travad[oa]|bloquead[oa]|em\s+alarme|fora\s+de\s+operacao|"
    r"risco\s+(?:a|de)\s+(?:pessoa|seguranca|acidente)|acidente|queimadura|"
    r"contaminac\w*|contaminou|refugo|perda\s+de\s+lote)\b"
)

RE_SINTOMA_PROBLEMA = re.compile(
    r"\b(?:quebrad\w*|quebr\w*|furad\w*|furou|vazand\w*|vazou|travad\w*|travou|"
    r"enroscand\w*|enroscou|enroscad\w*|alarme\w*|acionand\w*|"
    r"abert[oa]s?\b|perdend\w*|escapand\w*|escapou|escorregand\w*|escorregou|"
    r"desalinhad\w*|entupid\w*|entupiu|desgastad\w*|parou|falhand\w*|"
    r"defeit\w*|emperrad\w*|soltou|trincad\w*|trincou|rompid\w*|rompeu|"
    r"estourou|arrebentou|entortou|empenou|"
    r"nao\s+(?:funciona|liga|opera|parte|aciona|dosou|soldou)|"
    r"com\s+problema|apresentand\w*\s+problema|"
    r"fora\s+de\s+(?:medida|padrao|posicao|centro))\b"
)

RE_DESMONTAGEM = re.compile(
    r"\b(?:desmont\w*|desmontagem|"
    r"retirad[oa]\s+d[aeo]s?\s+|retirar\s+d[aeo]s?\s+|"
    r"removid[oa]\s+d[aeo]s?\s+|remover\s+d[aeo]s?\s+|"
    r"desinstal\w*|desacoplad\w*|retirad[oa]s?\s+para)\b"
)
RE_INSTALACAO = re.compile(
    r"\b(?:instalac\w*|instalou|instalad[oa]|"
    r"montagem\s+d[ao]|montad[oa]\s+n[ao]|remontagem)\b"
)
RE_RESERVA = re.compile(
    r"\b(?:reserva|backup|sobressalente|estoque|spare|"
    r"ficar\s+de\s+reserva|como\s+reserva|para\s+reserva)\b"
)
RE_REVISAO = re.compile(
    r"\b(?:revisad[oa]s?|revisar|revisao|reforma|overhaul|"
    r"retirada\s+de\s+pendenc\w*|pendenc\w*\s+d[ao]\s+ativo|"
    r"manutenc\w*\s+geral|revisao\s+geral)\b"
)
RE_PARA_MANUTENCAO = re.compile(
    r"\b(?:para\s+manutenc\w*|para\s+reparo|para\s+conserto|"
    r"enviad[oa]\s+para\s+manutenc\w*|trouxe\s+para\s+a\s+manutenc\w*|"
    r"levad[oa]\s+para\s+manutenc\w*|trazid[oa]\s+para\s+a\s+manutenc\w*|"
    r"na\s+oficina|para\s+a\s+oficina)\b"
)

RADICAIS_VERBO = [
    "troc", "substitu", "su\\w{0,2}titu", "sold", "desmont", "mont", "alinh", "regul",
    "apert", "reaper", "instal", "retir", "remov", "limp", "lubrific", "calibr",
    "ajust", "repar", "consert", "cort", "pol", "usin", "recuper", "reforc",
    "fix", "parafus", "grampe", "estanh", "prens", "aliv", "repos",
    "recondicion", "balance", "tension", "estica", "encurt", "emend",
    "revitaliz", "pint", "ved", "rebarb", "esmerilh", "lix", "furad", "rosc",
    "rearm", "reset", "relig", "destrav", "reposicion", "coloc", "prolong",
    "adapt", "repass", "liber", "desobstru", "solt", "esvaz", "purg",
    "confecc", "fabric", "reinici", "reinci",
    "invert", "invers", "girar", "abrir", "fechar", "engrax", "escovar",
    "vedar", "recompor", "revest", "rebocar", "refazer",
]
RE_VERBOS = re.compile(r"\b(?:" + "|".join(dict.fromkeys(RADICAIS_VERBO)) + r")\w*\b")

FALSOS_VERBOS = {
    "reparo", "reparos", "conserto", "consertos", "ajuste", "ajustes",
    "aperto", "apertos", "regulagem", "regulagens", "limpeza", "limpezas",
    "montagem", "montagens", "desmontagem", "desmontagens",
    "solda", "soldas", "pintura", "vedacao", "calibragem",
    "polimento", "corte", "cortes", "reparacao", "recuperacao",
    "rearme", "reset", "colocacao", "adaptacao", "prolongamento",
    "inversor", "inversores", "inversao", "inversoes",
}

RE_SERVICO_VAZIO = re.compile(
    r"^\s*(?:nao\s+informad[oa]|sem\s+informacao|sem\s+servico|"
    r"nao\s+se\s+aplica|sem\s+dados|sem\s+descricao|-+|\.+|n/?a|null|none|nan)\s*$",
    re.I,
)

RE_SERVICO_GENERICO = re.compile(
    r"^\s*(?:ok|sim|nao|verificado|verificacao|testado|teste|realizado|feito|"
    r"feito\s+servico|servico\s+realizado|conforme|conforme\s+solicitado|atendido|"
    r"sem\s+alteracao|nada\s+constatado|nada|nenhum\s+problema|sem\s+problema|"
    r"manutencao|servico|executado|resolvido|concluido|inspecionado|"
    r"acompanhado|acompanhamento)\s*$",
    re.I,
)


def servico_insuficiente(servico, problema=""):
    t = (servico or "").strip()
    pn = normalizar(problema or "")
    tn = normalizar(t)
    if not t or RE_SERVICO_VAZIO.match(t):
        return True
    if not re.search(r"[a-z]{3,}", tn):
        return True
    if RE_SERVICO_GENERICO.match(t):
        return True
    if pn and tn == pn:
        return True
    if len(tn) < 4:
        return True
    if len(tn) < 6 and len(pn) < 20:
        return True
    return False


def categoria_por_problema(problema, servico=""):
    p = normalizar(problema or "")
    if len(p) < 12:
        return None
    if RE_INSPECAO_ROTAS.search(p):
        return "INSPECAO DE ROTAS"
    if RE_PREVENTIVA.search(p):
        return "PREVENTIVA"
    if RE_PREDIAL_NUCLEO.search(p) and not RE_EQUIPAMENTO_PROCESSO.search(p):
        return "PREDIAL"
    if RE_FALHA_OPERACIONAL.search(p):
        return "FALHA OPERACIONAL"
    if RE_SETUP.search(p):
        return "SETUP PROGRAMADO"
    return None


def classificar_equipe(om, t_norm=""):
    bruto = normalizar(om.get("equipe") or "")
    if "eletr" in bruto:
        return "ELETRICA"
    if "mecan" in bruto:
        return "MECANICA"
    if "montag" in bruto:
        return "MONTAGEM"
    if "predial" in bruto:
        return "PREDIAL"

    t = normalizar(t_norm or f"{om.get('problema', '')} {om.get('servico', '')}")
    if RE_PREDIAL_NUCLEO.search(t) and not RE_EQUIPAMENTO_PROCESSO.search(t):
        return "PREDIAL"
    palavras_e = (
        "motor", "eletric", "inversor", "sensor", "fotocelula",
        "disjuntor", "contator", "clp", "painel", "fiacao",
        "cabo", "botoeira", "rele", "servo", "encoder", "alarme", "lampada",
    )
    palavras_m = (
        "rolamento", "correia", "esteira", "mangueira", "bomba",
        "redutor", "eixo", "engrenagem", "vedacao", "retentor",
        "corrente", "polia", "acoplamento", "bucha", "mola", "mordente", "bico",
    )
    n_e = sum(1 for p in palavras_e if p in t)
    n_m = sum(1 for p in palavras_m if p in t)
    if n_e and n_e > n_m:
        return "ELETRICA"
    return "MECANICA"


def assinatura_caso(problema, servico):
    t = normalizar(f"{problema or ''} {servico or ''}")
    return {w.rstrip("s")[:5] for w in t.split() if len(w) > 3 and w not in PARADAS_BIB}


def jaccard(a, b):
    if not a or not b:
        return 0.0
    sa = set(a)
    sb = set(b)
    uniao = len(sa | sb)
    return (len(sa & sb) / uniao) if uniao else 0.0


def tem_troca(t_norm):
    neg = RE_NEGACAO_TROCA.search(t_norm)
    if neg:
        janela = t_norm[neg.start():neg.start() + 90]
        return bool(RE_CONFIRMA_ADICIONAL.search(janela))
    return bool(RE_TROCA_FRACA.search(t_norm))


def servico_so_reset(t_norm):
    return bool(RE_SO_RESET.search(t_norm)) and not tem_troca(t_norm)


def lampada_em_lote(t_norm):
    return bool(re.search(r"\blampad|\blamp\b", t_norm)) and bool(
        RE_LAMPADA_LOTE.search(t_norm)
    )


def objeto_da_troca(t_norm):
    m = re.search(
        r"\b(?:troc\w*|substitu\w*)\s+(?:d[aeo]s?\s+|do\s+|da\s+)?([a-z0-9\s]{3,70})",
        t_norm,
    )
    return m.group(1).strip() if m else ""


def contar_acoes(servico_norm):
    return len({
        m.group(0) for m in RE_VERBOS.finditer(servico_norm)
        if m.group(0) not in FALSOS_VERBOS
    })


def evidencias(t_norm, servico_norm=None, data_str=None, problema_norm=""):
    ev = {}
    t_falha = RE_NEUTRALIZA_FALHA.sub(" ", t_norm)

    ev["troca"] = tem_troca(t_norm)
    ev["troca_forte"] = bool(RE_TROCA_FORTE.search(t_norm)) and not (
        RE_NEGACAO_TROCA.search(t_norm) and not ev["troca"]
    )
    ev["falha"] = bool(RE_FALHA.search(t_falha))
    ev["falha_real"] = bool(RE_FALHA_HARD.search(t_falha))
    ev["falha_hard"] = ev["falha_real"]
    ev["desgaste_natural"] = bool(RE_DESGASTE_NATURAL.search(t_norm))
    ev["parada_explicita"] = bool(RE_C3_EVIDENCIA.search(t_norm))
    ev["parada_producao"] = bool(RE_PARADA_PRODUCAO.search(t_norm))

    ev["sem_funcao"] = bool(RE_SEM_FUNCAO.search(t_norm))
    ev["consequencia"] = bool(RE_CONSEQUENCIA.search(t_norm))
    ev["pendente"] = bool(RE_PENDENTE.search(t_norm))
    ev["setup"] = bool(RE_SETUP.search(t_norm))
    ev["pos_setup"] = bool(RE_POS_SETUP.search(t_norm))
    ev["falha_operacional"] = bool(RE_FALHA_OPERACIONAL.search(t_norm))
    ev["indicio_operacional_conferir"] = bool(RE_INDICIO_OPERACIONAL_CONFERIR.search(t_norm))
    ev["peca_desgaste"] = bool(RE_PECA_DESGASTE.search(t_norm))
    ev["componente_critico"] = bool(RE_COMPONENTE_CRITICO.search(t_norm))
    ev["melhoria"] = bool(RE_MELHORIA.search(t_norm))
    ev["so_observacao"] = bool(
        RE_SO_OBSERVACAO.search(t_norm)
        and not ev["troca"]
        and not re.search(
            r"\b(?:ajust\w*|regul\w*|alinh\w*|repar\w*|consert\w*|troc\w*|substitu\w*|"
            r"sold\w*|desmont\w*|mont\w*|rearm\w*|reset\w*|limp\w*|lubrific\w*|"
            r"calibr\w*|apert\w*|reapert\w*|fix\w*|reposicion\w*|repass\w*|destrav\w*|invert\w*)\b",
            servico_norm if servico_norm is not None else t_norm,
        )
    )
    ev["falha_destrutiva"] = bool(
        re.search(
            r"\b(?:queim\w*|quebr\w*|trinc\w*|rompe\w*|rompid\w*|rasg\w*|furad[oa]|furou|"
            r"derret\w*|estour\w*|arrebent\w*|fundi\w*|partiu|partid[oa]|curto|danific\w*|avari\w*)\b",
            t_falha,
        )
    )
    ev["planejado"] = bool(RE_PLANEJADO.search(t_norm))
    ev["parada_programada"] = bool(RE_PARADA_PROGRAMADA.search(t_norm))
    ev["preventiva_forte"] = bool(RE_PREVENTIVA_FORTE.search(t_norm))
    ev["plano_fraco"] = bool(RE_PLANO_FRACO.search(t_norm))
    ev["preventiva"] = ev["preventiva_forte"]
    ev["inspecao_rotas"] = bool(RE_INSPECAO_ROTAS.search(t_norm))
    ev["predial"] = bool(RE_PREDIAL.search(t_norm))
    ev["equipamento_processo"] = bool(RE_EQUIPAMENTO_PROCESSO.search(t_norm))
    ev["ferramental"] = bool(RE_FERRAMENTAL.search(t_norm))
    ev["so_reset"] = servico_so_reset(t_norm)
    ev["lampada_lote"] = lampada_em_lote(t_norm)
    ev["so_lampada"] = bool(re.search(r"\blampad|\blamp\b", t_norm))
    ev["objeto_estranho"] = bool(RE_OBJETO_ESTRANHO.search(t_norm))
    ev["retirada"] = bool(RE_RETIRADA.search(t_norm))
    ev["troca_pedra"] = bool(ev["troca"] and RE_PEDRA.search(t_norm))

    if problema_norm:
        ev["predial_problema"] = bool(RE_PREDIAL_NUCLEO.search(problema_norm))
        ev["sintoma_problema"] = bool(RE_SINTOMA_PROBLEMA.search(problema_norm))
    else:
        ev["predial_problema"] = ev["predial"]
        ev["sintoma_problema"] = False

    obj = objeto_da_troca(t_norm)
    ev["objeto_troca"] = obj
    ev["desgaste_trocado"] = (
        bool(RE_PECA_DESGASTE.search(obj)) if obj else ev["peca_desgaste"]
    )
    ev["verbos"] = sorted({
        m.group(0) for m in RE_VERBOS.finditer(t_norm)
        if m.group(0) not in FALSOS_VERBOS
    })

    serv = servico_norm if servico_norm is not None else t_norm
    ev["desmontagem"] = bool(RE_DESMONTAGEM.search(t_norm))
    ev["instalacao"] = bool(RE_INSTALACAO.search(t_norm))
    ev["reserva"] = bool(RE_RESERVA.search(t_norm))
    ev["revisao"] = bool(RE_REVISAO.search(t_norm))
    ev["para_manutencao"] = bool(RE_PARA_MANUTENCAO.search(t_norm))
    ev["n_acoes"] = contar_acoes(serv)
    ev["escopo_amplo"] = bool(
        ev["n_acoes"] >= ESCOPO_VERBOS_MIN or len(serv) >= ESCOPO_CARACTERES
    )
    ev["contexto_formato"] = bool(
        ev["setup"] or ev["pos_setup"]
        or re.search(
            r"\bformato\b|\bproduto\b|\bsabor\b|\breceita\b|"
            r"\brotulo\b|\bembalagem\b|\b\d+\s*(?:gr|g|ml)\b",
            t_norm,
        )
    )

    dia, dia_abrev, eh_sabado, eh_domingo = dia_semana_info(data_str)
    ev["dia_semana"] = dia
    ev["dia_abrev"] = dia_abrev
    ev["eh_sabado"] = eh_sabado
    ev["eh_domingo"] = eh_domingo

    falha_para_quebra = ev["falha_real"]
    ev["falha_para_quebra"] = falha_para_quebra
    ev["base_quebra"] = bool(
        falha_para_quebra or ev["sem_funcao"] or ev["troca_forte"] or ev["consequencia"]
    )
    ev["setup_obrigatorio"] = bool(
        ev["setup"] and not ev["falha_destrutiva"] and not ev["troca_forte"]
    )
    ev["desgaste_para_programada"] = bool(
        ev["desgaste_trocado"]
        and ev["desgaste_natural"]
        and not ev["falha_destrutiva"]
        and not ev["parada_producao"]
        and not ev["troca_pedra"]
    )
    ev["programada_por_escopo"] = bool(
        (ev["desmontagem"] or ev["para_manutencao"] or ev["reserva"] or ev["revisao"] or ev["planejado"] or ev["parada_programada"])
        and not ev["parada_producao"]
    )
    ev["quebra_evidente"] = bool(
        (ev["falha_destrutiva"] and (ev["troca_forte"] or ev["sem_funcao"] or ev["parada_producao"]))
        or (ev["troca_forte"] and (ev["parada_producao"] or ev["sem_funcao"]))
        or ev["troca_pedra"]
    )
    ev["intervencao_ajuste"] = bool(
        ev["verbos"]
        or re.search(
            r"\b(?:ajust\w*|regul\w*|alinh\w*|limp\w*|apert\w*|reapert\w*|repar\w*|consert\w*|"
            r"calibr\w*|lubrific\w*|engrax\w*|posicion\w*|reposicion\w*|invers\w*|invert\w*|"
            r"destrav\w*|desobstru\w*|repass\w*|fix\w*|sold\w*|ved\w*|tension\w*|estic\w*)\b",
            serv,
        )
    )
    ev["ajuste_puro"] = bool(
        not ev["troca"]
        and not ev["falha_destrutiva"]
        and not ev["parada_producao"]
        and not ev["setup"]
        and not ev["pos_setup"]
        and not ev["preventiva"]
        and not ev["inspecao_rotas"]
        and not ev["predial_problema"]
        and not ev["falha_operacional"]
        and not ev["indicio_operacional_conferir"]
        and not ev["melhoria"]
        and not ev["parada_programada"]
        and not ev["revisao"]
        and not ev["so_observacao"]
        and not (ev["objeto_estranho"] and ev["retirada"])
        and ev["intervencao_ajuste"]
    )
    return ev


def predial_confirmado(ev):
    return bool(
        ev.get("predial")
        and not ev.get("equipamento_processo")
        and not ev.get("troca_forte")
        and ev.get("predial_problema")
    )


# ================= MATRIZ B×C (EN 13306) & SEVERIDADE =================
NIVEL_SEV = {1: "LEVE", 2: "MODERADA", 3: "GRAVE"}
ORDEM_SEV = {"LEVE": 1, "MODERADA": 2, "GRAVE": 3}

BASE_B_C = {
    (1, 1): 1, (1, 2): 1, (1, 3): 2,
    (2, 1): 1, (2, 2): 2, (2, 3): 3,
    (3, 1): 2, (3, 2): 3, (3, 3): 3,
}

TRAVA_LEVE = {(1, 1)}
TRAVA_GRAVE = {(3, 3)}

PESOS_QUEBRA = {
    "parada_producao": 2,
    "falha_destrutiva": 2,
    "troca": 1,
    "peca_desgaste": 1,
    "sem_funcao": 1,
    "consequencia": 1,
    "componente_critico": 0,
}

PENALIDADES_PROGRAMADA = {
    "desmontagem": 2,
    "para_manutencao": 2,
    "reserva": 2,
    "revisao": 2,
    "escopo_amplo": 2,
}


def score_quebra(ev, tempo=None):
    s = 0
    for chave, peso in PESOS_QUEBRA.items():
        if ev.get(chave):
            s += peso
    for chave, peso in PENALIDADES_PROGRAMADA.items():
        if ev.get(chave):
            s -= peso
    if ev.get("planejado") or ev.get("parada_programada"):
        s -= 3
    if ev.get("desgaste_natural") and not ev.get("falha_destrutiva"):
        s -= 2
    if ev.get("setup"):
        s -= 2
    if ev.get("ferramental") and not ev.get("falha_destrutiva"):
        s -= 2
    if tempo is not None and tempo > TEMPO_LONGO:
        s -= 2
    if ev.get("eh_sabado"):
        s -= 1
    return s


def ajuste_tempo(tempo_min):
    if tempo_min is None:
        return 0
    if tempo_min <= TEMPO_CURTO:
        return -1
    if tempo_min > TEMPO_LONGO:
        return 1
    return 0


def calcular_severidade(b, c, tempo_min):
    base = BASE_B_C.get((b, c))
    if base is None:
        return None, f"B={b} C={c} fora da faixa 1-3", None
    if (b, c) in TRAVA_LEVE:
        return "LEVE", f"B={b} C={c} travado em LEVE", None
    if (b, c) in TRAVA_GRAVE:
        return "GRAVE", f"B={b} C={c} travado em GRAVE", None

    aj = ajuste_tempo(tempo_min)
    nivel = max(1, min(3, base + aj))
    sev = NIVEL_SEV[nivel]

    det = f"B={b} C={c} base={NIVEL_SEV[base]}"
    if aj:
        det += f" | {tempo_min}min {aj:+d}"
    elif tempo_min is None:
        det += " | sem tempo"
    det += f" -> {sev}"
    return sev, det, None


def aplicar_teto_desgaste(sev, ev):
    if not sev or sev not in ORDEM_SEV:
        return sev, None
    if ev.get("troca_pedra"):
        return sev, None
    if ev.get("so_lampada") and not ev.get("componente_critico"):
        if ORDEM_SEV[sev] > ORDEM_SEV[TETO_LAMPADA_MAX]:
            return TETO_LAMPADA_MAX, f"teto lampada {TETO_LAMPADA_MAX}"
    if ev.get("desgaste_trocado") and not ev.get("componente_critico"):
        if ORDEM_SEV[sev] > ORDEM_SEV[TETO_DESGASTE_MAX]:
            return TETO_DESGASTE_MAX, "teto desgaste"
    return sev, None


def b_c_por_evidencia(ev, criticidade_linha=""):
    if ev.get("troca_pedra"):
        t_trinca = bool(re.search(r"\b(?:trinc\w*|rach\w*|quebr\w*)\b", ev.get("_texto_norm", "")))
        return 3, (2 if t_trinca else 1)
    if ev.get("componente_critico"):
        b = 3 if (ev.get("sem_funcao") or ev.get("parada_explicita") or criticidade_linha == "A") else 2
    elif ev.get("peca_desgaste") or ev.get("desgaste_trocado"):
        b = 1
    else:
        b = 2

    if ev.get("sem_funcao") and ev.get("componente_critico") and ev.get("parada_explicita"):
        c = 3
    elif ev.get("parada_producao") or ev.get("consequencia") or ev.get("sem_funcao"):
        c = 2
    elif ev.get("troca_forte") or ev.get("falha_destrutiva"):
        c = 2
    else:
        c = 1
    return b, c


def validar(dados, ev, t_norm):
    if not dados:
        return ["resposta vazia ou JSON invalido"]
    probs = []
    cat = str(dados.get("categoria", "")).strip().upper()
    b = dados.get("b")
    c = dados.get("c")

    if ev["inspecao_rotas"] and cat != "INSPECAO DE ROTAS":
        probs.append("texto declara inspecao de rotas — obrigatorio INSPECAO DE ROTAS")
    if ev["preventiva_forte"] and cat != "PREVENTIVA":
        probs.append("texto declara preventiva — obrigatorio PREVENTIVA")
    if predial_confirmado(ev) and cat != "PREDIAL":
        probs.append("infraestrutura civil no problema — obrigatorio PREDIAL")
    if ev["pos_setup"] and cat == "AJUSTE":
        probs.append("ajuste apos setup deveria ser AJUSTE POS SETUP")
    if cat == "QUEBRA" and ev["so_reset"]:
        probs.append("rearme/reset sem troca e AJUSTE")
    if cat == "QUEBRA" and ev["lampada_lote"]:
        probs.append("lampada em lote e MANUTENCAO PROGRAMADA")
    if cat == "QUEBRA" and ev["ferramental"] and not ev.get("falha_destrutiva"):
        probs.append("ferramental trocado sem falha e SETUP PROGRAMADO")
    if cat == "QUEBRA" and ev["objeto_estranho"] and ev["retirada"] and not ev["troca"]:
        probs.append("retirar objeto estranho e ACOMPANHAMENTO")
    if ev["setup_obrigatorio"] and cat in ("AJUSTE", "ACOMPANHAMENTO"):
        probs.append(f"evidencia de setup — deveria ser SETUP PROGRAMADO, nao {cat}")
    if cat == "MELHORIAS" and not ev["melhoria"]:
        probs.append("MELHORIAS sem termo explicito de benfeitoria")
    if cat == "ACOMPANHAMENTO" and ev["verbos"] and not ev["pendente"] \
            and not ev["so_observacao"] and not (ev["objeto_estranho"] and ev["retirada"]):
        probs.append("ACOMPANHAMENTO com verbo de intervencao")
    if cat == "QUEBRA":
        if not ev["base_quebra"] and not ev.get("troca_pedra"):
            probs.append("QUEBRA sem evidencia de falha, troca ou perda")
        if not isinstance(b, int) or b not in (1, 2, 3):
            probs.append("QUEBRA sem B valido")
        if not isinstance(c, int) or c not in (1, 2, 3):
            probs.append("QUEBRA sem C valido")
    return probs


def fallback_deterministico(ev, tempo=None, criticidade_linha=""):
    if ev.get("inspecao_rotas"):
        return {"categoria": "INSPECAO DE ROTAS", "b": None, "c": None, "confianca": 5,
                "justificativa": "Rota/roteiro de inspecao declarado explicitamente no apontamento."}
    if ev.get("preventiva"):
        return {"categoria": "PREVENTIVA", "b": None, "c": None, "confianca": 5,
                "justificativa": "Tarefa de plano de manutencao preventiva declarada."}
    if predial_confirmado(ev):
        return {"categoria": "PREDIAL", "b": None, "c": None, "confianca": 5,
                "justificativa": "Intervencao em infraestrutura civil/predial sem ativo de processo."}
    if ev.get("troca_pedra"):
        b, c = b_c_por_evidencia(ev, criticidade_linha)
        return {"categoria": "QUEBRA", "b": b, "c": c, "confianca": 5,
                "justificativa": "Regra fixa da planta: troca de conjunto de pedra de moagem (Fryma) e QUEBRA."}
    if ev.get("pos_setup"):
        return {"categoria": "AJUSTE POS SETUP", "b": None, "c": None, "confianca": 5,
                "justificativa": "Ajuste fino realizado logo apos setup/mudanca de formato."}
    if ev.get("ferramental") and ev.get("contexto_formato") and not ev.get("falha_destrutiva"):
        return {"categoria": "SETUP PROGRAMADO", "b": None, "c": None, "confianca": 5,
                "justificativa": "Troca de ferramental com mudanca de formato/produto."}
    if ev.get("falha_operacional") and not ev.get("falha_destrutiva"):
        return {"categoria": "FALHA OPERACIONAL", "b": None, "c": None, "confianca": 5,
                "justificativa": "Evidencia tecnica de operacao/ajuste fora do padrao ou acao operacional indevida."}
    if ev.get("so_reset") and not ev.get("troca"):
        return {"categoria": "AJUSTE", "b": None, "c": None, "confianca": 5,
                "justificativa": "Rearme/reset de protecao ou inversor sem troca de componente."}
    if ev.get("lampada_lote"):
        return {"categoria": "MANUTENCAO PROGRAMADA", "b": None, "c": None, "confianca": 5,
                "justificativa": "Troca programada de lampadas em lote/armadilha luminosa."}
    if ev.get("parada_programada") and not ev.get("falha_destrutiva"):
        return {"categoria": "MANUTENCAO PROGRAMADA", "b": None, "c": None, "confianca": 5,
                "justificativa": "Atividade executada em janela/parada programada de manutencao."}
    if ev.get("desgaste_para_programada"):
        return {"categoria": "MANUTENCAO PROGRAMADA", "b": None, "c": None, "confianca": 5,
                "justificativa": "Substituicao planejada por desgaste natural/fim de vida util sem parada corretiva."}
    if ev.get("setup_obrigatorio"):
        return {"categoria": "SETUP PROGRAMADO", "b": None, "c": None, "confianca": 5,
                "justificativa": "Preparacao/setup de linha para troca de formato ou produto."}
    if ev.get("objeto_estranho") and ev.get("retirada") and not ev.get("troca"):
        return {"categoria": "ACOMPANHAMENTO", "b": None, "c": None, "confianca": 5,
                "justificativa": "Retirada de corpo/material estranho (pre-forma/tampa) e acompanhamento de partida."}
    if ev.get("indicio_operacional_conferir") and not ev.get("falha_destrutiva"):
        return {"categoria": "FALHA OPERACIONAL", "b": None, "c": None, "confianca": 4,
                "justificativa": "Indicio operacional (receita/comando/insumo) encaminhado para conferencia da supervisao."}
    if ev.get("melhoria") and (ev.get("planejado") or ev.get("parada_programada")):
        return {"categoria": "MANUTENCAO PROGRAMADA", "b": None, "c": None, "confianca": 5,
                "justificativa": "Adequacao/benfeitoria executada em janela planejada."}
    if ev.get("melhoria") and not ev.get("falha_destrutiva"):
        return {"categoria": "MELHORIAS", "b": None, "c": None, "confianca": 5,
                "justificativa": "Confeccao/instalacao de benfeitoria para facilitar operacao ou seguranca."}

    # Programada por escopo amplo/revisão/oficina/sábado sem parada brusca de produção
    if ev.get("programada_por_escopo") and (ev.get("troca") or ev.get("revisao") or ev.get("desmontagem") or ev.get("eh_sabado")):
        return {"categoria": "MANUTENCAO PROGRAMADA", "b": None, "c": None, "confianca": 5,
                "justificativa": "Intervencao programada de revisao/oficina/janela planejada sem parada corretiva."}

    # QUEBRA (EN 13306): exige falha destrutiva ou troca de componente com perda funcional/parada
    s = score_quebra(ev, tempo)
    if ev.get("quebra_evidente") or (ev.get("falha_destrutiva") and (ev.get("troca") or ev.get("sem_funcao") or s >= 2)) or (ev.get("troca_forte") and s >= 2):
        b, c = b_c_por_evidencia(ev, criticidade_linha)
        conf_q = 5 if (ev.get("quebra_evidente") or s >= 3) else 4
        return {"categoria": "QUEBRA", "b": b, "c": c, "confianca": conf_q,
                "justificativa": f"Perda funcional / falha de componente com intervencao corretiva (score={s})."}

    # Troca planejada sem falha destrutiva nem perda de função
    if ev.get("troca_forte") and (ev.get("eh_sabado") or (tempo is not None and tempo >= 90) or ev.get("planejado")):
        return {"categoria": "MANUTENCAO PROGRAMADA", "b": None, "c": None, "confianca": 4,
                "justificativa": "Substituicao de componente em janela estendida sem perda funcional repentina."}

    if ev.get("so_observacao"):
        return {"categoria": "ACOMPANHAMENTO", "b": None, "c": None, "confianca": 5,
                "justificativa": "Acompanhamento operacional e observacao tecnica sem intervencao corretiva."}

    if (ev.get("intervencao_ajuste") or ev.get("verbos")) and not ev.get("pendente"):
        conf_aj = 5 if not ev.get("troca_forte") else 4
        return {"categoria": "AJUSTE", "b": None, "c": None, "confianca": conf_aj,
                "justificativa": "Restauracao de parametro/alinhamento/regulagem/limpeza com funcao mantida."}

    return {"categoria": "ACOMPANHAMENTO", "b": None, "c": None, "confianca": 4,
            "justificativa": "Atendimento/verificacao sem intervencao corretiva ou troca."}


def decidir_fast_path(om, ev, biblioteca=None, cache_rodada=None):
    """
    Nó 2 — Decide a R$ 0,00 (0 tokens) todos os casos 100% determinísticos por política da planta,
    memória validada do Bibliotecário (Jaccard >= 0.65), assinatura idêntica na mesma rodada ou
    ajuste puro sem troca/falha destrutiva.
    """
    problema = om.get("problema") or ""
    servico = om.get("servico") or ""

    if servico_insuficiente(servico, problema):
        cat_prob = categoria_por_problema(problema, servico)
        if cat_prob:
            return {
                "categoria": cat_prob,
                "b": None,
                "c": None,
                "confianca": 4,
                "origem": "FAST_PATH_PROBLEMA",
                "justificativa": "Servico sucinto/vazio; categoria decidida com seguranca pela descricao do problema.",
            }
        return {
            "categoria": "REVISAR_MANUAL",
            "b": None,
            "c": None,
            "confianca": 1,
            "origem": "BLOQUEIO_APONTAMENTO",
            "justificativa": "Servico executado vazio/generico e problema sem sinal tecnico suficiente.",
        }

    # 1. Memória validada do Bibliotecário
    alvo_ass = assinatura_caso(problema, servico)
    if biblioteca and alvo_ass:
        melhor_s = 0.0
        melhor_c = None
        for item in biblioteca:
            if item.get("status") == "REVERTIDO":
                continue
            ass_bib = item.get("_assinatura") or assinatura_caso(item.get("problema", ""), item.get("servico", ""))
            s = jaccard(alvo_ass, ass_bib)
            if s > melhor_s:
                melhor_s = s
                melhor_c = item
        if melhor_c and melhor_s >= 0.65 and melhor_c.get("categoria_supervisor"):
            cat_sup = norm_categoria(melhor_c["categoria_supervisor"])
            b, c = (b_c_por_evidencia(ev, om.get("criticidade_linha", "")) if cat_sup == "QUEBRA" else (None, None))
            return {
                "categoria": cat_sup,
                "b": b,
                "c": c,
                "confianca": 5,
                "origem": "BIBLIOTECA_MEMORIA",
                "justificativa": f"Padrao validado pelo Bibliotecario (sim={melhor_s:.0%}, sinal={melhor_c.get('sinal', 'PADRAO')}).",
            }

    # 2. Deduplicação exata na mesma rodada
    chave_dedup = f"{normalizar(problema)}||{normalizar(servico)}"
    if cache_rodada is not None and chave_dedup in cache_rodada:
        prev = dict(cache_rodada[chave_dedup])
        prev["origem"] = "DEDUP_RODADA"
        return prev

    # 3. Políticas determinísticas invariantes da planta (R$ 0,00)
    if ev.get("inspecao_rotas"):
        return {"categoria": "INSPECAO DE ROTAS", "b": None, "c": None, "confianca": 5,
                "origem": "FAST_PATH_R0", "justificativa": "Politica PCM: inspecao/roteiro de rota declarado no texto."}
    if ev.get("preventiva_forte"):
        return {"categoria": "PREVENTIVA", "b": None, "c": None, "confianca": 5,
                "origem": "FAST_PATH_R0", "justificativa": "Politica PCM: execucao de plano preventivo declarado."}
    if predial_confirmado(ev) or ("predial" in normalizar(om.get("equipe") or "") and not ev.get("equipamento_processo")):
        return {"categoria": "PREDIAL", "b": None, "c": None, "confianca": 5,
                "origem": "FAST_PATH_R0", "justificativa": "Politica PCM: manutencao predial/infraestrutura civil."}
    if ev.get("troca_pedra"):
        b, c = b_c_por_evidencia(ev, om.get("criticidade_linha", ""))
        return {"categoria": "QUEBRA", "b": b, "c": c, "confianca": 5,
                "origem": "FAST_PATH_R0", "justificativa": "Regra fixa da planta: troca do conjunto de pedra do moinho Fryma e QUEBRA."}
    if ev.get("lampada_lote"):
        return {"categoria": "MANUTENCAO PROGRAMADA", "b": None, "c": None, "confianca": 5,
                "origem": "FAST_PATH_R0", "justificativa": "Regra fixa da planta: troca de lampadas em lote/armadilha luminosa."}
    if ev.get("so_reset") and not ev.get("troca"):
        return {"categoria": "AJUSTE", "b": None, "c": None, "confianca": 5,
                "origem": "FAST_PATH_R0", "justificativa": "Regra fixa da planta: rearme/reset sem troca de componente e AJUSTE."}
    if ev.get("pos_setup") and not ev.get("troca_forte"):
        return {"categoria": "AJUSTE POS SETUP", "b": None, "c": None, "confianca": 5,
                "origem": "FAST_PATH_R0", "justificativa": "Politica PCM: regulagem/ajuste fino realizado apos setup."}
    if ev.get("setup_obrigatorio"):
        return {"categoria": "SETUP PROGRAMADO", "b": None, "c": None, "confianca": 5,
                "origem": "FAST_PATH_R0", "justificativa": "Politica PCM: troca de formato/produto/setup sem falha."}
    if ev.get("objeto_estranho") and ev.get("retirada") and not ev.get("troca"):
        return {"categoria": "ACOMPANHAMENTO", "b": None, "c": None, "confianca": 5,
                "origem": "FAST_PATH_R0", "justificativa": "Politica PCM: retirada de corpo/pre-forma/tampa presa sem troca."}
    if ev.get("falha_operacional") and not ev.get("falha_destrutiva"):
        return {"categoria": "FALHA OPERACIONAL", "b": None, "c": None, "confianca": 5,
                "origem": "FAST_PATH_R0", "justificativa": "Equilibrio Tecnico PCM: falha ou desvio operacional claro sem quebra de componente."}
    if ev.get("ajuste_puro") and (om.get("tempo_min") or 0) <= 60:
        return {"categoria": "AJUSTE", "b": None, "c": None, "confianca": 5,
                "origem": "FAST_PATH_R0", "justificativa": "Fast-Path PCM: ajuste/regulagem/alinhamento de curta duracao sem troca nem falha destrutiva."}

    return None


def calcular_score_qualidade_apontamento(problema, servico):
    """
    Calcula nota de 0 a 100 da qualidade técnica do apontamento da OM pelo manutentor,
    para alimentar o Ranking de Qualidade de Preenchimento por Equipe.
    """
    p = (problema or "").strip()
    s = (servico or "").strip()
    pn = normalizar(p)
    sn = normalizar(s)

    if servico_insuficiente(s, p):
        return {"score": 15, "nivel": "CRITICO", "motivo": "Servico vazio ou generico ('feito servico' / 'verificado')"}

    pts = 40
    n_palavras = len(sn.split())
    if n_palavras >= 6:
        pts += 20
    elif n_palavras >= 3:
        pts += 10

    n_verbos = contar_acoes(sn)
    if n_verbos >= 2:
        pts += 20
    elif n_verbos == 1:
        pts += 12

    tem_comp = bool(RE_PECA_DESGASTE.search(sn) or RE_COMPONENTE_CRITICO.search(sn) or RE_EQUIPAMENTO_PROCESSO.search(sn))
    if tem_comp:
        pts += 20

    pts = min(100, max(10, pts))
    nivel = "EXCELENTE" if pts >= 80 else ("ADEQUADO" if pts >= 55 else "RASO")
    motivo = "Apontamento tecnico completo (acao + componente)" if pts >= 80 else (
        "Apontamento aceitavel, mas pode detalhar melhor a causa/componente" if pts >= 55 else
        "Apontamento curto/vago; orientar tecnico a detalhar acao e componente"
    )
    return {"score": pts, "nivel": nivel, "motivo": motivo}


def cruzar_ativo_arvore(ativo_erp, linhas_arvore=None):
    """
    Cruza a string 'Descrição (Ativo)' do ERP (ex.: 'BOATOPACK 1 - ENVASADORA',
    'MULTIPET 2 - SOPRADORA 2/5', 'SERAC 3 - POSICIONADOR POSIMEC') com os ativos
    reais de ob_linhas (GESTAO-ATIVOS.html), retornando Setor, Máquina, Equipamento
    e Criticidade da Linha (A/B/C) sem depender de Conjuntos.xlsx.
    """
    bruto = (ativo_erp or "").strip()
    partes = [p.strip() for p in bruto.split("-") if p.strip()]
    maq_guess = partes[0] if partes else bruto
    eq_guess = partes[1] if len(partes) > 1 else maq_guess
    norm_b = normalizar(bruto)

    if linhas_arvore:
        melhor = None
        melhor_pts = 0
        for node in linhas_arvore:
            area = str(node.get("area") or node.get("setor") or "").strip()
            maq = str(node.get("maquina") or "").strip()
            eq = str(node.get("equipamento") or "").strip()
            crit = str(node.get("criticidade_linha") or node.get("criticidade") or "").strip().upper()
            pts = 0
            if maq and normalizar(maq) in norm_b:
                pts += 3
            if eq and normalizar(eq) in norm_b:
                pts += 4
            if area and normalizar(area) in norm_b:
                pts += 1
            if pts > melhor_pts:
                melhor_pts = pts
                melhor = {
                    "setor": area or "Produção",
                    "maquina": maq or maq_guess,
                    "equipamento": eq or eq_guess,
                    "criticidade_linha": crit if crit in ("A", "B", "C") else "A",
                    "vinculado_ob_linhas": True,
                }
        if melhor and melhor_pts >= 3:
            return melhor

    # Heurística industrial Cepêra quando ob_linhas ainda não foi carregado no CLI offline
    crit_default = "A" if any(k in norm_b for k in ("boatopack", "serac", "multipet", "fryma", "systempack", "cozinha", "caldeira")) else "B"
    setor_default = (
        "Envase Sachet" if any(k in norm_b for k in ("boatopack", "systempack", "volpack", "solupack")) else
        "Envase Frascos" if any(k in norm_b for k in ("serac", "posimec", "multipet", "dmon", "dmom")) else
        "Cozinha & Moagem" if any(k in norm_b for k in ("cozinha", "fryma", "moinho", "moagem", "buller", "tanque")) else
        "Conservas & Latas" if any(k in norm_b for k in ("conserva", "lata", "cft", "tetra")) else
        "Utilidades & Predial"
    )
    return {
        "setor": setor_default,
        "maquina": maq_guess,
        "equipamento": eq_guess,
        "criticidade_linha": crit_default,
        "vinculado_ob_linhas": False,
    }
