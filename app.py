import os
import io
import json
import sqlite3
import shutil
import calendar
from datetime import datetime
import streamlit as st
import pandas as pd
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

# 1. Configuração de página (Deve ser a primeira linha executada pelo Streamlit)
st.set_page_config(page_title="Eli Sistemas - Gestão, Inspeção Técnica e Chamados", page_icon="⚡", layout="wide")

# --- CONFIGURAÇÃO DE DIRETÓRIOS E BANCO DE DADOS ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__)) if "__file__" in locals() else "."
DB_FILE = os.path.join(BASE_DIR, "eli_sistemas.db")
CLIENTES_FILE = os.path.join(BASE_DIR, "clientes.json")
EMPRESA_FILE = os.path.join(BASE_DIR, "empresa.json")
CHAMADOS_FILE = os.path.join(BASE_DIR, "chamados.json")
USUARIOS_FILE = os.path.join(BASE_DIR, "usuarios.json")
LOGO_PATH = os.path.join(BASE_DIR, "logo_empresa.png")
PASTA_FOTOS_VISTORIA = os.path.join(BASE_DIR, "fotos_vistoria")
HISTORICO_CLIENTES_DIR = os.path.join(BASE_DIR, "historico_clientes")
BACKUP_DIR = os.path.join(BASE_DIR, "backups")

os.makedirs(PASTA_FOTOS_VISTORIA, exist_ok=True)
os.makedirs(HISTORICO_CLIENTES_DIR, exist_ok=True)
os.makedirs(BACKUP_DIR, exist_ok=True)

