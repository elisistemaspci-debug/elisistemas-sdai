import os
import io
import json
import sqlite3
import shutil
import hashlib
import calendar
from datetime import datetime
import streamlit as st
import pandas as pd
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, KeepTogether
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
            title TEXT, client TEXT, date TEXT, content TEXT, type TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS agenda (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task TEXT, category TEXT, due_date TEXT, status TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS rascunhos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente TEXT, data_visita TEXT, dados_json TEXT, atualizado_em TEXT
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
        with open(backup_path, "rb") as f:
            return f.read(), f"backup_{timestamp}.db"
    return None, None

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

# --- FUNÇÃO GERADORA DE PDF COM TIPO DE VISITA E ASSINATURA AJUSTADOS ---
def gerar_pdf_preventiva():
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=20, leftMargin=20, topMargin=20, bottomMargin=20)
    story = []
    styles = getSampleStyleSheet()
    
    style_celula = ParagraphStyle('CelTabela', parent=styles['Normal'], fontSize=8, leading=9, textColor=colors.black)
    style_celula_bold = ParagraphStyle('CelTabelaBold', parent=styles['Normal'], fontSize=8, leading=9, fontName='Helvetica-Bold', textColor=colors.black)
    style_texto_empresa = ParagraphStyle('EmpresaText', parent=styles['Normal'], fontSize=8, leading=10, textColor=colors.black)
    style_sec_header = ParagraphStyle('SecHeader', parent=styles['Normal'], fontSize=9, leading=11, fontName='Helvetica-Bold', textColor=colors.navy)
    style_center = ParagraphStyle('CenterText', parent=styles['Normal'], fontSize=8, leading=10, alignment=1, textColor=colors.black)

    img_logo = Image(LOGO_PATH, width=50, height=35) if os.path.exists(LOGO_PATH) else Paragraph("<b>ELI SISTEMAS</b>", style_celula)

    info_empresa_texto = f"""
    <b>{empresa_db.get('nome', '')}</b><br/>
    CNPJ: {empresa_db.get('cnpj', '')} | CREA: {empresa_db.get('crea', '')} | Tel: {empresa_db.get('telefone', '')}<br/>
    E-mail: {empresa_db.get('email', '')} | Endereço: {empresa_db.get('endereco', '')}<br/>
    <b>RELATÓRIO DE INSPEÇÃO PREVENTIVA & MANUTENÇÃO NORMADA</b>
    """
    
    tabela_cabecalho = Table([[Paragraph(info_empresa_texto, style_texto_empresa), img_logo]], colWidths=[485, 70])
    story.append(tabela_cabecalho)
    story.append(Spacer(1, 6))

    # 1. Dados da Edificação
    story.append(Paragraph("<b>1. DADOS DA EDIFICAÇÃO E IDENTIFICAÇÃO DA VISITA TÉCNICA</b>", style_sec_header))
    dados_edif = [
        [Paragraph(f"<b>CLIENTE:</b> {st.session_state.get('cliente', '')}", style_celula), Paragraph(f"<b>Data da Visita:</b> {st.session_state.get('data_visita', '')}", style_celula)],
        [Paragraph(f"<b>CNPJ:</b> {st.session_state.get('cnpj', '')}", style_celula), Paragraph(f"<b>Tipo de Visita:</b> {st.session_state.get('tipo_visita', 'Preventiva Trimestral')}", style_celula)],
        [Paragraph(f"<b>Endereço:</b> {st.session_state.get('endereco', '')}", style_celula), Paragraph(f"<b>Responsável Técnico:</b> {st.session_state.get('resp_tecnico', '')}", style_celula)]
    ]
    t_edif = Table(dados_edif, colWidths=[330, 225])
    t_edif.setStyle(TableStyle([('BOX', (0,0), (-1,-1), 0.5, colors.grey), ('INNERGRID', (0,0), (-1,-1), 0.25, colors.lightgrey)]))
    story.append(t_edif)
    story.append(Spacer(1, 6))

    # 2. Caracterização Técnica
    story.append(Paragraph("<b>2. CARACTERIZAÇÃO TÉCNICA DO SISTEMA</b>", style_sec_header))
    dados_tec = [
        [Paragraph(f"<b>Central:</b> {st.session_state.get('central_sdai', '')}", style_celula), Paragraph(f"<b>Tipo:</b> {st.session_state.get('tipo_central', '')}", style_celula), Paragraph(f"<b>Qtd. Laços:</b> {st.session_state.get('qtd_lacos', '')}", style_celula)],
        [Paragraph(f"<b>Detectores:</b> {st.session_state.get('det_fumaca', '')}", style_celula), Paragraph(f"<b>Acionadores:</b> {st.session_state.get('acionadores', '')}", style_celula), Paragraph(f"<b>Avisadores:</b> {st.session_state.get('avisadores', '')}", style_celula)],
        [Paragraph(f"<b>Pressurização:</b> {st.session_state.get('pressurizacao', '')}", style_celula), Paragraph(f"<b>Tensão Baterias:</b> {st.session_state.get('tensao_baterias', '')}", style_celula), Paragraph(f"<b>Status Geral:</b> {st.session_state.get('status_geral', '')}", style_celula_bold)]
    ]
    t_tec = Table(dados_tec, colWidths=[185, 185, 185])
    t_tec.setStyle(TableStyle([('BOX', (0,0), (-1,-1), 0.5, colors.grey), ('INNERGRID', (0,0), (-1,-1), 0.25, colors.lightgrey)]))
    story.append(t_tec)
    story.append(Spacer(1, 8))

    # 3, 4, 5, 6 - Tabelas de Itens de Inspeção
    titulos_secoes = {
        "sec3": "3. INSPEÇÃO E TESTES FUNCIONAIS DA CENTRAL / FONTE AUXILIAR",
        "sec4": "4. INFRAESTRUTURA E LAÇOS DE COMUNICAÇÃO (SDAI)",
        "sec5": "5. DISPOSITIVOS DE CAMPO E TESTES AMOSTRAIS",
        "sec6": "6. AUTOMAÇÕES, SINAIS DE INTERTRAVAMENTO E SEGURANÇA"
    }

    for sec_key, titulo_sec in titulos_secoes.items():
        story.append(Paragraph(f"<b>{titulo_sec}</b>", style_sec_header))
        tabela_dados = [[Paragraph("<b>Item / Descrição Normativa</b>", style_celula_bold), Paragraph("<b>Status</b>", style_celula_bold), Paragraph("<b>Medição</b>", style_celula_bold), Paragraph("<b>Observação</b>", style_celula_bold)]]
        
        for idx, (item_nome, norma_ref) in enumerate(ITENS_SECOES[sec_key]):
            st_val = st.session_state.get(f"{sec_key}_{idx}_status", "CONFORME")
            med_val = st.session_state.get(f"{sec_key}_{idx}_val", "")
            obs_val = st.session_state.get(f"{sec_key}_{idx}_obs", "")
            
            p_item = Paragraph(f"<b>{item_nome}</b><br/><font size=6 color=grey>{norma_ref}</font>", style_celula)
            p_st = Paragraph(f"<b>{st_val}</b>", style_celula)
            p_med = Paragraph(med_val, style_celula)
            p_obs = Paragraph(obs_val, style_celula)
            
            tabela_dados.append([p_item, p_st, p_med, p_obs])
            
        t_sec = Table(tabela_dados, colWidths=[240, 75, 80, 160])
        t_sec.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.whitesmoke),
            ('BOX', (0,0), (-1,-1), 0.5, colors.grey),
            ('INNERGRID', (0,0), (-1,-1), 0.25, colors.lightgrey),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE')
        ]))
        story.append(t_sec)
        story.append(Spacer(1, 6))

    # 7. Registro Fotográfico com Legendas
    fotos_info = st.session_state.get("fotos_detalhes", [])
    if fotos_info:
        story.append(Paragraph("<b>7. REGISTRO FOTOGRÁFICO DA INSPEÇÃO</b>", style_sec_header))
        fotos_rows = []
        row_atual = []
        for f_item in fotos_info:
            caminho_foto = f_item.get("caminho", "")
            obs_foto = f_item.get("obs", "")
            if os.path.exists(caminho_foto):
                img = Image(caminho_foto, width=160, height=110)
                caption_p = Paragraph(f"<font size=7><b>{obs_foto}</b></font>", style_center)
                cell_box = Table([[img], [caption_p]], colWidths=[165])
                cell_box.setStyle(TableStyle([('ALIGN', (0,0), (-1,-1), 'CENTER')]))
                row_atual.append(cell_box)
                if len(row_atual) == 3:
                    fotos_rows.append(row_atual)
                    row_atual = []
        if row_atual:
            while len(row_atual) < 3:
                row_atual.append(Paragraph("", style_celula))
            fotos_rows.append(row_atual)
            
        if fotos_rows:
            t_fotos = Table(fotos_rows, colWidths=[185, 185, 185])
            t_fotos.setStyle(TableStyle([('ALIGN', (0,0), (-1,-1), 'CENTER'), ('VALIGN', (0,0), (-1,-1), 'TOP')]))
            story.append(t_fotos)
            story.append(Spacer(1, 6))

    # 8. Parecer Técnico e Orientações
    story.append(Paragraph("<b>8. PARECER TÉCNICO E RECOMENDAÇÕES CORRETIVAS</b>", style_sec_header))
    parecer_txt = st.session_state.get("parecer", "Sem observações adicionais.")
    orientacoes_txt = st.session_state.get("orientacoes", "Manter a periodicidade das inspeções preventivas conforme normas NBR 17240 / IT 19.")
    
    dados_obs = [
        [Paragraph(f"<b>Parecer Técnico Geral:</b><br/>{parecer_txt}", style_celula)],
        [Paragraph(f"<b>Recomendações e Ações Corretivas:</b><br/>{orientacoes_txt}", style_celula)]
    ]
    t_obs = Table(dados_obs, colWidths=[555])
    t_obs.setStyle(TableStyle([('BOX', (0,0), (-1,-1), 0.5, colors.grey), ('INNERGRID', (0,0), (-1,-1), 0.25, colors.lightgrey)]))
    story.append(t_obs)
    story.append(Spacer(1, 15))

    # 9. Bloco de Assinaturas (Técnico e Cliente - Razão Social + CNPJ)
    story.append(Paragraph("<b>9. VALIDAÇÃO E ASSINATURAS DAS PARTES</b>", style_sec_header))
    story.append(Spacer(1, 20))
    
    nome_tecnico = st.session_state.get('resp_tecnico', empresa_db.get("resp_tecnico", "Eli Silva"))
    crea_tecnico = empresa_db.get("crea", "")
    
    # Exibe a Razão Social do Cliente/Condomínio e o CNPJ no campo do cliente
    razao_social_cliente = st.session_state.get('cliente', '')
    cnpj_cliente = st.session_state.get('cnpj', '')

    assinaturas_data = [
        [
            Paragraph("__________________________________________<br/><b>RESPONSÁVEL TÉCNICO</b><br/>" + f"{nome_tecnico}<br/>CREA: {crea_tecnico}", style_center),
            Paragraph("__________________________________________<br/><b>REPRESENTANTE / CLIENTE</b><br/>" + f"{razao_social_cliente}<br/>CNPJ: {cnpj_cliente}", style_center)
        ]
    ]
    t_ass = Table(assinaturas_data, colWidths=[277, 277])
    t_ass.setStyle(TableStyle([('ALIGN', (0,0), (-1,-1), 'CENTER'), ('VALIGN', (0,0), (-1,-1), 'MIDDLE')]))
    
    story.append(KeepTogether(t_ass))

    doc.build(story)
    buffer.seek(0)
    pdf_data = buffer.getvalue()

    nome_cliente_atual = st.session_state.get('cliente', '').strip()
    if nome_cliente_atual:
        registrar_historico_cliente(nome_cliente_atual, f"Relatório de Vistoria ({st.session_state.get('tipo_visita', 'Preventiva Trimestral')})", {
            "status_geral": st.session_state.get('status_geral', 'CONFORME'),
            "resp_tecnico": st.session_state.get('resp_tecnico', empresa_db.get("resp_tecnico", "Eli Silva"))
        })

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
        "tensao_baterias": "24 Vcc", "parecer": "", "orientacoes": "", "fotos_detalhes": []
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
            "📅 Agenda de Atividades", 
            "📂 Clientes & Histórico", 
            "🏢 Dados da Empresa", 
            "👥 Gestão de Usuários",
            "🎫 Chamados Técnicos", 
            "💾 Backup & Restauração"
        ]
    else:
        opcoes_menu = ["🎫 Chamados Técnicos"]
        
    menu = st.radio("Navegação Principal", opcoes_menu)

