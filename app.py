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

# --- AUTENTICAÇÃO E SESSÃO ---
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False
    st.session_state["user"] = ""
    st.session_state["perfil"] = ""
    st.session_state["cliente_vinculado"] = ""

if not st.session_state["logged_in"]:
    st.title("⚡ Eli Sistemas - Gestão & Inspeção Técnica")
    st.subheader("Acesso ao Sistema")
    
    with st.form("form_login"):
        u_input = st.text_input("Usuário")
        s_input = st.text_input("Senha", type="password")
        btn_login = st.form_submit_button("Entrar")
        
        if btn_login:
            if u_input in usuarios and usuarios[u_input]["senha"] == s_input:
                st.session_state["logged_in"] = True
                st.session_state["user"] = u_input
                st.session_state["perfil"] = usuarios[u_input].get("perfil", "cliente")
                st.session_state["cliente_vinculado"] = usuarios[u_input].get("cliente_vinculado", "")
                st.success("Login efetuado com sucesso!")
                st.rerun()
            else:
                st.error("Usuário ou senha incorretos.")
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

    # --- NOVO: INCLUSÃO DAS FOTOS ANEXADAS NO PDF ---
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
        "resp_tecnico": empresa_db.get("resp_tecnico", "Eli Silva"),
        "acompanhante": "", "status_geral": "CONFORME / SISTEMA OPERACIONAL",
        "central_sdai": "", "tipo_central": "SISTEMA ENDEREÇÁVEL",
        "qtd_lacos": "", "det_fumaca": "", "acionadores": "", "avisadores": "",
        "pressurizacao": "Sim", "tensao_baterias": "24 Vcc",
        "parecer": "", "orientacoes": "", "fotos_carregadas": []
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

# --- HELPER DE MANIPULAÇÃO DE RASCUNHO DA VISTORIA ---
def extrair_dados_vistoria_session():
    chaves = [
        "cliente", "cnpj", "endereco", "cidade_uf", "sindico", "zelador", "contato",
        "email", "data_visita", "tipo_visita", "resp_tecnico", "acompanhante",
        "status_geral", "central_sdai", "tipo_central", "qtd_lacos", "det_fumaca",
        "acionadores", "avisadores", "pressurizacao", "tensao_baterias", "parecer", "orientacoes", "fotos_carregadas"
    ]
    dados = {k: st.session_state.get(k, "") for k in chaves}
    for sec_key in ITENS_SECOES:
        for idx, _ in enumerate(ITENS_SECOES[sec_key]):
            dados[f"{sec_key}_{idx}_val"] = st.session_state.get(f"{sec_key}_{idx}_val", "")
            dados[f"{sec_key}_{idx}_obs"] = st.session_state.get(f"{sec_key}_{idx}_obs", "")
            dados[f"{sec_key}_{idx}_status"] = st.session_state.get(f"{sec_key}_{idx}_status", "CONFORME")
    return dados

def carregar_dados_vistoria_session(dados):
    for k, v in dados.items():
        st.session_state[k] = v

def salvar_rascunho_bd(cliente, data_visita, dados):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM rascunhos WHERE cliente = ? AND data_visita = ?", (cliente, data_visita))
    row = cursor.fetchone()
    agora_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    json_str = json.dumps(dados, ensure_ascii=False)
    if row:
        cursor.execute("UPDATE rascunhos SET dados_json = ?, atualizado_em = ? WHERE id = ?", (json_str, agora_str, row[0]))
    else:
        cursor.execute("INSERT INTO rascunhos (cliente, data_visita, dados_json, atualizado_em) VALUES (?, ?, ?, ?)",
                       (cliente, data_visita, json_str, agora_str))
    conn.commit()
    conn.close()

def excluir_rascunho_bd(cliente, data_visita):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM rascunhos WHERE cliente = ? AND data_visita = ?", (cliente, data_visita))
    conn.commit()
    conn.close()

# --- BARRA LATERAL E NAVEGAÇÃO COMPATÍVEL ---
st.sidebar.markdown(f"### ⚡ Eli Sistemas")
st.sidebar.caption(f"Usuário: **{st.session_state['user']}** ({st.session_state['perfil'].upper()})")

if st.sidebar.button("🚪 Sair / Logout"):
    st.session_state["logged_in"] = False
    st.rerun()

st.sidebar.divider()

if st.session_state["perfil"] == "cliente":
    menu_opcoes = ["📞 Abertura e Acompanhamento de Chamados"]
else:
    menu_opcoes = [
        "📅 Agenda Principal",
        "📋 Vistoria & Relatório Técnico NBR 17240",
        "🏢 Cadastro de Clientes & SDAI",
        "📞 Gestão de Chamados",
        "📂 Histórico & Pasta do Cliente",
        "🏢 Dados da Minha Empresa",
        "👥 Gerenciar Usuários",
        "💾 Backup & Restauração"
    ]