# --- INICIALIZAÇÃO DO BANCO SQLITE ---
def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            client TEXT,
            date TEXT,
            content TEXT,
            type TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS agenda (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task TEXT,
            category TEXT, 
            due_date TEXT,
            status TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS rascunhos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente TEXT,
            data_visita TEXT,
            dados_json TEXT,
            atualizado_em TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

def perform_backup():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(BACKUP_DIR, f"backup_{timestamp}.db")
    if os.path.exists(DB_FILE):
        shutil.copyfile(DB_FILE, backup_path)
        return backup_path
    return None

def restaurar_backup(uploaded_file):
    if uploaded_file is not None:
        perform_backup()
        with open(DB_FILE, "wb") as f:
            f.write(uploaded_file.getbuffer())
        return True
    return False

# --- CARREGAMENTO E MANIPULAÇÃO DE DADOS JSON ---
@st.cache_data
def carregar_json_cached(path):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return None
    return None

def carregar_json(path, default):
    data = carregar_json_cached(path)
    return data if data is not None else default

def salvar_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    carregar_json_cached.clear()

def registrar_historico_cliente(nome_cliente, tipo_acao, detalhes_dict):
    if not nome_cliente:
        return
    nome_pasta_cliente = "".join(c for c in nome_cliente.strip() if c.isalnum() or c in (' ', '_', '-')).strip()
    if not nome_pasta_cliente:
        return
        
    cliente_dir = os.path.join(HISTORICO_CLIENTES_DIR, nome_pasta_cliente)
    os.makedirs(cliente_dir, exist_ok=True)
    
    historico_path = os.path.join(cliente_dir, "historico_atendimentos.json")
    historico_lista = []
    if os.path.exists(historico_path):
        try:
            with open(historico_path, "r", encoding="utf-8") as f_hist:
                historico_lista = json.load(f_hist)
        except:
            pass
            
    detalhes_dict["data"] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    detalhes_dict["tipo"] = tipo_acao
    historico_lista.append(detalhes_dict)
    
    with open(historico_path, "w", encoding="utf-8") as f_hist:
        json.dump(historico_lista, f_hist, ensure_ascii=False, indent=4)

clientes_db = carregar_json(CLIENTES_FILE, {})
if not isinstance(clientes_db, dict):
    clientes_db = {}

empresa_db = carregar_json(EMPRESA_FILE, {
    "nome": "ELI SISTEMAS PROTEÇÃO CONTRA INCÊNDIO",
    "cnpj": "68.440.457/0001-50",
    "crea": "5071689704",
    "telefone": "(16) 981046121",
    "email": "elisistemas@gmail.com.br",
    "endereco": "Rua Floriano Peixoto, 122 - Sala 02 - Centro",
    "resp_tecnico": "Eli Silva"
})

chamados_db = carregar_json(CHAMADOS_FILE, [])
usuarios = carregar_json(USUARIOS_FILE, {
    "admin": {"senha": "123", "nome": "Eli Silva", "perfil": "master", "cliente_vinculado": ""}
})

ITENS_SECOES = {
    "sec3": [
        ("3.1 Alimentação Principal (AC)", "Rede elétrica estável 220V ± 10% (NBR 5410)"),
        ("3.2 Estado Físico das Baterias", "Ausência de vazamento, estufamento e oxidação"),
        ("3.3 Tensão / Carga das Baterias", "Regime de flutuação adequado (25.2V - 27.6V)"),
        ("3.4 Ensaio de Autonomia (DC)", "Simulação de corte de energia (operação em Vcc)"),
        ("3.5 Proteção Elétrica / Quadro AC", "Circuito exclusivo, disjuntor id. e DPS (NBR 5410)"),
        ("3.6 Painel Indicador / Display / Buzzer", "Sinalização visual e audível na central de alarme")
    ],
    "sec4": [
        ("4.1 Tensão de Operação do Laço", "Estabilidade de comunicação Vcc nos dispositivos"),
        ("4.2 Pesquisa de Fuga de Terra (Shield)", "Aterramento da blindagem e ausência de fuga a terra"),
        ("4.3 Supervisionamento de Ruptura de Linha", "Simulação de circuito aberto em laço/zona"),
        ("4.4 Atuação de Relés e Interconexão", "Comando de relés auxiliares / retenção")
    ],
    "sec5": [
        ("5.1 Detectores de Fumaça / Térmicos", "Mínimo 25% por trimestre (100% ao ano - ensaio com aerossol/calor)"),
        ("5.2 Acionadores Manuais (Botoeiras)", "Acesso desimpedido, rearme e atuação mecânica"),
        ("5.3 Avisadores Sonoros e Visuais", "Nível de pressões sonoras adequadas (> 65 dB) e flash visível"),
        ("5.4 Módulos de Entrada e Saída", "Endereçamento correto e supervisão de atuadores")
    ],
    "sec6": [
        ("6.1 Pressurização de Escadas (IT 13)", "Acionamento por fluxo/pressostato ou central SDAI"),
        ("6.2 Portas Corta-Fogo / Eletroímãs", "Liberação automática dos eletroímãs em caso de alarme geral")
    ]
}

# --- GERENCIAMENTO DE AUTENTICAÇÃO E SESSÃO (CORRIGIDO) ---
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False
if "user" not in st.session_state:
    st.session_state["user"] = ""
if "perfil" not in st.session_state:
    st.session_state["perfil"] = ""
if "cliente_vinculado" not in st.session_state:
    st.session_state["cliente_vinculado"] = ""

def verificar_credenciais(u_input, s_input):
    if u_input in usuarios and usuarios[u_input]["senha"] == s_input:
        st.session_state["logged_in"] = True
        st.session_state["user"] = u_input
        st.session_state["perfil"] = usuarios[u_input].get("perfil", "cliente")
        st.session_state["cliente_vinculado"] = usuarios[u_input].get("cliente_vinculado", "")
        return True
    return False

def tela_login():
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.title("⚡ Eli Sistemas - Gestão & Inspeção")
        st.subheader("Acesso ao Sistema")
        
        with st.form("form_login_principal"):
            u_input = st.text_input("Usuário")
            s_input = st.text_input("Senha", type="password")
            btn_login = st.form_submit_button("Entrar", type="primary")
            
            if btn_login:
                if verificar_credenciais(u_input, s_input):
                    st.success("Login efetuado com sucesso!")
                    st.rerun()
                else:
                    st.error("Usuário ou senha incorretos.")

# BLOQUEIO DE TELA SE NÃO ESTIVER AUTENTICADO
if not st.session_state["logged_in"]:
    tela_login()
    st.stop()

# --- FUNÇÃO PARA GERAR PDF EM FORMATO DE CALENDÁRIO ---
def gerar_pdf_calendario(ano=None, mes=None, incluir_tudo=False):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, 
        pagesize=(A4[1], A4[0]), 
        rightMargin=15, 
        leftMargin=15, 
        topMargin=15, 
        bottomMargin=15
    )
    story = []
    styles = getSampleStyleSheet()

    style_titulo = ParagraphStyle('CalTitulo', parent=styles['Heading1'], fontSize=14, leading=16, fontName='Helvetica-Bold', alignment=1)
    style_dia_num = ParagraphStyle('DiaNum', parent=styles['Normal'], fontSize=9, leading=10, fontName='Helvetica-Bold', textColor=colors.HexColor("#2C3E50"))
    style_tarefa = ParagraphStyle('TarefaCal', parent=styles['Normal'], fontSize=6.5, leading=7.5, textColor=colors.HexColor("#16A085"))
    style_cab_dia = ParagraphStyle('CabDia', parent=styles['Normal'], fontSize=9, leading=10, fontName='Helvetica-Bold', alignment=1, textColor=colors.whitesmoke)

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT task, due_date, status FROM agenda ORDER BY due_date ASC")
    rows = cursor.fetchall()
    conn.close()

    tarefas_por_dia = {}
    for task, due_date, status in rows:
        try:
            dt = datetime.strptime(due_date, "%Y-%m-%d")
            if incluir_tudo or (dt.year == ano and dt.month == mes):
                d = dt.day if not incluir_tudo else f"{dt.day}/{dt.month}/{dt.year}"
                if d not in tarefas_por_dia:
                    tarefas_por_dia[d] = []
                tarefas_por_dia[d].append((task, status, due_date))
        except:
            pass

    meses_pt = ["", "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
    
    if incluir_tudo:
        story.append(Paragraph(f"<b>RELATÓRIO COMPLETO DE TAREFAS E HISTÓRICO DA AGENDA</b>", style_titulo))
    else:
        story.append(Paragraph(f"<b>AGENDA DE MANUTENÇÕES & ATIVIDADES - {meses_pt[mes].upper()} / {ano}</b>", style_titulo))
        
    story.append(Paragraph(f"<font size=8>{empresa_db.get('nome', '')}</font>", ParagraphStyle('Sub', parent=styles['Normal'], alignment=1)))
    story.append(Spacer(1, 8))

    if not incluir_tudo and ano and mes:
        dias_semana = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]
        tabela_dados = [[Paragraph(f"<b>{d}</b>", style_cab_dia) for d in dias_semana]]

        cal = calendar.Calendar(firstweekday=0)
        mes_matriz = cal.monthdayscalendar(ano, mes)

        for semana in mes_matriz:
            linha_semana = []
            for dia in semana:
                if dia == 0:
                    linha_semana.append(Paragraph("", style_dia_num))
                else:
                    conteudo = [Paragraph(f"<b>{dia}</b>", style_dia_num)]
                    if dia in tarefas_por_dia:
                        for t_desc, t_stat, _ in tarefas_por_dia[dia]:
                            check = "✔ " if t_stat == "Realizado" else "• "
                            conteudo.append(Paragraph(f"{check}{t_desc}", style_tarefa))
                    linha_semana.append(conteudo)
            tabela_dados.append(linha_semana)

        largura_col = 114
        t_cal = Table(tabela_dados, colWidths=[largura_col]*7)
        
        estilo_tabela = [
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#2C3E50")),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#BDC3C7")),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ]
        
        for i in range(1, len(tabela_dados)):
            estilo_tabela.append(('ROWBACKGROUNDS', (0, i), (-1, i), [colors.whitesmoke if i % 2 == 0 else colors.HexColor("#FAFAFA")]))

        t_cal.setStyle(TableStyle(estilo_tabela))
        story.append(t_cal)
    else:
        dados_tabela = [[
            Paragraph("<b>Data Alvo</b>", style_cab_dia),
            Paragraph("<b>Descrição da Tarefa</b>", style_cab_dia),
            Paragraph("<b>Status</b>", style_cab_dia)
        ]]
        for task, due_date, status in rows:
            check = "✔ Realizado" if status == "Realizado" else "⏳ Não realizado"
            dados_tabela.append([
                Paragraph(due_date, style_dia_num),
                Paragraph(task, style_dia_num),
                Paragraph(check, style_tarefa)
            ])
        t_list = Table(dados_tabela, colWidths=[100, 550, 150])
        t_list.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#2C3E50")),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#BDC3C7")),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        story.append(t_list)

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()

# --- MÉRITO GERADOR DE PDFS DE VISTORIA (REPORTLAB COM REGISTRO FOTOGRÁFICO) ---
def gerar_pdf_preventiva():
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=20, leftMargin=20, topMargin=20, bottomMargin=20)
    story = []
    styles = getSampleStyleSheet()
    
    style_celula = ParagraphStyle('CelTabela', parent=styles['Normal'], fontSize=8, leading=9, textColor=colors.black)
    style_cabecalho_tabela = ParagraphStyle('CabTabela', parent=styles['Normal'], fontSize=8, leading=9, fontName='Helvetica-Bold', textColor=colors.whitesmoke, alignment=1)
    style_texto_empresa = ParagraphStyle('EmpresaText', parent=styles['Normal'], fontSize=8, leading=10, textColor=colors.black)
    style_sec_header = ParagraphStyle('SecHeader', parent=styles['Normal'], fontSize=9, leading=11, fontName='Helvetica-Bold', textColor=colors.black)

    logo_w, logo_h = 45, 30
    img_logo = Image(LOGO_PATH, width=logo_w, height=logo_h) if os.path.exists(LOGO_PATH) else Paragraph("<b>LOGO</b>", style_celula)

    info_empresa_texto = f"""
    <b>{empresa_db.get('nome', '')}</b><br/>
    CNPJ: {empresa_db.get('cnpj', '')} | CREA: {empresa_db.get('crea', '')} | Tel: {empresa_db.get('telefone', '')}<br/>
    E-mail: {empresa_db.get('email', '')} | Endereço: {empresa_db.get('endereco', '')}<br/>
    <b>RELATÓRIO DE INSPEÇÃO PREVENTIVA & MANUTENÇÃO NORMADA</b><br/>
    ABNT NBR 17240 | IT 19 | IT 13 CBMESP | ABNT NBR 5410
    """
    
    tabela_cabecalho = Table([[Paragraph(info_empresa_texto, style_texto_empresa), img_logo]], colWidths=[495, 60])
    tabela_cabecalho.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'), ('ALIGN', (1, 0), (1, 0), 'RIGHT'), ('BOTTOMPADDING', (0, 0), (-1, -1), 6)]))
    story.append(tabela_cabecalho)
    story.append(Spacer(1, 4))

    story.append(Paragraph("<b>1. DADOS DA EDIFICAÇÃO E IDENTIFICAÇÃO DA VISITA TÉCNICA</b>", style_sec_header))
    dados_edif = [
        [Paragraph(f"<b>CLIENTE:</b> {st.session_state.get('cliente', '')}", style_celula), Paragraph(f"<b>Data da Visita:</b> {st.session_state.get('data_visita', '')}", style_celula)],
        [Paragraph(f"<b>CNPJ:</b> {st.session_state.get('cnpj', '')}", style_celula), Paragraph(f"<b>Tipo de Visita:</b> {st.session_state.get('tipo_visita', '')}", style_celula)],
        [Paragraph(f"<b>Endereço:</b> {st.session_state.get('endereco', '')}", style_celula), Paragraph(f"<b>Responsável Técnico:</b> {st.session_state.get('resp_tecnico', '')}", style_celula)],
        [Paragraph(f"<b>Cidade / UF:</b> {st.session_state.get('cidade_uf', '')}", style_celula), Paragraph(f"<b>Acompanhante / Portaria:</b> {st.session_state.get('acompanhante', '')}", style_celula)],
        [Paragraph(f"<b>Síndico:</b> {st.session_state.get('sindico', '')} | <b>Zelador:</b> {st.session_state.get('zelador', '')}", style_celula), Paragraph(f"<b>Contato:</b> {st.session_state.get('contato', '')}", style_celula)],
        [Paragraph(f"<b>E-mail:</b> {st.session_state.get('email', '')}", style_celula), Paragraph(f"<b>Status Geral Parecer:</b> {st.session_state.get('status_geral', '')}", style_celula)]
    ]
    t_edif = Table(dados_edif, colWidths=[330, 225])
    t_edif.setStyle(TableStyle([('BOX', (0,0), (-1,-1), 0.5, colors.grey), ('INNERGRID', (0,0), (-1,-1), 0.25, colors.lightgrey), ('TOPPADDING', (0,0), (-1,-1), 2), ('BOTTOMPADDING', (0,0), (-1,-1), 2)]))
    story.append(t_edif)
    story.append(Spacer(1, 4))

    story.append(Paragraph("<b>2. CARACTERÍSTICAS TÉCNICAS DO SISTEMA CADASTRADO NO LOCAL</b>", style_sec_header))
    dados_tec = [
        [Paragraph(f"<b>Central SDAI:</b> {st.session_state.get('central_sdai', '')}", style_celula), Paragraph(f"<b>Tipo Central:</b> {st.session_state.get('tipo_central', '')}", style_celula), Paragraph(f"<b>Qtd. Laços / Zonas:</b> {st.session_state.get('qtd_lacos', '')}", style_celula)],
        [Paragraph(f"<b>Detectores Fumaça/Térmicos:</b> {st.session_state.get('det_fumaca', '')}", style_celula), Paragraph(f"<b>Acionadores Manuais:</b> {st.session_state.get('acionadores', '')}", style_celula), Paragraph(f"<b>Avisadores Sonoros/Visuais:</b> {st.session_state.get('avisadores', '')}", style_celula)],
        [Paragraph(f"<b>Pressurização Escada (IT 13):</b> {st.session_state.get('pressurizacao', '')}", style_celula), Paragraph(f"<b>Tensão & Baterias Nominais:</b> {st.session_state.get('tensao_baterias', '')}", style_celula), Paragraph("", style_celula)]
    ]
    t_tec = Table(dados_tec, colWidths=[185, 185, 185])
    t_tec.setStyle(TableStyle([('BOX', (0,0), (-1,-1), 0.5, colors.grey), ('INNERGRID', (0,0), (-1,-1), 0.25, colors.lightgrey), ('TOPPADDING', (0,0), (-1,-1), 2), ('BOTTOMPADDING', (0,0), (-1,-1), 2)]))
    story.append(t_tec)
    story.append(Spacer(1, 4))

    sec_titulos = {
        "sec3": "3. VERIFICAÇÃO FÍSICA E ELÉTRICA DA CENTRAL E FONTES",
        "sec4": "4. INTEGRIDADE DAS LINHAS DE SINAL (LAÇOS)",
        "sec5": "5. ENSAIOS FUNCIONAIS & AMOSTRAGEM DE PERIFÉRICOS",
        "sec6": "6. PRESSURIZAÇÃO DE ESCADAS DE SEGURANÇA & INTERLIGAÇÕES (IT 13)"
    }

    for sec_key, sec_title in sec_titulos.items():
        story.append(Paragraph(f"<b>{sec_title}</b>", style_sec_header))
        dados_tabela = [[
            Paragraph("<b>Item / Periférico</b>", style_cabecalho_tabela),
            Paragraph("<b>Parâmetro Normativo</b>", style_cabecalho_tabela),
            Paragraph("<b>Valor Medido</b>", style_cabecalho_tabela),
            Paragraph("<b>Status</b>", style_cabecalho_tabela),
            Paragraph("<b>Observações Técnicas</b>", style_cabecalho_tabela)
        ]]

        for idx, item in enumerate(ITENS_SECOES[sec_key]):
            val = st.session_state.get(f"{sec_key}_{idx}_val", "")
            stat = st.session_state.get(f"{sec_key}_{idx}_status", "CONFORME")
            obs = st.session_state.get(f"{sec_key}_{idx}_obs", "")
            
            dados_tabela.append([
                Paragraph(item[0], style_celula),
                Paragraph(item[1], style_celula),
                Paragraph(str(val), style_celula),
                Paragraph(str(stat), style_celula),
                Paragraph(str(obs), style_celula)
            ])

        tabela_itens = Table(dados_tabela, colWidths=[90, 185, 65, 75, 140], repeatRows=1)
        tabela_itens.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#333333")),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ]))
        story.append(tabela_itens)
        story.append(Spacer(1, 4))

    story.append(Paragraph("<b>7. CONCLUSÃO TÉCNICA E ORIENTAÇÕES OPERACIONAIS</b>", style_sec_header))
    parecer_texto = f"<b>Parecer Técnico / Conclusão:</b><br/>{st.session_state.get('parecer', 'Nenhuma observação registrada.')}"
    orientacoes_texto = f"<b>Orientações Operacionais:</b><br/>{st.session_state.get('orientacoes', 'Nenhuma orientação específica.')}"
    
    t_conclusao = Table([[Paragraph(parecer_texto, style_celula)], [Paragraph(orientacoes_texto, style_celula)]], colWidths=[555])
    t_conclusao.setStyle(TableStyle([('BOX', (0,0), (-1,-1), 0.5, colors.grey), ('INNERGRID', (0,0), (-1,-1), 0.25, colors.lightgrey), ('TOPPADDING', (0,0), (-1,-1), 4), ('BOTTOMPADDING', (0,0), (-1,-1), 4)]))
    story.append(t_conclusao)
    story.append(Spacer(1, 6))

    story.append(Paragraph("<b>8. VALIDAÇÃO E ASSINATURAS TÉCNICAS</b>", style_sec_header))
    assinaturas_data = [[
        Paragraph(f"<b>Responsável Técnico:</b> {st.session_state.get('resp_tecnico', '')}<br/>CREA: {empresa_db.get('crea', '')}<br/><br/><br/>________________________________________<br/>Assinatura do Técnico", style_celula),
        Paragraph(f"<b>Responsável / Síndico / Portaria:</b> {st.session_state.get('acompanhante', st.session_state.get('sindico', ''))}<br/><br/><br/><br/>________________________________________<br/>Assinatura do Cliente / Recebedor", style_celula)
    ]]
    t_ass = Table(assinaturas_data, colWidths=[277, 278])
    t_ass.setStyle(TableStyle([('BOX', (0,0), (-1,-1), 0.5, colors.grey), ('INNERGRID', (0,0), (-1,-1), 0.25, colors.lightgrey), ('TOPPADDING', (0,0), (-1,-1), 6), ('BOTTOMPADDING', (0,0), (-1,-1), 6)]))
    story.append(t_ass)

    fotos_relatorio = st.session_state.get("fotos_carregadas", [])
    fotos_validas = [f for f in fotos_relatorio if os.path.exists(f)]
    if fotos_validas:
        story.append(Spacer(1, 10))
        story.append(Paragraph("<b>9. REGISTRO FOTOGRÁFICO DA INSPEÇÃO</b>", style_sec_header))
        tabela_fotos_dados = []
        linha_atual = []
        for idx_foto, p_foto in enumerate(fotos_validas):
            try:
                img_obj = Image(p_foto, width=260, height=180)
                celula_foto = [img_obj, Paragraph(f"<small>Foto {idx_foto+1}: Registro de Vistoria</small>", style_celula)]
                linha_atual.append(celula_foto)
            except:
                pass
            if len(linha_atual) == 2:
                tabela_fotos_dados.append(linha_atual)
                linha_atual = []
        if linha_atual:
            if len(linha_atual) == 1:
                linha_atual.append("")
            tabela_fotos_dados.append(linha_atual)

        if tabela_fotos_dados:
            t_fotos = Table(tabela_fotos_dados, colWidths=[275, 275])
            t_fotos.setStyle(TableStyle([
                ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                ('BOTTOMPADDING', (0,0), (-1,-1), 8),
                ('TOPPADDING', (0,0), (-1,-1), 4)
            ]))
            story.append(t_fotos)

    doc.build(story)
    buffer.seek(0)
    pdf_data = buffer.getvalue()

    nome_cliente_atual = st.session_state.get('cliente', '').strip()
    if nome_cliente_atual:
        nome_pasta_cliente = "".join(c for c in nome_cliente_atual if c.isalnum() or c in (' ', '_', '-')).strip()
        cliente_dir = os.path.join(HISTORICO_CLIENTES_DIR, nome_pasta_cliente)
        os.makedirs(cliente_dir, exist_ok=True)
        
        data_hora_str = datetime.now().strftime('%Y%m%d_%H%M%S')
        nome_arq_pdf = f"Relatorio_Preventiva_{data_hora_str}.pdf"
        caminho_completo_pdf = os.path.join(cliente_dir, nome_arq_pdf)
        
        with open(caminho_completo_pdf, "wb") as f_pdf:
            f_pdf.write(pdf_data)
            
        registrar_historico_cliente(
            nome_cliente_atual, 
            "Relatório de Vistoria Preventiva", 
            {
                "arquivo_pdf": nome_arq_pdf,
                "status_geral": st.session_state.get('status_geral', ''),
                "resp_tecnico": st.session_state.get('resp_tecnico', '')
            }
        )

    return pdf_data