# --- CORPO DAS PÁGINAS ---

if menu == "📋 Nova Vistoria / Laudo":
    st.header("📋 Emissão de Relatório / Vistoria Preventiva")
    
    if clientes_db:
        lista_cli = ["-- Selecionar Cliente Cadastrado --"] + sorted(list(clientes_db.keys()))
        cli_sel = st.selectbox("Carregar Dados de Cliente Existente", lista_cli)
        if cli_sel != "-- Selecionar Cliente Cadastrado --":
            info_c = clientes_db[cli_sel]
            st.session_state["cliente"] = cli_sel
            st.session_state["cnpj"] = info_c.get("cnpj", "")
            st.session_state["endereco"] = info_c.get("endereco", "")

    st.subheader("1. Dados Gerais da Edificação")
    col1, col2 = st.columns(2)
    with col1:
        st.session_state["cliente"] = st.text_input("Cliente / Condomínio", value=st.session_state["cliente"])
        st.session_state["cnpj"] = st.text_input("CNPJ", value=st.session_state["cnpj"])
        st.session_state["sindico"] = st.text_input("Síndico(a)", value=st.session_state["sindico"])
        st.session_state["contato"] = st.text_input("Contato / Telefone", value=st.session_state["contato"])
    with col2:
        st.session_state["endereco"] = st.text_input("Endereço", value=st.session_state["endereco"])
        st.session_state["data_visita"] = st.date_input("Data da Visita", datetime.strptime(st.session_state["data_visita"], "%Y-%m-%d") if isinstance(st.session_state["data_visita"], str) else datetime.now()).strftime("%Y-%m-%d")
        
        # Opções de Seleção do Tipo de Visita
        opcoes_visita = [
            "Preventiva Mensal", 
            "Preventiva Trimestral", 
            "Preventiva Semestral", 
            "Preventiva Anual", 
            "Corretiva / Chamado Técnico", 
            "Vistoria Inicial / Diagnóstico",
            "Outro"
        ]
        
        pos_index = 1
        if st.session_state["tipo_visita"] in opcoes_visita:
            pos_index = opcoes_visita.index(st.session_state["tipo_visita"])
        else:
            pos_index = 6
            
        tipo_sel = st.selectbox("Tipo de Visita Técnica", opcoes_visita, index=pos_index)
        
        if tipo_sel == "Outro":
            st.session_state["tipo_visita"] = st.text_input("Especifique o Tipo de Visita", value=st.session_state.get("tipo_visita_custom", ""))
            st.session_state["tipo_visita_custom"] = st.session_state["tipo_visita"]
        else:
            st.session_state["tipo_visita"] = tipo_sel
            
        st.session_state["zelador"] = st.text_input("Zelador / Resp. Local", value=st.session_state["zelador"])
        st.session_state["email"] = st.text_input("E-mail do Cliente", value=st.session_state["email"])

    st.subheader("2. Caracterização Técnica e Equipamentos Instalados")
    col2_1, col2_2, col2_3 = st.columns(3)
    with col2_1:
        st.session_state["central_sdai"] = st.text_input("Marca / Modelo da Central", value=st.session_state["central_sdai"])
        st.session_state["det_fumaca"] = st.text_input("Qtd. Detectores (Fumaça/Térmico)", value=st.session_state["det_fumaca"])
        st.session_state["tensao_baterias"] = st.text_input("Tensão Baterias (Vcc)", value=st.session_state["tensao_baterias"])
    with col2_2:
        st.session_state["tipo_central"] = st.selectbox("Tipo de Sistema", ["SISTEMA ENDEREÇÁVEL", "SISTEMA CONVENCIONAL"], index=0 if st.session_state["tipo_central"] == "SISTEMA ENDEREÇÁVEL" else 1)
        st.session_state["acionadores"] = st.text_input("Qtd. Acionadores Manuais", value=st.session_state["acionadores"])
        st.session_state["pressurizacao"] = st.selectbox("Possui Pressurização de Escada?", ["Sim", "Não", "Não Aplicável"], index=0)
    with col2_3:
        st.session_state["qtd_lacos"] = st.text_input("Quantidade de Laços / Zonas", value=st.session_state["qtd_lacos"])
        st.session_state["avisadores"] = st.text_input("Qtd. Avisadores Sonoros/Visuais", value=st.session_state["avisadores"])
        st.session_state["status_geral"] = st.selectbox("Status Geral da Vistoria", ["CONFORME / SISTEMA OPERACIONAL", "SISTEMA COM ANOMALIAS / NECESSITA REPAROS", "CRÍTICO / OPERAÇÃO PARCIAL"], index=0)

    # RENDERIZAÇÃO DAS SEÇÕES 3, 4, 5 e 6
    titulos_secoes = {
        "sec3": "3. Inspeção e Testes Funcionais da Central / Fonte Auxiliar",
        "sec4": "4. Infraestrutura e Laços de Comunicação (SDAI)",
        "sec5": "5. Dispositivos de Campo e Testes Amostrais",
        "sec6": "6. Automações, Sinais de Intertravamento e Segurança"
    }

    for sec_key, titulo_sec in titulos_secoes.items():
        st.subheader(titulo_sec)
        for idx, (item_nome, norma_ref) in enumerate(ITENS_SECOES[sec_key]):
            c_a, c_b, c_c, c_d = st.columns([2.5, 1.5, 1.5, 2.5])
            with c_a:
                st.caption(f"**{item_nome}**\n*{norma_ref}*")
            with c_b:
                st.session_state[f"{sec_key}_{idx}_status"] = st.selectbox(f"Status", ["CONFORME", "NÃO CONFORME", "NÃO APLICÁVEL"], key=f"st_{sec_key}_{idx}", label_visibility="collapsed")
            with c_c:
                st.session_state[f"{sec_key}_{idx}_val"] = st.text_input("Medição/Valor", value=st.session_state[f"{sec_key}_{idx}_val"], key=f"vl_{sec_key}_{idx}", placeholder="Ex: 27.2V", label_visibility="collapsed")
            with c_d:
                st.session_state[f"{sec_key}_{idx}_obs"] = st.text_input("Observação", value=st.session_state[f"{sec_key}_{idx}_obs"], key=f"ob_{sec_key}_{idx}", placeholder="Detalhes", label_visibility="collapsed")

    st.subheader("7. Registro Fotográfico da Inspeção")
    uploaded_files = st.file_uploader("Carregar Fotos da Vistoria", type=["jpg", "png", "jpeg"], accept_multiple_files=True)
    
    if uploaded_files:
        fotos_processadas = set()
        novas_fotos_list = []
        for idx_f, file in enumerate(uploaded_files):
            file_bytes = file.getvalue()
            file_hash = hashlib.md5(file_bytes).hexdigest()
            if file_hash not in fotos_processadas:
                fotos_processadas.add(file_hash)
                nome_foto = f"{file_hash}_{file.name}"
                caminho_foto = os.path.join(PASTA_FOTOS_VISTORIA, nome_foto)
                with open(caminho_foto, "wb") as f_img:
                    f_img.write(file_bytes)
                
                col_f1, col_f2 = st.columns([1, 3])
                with col_f1:
                    st.image(caminho_foto, width=120)
                with col_f2:
                    obs_f = st.text_input(f"Legenda/Descrição da Foto #{idx_f+1}", value=f"Foto {idx_f+1} - Inspeção", key=f"legenda_foto_{file_hash}")
                
                novas_fotos_list.append({"caminho": caminho_foto, "obs": obs_f})
                
        st.session_state["fotos_detalhes"] = novas_fotos_list

    st.subheader("8. Parecer Técnico e Recomendações")
    st.session_state["parecer"] = st.text_area("Parecer Técnico Geral", value=st.session_state["parecer"], height=100)
    st.session_state["orientacoes"] = st.text_area("Recomendações e Ações Corretivas", value=st.session_state["orientacoes"], height=100)

    st.subheader("9. Identificação para Assinaturas")
    col_a1, col_a2 = st.columns(2)
    with col_a1:
        st.session_state["resp_tecnico"] = st.text_input("Responsável Técnico (Nome)", value=st.session_state["resp_tecnico"])
    with col_a2:
        st.info("ℹ️ No PDF, a assinatura do cliente será gerada automaticamente com a Razão Social e o CNPJ informados no formulário.")

    st.divider()
    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        if st.button("💾 Salvar Rascunho Completo", type="secondary"):
            if st.session_state["cliente"]:
                estado_completo = {k: v for k, v in st.session_state.items() if k not in ["logged_in", "user", "perfil"]}
                conn = sqlite3.connect(DB_FILE)
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO rascunhos (cliente, data_visita, dados_json, atualizado_em) VALUES (?, ?, ?, ?)",
                    (st.session_state["cliente"], st.session_state["data_visita"], json.dumps(estado_completo), datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                )
                conn.commit()
                conn.close()
                st.success("Rascunho completo salvo com sucesso!")
            else:
                st.error("Informe o nome do cliente para salvar o rascunho.")

    with col_btn2:
        if st.button("📄 Gerar e Salvar PDF do Relatório", type="primary"):
            pdf_bytes = gerar_pdf_preventiva()
            st.success("Relatório gerado com fotos e campo de assinaturas!")
            st.download_button("💾 Baixar Relatório PDF Completo", pdf_bytes, file_name=f"Vistoria_{st.session_state['cliente']}.pdf", mime="application/pdf")