menu = st.sidebar.selectbox("Navegação", menu_opcoes)

# ==============================================================================
# PERFIL CLIENTE: TELA EXCLUSIVA DE CHAMADOS
# ==============================================================================
if menu == "📞 Abertura e Acompanhamento de Chamados":
    st.header("📞 Central de Chamados Técnicos")
    cliente_nome_usuario = st.session_state.get("cliente_vinculado", "")
    
    if not cliente_nome_usuario:
        st.warning("Seu usuário não possui um condomínio/cliente vinculado. Entre em contato com a Eli Sistemas.")
    else:
        st.subheader(f"Cliente: {cliente_nome_usuario}")
        tab_ch1, tab_ch2 = st.tabs(["➕ Abrir Novo Chamado", "📋 Acompanhar Meus Chamados"])
        
        with tab_ch1:
            with st.form("form_abrir_chamado_cliente", clear_on_submit=True):
                solicitante = st.text_input("Nome do Solicitante / Responsável", value=st.session_state["user"])
                contato_tel = st.text_input("Telefone de Contato / WhatsApp")
                email_contato = st.text_input("E-mail para Acompanhamento")
                descricao_prob = st.text_area("Descreva o Problema / Ocorrência no Sistema de Alarme")
                foto_chamado = st.file_uploader("Anexar Imagem/Foto da Falha (Opcional)", type=["png", "jpg", "jpeg"])
                
                if st.form_submit_button("🚀 Abrir Chamado Técnico"):
                    if descricao_prob:
                        novo_id = len(chamados_db) + 1
                        caminho_foto = ""
                        if foto_chamado:
                            caminho_foto = os.path.join(PASTA_FOTOS_VISTORIA, f"chamado_{novo_id}_{foto_chamado.name}")
                            with open(caminho_foto, "wb") as f:
                                f.write(foto_chamado.getbuffer())
                                
                        novo_chamado = {
                            "id": novo_id,
                            "cliente": cliente_nome_usuario,
                            "solicitante": solicitante,
                            "contato": contato_tel,
                            "email": email_contato,
                            "problema": descricao_prob,
                            "anexo": caminho_foto,
                            "status": "Pendente",
                            "historico_atendimento": "",
                            "conclusao_tecnica": "",
                            "data_abertura": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        }
                        chamados_db.append(novo_chamado)
                        salvar_json(CHAMADOS_FILE, chamados_db)
                        
                        registrar_historico_cliente(
                            cliente_nome_usuario,
                            f"Abertura de Chamado #{novo_id}",
                            {"problema": descricao_prob, "status": "Pendente", "solicitante": solicitante}
                        )
                        st.success(f"✅ Chamado #{novo_id} aberto com sucesso! A equipe técnica retornará em breve.")
                        st.rerun()
                    else:
                        st.error("A descrição do problema é obrigatória.")

        with tab_ch2:
            st.subheader("Meus Chamados")
            meus_chamados = [c for c in chamados_db if c.get("cliente") == cliente_nome_usuario]
            if not meus_chamados:
                st.info("Nenhum chamado aberto até o momento.")
            else:
                for ch in reversed(meus_chamados):
                    with st.expander(f"Chamado #{ch['id']} - Data: {ch.get('data_abertura', 'N/A')} (Status: {ch['status']})"):
                        st.write(f"**Solicitante:** {ch.get('solicitante', 'N/A')} | **Contato:** {ch.get('contato', 'N/A')}")
                        st.write(f"**Descrição da Ocorrência:** {ch['problema']}")
                        if ch.get("anexo") and os.path.exists(ch["anexo"]):
                            st.image(ch["anexo"], width=300)
                            
                        if ch.get("historico_atendimento"):
                            st.info(f"**🛠️ Histórico/Andamento Técnico:**\n\n{ch['historico_atendimento']}")
                        if ch.get("conclusao_tecnica"):
                            st.success(f"**✅ Parecer / Conclusão Técnica Final:**\n\n{ch['conclusao_tecnica']}")