def inicializar_defaults():
    defaults_vistoria = {
        "cliente": "", "cnpj": "", "endereco": "", "cidade_uf": "Ribeirão Preto - SP",
        "sindico": "", "zelador": "", "contato": "", "email": "",
        "data_visita": datetime.now().strftime("%Y-%m-%d"), "tipo_visita": "Preventiva Trimestral",
        "resp_tecnico": empresa_db.get("resp_tecnico", "Eli Silva"), "acompanhante": "",
        "status_geral": "CONFORME / SISTEMA OPERACIONAL", "central_sdai": "",
        "tipo_central": "SISTEMA ENDEREÇÁVEL", "qtd_lacos": "", "det_fumaca": "",
        "acionadores": "", "avisadores": "", "pressurizacao": "Sim",
        "tensao_baterias": "24 Vcc", "parecer": "", "orientacoes": "", "fotos_carregadas": []
    }
    for k, v in defaults_vistoria.items():
        if k not in st.session_state:
            st.session_state[k] = v

    for sec_key in ITENS_SECOES:
        for idx, _ in enumerate(ITENS_SECOES[sec_key]):
            if f"{sec_key}_{idx}_val" not in st.session_state:
                st.session_state[f"{sec_key}_{idx}_val"] = ""
            if f"{sec_key}_{idx}_obs" not in st.session_state:
                st.session_state[f"{sec_key}_{idx}_obs"] = ""
            if f"{sec_key}_{idx}_status" not in st.session_state:
                st.session_state[f"{sec_key}_{idx}_status"] = "CONFORME"