elif menu == "📂 Rascunhos de Vistoria":
    st.header("📂 Rascunhos de Vistoria")
    
    conn = sqlite3.connect(DB_FILE)
    df_rascunhos = pd.read_sql_query("SELECT id, cliente AS Cliente, data_visita AS 'Data Visita', atualizado_em AS 'Atualizado Em' FROM rascunhos ORDER BY id DESC", conn)
    conn.close()
    
    if not df_rascunhos.empty:
        st.dataframe(df_rascunhos, use_container_width=True)
        col_r1, col_r2, col_r3 = st.columns(3)
        with col_r1:
            id_rascunho = st.number_input("ID do Rascunho", min_value=1, step=1)
        with col_r2:
            if st.button("📥 Carregar / Restaurar Rascunho", type="primary"):
                conn = sqlite3.connect(DB_FILE)
                cursor = conn.cursor()
                cursor.execute("SELECT dados_json FROM rascunhos WHERE id = ?", (id_rascunho,))
                row = cursor.fetchone()
                conn.close()
                if row:
                    dados_recuperados = json.loads(row[0])
                    for key_r, val_r in dados_recuperados.items():
                        st.session_state[key_r] = val_r
                    st.success(f"Rascunho #{id_rascunho} carregado no formulário! Vá até a aba 'Nova Vistoria' para continuar.")
                else:
                    st.error("ID de rascunho não encontrado.")
        with col_r3:
            if st.button("🗑️ Excluir Rascunho"):
                conn = sqlite3.connect(DB_FILE)
                cursor = conn.cursor()
                cursor.execute("DELETE FROM rascunhos WHERE id = ?", (id_rascunho,))
                conn.commit()
                conn.close()
                st.success(f"Rascunho #{id_rascunho} excluído!")
                st.rerun()
    else:
        st.info("Nenhum rascunho pendente registrado.")