# ==============================================================================
# PERFIL MASTER (ADMINISTRADOR)
# ==============================================================================
elif menu == "📅 Agenda Principal":
    st.title("📅 Agenda de Atividades e Manutenções")
    
    col_ag1, col_ag2 = st.columns([2, 1])
    
    with col_ag2:
        st.subheader("📄 Exportar Calendário PDF")
        hoje = datetime.today()
        
        modo_export = st.radio("Modo de Exportação", ["Mês Específico", "Histórico Completo"], horizontal=True)
        
        if modo_export == "Mês Específico":
            mes_pdf = st.selectbox("Mês", list(range(1, 13)), index=hoje.month - 1)
            ano_pdf = st.number_input("Ano", min_value=2024, max_value=2035, value=hoje.year)
            pdf_cal = gerar_pdf_calendario(ano_pdf, mes_pdf, incluir_tudo=False)
            file_title = f"Calendario_Agenda_{mes_pdf}_{ano_pdf}.pdf"
        else:
            pdf_cal = gerar_pdf_calendario(incluir_tudo=True)
            file_title = "Historico_Completo_Agenda.pdf"
            
        st.download_button(
            "📅 Baixar Calendário (PDF)",
            data=pdf_cal,
            file_name=file_title,
            mime="application/pdf",
            use_container_width=True
        )

    with col_ag1:
        with st.form("new_task_form", clear_on_submit=True):
            st.subheader("Cadastrar Nova Tarefa")
            task_name = st.text_input("Descrição da Tarefa / Serviço")
            col1, col2 = st.columns(2)
            with col1:
                category = st.selectbox("Período / Categoria", ["Diária", "Semanal", "Mensal", "Trimestral", "Anual"])
            with col2:
                due_date = st.date_input("Data Alvo", value=datetime.today())
                
            submitted = st.form_submit_button("Cadastrar na Agenda")
            if submitted and task_name:
                conn = sqlite3.connect(DB_FILE)
                cursor = conn.cursor()
                cursor.execute("INSERT INTO agenda (task, category, due_date, status) VALUES (?, ?, ?, ?)",
                               (task_name, category, str(due_date), "Não realizado"))
                conn.commit()
                conn.close()
                st.success("Tarefa cadastrada com sucesso!")
                st.rerun()

    st.divider()
    
    st.subheader("📋 Lista de Tarefas")
    filtro_exibicao = st.radio("Filtrar Tarefas por:", ["Exibir Tudo (Histórico Completo)", "Apenas Mês Atual"], horizontal=True)
    
    conn = sqlite3.connect(DB_FILE)
    if filtro_exibicao == "Apenas Mês Atual":
        mes_atual_str = datetime.today().strftime("%Y-%m")
        df_agenda = pd.read_sql(f"SELECT * FROM agenda WHERE due_date LIKE '{mes_atual_str}%' ORDER BY due_date ASC", conn)
    else:
        df_agenda = pd.read_sql("SELECT * FROM agenda ORDER BY due_date ASC", conn)
    conn.close()
    
    if df_agenda.empty:
        st.info("Nenhuma tarefa registrada para a seleção.")
    else:
        for index, row in df_agenda.iterrows():
            cols = st.columns([3, 1, 1, 1])
            with cols[0]:
                st.markdown(f"**{row['task']}**<br><small>Período: {row['category']} | Data: {row['due_date']}</small>", unsafe_allow_html=True)
            with cols[1]:
                status_color = "green" if row['status'] == "Realizado" else "orange"
                st.markdown(f"<span style='color:{status_color}; font-weight:bold;'>● {row['status']}</span>", unsafe_allow_html=True)
            with cols[2]:
                new_status = st.selectbox("Status", ["Não realizado", "Realizado"], key=f"status_{row['id']}", index=0 if row['status']=="Não realizado" else 1)
                if new_status != row['status']:
                    conn = sqlite3.connect(DB_FILE)
                    cursor = conn.cursor()
                    cursor.execute("UPDATE agenda SET status = ? WHERE id = ?", (new_status, row['id']))
                    conn.commit()
                    conn.close()
                    st.rerun()
            with cols[3]:
                if st.button("Excluir", key=f"del_{row['id']}"):
                    conn = sqlite3.connect(DB_FILE)
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM agenda WHERE id = ?", (row['id'],))
                    conn.commit()
                    conn.close()
                    st.rerun()