inicializar_defaults()

# --- BARRA LATERAL E LOGOUT ---
with st.sidebar:
    st.title("⚡ Eli Sistemas")
    st.write(f"👤 Usuário: **{st.session_state['user']}** ({st.session_state['perfil'].upper()})")
    
    if st.button("🚪 Sair / Logout", type="primary"):
        st.session_state["logged_in"] = False
        st.session_state["user"] = ""
        st.session_state["perfil"] = ""
        st.session_state["cliente_vinculado"] = ""
        st.rerun()
        
    st.divider()

    # Menu Adaptativo por Perfil
    if st.session_state["perfil"] == "master":
        opcoes_menu = [
            "📋 Nova Vistoria / Laudo", 
            "📂 Rascunhos de Vistoria", 
            "📅 Agenda de Manutenções", 
            "📂 Clientes & Histórico", 
            "🎫 Chamados Técnicos", 
            "🏢 Dados da Empresa", 
            "👥 Gestão de Usuários",
            "💾 Backup & Restauração"
        ]
    else:
        opcoes_menu = ["🎫 Chamados Técnicos", "📂 Clientes & Histórico"]
        
    menu = st.radio("Navegação Principal", opcoes_menu)

# --- NAVEGAÇÃO PRINCIPAL DAS MÓDULOS ---
if menu == "📋 Nova Vistoria / Laudo":
    st.header("📋 Emissão de Relatório / Vistoria Preventiva")
    
    # Seleção de cliente cadastrado para autopreencher
    if clientes_db:
        lista_cli = ["-- Selecionar Cliente Cadastrado --"] + list(clientes_db.keys())
        cli_sel = st.selectbox("Carregar Dados de Cliente Existente", lista_cli)
        if cli_sel != "-- Selecionar Cliente Cadastrado --":
            info_c = clientes_db[cli_sel]
            st.session_state["cliente"] = cli_sel
            st.session_state["cnpj"] = info_c.get("cnpj", "")
            st.session_state["endereco"] = info_c.get("endereco", "")
            st.session_state["cidade_uf"] = info_c.get("cidade_uf", "Ribeirão Preto - SP")
            st.session_state["sindico"] = info_c.get("sindico", "")
            st.session_state["zelador"] = info_c.get("zelador", "")
            st.session_state["contato"] = info_c.get("telefone", "")
            st.session_state["email"] = info_c.get("email", "")

    st.subheader("1. Dados Gerais da Edificação")
    col1, col2 = st.columns(2)
    with col1:
        st.session_state["cliente"] = st.text_input("Cliente / Condomínio", value=st.session_state["cliente"])
        st.session_state["cnpj"] = st.text_input("CNPJ", value=st.session_state["cnpj"])
        st.session_state["endereco"] = st.text_input("Endereço", value=st.session_state["endereco"])
        st.session_state["cidade_uf"] = st.text_input("Cidade / UF", value=st.session_state["cidade_uf"])
        st.session_state["sindico"] = st.text_input("Síndico", value=st.session_state["sindico"])
    with col2:
        st.session_state["data_visita"] = st.text_input("Data da Visita", value=st.session_state["data_visita"])
        st.session_state["tipo_visita"] = st.text_input("Tipo de Visita", value=st.session_state["tipo_visita"])
        st.session_state["resp_tecnico"] = st.text_input("Responsável Técnico", value=st.session_state["resp_tecnico"])
        st.session_state["zelador"] = st.text_input("Zelador", value=st.session_state["zelador"])
        st.session_state["contato"] = st.text_input("Contato / Tel", value=st.session_state["contato"])

    st.subheader("2. Características Técnicas do Sistema")
    col_t1, col_t2, col_t3 = st.columns(3)
    with col_t1:
        st.session_state["central_sdai"] = st.text_input("Central SDAI (Marca/Modelo)", value=st.session_state["central_sdai"])
        st.session_state["det_fumaca"] = st.text_input("Detectores Fumaça/Térmicos", value=st.session_state["det_fumaca"])
    with col_t2:
        st.session_state["tipo_central"] = st.text_input("Tipo de Central", value=st.session_state["tipo_central"])
        st.session_state["acionadores"] = st.text_input("Acionadores Manuais", value=st.session_state["acionadores"])
    with col_t3:
        st.session_state["qtd_lacos"] = st.text_input("Qtd. Laços / Zonas", value=st.session_state["qtd_lacos"])
        st.session_state["avisadores"] = st.text_input("Avisadores Sonoros/Visuais", value=st.session_state["avisadores"])

    st.subheader("3. Checklist & Vistorias por Seção")
    for sec_key, sec_title in {
        "sec3": "3. Verificação Física e Elétrica da Central e Fontes",
        "sec4": "4. Integridade das Linhas de Sinal (Laços)",
        "sec5": "5. Ensaios Funcionais & Amostragem de Periféricos",
        "sec6": "6. Pressurização de Escadas de Segurança & Interligações (IT 13)"
    }.items():
        with st.expander(sec_title, expanded=True):
            for idx, item in enumerate(ITENS_SECOES[sec_key]):
                c_item, c_val, c_stat, c_obs = st.columns([3, 1, 1, 2])
                with c_item:
                    st.write(f"**{item[0]}**")
                    st.caption(item[1])
                with c_val:
                    st.session_state[f"{sec_key}_{idx}_val"] = st.text_input("Medição", value=st.session_state[f"{sec_key}_{idx}_val"], key=f"inp_v_{sec_key}_{idx}")
                with c_stat:
                    st.session_state[f"{sec_key}_{idx}_status"] = st.selectbox("Status", ["CONFORME", "NÃO CONFORME", "N/A"], index=["CONFORME", "NÃO CONFORME", "N/A"].index(st.session_state[f"{sec_key}_{idx}_status"]), key=f"inp_s_{sec_key}_{idx}")
                with c_obs:
                    st.session_state[f"{sec_key}_{idx}_obs"] = st.text_input("Observações", value=st.session_state[f"{sec_key}_{idx}_obs"], key=f"inp_o_{sec_key}_{idx}")

    st.subheader("4. Conclusão & Fotos")
    st.session_state["parecer"] = st.text_area("Parecer Técnico / Conclusão", value=st.session_state["parecer"])
    st.session_state["orientacoes"] = st.text_area("Orientações Operacionais", value=st.session_state["orientacoes"])

    uploaded_images = st.file_uploader("Anexar Fotos da Vistoria", type=["jpg", "jpeg", "png"], accept_multiple_files=True)
    if uploaded_images:
        paths = []
        for img in uploaded_images:
            p = os.path.join(PASTA_FOTOS_VISTORIA, img.name)
            with open(p, "wb") as f:
                f.write(img.getbuffer())
            paths.append(p)
        st.session_state["fotos_carregadas"] = paths
        st.success(f"{len(paths)} foto(s) anexada(s) com sucesso!")

    st.divider()
    col_pdf, col_rascunho = st.columns(2)
    with col_pdf:
        if st.button("📄 Gerar e Salvar PDF do Relatório", type="primary"):
            pdf_bytes = gerar_pdf_preventiva()
            st.success("Relatório PDF gerado e arquivado!")
            st.download_button("💾 Baixar Relatório PDF", pdf_bytes, file_name=f"Vistoria_{st.session_state['cliente']}.pdf", mime="application/pdf")

