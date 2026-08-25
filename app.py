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

# 1. Configuração da Página
st.set_page_config(page_title="Eli Sistemas - Gestão, Inspeção Técnica e Chamados", page_icon="⚡", layout="wide")

# --- DIRETÓRIOS E ARQUIVOS ---
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

# --- CARREGAMENTO E SALVAMENTO JSON ---
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

# --- GERENCIAMENTO DE AUTENTICAÇÃO ---
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

if not st.session_state["logged_in"]:
    tela_login()
    st.stop()

# --- FUNÇÕES DE PDF ---
def gerar_pdf_calendario(ano=None, mes=None, incluir_tudo=False):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=(A4[1], A4[0]), rightMargin=15, leftMargin=15, topMargin=15, bottomMargin=15)
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
        story.append(Paragraph("<b>RELATÓRIO COMPLETO DE TAREFAS E HISTÓRICO DA AGENDA</b>", style_titulo))
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
        t_cal.setStyle(TableStyle(estilo_tabela))
        story.append(t_cal)

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()

def gerar_pdf_preventiva():
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=20, leftMargin=20, topMargin=20, bottomMargin=20)
    story = []
    styles = getSampleStyleSheet()
    
    style_celula = ParagraphStyle('CelTabela', parent=styles['Normal'], fontSize=8, leading=9, textColor=colors.black)
    style_cabecalho_tabela = ParagraphStyle('CabTabela', parent=styles['Normal'], fontSize=8, leading=9, fontName='Helvetica-Bold', textColor=colors.whitesmoke, alignment=1)
    style_texto_empresa = ParagraphStyle('EmpresaText', parent=styles['Normal'], fontSize=8, leading=10, textColor=colors.black)
    style_sec_header = ParagraphStyle('SecHeader', parent=styles['Normal'], fontSize=9, leading=11, fontName='Helvetica-Bold', textColor=colors.black)

    img_logo = Image(LOGO_PATH, width=45, height=30) if os.path.exists(LOGO_PATH) else Paragraph("<b>LOGO</b>", style_celula)

    info_empresa_texto = f"""
    <b>{empresa_db.get('nome', '')}</b><br/>
    CNPJ: {empresa_db.get('cnpj', '')} | CREA: {empresa_db.get('crea', '')} | Tel: {empresa_db.get('telefone', '')}<br/>
    E-mail: {empresa_db.get('email', '')} | Endereço: {empresa_db.get('endereco', '')}<br/>
    <b>RELATÓRIO DE INSPEÇÃO PREVENTIVA & MANUTENÇÃO NORMADA</b>
    """
    
    tabela_cabecalho = Table([[Paragraph(info_empresa_texto, style_texto_empresa), img_logo]], colWidths=[495, 60])
    story.append(tabela_cabecalho)
    story.append(Spacer(1, 4))

    story.append(Paragraph("<b>1. DADOS DA EDIFICAÇÃO E IDENTIFICAÇÃO DA VISITA TÉCNICA</b>", style_sec_header))
    dados_edif = [
        [Paragraph(f"<b>CLIENTE:</b> {st.session_state.get('cliente', '')}", style_celula), Paragraph(f"<b>Data da Visita:</b> {st.session_state.get('data_visita', '')}", style_celula)],
        [Paragraph(f"<b>CNPJ:</b> {st.session_state.get('cnpj', '')}", style_celula), Paragraph(f"<b>Tipo de Visita:</b> {st.session_state.get('tipo_visita', '')}", style_celula)],
        [Paragraph(f"<b>Endereço:</b> {st.session_state.get('endereco', '')}", style_celula), Paragraph(f"<b>Responsável Técnico:</b> {st.session_state.get('resp_tecnico', '')}", style_celula)]
    ]
    t_edif = Table(dados_edif, colWidths=[330, 225])
    t_edif.setStyle(TableStyle([('BOX', (0,0), (-1,-1), 0.5, colors.grey), ('INNERGRID', (0,0), (-1,-1), 0.25, colors.lightgrey)]))
    story.append(t_edif)

    doc.build(story)
    buffer.seek(0)
    pdf_data = buffer.getvalue()

    nome_cliente_atual = st.session_state.get('cliente', '').strip()
    if nome_cliente_atual:
        registrar_historico_cliente(nome_cliente_atual, "Relatório de Vistoria Preventiva", {"status": "Gerado"})

    return pdf_data

def inicializar_defaults():
    defaults = {
        "cliente": "", "cnpj": "", "endereco": "", "cidade_uf": "Ribeirão Preto - SP",
        "sindico": "", "zelador": "", "contato": "", "email": "",
        "data_visita": datetime.now().strftime("%Y-%m-%d"), "tipo_visita": "Preventiva Trimestral",
        "resp_tecnico": empresa_db.get("resp_tecnico", "Eli Silva"), "acompanhante": "",
        "status_geral": "CONFORME / SISTEMA OPERACIONAL", "central_sdai": "",
        "tipo_central": "SISTEMA ENDEREÇÁVEL", "qtd_lacos": "", "det_fumaca": "",
        "acionadores": "", "avisadores": "", "pressurizacao": "Sim",
        "tensao_baterias": "24 Vcc", "parecer": "", "orientacoes": "", "fotos_carregadas": []
    }
    for k, v in defaults.items():
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