elif menu == "📅 Agenda de Atividades":
    st.header("📅 Agenda de Atividades & Manutenções")
    
    tab_a1, tab_a2 = st.tabs(["📆 Visualizar Calendário Mensal", "➕ Nova Atividade / Registro"])
    
    with tab_a2:
        with st.form("form_nova_agenda"):
            nova_tarefa = st.text_input("Descrição da Tarefa / Atividade / Cobrança")
            categoria = st.selectbox("Categoria", ["Atividade Técnica", "Manutenção Preventiva", "Cobrança / Pagamento", "Diária"])
            data_prev = st.date_input("Data Prevista", datetime.now())
            status_inicial = st.selectbox("Status", ["Não realizado", "Realizado", "Pendente"])
            
            if st.form_submit_button("➕ Adicionar à Agenda", type="primary"):
                if nova_tarefa:
                    conn = sqlite3.connect(DB_FILE)
                    cursor = conn.cursor()
                    cursor.execute("INSERT INTO agenda (task, category, due_date, status) VALUES (?, ?, ?, ?)",
                                   (nova_tarefa, categoria, data_prev.strftime("%Y-%m-%d"), status_inicial))
                    conn.commit()
                    conn.close()
                    st.success("Item adicionado à agenda!")
                    st.rerun()

    with tab_a1:
        conn = sqlite3.connect(DB_FILE)
        df_agenda = pd.read_sql_query("SELECT id AS ID, task AS Tarefa, category AS Categoria, due_date AS 'Data Prevista', status AS Status FROM agenda ORDER BY due_date ASC", conn)
        conn.close()

        col_m1, col_m2, col_m3 = st.columns([2, 2, 3])
        with col_m1:
            mes_sel = st.selectbox("Mês", list(range(1, 13)), index=datetime.now().month - 1)
        with col_m2:
            ano_sel = st.number_input("Ano", min_value=2024, max_value=2030, value=datetime.now().year)
            
        cal = calendar.monthcalendar(ano_sel, mes_sel)
        dias_semana = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
        
        st.markdown(f"### 🗓️ {calendar.month_name[mes_sel].capitalize()} de {ano_sel}")
        
        cols_header = st.columns(7)
        for idx, dia_nome in enumerate(dias_semana):
            cols_header[idx].markdown(f"**{dia_nome}**")

        st.divider()

        for semana in cal:
            cols_dia = st.columns(7)
            for idx_dia, dia_num in enumerate(semana):
                with cols_dia[idx_dia]:
                    if dia_num != 0:
                        data_str = f"{ano_sel}-{mes_sel:02d}-{dia_num:02d}"
                        e_hoje = (data_str == datetime.now().strftime("%Y-%m-%d"))
                        label_dia = f"**{dia_num}** 📍" if e_hoje else f"**{dia_num}**"
                        st.markdown(label_dia)

                        if not df_agenda.empty:
                            tarefas_dia = df_agenda[df_agenda["Data Prevista"] == data_str]
                            for _, item in tarefas_dia.iterrows():
                                cor_status = "🟢" if item["Status"] == "Realizado" else ("🔴" if item["Status"] == "Não realizado" else "🟡")
                                st.caption(f"{cor_status} #{item['ID']} - {item['Tarefa']}")
                        st.markdown("---")
                    else:
                        st.write("")

        with st.expander("📋 Ver Lista Completa de Tarefas e Gerenciar Status"):
            if not df_agenda.empty:
                st.dataframe(df_agenda, use_container_width=True)
                
                col_ed1, col_ed2, col_ed3 = st.columns(3)
                with col_ed1:
                    id_agenda = st.number_input("ID do Item", min_value=1, step=1)
                with col_ed2:
                    novo_status = st.selectbox("Mudar Status Para", ["Realizado", "Não realizado", "Pendente"])
                with col_ed3:
                    if st.button("🔄 Atualizar Status"):
                        conn = sqlite3.connect(DB_FILE)
                        cursor = conn.cursor()
                        cursor.execute("UPDATE agenda SET status = ? WHERE id = ?", (novo_status, id_agenda))
                        conn.commit()
                        conn.close()
                        st.success(f"Status do ID #{id_agenda} atualizado!")
                        st.rerun()

                if st.button("🗑️ Excluir Item da Agenda"):
                    conn = sqlite3.connect(DB_FILE)
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM agenda WHERE id = ?", (id_agenda,))
                    conn.commit()
                    conn.close()
                    st.success(f"Item #{id_agenda} excluído!")
                    st.rerun()
            else:
                st.info("Nenhuma atividade cadastrada.")