elif menu == "📅 Agenda de Manutenções":
    st.header("📅 Agenda & Controle de Manutenções")
    
    col_ag1, col_ag2 = st.columns([1, 2])
    with col_ag1:
        st.subheader("Nova Tarefa / Agendamento")
        with st.form("form_agenda"):
            nova_tarefa = st.text_input("Descrição da Tarefa")
            categoria = st.selectbox("Categoria", ["Preventiva", "Corretiva", "Vistoria", "Atendimento"])
            data_alvo = st.date_input("Data Alvo")
            status_t = st.selectbox("Status Inicial", ["Pendente", "Realizado"])
            
            if st.form_submit_button("Agendar"):
                conn = sqlite3.connect(DB_FILE)
                c = conn.cursor()
                c.execute("INSERT INTO agenda (task, category, due_date, status) VALUES (?, ?, ?, ?)", (nova_tarefa, categoria, str(data_alvo), status_t))
                conn.commit()
                conn.close()
                st.success("Agendamento gravado!")
                st.rerun()

    with col_ag2:
        st.subheader("Próximas Atividades")
        conn = sqlite3.connect(DB_FILE)
        df_agenda = pd.read_sql_query("SELECT id, task AS Tarefa, category AS Categoria, due_date AS Data, status AS Status FROM agenda ORDER BY due_date ASC", conn)
        conn.close()
        st.dataframe(df_agenda, use_container_width=True)
        
        if st.button("📄 Exportar PDF do Calendário"):
            hoje = datetime.now()
            pdf_cal = gerar_pdf_calendario(ano=hoje.year, mes=hoje.month)
            st.download_button("💾 Baixar PDF do Mês", pdf_cal, file_name=f"Agenda_{hoje.month}_{hoje.year}.pdf", mime="application/pdf")