elif menu == "📋 Vistoria & Relatório Técnico NBR 17240":
    st.header("📋 Inspeção Preventiva & Relatório NBR 17240")
    
    # --- GERENCIAMENTO E BUSCA DE RASCUNHOS SALVOS ---
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT id, cliente, data_visita, atualizado_em, dados_json FROM rascunhos ORDER BY atualizado_em DESC")
    lista_rascunhos = cursor.fetchall()
    conn.close()

    dict_rascunhos = {r[1]: r for r in lista_rascunhos} # Mapeia cliente -> rascunho mais recente
    
    with st.expander("📝 Gerenciar e Buscar Rascunhos Salvos", expanded=bool(lista_rascunhos)):
        if not lista_rascunhos:
            st.info("Nenhum rascunho pendente no momento.")
        else:
            filtro_rascunho = st.text_input("🔍 Buscar rascunho por nome do cliente ou data:", placeholder="Digite para filtrar...")
            
            rascunhos_filtrados = [
                r for r in lista_rascunhos 
                if filtro_rascunho.lower() in r[1].lower() or filtro_rascunho.lower() in r[2].lower()
            ]
            
            if not rascunhos_filtrados:
                st.warning("Nenhum rascunho encontrado com o termo digitado.")
            else:
                for r in rascunhos_filtrados:
                    r_id, r_cliente, r_data, r_atualizado, r_json = r
                    col_r1, col_r2, col_r3 = st.columns([3, 1, 1])
                    
                    with col_r1:
                        st.markdown(f"**🏢 {r_cliente}** — Visita: `{r_data}` <br/><small>Última alteração: {r_atualizado}</small>", unsafe_allow_html=True)
                    with col_r2:
                        if st.button("🔄 Carregar", key=f"btn_load_rasc_{r_id}", use_container_width=True):
                            dados_r = json.loads(r_json)
                            carregar_dados_vistoria_session(dados_r)
                            st.success(f"Rascunho de '{r_cliente}' carregado!")
                            st.rerun()
                    with col_r3:
                        if st.button("🗑️ Excluir", key=f"btn_del_rasc_{r_id}", use_container_width=True):
                            excluir_rascunho_bd(r_cliente, r_data)
                            st.warning(f"Rascunho de '{r_cliente}' excluído!")
                            st.rerun()

    st.divider()

    # --- SELEÇÃO DE CLIENTE COM INDICAÇÃO DE RASCUNHO PENDENTE ---
    clientes_ativos = {k: v for k, v in clientes_db.items() if isinstance(v, dict) and v.get("status", "Ativo") == "Ativo"}
    
    if clientes_ativos:
        opcoes_dropdown = ["-- Selecione o Cliente --"]
        mapa_nomes = {}
        
        for nome_cli in clientes_ativos.keys():
            label = f"{nome_cli} 📝 (Rascunho Pendente)" if nome_cli in dict_rascunhos else nome_cli
            opcoes_dropdown.append(label)
            mapa_nomes[label] = nome_cli

        def ao_selecionar_cliente():
            label_sel = st.session_state["select_carregar_cliente"]
            if label_sel != "-- Selecione o Cliente --":
                cli_nome = mapa_nomes[label_sel]
                
                if cli_nome in dict_rascunhos:
                    r_dados = json.loads(dict_rascunhos[cli_nome][4])
                    carregar_dados_vistoria_session(r_dados)
                    st.toast(f"📝 Rascunho do cliente '{cli_nome}' recarregado automaticamente!", icon="✅")
                else:
                    c_info = clientes_ativos[cli_nome]
                    st.session_state["cliente"] = c_info.get("nome", "")
                    st.session_state["cnpj"] = c_info.get("cnpj", "")
                    st.session_state["endereco"] = c_info.get("endereco", "")
                    st.session_state["cidade_uf"] = c_info.get("cidade_uf", "")
                    st.session_state["sindico"] = c_info.get("sindico", "")
                    st.session_state["zelador"] = c_info.get("zelador", "")
                    st.session_state["contato"] = c_info.get("contato", "")
                    st.session_state["email"] = c_info.get("email", "")
                    st.session_state["central_sdai"] = c_info.get("central_sdai", "")
                    st.session_state["tipo_central"] = c_info.get("tipo_central", "")
                    st.session_state["qtd_lacos"] = c_info.get("qtd_lacos", "")
                    st.session_state["det_fumaca"] = c_info.get("det_fumaca", "")
                    st.session_state["acionadores"] = c_info.get("acionadores", "")
                    st.session_state["avisadores"] = c_info.get("avisadores", "")
                    st.session_state["pressurizacao"] = c_info.get("pressurizacao", "")
                    st.session_state["tensao_baterias"] = c_info.get("tensao_baterias", "")

        st.selectbox(
            "Selecione um Cliente Ativo para Preenchimento ou Continuação",
            opcoes_dropdown,
            key="select_carregar_cliente",
            on_change=ao_selecionar_cliente
        )

    cliente_atual = st.session_state.get("cliente", "").strip()
    if cliente_atual in dict_rascunhos:
        st.info(f"💡 **Atenção:** Existe um rascunho em aberto para **{cliente_atual}** (Última atualização: {dict_rascunhos[cliente_atual][3]}). Os dados abaixo referem-se a esta edição em andamento.")

    col1, col2 = st.columns(2)
    with col1:
        st.text_input("Cliente / Condomínio", key="cliente")
        st.text_input("CNPJ do Cliente", key="cnpj")
        st.text_input("Endereço", key="endereco")
        st.text_input("Cidade / UF", key="cidade_uf")
    with col2:
        st.text_input("Data da Visita", key="data_visita")
        st.text_input("Tipo de Visita", key="tipo_visita")
        st.text_input("Responsável Técnico", key="resp_tecnico")
        st.text_input("Acompanhante / Portaria", key="acompanhante")

    st.subheader("🔍 Verificação dos Itens Normativos (Checklist)")
    for sec_key, sec_title in [("sec3", "3. Central & Fontes"), ("sec4", "4. Laços"), ("sec5", "5. Periféricos"), ("sec6", "6. Pressurização/IT13")]:
        with st.expander(sec_title):
            for idx, item in enumerate(ITENS_SECOES[sec_key]):
                col_i1, col_i2, col_i3 = st.columns([1.5, 3, 1])
                with col_i1:
                    st.text_input(f"Valor ({item[0]})", key=f"{sec_key}_{idx}_val")
                with col_i2:
                    st.text_input(f"Obs ({item[0]})", key=f"{sec_key}_{idx}_obs")
                with col_i3:
                    st.selectbox(f"Status ({item[0]})", ["CONFORME", "NÃO CONFORME", "N/A"], key=f"{sec_key}_{idx}_status")

    st.text_area("Parecer Técnico / Conclusão", key="parecer")
    st.text_area("Orientações Operacionais", key="orientacoes")

    # --- NOVO: SEÇÃO PARA ANEXAR E EXIBIR FOTOS DA VISTORIA ---
    st.subheader("📷 Registro Fotográfico da Vistoria")
    novas_fotos = st.file_uploader(
        "Anexar imagens/fotos para o relatório (PDF)", 
        type=["png", "jpg", "jpeg"], 
        accept_multiple_files=True
    )
    
    if novas_fotos:
        for f_upload in novas_fotos:
            time_stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            nome_arq_foto = f"vistoria_{time_stamp}_{f_upload.name}"
            caminho_salvar = os.path.join(PASTA_FOTOS_VISTORIA, nome_arq_foto)
            
            with open(caminho_salvar, "wb") as f_out:
                f_out.write(f_upload.getbuffer())
                
            if caminho_salvar not in st.session_state["fotos_carregadas"]:
                st.session_state["fotos_carregadas"].append(caminho_salvar)
        st.toast("✅ Foto(s) adicionada(s) com sucesso!", icon="📷")

    fotos_atuais = st.session_state.get("fotos_carregadas", [])
    if fotos_atuais:
        st.markdown(f"**Fotos Anexadas ({len(fotos_atuais)}):**")
        cols_foto = st.columns(4)
        for idx, path_f in enumerate(fotos_atuais):
            if os.path.exists(path_f):
                with cols_foto[idx % 4]:
                    st.image(path_f, use_container_width=True)
                    if st.button("🗑️ Remover", key=f"btn_del_foto_{idx}"):
                        st.session_state["fotos_carregadas"].pop(idx)
                        st.rerun()

    st.divider()

    col_btn_rascunho, col_btn_finalizar = st.columns(2)

    with col_btn_rascunho:
        if st.button("📝 Salvar como Rascunho", use_container_width=True):
            c_nome = st.session_state.get("cliente", "").strip()
            d_visita = st.session_state.get("data_visita", "").strip()
            if not c_nome:
                st.error("Informe o nome do cliente antes de salvar o rascunho.")
            else:
                dados_v = extrair_dados_vistoria_session()
                salvar_rascunho_bd(c_nome, d_visita, dados_v)
                st.success("✅ Rascunho salvo com sucesso!")
                st.rerun()

    with col_btn_finalizar:
        if st.button("💾 Finalizar e Gerar PDF", type="primary", use_container_width=True):
            c_nome = st.session_state.get("cliente", "").strip()
            d_visita = st.session_state.get("data_visita", "").strip()
            if not c_nome:
                st.error("Informe o nome do cliente para finalizar o relatório.")
            else:
                pdf_bytes = gerar_pdf_preventiva()
                excluir_rascunho_bd(c_nome, d_visita)
                st.success("✅ Relatório finalizado e salvo na Pasta Digital!")
                st.download_button("📄 BAIXAR RELATÓRIO PDF", data=pdf_bytes, file_name=f"Relatorio_{c_nome}.pdf", mime="application/pdf")