elif menu == "📂 Clientes & Histórico" and st.session_state["perfil"] == "master":
    st.header("📂 Clientes & Histórico de Atendimentos")
    
    tab_c1, tab_c2, tab_c3 = st.tabs([
        "🔍 Consultar Clientes e Histórico", 
        "➕ Cadastrar / Editar Cliente", 
        "🗑️ Gerenciar / Excluir Cliente"
    ])
    
    with tab_c2:
        st.subheader("Cadastrar ou Editar Cliente")
        with st.form("form_novo_cliente"):
            nome_cli = st.text_input("Nome do Cliente / Condomínio (Ex: CONDOMÍNIO PRAÇAS DO GOLF RESORT I)")
            cnpj_cli = st.text_input("CNPJ")
            end_cli = st.text_input("Endereço")
            cid_cli = st.text_input("Cidade / UF", value="Ribeirão Preto - SP")
            sindico_cli = st.text_input("Síndico")
            zelador_cli = st.text_input("Zelador")
            tel_cli = st.text_input("Telefone")
            email_cli = st.text_input("E-mail")
            
            if st.form_submit_button("💾 Salvar / Atualizar Cliente"):
                if nome_cli:
                    nome_formatado = nome_cli.strip().upper()
                    clientes_db[nome_formatado] = {
                        "cnpj": cnpj_cli,
                        "endereco": end_cli,
                        "cidade_uf": cid_cli,
                        "sindico": sindico_cli,
                        "zelador": zelador_cli,
                        "telefone": tel_cli,
                        "email": email_cli
                    }
                    salvar_json(CLIENTES_FILE, clientes_db)
                    st.success(f"Cliente '{nome_formatado}' gravado com sucesso!")
                    st.rerun()
                else:
                    st.error("Informe o nome do cliente.")

    with tab_c3:
        st.subheader("Excluir Cliente")
        if clientes_db:
            cli_excluir = st.selectbox("Selecione o Cliente para Excluir", list(clientes_db.keys()), key="del_cli_select")
            if st.button("🗑️ Confirmar Exclusão de Cliente", type="primary"):
                del clientes_db[cli_excluir]
                salvar_json(CLIENTES_FILE, clientes_db)
                st.success(f"Cliente '{cli_excluir}' removido com sucesso!")
                st.rerun()

    with tab_c1:
        st.subheader("Base de Clientes")
        if clientes_db:
            cli_selecionado = st.selectbox("Selecione um Cliente", sorted(list(clientes_db.keys())))
            if cli_selecionado:
                info = clientes_db[cli_selecionado]
                st.write(f"**CNPJ:** {info.get('cnpj', '')}")
                st.write(f"**Endereço:** {info.get('endereco', '')}")
                st.write(f"**Telefone:** {info.get('telefone', '')}")
                
                nome_pasta_cliente = "".join(c for c in cli_selecionado.strip() if c.isalnum() or c in (' ', '_', '-')).strip()
                cliente_dir = os.path.join(HISTORICO_CLIENTES_DIR, nome_pasta_cliente)
                historico_path = os.path.join(cliente_dir, "historico_atendimentos.json")
                
                st.subheader("📜 Histórico de Atendimentos & Documentos")
                if os.path.exists(historico_path):
                    with open(historico_path, "r", encoding="utf-8") as f_h:
                        hist_data = json.load(f_h)
                    df_hist = pd.DataFrame(hist_data)
                    st.dataframe(df_hist, use_container_width=True)
                    
                    if st.button("🧹 Limpar Histórico do Cliente"):
                        os.remove(historico_path)
                        st.success("Histórico deste cliente foi limpo.")
                        st.rerun()
                else:
                    st.info("Nenhum histórico gravado para este cliente até o momento.")
        else:
            st.info("Nenhum cliente cadastrado no sistema.")