elif menu == "💾 Backup & Restauração":
    st.header("💾 Central de Backup e Restauração de Dados")
    
    tab_b1, tab_b2 = st.tabs(["⬇️ Fazer Backup", "⬆️ Restaurar / Upload de Backup"])
    
    with tab_b1:
        st.subheader("Exportar Banco de Dados Atual")
        st.write("Baixe o arquivo de banco de dados (`.db`) para manter uma cópia de segurança de toda a sua agenda e relatórios.")
        if st.button("📦 Executar Backup Agora"):
            b_path = perform_backup()
            if b_path:
                st.success(f"Backup criado com sucesso em: `{b_path}`")
                with open(b_path, "rb") as f:
                    st.download_button("💾 Baixar Arquivo de Banco (.db)", f, file_name=os.path.basename(b_path))
                    
    with tab_b2:
        st.subheader("Importar e Restaurar Banco de Dados")
        st.warning("⚠️ Atenção: Fazer o upload de um arquivo de backup substituirá o banco de dados atual.")
        uploaded_db = st.file_uploader("Selecione o arquivo de banco de dados (.db)", type=["db"])
        
        if uploaded_db is not None:
            if st.button("🔄 Restaurar Dados deste Arquivo"):
                if restaurar_backup(uploaded_db):
                    st.success("✅ Banco de dados restaurado com sucesso!")
                    st.rerun()