elif menu == "🏢 Cadastro de Clientes & SDAI":
    st.header("🏢 Cadastro e Edição de Clientes & Equipamentos")
    
    modo = st.radio("Ação desejada:", ["Novo Cliente", "Editar Cliente Existente"], horizontal=True)
    
    cliente_editando = None
    if modo == "Editar Cliente Existente":
        if not clientes_db:
            st.info("Nenhum cliente cadastrado.")
        else:
            cli_selecionado = st.selectbox("Selecione o Cliente para Editar", list(clientes_db.keys()))
            if cli_selecionado:
                cliente_editando = clientes_db.get(cli_selecionado, {})

    with st.form("form_cad_cliente"):
        val_status = cliente_editando.get("status", "Ativo") if cliente_editando else "Ativo"
        val_nome = cliente_editando.get("nome", "") if cliente_editando else ""
        val_cnpj = cliente_editando.get("cnpj", "") if cliente_editando else ""
        val_end = cliente_editando.get("endereco", "") if cliente_editando else ""
        val_cid = cliente_editando.get("cidade_uf", "Ribeirão Preto - SP") if cliente_editando else "Ribeirão Preto - SP"
        val_tel = cliente_editando.get("contato", "") if cliente_editando else ""
        val_email = cliente_editando.get("email", "") if cliente_editando else ""
        val_csdai = cliente_editando.get("central_sdai", "") if cliente_editando else ""
        val_tsdai = cliente_editando.get("tipo_central", "SISTEMA ENDEREÇÁVEL") if cliente_editando else "SISTEMA ENDEREÇÁVEL"
        val_qlacos = cliente_editando.get("qtd_lacos", "01 LAÇO") if cliente_editando else "01 LAÇO"

        c_status_cad = st.selectbox("Status do Cliente", ["Ativo", "Inativo"], index=0 if val_status == "Ativo" else 1)
        c_nome_cad = st.text_input("Nome do Condomínio / Empresa", value=val_nome)
        c_cnpj_cad = st.text_input("CNPJ", value=val_cnpj)
        c_end_cad = st.text_input("Endereço", value=val_end)
        c_cid_cad = st.text_input("Cidade / UF", value=val_cid)
        c_tel_cad = st.text_input("Telefone", value=val_tel)
        c_email_cad = st.text_input("E-mail", value=val_email)
        
        st.subheader("Configuração SDAI")
        c_csdai = st.text_input("Central SDAI (Modelo/Marca)", value=val_csdai)
        c_tsdai = st.text_input("Tipo de Central", value=val_tsdai)
        c_qlacos = st.text_input("Qtd. Laços", value=val_qlacos)
        
        if st.form_submit_button("💾 Salvar Cliente"):
            if c_nome_cad:
                clientes_db[c_nome_cad] = {
                    "status": c_status_cad,
                    "nome": c_nome_cad, "cnpj": c_cnpj_cad, "endereco": c_end_cad,
                    "cidade_uf": c_cid_cad, "contato": c_tel_cad, "email": c_email_cad,
                    "central_sdai": c_csdai, "tipo_central": c_tsdai, "qtd_lacos": c_qlacos
                }
                salvar_json(CLIENTES_FILE, clientes_db)
                st.success(f"Cliente '{c_nome_cad}' salvo com sucesso! Status: **{c_status_cad}**")
                st.rerun()