# --- BARRA LATERAL ---
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

    if st.session_state["perfil"] == "master":
        opcoes_menu = [
            "📋 Nova Vistoria / Laudo", 
            "📂 Rascunhos de Vistoria", 
            "📅 Agenda de Manutenções", 
            "📂 Clientes & Histórico", 
            "🏢 Dados da Empresa", 
            "👥 Gestão de Usuários",
            "🎫 Chamados Técnicos", 
            "💾 Backup & Restauração"
        ]
    else:
        opcoes_menu = ["🎫 Chamados Técnicos", "📂 Clientes & Histórico"]
        
    menu = st.radio("Navegação Principal", opcoes_menu)

# --- NAVEGAÇÃO DOS MÓDULOS (TODAS AS PÁGINAS ATIVAS) ---

if menu == "📋 Nova Vistoria / Laudo":
    st.header("📋 Emissão de Relatório / Vistoria Preventiva")
    if clientes_db:
        lista_cli = ["-- Selecionar Cliente Cadastrado --"] + list(clientes_db.keys())
        cli_sel = st.selectbox("Carregar Dados de Cliente Existente", lista_cli)
        if cli_sel != "-- Selecionar Cliente Cadastrado --":
            info_c = clientes_db[cli_sel]
            st.session_state["cliente"] = cli_sel
            st.session_state["cnpj"] = info_c.get("cnpj", "")
            st.session_state["endereco"] = info_c.get("endereco", "")

    st.subheader("1. Dados Gerais da Edificação")
    st.session_state["cliente"] = st.text_input("Cliente / Condomínio", value=st.session_state["cliente"])
    st.session_state["cnpj"] = st.text_input("CNPJ", value=st.session_state["cnpj"])
    st.session_state["endereco"] = st.text_input("Endereço", value=st.session_state["endereco"])

    if st.button("📄 Gerar e Salvar PDF do Relatório", type="primary"):
        pdf_bytes = gerar_pdf_preventiva()
        st.success("Relatório gerado!")
        st.download_button("💾 Baixar Relatório PDF", pdf_bytes, file_name=f"Vistoria_{st.session_state['cliente']}.pdf", mime="application/pdf")

elif menu == "🏢 Dados da Empresa":
    st.header("🏢 Configuração dos Dados da Empresa")
    st.write("Estes dados serão exibidos no cabeçalho dos relatórios e documentos gerados.")
    
    with st.form("form_dados_empresa"):
        nome_emp = st.text_input("Razão Social / Nome da Empresa", value=empresa_db.get("nome", ""))
        cnpj_emp = st.text_input("CNPJ", value=empresa_db.get("cnpj", ""))
        crea_emp = st.text_input("Registro CREA", value=empresa_db.get("crea", ""))
        tel_emp = st.text_input("Telefone de Contato", value=empresa_db.get("telefone", ""))
        email_emp = st.text_input("E-mail Oficial", value=empresa_db.get("email", ""))
        end_emp = st.text_input("Endereço Completo", value=empresa_db.get("endereco", ""))
        resp_emp = st.text_input("Responsável Técnico Padrão", value=empresa_db.get("resp_tecnico", ""))
        
        btn_salvar_empresa = st.form_submit_button("💾 Salvar Alterações", type="primary")
        if btn_salvar_empresa:
            empresa_db.update({
                "nome": nome_emp,
                "cnpj": cnpj_emp,
                "crea": crea_emp,
                "telefone": tel_emp,
                "email": email_emp,
                "endereco": end_emp,
                "resp_tecnico": resp_emp
            })
            salvar_json(EMPRESA_FILE, empresa_db)
            st.success("Dados da empresa atualizados com sucesso!")