elif menu == "🏢 Dados da Empresa":
    st.header("🏢 Dados da Empresa & Logotipo")
    
    st.subheader("1. Logotipo Oficial")
    if os.path.exists(LOGO_PATH):
        st.image(LOGO_PATH, width=180, caption="Logotipo Cadastrado")
    
    logo_upload = st.file_uploader("Upload do Logotipo (PNG ou JPG)", type=["png", "jpg", "jpeg"])
    if logo_upload is not None:
        with open(LOGO_PATH, "wb") as f:
            f.write(logo_upload.getbuffer())
        st.success("Novo logotipo salvo com sucesso!")
        st.rerun()

    st.subheader("2. Informações Cadastrais")
    with st.form("form_dados_empresa"):
        nome_emp = st.text_input("Razão Social / Nome da Empresa", value=empresa_db.get("nome", ""))
        cnpj_emp = st.text_input("CNPJ", value=empresa_db.get("cnpj", ""))
        crea_emp = st.text_input("Registro CREA", value=empresa_db.get("crea", ""))
        tel_emp = st.text_input("Telefone de Contato", value=empresa_db.get("telefone", ""))
        email_emp = st.text_input("E-mail Oficial", value=empresa_db.get("email", ""))
        end_emp = st.text_input("Endereço Completo", value=empresa_db.get("endereco", ""))
        resp_emp = st.text_input("Responsável Técnico Padrão", value=empresa_db.get("resp_tecnico", ""))
        
        if st.form_submit_button("💾 Salvar Dados da Empresa", type="primary"):
            empresa_db.update({
                "nome": nome_emp, "cnpj": cnpj_emp, "crea": crea_emp,
                "telefone": tel_emp, "email": email_emp, "endereco": end_emp,
                "resp_tecnico": resp_emp
            })
            salvar_json(EMPRESA_FILE, empresa_db)
            st.success("Dados da empresa atualizados com sucesso!")