elif menu == "📞 Gestão de Chamados":
    st.header("📞 Gestão e Acompanhamento de Chamados Técnicos")
    if not chamados_db:
        st.info("Nenhum chamado registrado.")
    else:
        for ch in reversed(chamados_db):
            with st.expander(f"Chamado #{ch['id']} - {ch['cliente']} (Status: {ch['status']})"):
                st.write(f"**Solicitante:** {ch.get('solicitante', 'N/A')} | **Contato:** {ch.get('contato', 'N/A')} | **Data Abertura:** {ch.get('data_abertura', 'N/A')}")
                st.write(f"**Descrição do Problema:** {ch['problema']}")
                if ch.get("anexo") and os.path.exists(ch["anexo"]):
                    st.image(ch["anexo"], width=300)
                
                st.divider()
                st.markdown("### 🛠️ Acompanhamento e Parecer Técnico")
                
                col_c1, col_c2 = st.columns(2)
                with col_c1:
                    status_opcoes = ["Pendente", "Em Andamento", "Concluído", "Cancelado"]
                    idx_stat = status_opcoes.index(ch["status"]) if ch["status"] in status_opcoes else 0
                    novo_status = st.selectbox("Status do Chamado", status_opcoes, index=idx_stat, key=f"status_adm_{ch['id']}")
                
                hist_atual = st.text_area(
                    "Histórico de Ações em Andamento (visível ao cliente)", 
                    value=ch.get("historico_atendimento", ""), 
                    height=100, 
                    key=f"hist_{ch['id']}",
                    help="Ex: 'Técnico deslocado em 10/05', 'Substituída fonte da central', etc."
                )
                
                conclusao_atual = st.text_area(
                    "Texto Final / Conclusão Técnica do Atendimento", 
                    value=ch.get("conclusao_tecnica", ""), 
                    height=100, 
                    key=f"concl_{ch['id']}",
                    help="Parecer conclusivo do técnico referente ao encerramento/solução do problema."
                )
                
                if st.button("💾 Atualizar Chamado", key=f"btn_salvar_ch_{ch['id']}"):
                    ch["status"] = novo_status
                    ch["historico_atendimento"] = hist_atual
                    ch["conclusao_tecnica"] = conclusao_atual
                    salvar_json(CHAMADOS_FILE, chamados_db)
                    
                    registrar_historico_cliente(
                        ch['cliente'],
                        f"Atualização Chamado #{ch['id']}",
                        {
                            "status": novo_status,
                            "historico": hist_atual,
                            "conclusao": conclusao_atual
                        }
                    )
                    st.success(f"Chamado #{ch['id']} atualizado com sucesso!")
                    st.rerun()