elif menu == "📂 Clientes & Histórico":
    st.header("📂 Gestão de Clientes e Histórico de Visitas")
    
    tab_c1, tab_c2 = st.tabs(["➕ Cadastrar / Editar Cliente", "🔍 Consultar Clientes e Histórico"])
    
    with tab_c1:
        st.subheader("Novo Cliente")
        with st.form("form_novo_cliente"):
            nome_cli = st.text_input("Nome do Cliente / Condomínio")
            cnpj_cli = st.text_input("CNPJ")
            end_cli = st.text_input("Endereço")
            cid_cli = st.text_input("Cidade / UF", value="Ribeirão Preto - SP")
            sindico_cli = st.text_input("Síndico")
            zelador_cli = st.text_input("Zelador")
            tel_cli = st.text_input("Telefone")
            email_cli = st.text_input("E-mail")
            
            if st.form_submit_button("Salvar Cliente"):
                if nome_cli:
                    clientes_db[nome_cli] = {
                        "cnpj": cnpj_cli,
                        "endereco": end_cli,
                        "cidade_uf": cid_cli,
                        "sindico": sindico_cli,
                        "zelador": zelador_cli,
                        "telefone": tel_cli,
                        "email": email_cli
                    }
                    salvar_json(CLIENTES_FILE, clientes_db)
                    st.success(f"Cliente '{nome_cli}' cadastrado com sucesso!")
                    st.rerun()
                else:
                    st.error("Informe o nome do cliente.")
                    
    with tab_c2:
        st.subheader("Base de Clientes")
        if clientes_db:
            cli_selecionado = st.selectbox("Selecione um Cliente", list(clientes_db.keys()))
            if cli_selecionado:
                info = clientes_db[cli_selecionado]
                st.write(f"**CNPJ:** {info.get('cnpj', '')}")
                st.write(f"**Endereço:** {info.get('endereco', '')}")
                st.write(f"**Telefone:** {info.get('telefone', '')}")
                
                # Histórico de Atendimentos
                nome_pasta_cliente = "".join(c for c in cli_selecionado.strip() if c.isalnum() or c in (' ', '_', '-')).strip()
                cliente_dir = os.path.join(HISTORICO_CLIENTES_DIR, nome_pasta_cliente)
                historico_path = os.path.join(cliente_dir, "historico_atendimentos.json")
                
                st.subheader("📜 Histórico de Atendimentos & Documentos")
                if os.path.exists(historico_path):
                    with open(historico_path, "r", encoding="utf-8") as f_h:
                        hist_data = json.load(f_h)
                    st.dataframe(pd.DataFrame(hist_data), use_container_width=True)
                else:
                    st.info("Nenhum histórico gravado para este cliente até o momento.")
        else:
            st.info("Nenhum cliente cadastrado no sistema.")

elif menu == "📂 Rascunhos de Vistoria":
    st.header("📂 Rascunhos Salvamente Temporário")
    conn = sqlite3.connect(DB_FILE)
    df_rascunhos = pd.read_sql_query("SELECT id, cliente, data_visita, atualizado_em FROM rascunhos ORDER BY id DESC", conn)
    conn.close()
    
    if not df_rascunhos.empty:
        st.dataframe(df_rascunhos, use_container_width=True)
    else:
        st.info("Nenhum rascunho pendente.")

elif menu == "👥 Gestão de Usuários":
    st.header("👥 Gestão de Usuários do Sistema")
    
    with st.form("form_usuarios"):
        novo_u = st.text_input("Usuário")
        nova_s = st.text_input("Senha", type="password")
        novo_p = st.selectbox("Perfil de Acesso", ["master", "cliente"])
        cli_vinc = st.selectbox("Vincular a Cliente (Se perfil Cliente)", [""] + list(clientes_db.keys()))
        
        if st.form_submit_button("Cadastrar Usuário"):
            if novo_u and nova_s:
                usuarios[novo_u] = {"senha": nova_s, "perfil": novo_p, "cliente_vinculado": cli_vinc}
                salvar_json(USUARIOS_FILE, usuarios)
                st.success(f"Usuário '{novo_u}' salvo!")
                st.rerun()

elif menu == "🎫 Chamados Técnicos":
    st.header("🎫 Chamados Técnicos")
    
    with st.form("form_chamado"):
        titulo_ch = st.text_input("Título do Chamado")
        desc_ch = st.text_area("Descrição do Problema / Solicitação")
        if st.form_submit_button("Abrir Chamado"):
            chamados_db.append({
                "usuario": st.session_state["user"],
                "cliente": st.session_state.get("cliente_vinculado", "Geral"),
                "titulo": titulo_ch,
                "descricao": desc_ch,
                "data": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "status": "Aberto"
            })
            salvar_json(CHAMADOS_FILE, chamados_db)
            st.success("Chamado registrado!")
            st.rerun()

    st.subheader("Chamados Registrados")
    st.dataframe(pd.DataFrame(chamados_db), use_container_width=True)

elif menu == "📅 Agenda de Manutenções":
    st.header("📅 Agenda de Manutenções")
    conn = sqlite3.connect(DB_FILE)
    df_agenda = pd.read_sql_query("SELECT id, task AS Tarefa, category AS Categoria, due_date AS Data, status AS Status FROM agenda ORDER BY due_date ASC", conn)
    conn.close()
    st.dataframe(df_agenda, use_container_width=True)

elif menu == "💾 Backup & Restauração":
    st.header("💾 Central de Backup")
    if st.button("📦 Executar Backup Agora"):
        b_path = perform_backup()
        if b_path:
            st.success(f"Backup realizado: `{b_path}`")