elif menu == "👥 Gestão de Usuários":
    st.header("👥 Gestão de Usuários do Sistema")
    
    with st.form("form_usuarios"):
        novo_u = st.text_input("Usuário")
        nova_s = st.text_input("Senha", type="password")
        novo_p = st.selectbox("Perfil de Acesso", ["master", "cliente"])
        cli_vinc = st.selectbox("Vincular a Cliente (Se perfil Cliente)", [""] + sorted(list(clientes_db.keys())))
        
        if st.form_submit_button("Cadastrar / Atualizar Usuário"):
            if novo_u and nova_s:
                usuarios[novo_u] = {"senha": nova_s, "perfil": novo_p, "cliente_vinculado": cli_vinc}
                salvar_json(USUARIOS_FILE, usuarios)
                st.success(f"Usuário '{novo_u}' salvo!")
                st.rerun()

elif menu == "🎫 Chamados Técnicos":
    st.header("🎫 Chamados Técnicos")
    
    with st.form("form_chamado"):
        cli_chamado = st.selectbox("Selecione o Cliente Vinculado", sorted(list(clientes_db.keys())) if clientes_db else ["Geral"])
        titulo_ch = st.text_input("Título do Chamado")
        desc_ch = st.text_area("Descrição do Problema / Solicitação")
        
        if st.form_submit_button("📩 ABRIR CHAMADO", type="primary"):
            if titulo_ch and desc_ch:
                chamados_db.append({
                    "usuario": st.session_state["user"],
                    "cliente": cli_chamado,
                    "titulo": titulo_ch,
                    "descricao": desc_ch,
                    "data": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "status": "Aberto"
                })
                salvar_json(CHAMADOS_FILE, chamados_db)
                st.success("Chamado registrado com sucesso!")
                st.rerun()
            else:
                st.error("Preencha o título e a descrição.")

    st.subheader("Chamados Registrados")
    if chamados_db:
        st.dataframe(pd.DataFrame(chamados_db), use_container_width=True)
    else:
        st.info("Nenhum chamado aberto até o momento.")

elif menu == "💾 Backup & Restauração":
    st.header("💾 Backup e Restauração de Dados")
    
    col_b1, col_b2 = st.columns(2)
    with col_b1:
        st.subheader("1. Fazer Backup")
        if st.button("📦 Gerar Arquivo de Backup"):
            data_bytes, file_name = perform_backup()
            if data_bytes:
                st.success(f"Backup gerado: `{file_name}`")
                st.download_button("⬇️ Baixar Backup (.db)", data_bytes, file_name=file_name, mime="application/x-sqlite3")

    with col_b2:
        st.subheader("2. Restaurar Backup")
        uploaded_backup = st.file_uploader("Carregar arquivo de backup (.db)", type=["db"])
        if uploaded_backup is not None:
            if st.button("⚠️ Restaurar Banco de Dados", type="primary"):
                if restaurar_backup(uploaded_backup):
                    st.success("Banco de dados restaurado com sucesso! Recarregue a página.")
                    st.rerun()