elif menu == "📂 Histórico & Pasta do Cliente":
    st.header("📂 Pasta Digital por Cliente")
    if clientes_db:
        cli_sel = st.selectbox("Selecione o Cliente", list(clientes_db.keys()))
        
        # --- EXIBIÇÃO DE RASCUNHOS PENDENTES DO CLIENTE ---
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT id, data_visita, atualizado_em FROM rascunhos WHERE cliente = ? ORDER BY atualizado_em DESC", (cli_sel,))
        rascunhos_cliente = cursor.fetchall()
        conn.close()

        if rascunhos_cliente:
            st.subheader("📝 Rascunhos em Edição")
            for r_item in rascunhos_cliente:
                st.warning(f"📝 **[RASCUNHO Pendente]** - Vistoria para {r_item[1]} (Última modificação: {r_item[2]})")
            st.divider()

        nome_pasta_cliente = "".join(c for c in cli_sel if c.isalnum() or c in (' ', '_', '-')).strip()
        cliente_dir = os.path.join(HISTORICO_CLIENTES_DIR, nome_pasta_cliente)
        
        if os.path.exists(cliente_dir):
            historico_path = os.path.join(cliente_dir, "historico_atendimentos.json")
            if os.path.exists(historico_path):
                with open(historico_path, "r", encoding="utf-8") as f:
                    hist = json.load(f)
                
                if not hist:
                    st.info("Nenhum histórico finalizado para este cliente.")
                else:
                    st.subheader("📌 Histórico e Documentos Finalizados")
                    for item in reversed(hist):
                        tipo = item.get('tipo', 'Atendimento')
                        data_hist = item.get('data', 'N/A')
                        
                        with st.expander(f"📌 {tipo} - Data: {data_hist}"):
                            if "Chamado" in tipo:
                                if item.get("status"):
                                    st.markdown(f"**Status:** `{item.get('status')}`")
                                if item.get("solicitante"):
                                    st.markdown(f"**Solicitante:** {item.get('solicitante')}")
                                if item.get("problema"):
                                    st.markdown(f"**Descrição da Ocorrência:** {item.get('problema')}")
                                if item.get("historico"):
                                    st.info(f"**🛠️ Histórico / Andamento:**\n\n{item.get('historico')}")
                                if item.get("conclusao"):
                                    st.success(f"**✅ Conclusão Técnica:**\n\n{item.get('conclusao')}")
                            
                            elif "Relatório" in tipo:
                                st.markdown(f"**Técnico Resp.:** {item.get('resp_tecnico', 'N/A')}")
                                st.markdown(f"**Status Geral:** {item.get('status_geral', 'N/A')}")
                                arq = item.get("arquivo_pdf")
                                if arq:
                                    caminho_pdf = os.path.join(cliente_dir, arq)
                                    if os.path.exists(caminho_pdf):
                                        with open(caminho_pdf, "rb") as f_pdf:
                                            st.download_button(
                                                f"📄 Baixar {arq}",
                                                f_pdf,
                                                file_name=arq,
                                                mime="application/pdf",
                                                key=f"btn_hist_{arq}_{data_hist}"
                                            )
                            else:
                                for k, v in item.items():
                                    if k not in ["tipo", "data"]:
                                        st.write(f"**{k.capitalize()}:** {v}")

elif menu == "🏢 Dados da Minha Empresa":
    st.header("🏢 Configurações da Empresa Prestadora")
    
    col_emp1, col_emp2 = st.columns([2, 1])
    
    with col_emp1:
        with st.form("form_empresa"):
            e_nome = st.text_input("Nome da Empresa", value=empresa_db.get("nome", ""))
            e_cnpj = st.text_input("CNPJ", value=empresa_db.get("cnpj", ""))
            e_crea = st.text_input("CREA", value=empresa_db.get("crea", ""))
            e_tel = st.text_input("Telefone", value=empresa_db.get("telefone", ""))
            e_email = st.text_input("E-mail", value=empresa_db.get("email", ""))
            e_end = st.text_input("Endereço", value=empresa_db.get("endereco", ""))
            e_resp = st.text_input("Responsável Técnico padrão", value=empresa_db.get("resp_tecnico", ""))
            
            if st.form_submit_button("💾 Salvar Dados da Empresa"):
                empresa_db["nome"] = e_nome
                empresa_db["cnpj"] = e_cnpj
                empresa_db["crea"] = e_crea
                empresa_db["telefone"] = e_tel
                empresa_db["email"] = e_email
                empresa_db["endereco"] = e_end
                empresa_db["resp_tecnico"] = e_resp
                salvar_json(EMPRESA_FILE, empresa_db)
                st.success("Dados da empresa salvos com sucesso!")

    with col_emp2:
        st.subheader("🖼️ Logotipo da Empresa")
        if os.path.exists(LOGO_PATH):
            st.image(LOGO_PATH, caption="Logotipo Atual", width=150)
            
        uploaded_logo = st.file_uploader("Upload de nova Logo (usada nos relatórios PDF)", type=["png", "jpg", "jpeg"])
        if uploaded_logo is not None:
            with open(LOGO_PATH, "wb") as f:
                f.write(uploaded_logo.getbuffer())
            st.success("✅ Logotipo atualizado com sucesso!")
            st.rerun()

elif menu == "👥 Gerenciar Usuários":
    st.header("👥 Gestão de Usuários e Vínculos com Clientes")
    tab_u1, tab_u2, tab_u3 = st.tabs(["➕ Novo Usuário", "✏️ Vincular / Editar Usuário", "📋 Usuários Cadastrados"])
    
    lista_cli_vinculo = ["-- Nenhum / Administrador --"] + list(clientes_db.keys())

    with tab_u1:
        with st.form("form_novo_usuario"):
            u_login = st.text_input("Login de Acesso")
            u_senha = st.text_input("Senha", type="password")
            u_nome = st.text_input("Nome do Usuário / Responsável")
            u_perfil = st.selectbox("Perfil de Acesso", ["cliente", "master"])
            u_vinculo = st.selectbox("Vincular ao Cliente/Condomínio", lista_cli_vinculo, key="cad_vinc")
            
            if st.form_submit_button("💾 Cadastrar Usuário"):
                if u_login and u_senha:
                    cli_final = u_vinculo if u_vinculo != "-- Nenhum / Administrador --" else ""
                    usuarios[u_login] = {
                        "senha": u_senha,
                        "nome": u_nome,
                        "perfil": u_perfil,
                        "cliente_vinculado": cli_final
                    }
                    salvar_json(USUARIOS_FILE, usuarios)
                    st.success(f"✅ Usuário {u_login} cadastrado com sucesso!")
                    st.rerun()

    with tab_u2:
        st.subheader("Editar Vínculo e Perfil de Usuário Existente")
        usr_sel = st.selectbox("Selecione o Usuário para Alterar", list(usuarios.keys()))
        if usr_sel:
            dados_u = usuarios[usr_sel]
            with st.form("form_edit_usuario"):
                edit_nome = st.text_input("Nome do Usuário", value=dados_u.get("nome", ""))
                edit_senha = st.text_input("Senha", value=dados_u.get("senha", ""), type="password")
                edit_perfil = st.selectbox("Perfil", ["cliente", "master"], index=0 if dados_u.get("perfil") == "cliente" else 1)
                
                cli_atual = dados_u.get("cliente_vinculado", "")
                idx_vinc = lista_cli_vinculo.index(cli_atual) if cli_atual in lista_cli_vinculo else 0
                edit_vinc = st.selectbox("Cliente/Condomínio Vinculado", lista_cli_vinculo, index=idx_vinc)
                
                if st.form_submit_button("💾 Salvar Alterações no Usuário"):
                    cli_vinc_salvar = edit_vinc if edit_vinc != "-- Nenhum / Administrador --" else ""
                    usuarios[usr_sel]["nome"] = edit_nome
                    usuarios[usr_sel]["senha"] = edit_senha
                    usuarios[usr_sel]["perfil"] = edit_perfil
                    usuarios[usr_sel]["cliente_vinculado"] = cli_vinc_salvar
                    salvar_json(USUARIOS_FILE, usuarios)
                    st.success(f"✅ Alterações salvas para o usuário {usr_sel}!")
                    st.rerun()

    with tab_u3:
        st.subheader("Lista de Usuários Cadastrados")
        for u, d in usuarios.items():
            st.markdown(f"**Login:** `{u}` | **Nome:** {d.get('nome')} | **Perfil:** `{d.get('perfil')}` | **Cliente Vinculado:** {d.get('cliente_vinculado') if d.get('cliente_vinculado') else 'Nenhum (Master)'}")
            st.divider()

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
                    st.success("✅ Banco de dados restaurado com sucesso! Recarregando sistema...")
                    st.rerun()
                else:
                    st.error("Erro ao tentar restaurar o arquivo fornecido.")
