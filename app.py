import os
import io
import json
from datetime import datetime
import streamlit as st
import pandas as pd
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

# --- CONFIGURAÇÃO DE DIRETÓRIOS ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__)) if "__file__" in locals() else "."
CLIENTES_FILE = os.path.join(BASE_DIR, "clientes.json")
EMPRESA_FILE = os.path.join(BASE_DIR, "empresa.json")
CHAMADOS_FILE = os.path.join(BASE_DIR, "chamados.json")
USUARIOS_FILE = os.path.join(BASE_DIR, "usuarios.json")
LOGO_PATH = os.path.join(BASE_DIR, "logo_empresa.png")
PASTA_FOTOS_VISTORIA = os.path.join(BASE_DIR, "fotos_vistoria")
HISTORICO_CLIENTES_DIR = os.path.join(BASE_DIR, "historico_clientes")

os.makedirs(PASTA_FOTOS_VISTORIA, exist_ok=True)
os.makedirs(HISTORICO_CLIENTES_DIR, exist_ok=True)

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
    """Função unificada para salvar qualquer evento/relatório/chamado na pasta do cliente."""
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

# Carregamento inicial de dados
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
    "admin": {"senha": "123", "nome": "Eli Silva", "perfil": "master"}
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

# --- CONFIGURAÇÃO DA PÁGINA E CONTROLE DE AUTENTICAÇÃO ---
st.set_page_config(page_title="SDAI - Gestão & Inspeção Técnica", layout="wide")

if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False
    st.session_state["user"] = ""
    st.session_state["perfil"] = ""

# Se não estiver logado, exibe apenas a tela de login e interrompe a execução
if not st.session_state["logged_in"]:
    st.title("🔥 SDAI - Sistema de Gestão e Inspeção Técnica")
    st.subheader("Login de Acesso")
    
    with st.form("form_login"):
        u_input = st.text_input("Usuário")
        s_input = st.text_input("Senha", type="password")
        btn_login = st.form_submit_button("Entrar")
        
        if btn_login:
            if u_input in usuarios and usuarios[u_input]["senha"] == s_input:
                st.session_state["logged_in"] = True
                st.session_state["user"] = u_input
                st.session_state["perfil"] = usuarios[u_input].get("perfil", "cliente")
                st.success("Login efetuado com sucesso!")
                st.rerun()
            else:
                st.error("Usuário ou senha incorretos.")
    st.stop()

def gerar_pdf_preventiva():
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=20, leftMargin=20,
        topMargin=20, bottomMargin=20
    )
    
    story = []
    styles = getSampleStyleSheet()
    
    style_celula = ParagraphStyle('CelTabela', parent=styles['Normal'], fontSize=8, leading=9, textColor=colors.black)
    style_cabecalho_tabela = ParagraphStyle('CabTabela', parent=styles['Normal'], fontSize=8, leading=9, fontName='Helvetica-Bold', textColor=colors.whitesmoke, alignment=1)
    style_texto_empresa = ParagraphStyle('EmpresaText', parent=styles['Normal'], fontSize=8, leading=10, textColor=colors.black)
    style_sec_header = ParagraphStyle('SecHeader', parent=styles['Normal'], fontSize=9, leading=11, fontName='Helvetica-Bold', textColor=colors.black)

    logo_w, logo_h = 45, 30
    if os.path.exists(LOGO_PATH):
        img_logo = Image(LOGO_PATH, width=logo_w, height=logo_h)
    else:
        img_logo = Paragraph("<b>LOGO</b>", style_celula)

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

    fotos = st.session_state.get("fotos_carregadas", [])
    if fotos:
        story.append(Spacer(1, 10))
        story.append(Paragraph("<b>9. REGISTRO FOTOGRÁFICO DA VISTORIA</b>", style_sec_header))
        story.append(Spacer(1, 4))
        
        linhas_fotos = []
        par_atual = []
        for f_path in fotos:
            if os.path.exists(f_path):
                img_obj = Image(f_path, width=250, height=180)
                par_atual.append(img_obj)
                if len(par_atual) == 2:
                    linhas_fotos.append(par_atual)
                    par_atual = []
        if par_atual:
            par_atual.append(Paragraph("", style_celula))
            linhas_fotos.append(par_atual)

        for par in linhas_fotos:
            t_foto = Table([par], colWidths=[277, 278])
            t_foto.setStyle(TableStyle([('ALIGN', (0,0), (-1,-1), 'CENTER'), ('VALIGN', (0,0), (-1,-1), 'MIDDLE'), ('BOTTOMPADDING', (0,0), (-1,-1), 6)]))
            story.append(t_foto)

    doc.build(story)
    buffer.seek(0)
    pdf_data = buffer.getvalue()

    # SALVAR AUTOMATICAMENTE NA PASTA DO CLIENTE
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

def gerar_pdf_chamado_simples():
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=20, leftMargin=20, topMargin=20, bottomMargin=20)
    story = []
    styles = getSampleStyleSheet()
    
    style_celula = ParagraphStyle('CelTabela', parent=styles['Normal'], fontSize=8, leading=9, textColor=colors.black)
    style_texto_empresa = ParagraphStyle('EmpresaText', parent=styles['Normal'], fontSize=8, leading=10, textColor=colors.black)
    style_sec_header = ParagraphStyle('SecHeader', parent=styles['Normal'], fontSize=9, leading=11, fontName='Helvetica-Bold', textColor=colors.black)

    logo_w, logo_h = 45, 30
    if os.path.exists(LOGO_PATH):
        img_logo = Image(LOGO_PATH, width=logo_w, height=logo_h)
    else:
        img_logo = Paragraph("<b>LOGO</b>", style_celula)

    info_empresa_texto = f"""
    <b>{empresa_db.get('nome', '')}</b><br/>
    CNPJ: {empresa_db.get('cnpj', '')} | CREA: {empresa_db.get('crea', '')} | Tel: {empresa_db.get('telefone', '')}<br/>
    E-mail: {empresa_db.get('email', '')} | Endereço: {empresa_db.get('endereco', '')}<br/>
    <b>RELATÓRIO TÉCNICO DE ATENDIMENTO / CHAMADO / VISTORIA SIMPLES</b>
    """
    
    tabela_cabecalho = Table([[Paragraph(info_empresa_texto, style_texto_empresa), img_logo]], colWidths=[495, 60])
    tabela_cabecalho.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'), ('ALIGN', (1, 0), (1, 0), 'RIGHT'), ('BOTTOMPADDING', (0, 0), (-1, -1), 6)]))
    story.append(tabela_cabecalho)
    story.append(Spacer(1, 4))

    story.append(Paragraph("<b>1. DADOS DA EDIFICAÇÃO E DO ATENDIMENTO</b>", style_sec_header))
    dados_edif = [
        [Paragraph(f"<b>CLIENTE:</b> {st.session_state.get('cs_cliente', '')}", style_celula), Paragraph(f"<b>Data:</b> {st.session_state.get('cs_data', '')}", style_celula)],
        [Paragraph(f"<b>CNPJ:</b> {st.session_state.get('cs_cnpj', '')}", style_celula), Paragraph(f"<b>Tipo de Atendimento:</b> {st.session_state.get('cs_tipo', '')}", style_celula)],
        [Paragraph(f"<b>Endereço:</b> {st.session_state.get('cs_endereco', '')}", style_celula), Paragraph(f"<b>Responsável Técnico:</b> {st.session_state.get('cs_resp_tecnico', '')}", style_celula)],
        [Paragraph(f"<b>Cidade / UF:</b> {st.session_state.get('cs_cidade_uf', '')}", style_celula), Paragraph(f"<b>Solicitante / Contato:</b> {st.session_state.get('cs_acompanhante', '')}", style_celula)],
    ]
    t_edif = Table(dados_edif, colWidths=[330, 225])
    t_edif.setStyle(TableStyle([('BOX', (0,0), (-1,-1), 0.5, colors.grey), ('INNERGRID', (0,0), (-1,-1), 0.25, colors.lightgrey), ('TOPPADDING', (0,0), (-1,-1), 2), ('BOTTOMPADDING', (0,0), (-1,-1), 2)]))
    story.append(t_edif)
    story.append(Spacer(1, 4))

    story.append(Paragraph("<b>2. INFORMAÇÕES DO SISTEMA SDAI NO LOCAL</b>", style_sec_header))
    dados_tec = [
        [Paragraph(f"<b>Central SDAI:</b> {st.session_state.get('cs_central_sdai', '')}", style_celula), Paragraph(f"<b>Tipo Central:</b> {st.session_state.get('cs_tipo_central', '')}", style_celula), Paragraph(f"<b>Qtd. Laços / Zonas:</b> {st.session_state.get('cs_qtd_lacos', '')}", style_celula)],
    ]
    t_tec = Table(dados_tec, colWidths=[185, 185, 185])
    t_tec.setStyle(TableStyle([('BOX', (0,0), (-1,-1), 0.5, colors.grey), ('INNERGRID', (0,0), (-1,-1), 0.25, colors.lightgrey), ('TOPPADDING', (0,0), (-1,-1), 2), ('BOTTOMPADDING', (0,0), (-1,-1), 2)]))
    story.append(t_tec)
    story.append(Spacer(1, 4))

    story.append(Paragraph("<b>3. DESCRIÇÃO TÉCNICA / RELATO DO ATENDIMENTO</b>", style_sec_header))
    relato_texto = f"<b>Relatório / Escopo Executado / Ocorrência:</b><br/>{st.session_state.get('cs_relato', 'Nenhum relato informado.')}"
    t_relato = Table([[Paragraph(relato_texto, style_celula)]], colWidths=[555])
    t_relato.setStyle(TableStyle([('BOX', (0,0), (-1,-1), 0.5, colors.grey), ('TOPPADDING', (0,0), (-1,-1), 6), ('BOTTOMPADDING', (0,0), (-1,-1), 6)]))
    story.append(t_relato)
    story.append(Spacer(1, 6))

    story.append(Paragraph("<b>4. VALIDAÇÃO E ASSINATURAS</b>", style_sec_header))
    assinaturas_data = [[
        Paragraph(f"<b>Responsável Técnico:</b> {st.session_state.get('cs_resp_tecnico', '')}<br/>CREA: {empresa_db.get('crea', '')}<br/><br/><br/>________________________________________<br/>Assinatura do Técnico", style_celula),
        Paragraph(f"<b>Recebedor / Solicitante:</b> {st.session_state.get('cs_acompanhante', '')}<br/><br/><br/><br/>________________________________________<br/>Assinatura do Cliente", style_celula)
    ]]
    t_ass = Table(assinaturas_data, colWidths=[277, 278])
    t_ass.setStyle(TableStyle([('BOX', (0,0), (-1,-1), 0.5, colors.grey), ('INNERGRID', (0,0), (-1,-1), 0.25, colors.lightgrey), ('TOPPADDING', (0,0), (-1,-1), 6), ('BOTTOMPADDING', (0,0), (-1,-1), 6)]))
    story.append(t_ass)

    fotos = st.session_state.get("cs_fotos_carregadas", [])
    if fotos:
        story.append(Spacer(1, 10))
        story.append(Paragraph("<b>5. REGISTRO FOTOGRÁFICO</b>", style_sec_header))
        story.append(Spacer(1, 4))
        
        linhas_fotos = []
        par_atual = []
        for f_path in fotos:
            if os.path.exists(f_path):
                img_obj = Image(f_path, width=250, height=180)
                par_atual.append(img_obj)
                if len(par_atual) == 2:
                    linhas_fotos.append(par_atual)
                    par_atual = []
        if par_atual:
            par_atual.append(Paragraph("", style_celula))
            linhas_fotos.append(par_atual)

        for par in linhas_fotos:
            t_foto = Table([par], colWidths=[277, 278])
            t_foto.setStyle(TableStyle([('ALIGN', (0,0), (-1,-1), 'CENTER'), ('VALIGN', (0,0), (-1,-1), 'MIDDLE'), ('BOTTOMPADDING', (0,0), (-1,-1), 6)]))
            story.append(t_foto)

    doc.build(story)
    buffer.seek(0)
    pdf_data = buffer.getvalue()

    nome_cliente_atual = st.session_state.get('cs_cliente', '').strip()
    if nome_cliente_atual:
        nome_pasta_cliente = "".join(c for c in nome_cliente_atual if c.isalnum() or c in (' ', '_', '-')).strip()
        cliente_dir = os.path.join(HISTORICO_CLIENTES_DIR, nome_pasta_cliente)
        os.makedirs(cliente_dir, exist_ok=True)
        
        data_hora_str = datetime.now().strftime('%Y%m%d_%H%M%S')
        nome_arq_pdf = f"Vistoria_Chamado_{data_hora_str}.pdf"
        caminho_completo_pdf = os.path.join(cliente_dir, nome_arq_pdf)
        
        with open(caminho_completo_pdf, "wb") as f_pdf:
            f_pdf.write(pdf_data)
            
        registrar_historico_cliente(
            nome_cliente_atual,
            "Relatório de Vistoria/Chamado Simples",
            {
                "arquivo_pdf": nome_arq_pdf,
                "resp_tecnico": st.session_state.get('cs_resp_tecnico', '')
            }
        )

    return pdf_data

def gerar_pdf_orcamento():
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=20, leftMargin=20, topMargin=20, bottomMargin=20)
    story = []
    styles = getSampleStyleSheet()
    
    style_celula = ParagraphStyle('CelTabela', parent=styles['Normal'], fontSize=8, leading=9, textColor=colors.black)
    style_texto_empresa = ParagraphStyle('EmpresaText', parent=styles['Normal'], fontSize=8, leading=10, textColor=colors.black)
    style_sec_header = ParagraphStyle('SecHeader', parent=styles['Normal'], fontSize=9, leading=11, fontName='Helvetica-Bold', textColor=colors.black)

    logo_w, logo_h = 45, 30
    if os.path.exists(LOGO_PATH):
        img_logo = Image(LOGO_PATH, width=logo_w, height=logo_h)
    else:
        img_logo = Paragraph("<b>LOGO</b>", style_celula)

    info_empresa_texto = f"""
    <b>{empresa_db.get('nome', '')}</b><br/>
    CNPJ: {empresa_db.get('cnpj', '')} | CREA: {empresa_db.get('crea', '')} | Tel: {empresa_db.get('telefone', '')}<br/>
    E-mail: {empresa_db.get('email', '')} | Endereço: {empresa_db.get('endereco', '')}<br/>
    <b>PROPOSTA COMERCIAL / ORÇAMENTO DE SERVIÇOS & MATERIAIS</b>
    """
    
    tabela_cabecalho = Table([[Paragraph(info_empresa_texto, style_texto_empresa), img_logo]], colWidths=[495, 60])
    tabela_cabecalho.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'), ('ALIGN', (1, 0), (1, 0), 'RIGHT'), ('BOTTOMPADDING', (0, 0), (-1, -1), 6)]))
    story.append(tabela_cabecalho)
    story.append(Spacer(1, 4))

    story.append(Paragraph("<b>1. DADOS DO CLIENTE</b>", style_sec_header))
    dados_edif = [
        [Paragraph(f"<b>CLIENTE:</b> {st.session_state.get('orc_cliente', '')}", style_celula), Paragraph(f"<b>Data da Proposta:</b> {st.session_state.get('orc_data', '')}", style_celula)],
        [Paragraph(f"<b>CNPJ:</b> {st.session_state.get('orc_cnpj', '')}", style_celula), Paragraph(f"<b>Validade da Proposta:</b> {st.session_state.get('orc_validade', '')}", style_celula)],
        [Paragraph(f"<b>Endereço:</b> {st.session_state.get('orc_endereco', '')}", style_celula), Paragraph(f"<b>Responsável Técnico:</b> {st.session_state.get('orc_resp_tecnico', '')}", style_celula)],
        [Paragraph(f"<b>Contato / E-mail:</b> {st.session_state.get('orc_contato', '')} | {st.session_state.get('orc_email', '')}", style_celula), Paragraph("", style_celula)],
    ]
    t_edif = Table(dados_edif, colWidths=[330, 225])
    t_edif.setStyle(TableStyle([('BOX', (0,0), (-1,-1), 0.5, colors.grey), ('INNERGRID', (0,0), (-1,-1), 0.25, colors.lightgrey), ('TOPPADDING', (0,0), (-1,-1), 2), ('BOTTOMPADDING', (0,0), (-1,-1), 2)]))
    story.append(t_edif)
    story.append(Spacer(1, 4))

    story.append(Paragraph("<b>2. ESCOPO DOS SERVIÇOS / FORNECIMENTO</b>", style_sec_header))
    escopo_texto = f"<b>Descrição Detalhada do Escopo:</b><br/>{st.session_state.get('orc_escopo', 'Nenhum escopo detalhado.')}"
    t_escopo = Table([[Paragraph(escopo_texto, style_celula)]], colWidths=[555])
    t_escopo.setStyle(TableStyle([('BOX', (0,0), (-1,-1), 0.5, colors.grey), ('TOPPADDING', (0,0), (-1,-1), 6), ('BOTTOMPADDING', (0,0), (-1,-1), 6)]))
    story.append(t_escopo)
    story.append(Spacer(1, 4))

    story.append(Paragraph("<b>3. VALOR TOTAL E CONDIÇÕES DE PAGAMENTO</b>", style_sec_header))
    valores_texto = f"""
    <b>Valor Total do Orçamento:</b> {st.session_state.get('orc_valores', '')}<br/>
    <b>Condições de Pagamento e Prazo:</b> {st.session_state.get('orc_pagamento', '')}
    """
    t_val = Table([[Paragraph(valores_texto, style_celula)]], colWidths=[555])
    t_val.setStyle(TableStyle([('BOX', (0,0), (-1,-1), 0.5, colors.grey), ('TOPPADDING', (0,0), (-1,-1), 6), ('BOTTOMPADDING', (0,0), (-1,-1), 6)]))
    story.append(t_val)
    story.append(Spacer(1, 6))

    story.append(Paragraph("<b>4. VALIDAÇÃO COMERCIAL</b>", style_sec_header))
    assinaturas_data = [[
        Paragraph(f"<b>Prestador:</b> {st.session_state.get('orc_resp_tecnico', '')}<br/>CNPJ: {empresa_db.get('cnpj', '')}<br/><br/><br/>________________________________________<br/>Assinatura / Emissor", style_celula),
        Paragraph(f"<b>De Acordo (Cliente):</b> {st.session_state.get('orc_cliente', '')}<br/><br/><br/><br/>________________________________________<br/>Aprovação do Cliente", style_celula)
    ]]
    t_ass = Table(assinaturas_data, colWidths=[277, 278])
    t_ass.setStyle(TableStyle([('BOX', (0,0), (-1,-1), 0.5, colors.grey), ('INNERGRID', (0,0), (-1,-1), 0.25, colors.lightgrey), ('TOPPADDING', (0,0), (-1,-1), 6), ('BOTTOMPADDING', (0,0), (-1,-1), 6)]))
    story.append(t_ass)

    doc.build(story)
    buffer.seek(0)
    pdf_data = buffer.getvalue()

    nome_cliente_atual = st.session_state.get('orc_cliente', '').strip()
    if nome_cliente_atual:
        nome_pasta_cliente = "".join(c for c in nome_cliente_atual if c.isalnum() or c in (' ', '_', '-')).strip()
        cliente_dir = os.path.join(HISTORICO_CLIENTES_DIR, nome_pasta_cliente)
        os.makedirs(cliente_dir, exist_ok=True)
        
        data_hora_str = datetime.now().strftime('%Y%m%d_%H%M%S')
        nome_arq_pdf = f"Orcamento_{data_hora_str}.pdf"
        caminho_completo_pdf = os.path.join(cliente_dir, nome_arq_pdf)
        
        with open(caminho_completo_pdf, "wb") as f_pdf:
            f_pdf.write(pdf_data)
            
        registrar_historico_cliente(
            nome_cliente_atual,
            "Proposta Comercial / Orçamento",
            {
                "arquivo_pdf": nome_arq_pdf,
                "valor": st.session_state.get('orc_valores', ''),
                "resp_tecnico": st.session_state.get('orc_resp_tecnico', '')
            }
        )

    return pdf_data

defaults_vistoria = {
    "cliente": "", "cnpj": "", "endereco": "", "cidade_uf": "Ribeirão Preto - SP",
    "sindico": "", "zelador": "", "contato": "", "email": "",
    "data_visita": datetime.now().strftime("%Y-%m-%d"),
    "tipo_visita": "Preventiva Trimestral",
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

defaults_chamado_simples = {
    "cs_cliente": "", "cs_cnpj": "", "cs_endereco": "", "cs_cidade_uf": "Ribeirão Preto - SP",
    "cs_acompanhante": "", "cs_data": datetime.now().strftime("%Y-%m-%d"),
    "cs_tipo": "Atendimento Corretivo / Chamado Técnico",
    "cs_resp_tecnico": empresa_db.get("resp_tecnico", "Eli Silva"),
    "cs_central_sdai": "", "cs_tipo_central": "SISTEMA ENDEREÇÁVEL", "cs_qtd_lacos": "",
    "cs_relato": "", "cs_fotos_carregadas": []
}

for k, v in defaults_chamado_simples.items():
    if k not in st.session_state:
        st.session_state[k] = v

defaults_orcamento = {
    "orc_cliente": "", "orc_cnpj": "", "orc_endereco": "", "orc_contato": "", "orc_email": "",
    "orc_data": datetime.now().strftime("%Y-%m-%d"), "orc_validade": "10 Dias",
    "orc_resp_tecnico": empresa_db.get("resp_tecnico", "Eli Silva"),
    "orc_escopo": "", "orc_valores": "", "orc_pagamento": ""
}

for k, v in defaults_orcamento.items():
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

st.sidebar.title(f"Bem-vindo, {st.session_state['user']}")
if st.sidebar.button("🚪 Sair / Logout"):
    st.session_state["logged_in"] = False
    st.rerun()

st.sidebar.divider()
menu_opcao = st.sidebar.radio(
    "Menu Principal",
    [
        "📋 Vistoria & Relatório Técnico",
        "🛠️ Vistoria Simples / Chamado",
        "💰 Orçamento Comercial",
        "🏢 Cadastro de Clientes & SDAI",
        "📂 Histórico & Pasta do Cliente"
    ]
)

# --- ROTAS DA APLICAÇÃO ---

if menu_opcao == "📋 Vistoria & Relatório Técnico":
    st.title("📋 Relatório de Inspeção Preventiva & Manutenção Normada")
    
    with st.expander("1. Dados da Edificação", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            st.session_state['cliente'] = st.text_input("Cliente / Edif.", value=st.session_state['cliente'])
            st.session_state['cnpj'] = st.text_input("CNPJ", value=st.session_state['cnpj'])
            st.session_state['endereco'] = st.text_input("Endereço", value=st.session_state['endereco'])
            st.session_state['cidade_uf'] = st.text_input("Cidade / UF", value=st.session_state['cidade_uf'])
        with col2:
            st.session_state['data_visita'] = st.text_input("Data da Visita", value=st.session_state['data_visita'])
            st.session_state['tipo_visita'] = st.text_input("Tipo de Visita", value=st.session_state['tipo_visita'])
            st.session_state['resp_tecnico'] = st.text_input("Responsável Técnico", value=st.session_state['resp_tecnico'])
            st.session_state['acompanhante'] = st.text_input("Acompanhante / Portaria", value=st.session_state['acompanhante'])
        
        col3, col4, col5 = st.columns(3)
        with col3:
            st.session_state['sindico'] = st.text_input("Síndico", value=st.session_state['sindico'])
        with col4:
            st.session_state['zelador'] = st.text_input("Zelador", value=st.session_state['zelador'])
        with col5:
            st.session_state['contato'] = st.text_input("Contato / E-mail", value=st.session_state['contato'])
        st.session_state['email'] = st.text_input("E-mail principal", value=st.session_state['email'])
        st.session_state['status_geral'] = st.text_input("Status Geral Parecer", value=st.session_state['status_geral'])

    with st.expander("2. Características Técnicas do Sistema", expanded=False):
        col1, col2, col3 = st.columns(3)
        with col1:
            st.session_state['central_sdai'] = st.text_input("Central SDAI (Marca/Modelo)", value=st.session_state['central_sdai'])
            st.session_state['det_fumaca'] = st.text_input("Detectores Fumaça/Térmicos (Qtd)", value=st.session_state['det_fumaca'])
        with col2:
            st.session_state['tipo_central'] = st.text_input("Tipo Central", value=st.session_state['tipo_central'])
            st.session_state['acionadores'] = st.text_input("Acionadores Manuais (Qtd)", value=st.session_state['acionadores'])
        with col3:
            st.session_state['qtd_lacos'] = st.text_input("Qtd. Laços / Zonas", value=st.session_state['qtd_lacos'])
            st.session_state['avisadores'] = st.text_input("Avisadores Sonoros/Visuais (Qtd)", value=st.session_state['avisadores'])
        
        col4, col5 = st.columns(2)
        with col4:
            st.session_state['pressurizacao'] = st.text_input("Pressurização Escada (IT 13)", value=st.session_state['pressurizacao'])
        with col5:
            st.session_state['tensao_baterias'] = st.text_input("Tensão & Baterias Nominais", value=st.session_state['tensao_baterias'])

    for sec_key, sec_title in [
        ("sec3", "3. Verificação Física e Elétrica da Central e Fontes"),
        ("sec4", "4. Integridade das Linhas de Sinal (Laços)"),
        ("sec5", "5. Ensaios Funcionais & Amostragem de Periféricos"),
        ("sec6", "6. Pressurização de Escadas de Segurança & Interligações (IT 13)")
    ]:
        with st.expander(sec_title, expanded=False):
            for idx, item in enumerate(ITENS_SECOES[sec_key]):
                st.markdown(f"**{item[0]}** — *{item[1]}*")
                c1, c2, c3 = st.columns([1, 1, 2])
                with c1:
                    st.session_state[f"{sec_key}_{idx}_val"] = st.text_input("Valor Medido", value=st.session_state.get(f"{sec_key}_{idx}_val", ""), key=f"inp_{sec_key}_{idx}_val")
                with c2:
                    st.session_state[f"{sec_key}_{idx}_status"] = st.selectbox("Status", ["CONFORME", "NÃO CONFORME", "N/A"], index=0 if st.session_state.get(f"{sec_key}_{idx}_status")=="CONFORME" else 0, key=f"inp_{sec_key}_{idx}_stat")
                with c3:
                    st.session_state[f"{sec_key}_{idx}_obs"] = st.text_input("Observações", value=st.session_state.get(f"{sec_key}_{idx}_obs", ""), key=f"inp_{sec_key}_{idx}_obs")
                st.divider()

    with st.expander("7. Conclusão Técnica e Orientações", expanded=False):
        st.session_state['parecer'] = st.text_area("Parecer Técnico / Conclusão", value=st.session_state['parecer'])
        st.session_state['orientacoes'] = st.text_area("Orientações Operacionais", value=st.session_state['orientacoes'])

    with st.expander("8. Registro Fotográfico", expanded=False):
        uploaded_files = st.file_uploader("Enviar fotos da vistoria", type=["png", "jpg", "jpeg"], accept_multiple_files=True, key="up_fotos_prev")
        if uploaded_files:
            caminhos_temp = []
            for file in uploaded_files:
                path_foto = os.path.join(PASTA_FOTOS_VISTORIA, file.name)
                with open(path_foto, "wb") as f:
                    f.write(file.getbuffer())
                caminhos_temp.append(path_foto)
            st.session_state["fotos_carregadas"] = caminhos_temp
            st.success(f"{len(caminhos_temp)} foto(s) carregada(s) com sucesso!")

    st.markdown("### Gerar Relatório PDF")
    if st.button("🚀 Gerar PDF de Inspeção Preventiva", type="primary"):
        pdf_bytes = gerar_pdf_preventiva()
        st.success("Relatório gerado com sucesso e salvo na pasta do cliente!")
        st.download_button(
            label="📥 Baixar PDF da Preventiva",
            data=pdf_bytes,
            file_name="relatorio_preventiva.pdf",
            mime="application/pdf"
        )

elif menu_opcao == "🛠️ Vistoria Simples / Chamado":
    st.title("🛠️ Vistoria Simples / Atendimento Corretivo / Chamado")
    
    with st.form("form_chamado"):
        c1, c2 = st.columns(2)
        with c1:
            st.session_state['cs_cliente'] = st.text_input("Cliente", value=st.session_state['cs_cliente'])
            st.session_state['cs_cnpj'] = st.text_input("CNPJ", value=st.session_state['cs_cnpj'])
            st.session_state['cs_endereco'] = st.text_input("Endereço", value=st.session_state['cs_endereco'])
        with c2:
            st.session_state['cs_cidade_uf'] = st.text_input("Cidade / UF", value=st.session_state['cs_cidade_uf'])
            st.session_state['cs_acompanhante'] = st.text_input("Solicitante / Contato", value=st.session_state['cs_acompanhante'])
            st.session_state['cs_data'] = st.text_input("Data do Atendimento", value=st.session_state['cs_data'])
        
        st.session_state['cs_tipo'] = st.selectbox("Tipo de Atendimento", ["Atendimento Corretivo / Chamado Técnico", "Vistoria Simples", "Visita Técnica Avulsa"], index=0)
        
        c3, c4, c5 = st.columns(3)
        with c3:
            st.session_state['cs_central_sdai'] = st.text_input("Central SDAI", value=st.session_state['cs_central_sdai'])
        with c4:
            st.session_state['cs_tipo_central'] = st.text_input("Tipo Central", value=st.session_state['cs_tipo_central'])
        with c5:
            st.session_state['cs_qtd_lacos'] = st.text_input("Qtd. Laços / Zonas", value=st.session_state['cs_qtd_lacos'])
            
        st.session_state['cs_relato'] = st.text_area("Relatório / Escopo Executado / Ocorrência", value=st.session_state['cs_relato'])
        
        uploaded_files_cs = st.file_uploader("Fotos do Atendimento (Opcional)", type=["png", "jpg", "jpeg"], accept_multiple_files=True, key="up_fotos_cs")
        
        btn_gerar_cs = st.form_submit_button("Gerar PDF de Chamado Simples", type="primary")
        if btn_gerar_cs:
            if uploaded_files_cs:
                caminhos_temp_cs = []
                for file in uploaded_files_cs:
                    path_foto = os.path.join(PASTA_FOTOS_VISTORIA, file.name)
                    with open(path_foto, "wb") as f:
                        f.write(file.getbuffer())
                    caminhos_temp_cs.append(path_foto)
                st.session_state["cs_fotos_carregadas"] = caminhos_temp_cs
            
            pdf_bytes_cs = gerar_pdf_chamado_simples()
            st.success("Relatório de chamado gerado e salvo com sucesso!")
            st.download_button(
                label="📥 Baixar PDF do Chamado",
                data=pdf_bytes_cs,
                file_name="relatorio_chamado.pdf",
                mime="application/pdf"
            )

elif menu_opcao == "💰 Orçamento Comercial":
    st.title("💰 Proposta Comercial / Orçamento")
    
    with st.form("form_orcamento"):
        c1, c2 = st.columns(2)
        with c1:
            st.session_state['orc_cliente'] = st.text_input("Cliente", value=st.session_state['orc_cliente'])
            st.session_state['orc_cnpj'] = st.text_input("CNPJ", value=st.session_state['orc_cnpj'])
            st.session_state['orc_endereco'] = st.text_input("Endereço", value=st.session_state['orc_endereco'])
        with c2:
            st.session_state['orc_contato'] = st.text_input("Contato", value=st.session_state['orc_contato'])
            st.session_state['orc_email'] = st.text_input("E-mail", value=st.session_state['orc_email'])
            st.session_state['orc_validade'] = st.text_input("Validade da Proposta", value=st.session_state['orc_validade'])
            
        st.session_state['orc_escopo'] = st.text_area("Descrição Detalhada do Escopo / Materiais / Serviços", value=st.session_state['orc_escopo'])
        
        c3, c4 = st.columns(2)
        with c3:
            st.session_state['orc_valores'] = st.text_input("Valor Total do Orçamento (Ex: R$ 5.000,00)", value=st.session_state['orc_valores'])
        with c4:
            st.session_state['orc_pagamento'] = st.text_input("Condições de Pagamento", value=st.session_state['orc_pagamento'])
            
        btn_gerar_orc = st.form_submit_button("Gerar PDF de Orçamento", type="primary")
        if btn_gerar_orc:
            pdf_bytes_orc = gerar_pdf_orcamento()
            st.success("Orçamento gerado e salvo com sucesso!")
            st.download_button(
                label="📥 Baixar PDF da Proposta Comercial",
                data=pdf_bytes_orc,
                file_name="proposta_comercial.pdf",
                mime="application/pdf"
            )

elif menu_opcao == "🏢 Cadastro de Clientes & SDAI":
    st.title("🏢 Gestão de Clientes e Equipamentos SDAI")
    
    nome_cliente_busca = st.text_input("Nome do Cliente para Cadastrar/Editar")
    if nome_cliente_busca:
        cliente_key = nome_cliente_busca.strip()
        dados_cli = clientes_db.get(cliente_key, {})
        
        with st.form("form_cad_cliente"):
            st.subheader(f"Dados Cadastrais: {cliente_key}")
            cnpj_cli = st.text_input("CNPJ", value=dados_cli.get("cnpj", ""))
            end_cli = st.text_input("Endereço", value=dados_cli.get("endereco", ""))
            cidade_cli = st.text_input("Cidade/UF", value=dados_cli.get("cidade_uf", "Ribeirão Preto - SP"))
            sindico_cli = st.text_input("Síndico / Responsável", value=dados_cli.get("sindico", ""))
            contato_cli = st.text_input("Telefone / Contato", value=dados_cli.get("contato", ""))
            email_cli = st.text_input("E-mail", value=dados_cli.get("email", ""))
            
            st.markdown("---")
            st.markdown("### Configuração do Sistema SDAI no Local")
            central_cli = st.text_input("Central SDAI (Modelo)", value=dados_cli.get("central_sdai", ""))
            tipo_cent_cli = st.text_input("Tipo de Central", value=dados_cli.get("tipo_central", "SISTEMA ENDEREÇÁVEL"))
            lacos_cli = st.text_input("Qtd. Laços / Zonas", value=dados_cli.get("lacos", ""))
            
            btn_salvar_cli = st.form_submit_button("Salvar Cadastro do Cliente")
            if btn_salvar_cli:
                clientes_db[cliente_key] = {
                    "cnpj": cnpj_cli,
                    "endereco": end_cli,
                    "cidade_uf": cidade_cli,
                    "sindico": sindico_cli,
                    "contato": contato_cli,
                    "email": email_cli,
                    "central_sdai": central_cli,
                    "tipo_central": tipo_cent_cli,
                    "lacos": lacos_cli
                }
                salvar_json(CLIENTES_FILE, clientes_db)
                st.success(f"Cliente '{cliente_key}' salvo com sucesso!")

    st.markdown("### Clientes Cadastrados Atualmente")
    if clientes_db:
        df_cli = pd.DataFrame.from_dict(clientes_db, orient="index")
        st.dataframe(df_cli, use_container_width=True)
    else:
        st.info("Nenhum cliente cadastrado no momento.")

elif menu_opcao == "📂 Histórico & Pasta do Cliente":
    st.title("📂 Histórico de Atendimentos & Documentos por Cliente")
    
    if os.path.exists(HISTORICO_CLIENTES_DIR):
        pastas_clientes = [d for d in os.listdir(HISTORICO_CLIENTES_DIR) if os.path.isdir(os.path.join(HISTORICO_CLIENTES_DIR, d))]
        if pastas_clientes:
            cliente_selecionado = st.selectbox("Selecione o Cliente", pastas_clientes)
            if cliente_selecionado:
                caminho_pasta_cli = os.path.join(HISTORICO_CLIENTES_DIR, cliente_selecionado)
                historico_path = os.path.join(caminho_pasta_cli, "historico_atendimentos.json")
                
                st.subheader(f"Histórico de: {cliente_selecionado}")
                
                if os.path.exists(historico_path):
                    try:
                        with open(historico_path, "r", encoding="utf-8") as f:
                            hist_data = json.load(f)
                        
                        for h in reversed(hist_data):
                            with st.container():
                                st.markdown(f"**Ação / Tipo:** {h.get('tipo', 'N/A')} — *Data: {h.get('data', 'N/A')}*")
                                if "arquivo_pdf" in h:
                                    arq_pdf = h["arquivo_pdf"]
                                    caminho_pdf_completo = os.path.join(caminho_pasta_cli, arq_pdf)
                                    if os.path.exists(caminho_pdf_completo):
                                        with open(caminho_pdf_completo, "rb") as pdf_file:
                                            st.download_button(
                                                label=f"📥 Baixar PDF ({arq_pdf})",
                                                data=pdf_file.read(),
                                                file_name=arq_pdf,
                                                mime="application/pdf",
                                                key=f"dl_{cliente_selecionado}_{arq_pdf}"
                                            )
                                st.json(h, expanded=False)
                                st.divider()
                    except Exception as e:
                        st.error(f"Erro ao ler histórico: {e}")
                else:
                    st.info("Nenhum registro de atendimento encontrado para este cliente.")
                
                st.markdown("### Arquivos na Pasta do Cliente")
                arquivos_pasta = os.listdir(caminho_pasta_cli)
                for arq in arquivos_pasta:
                    if arq != "historico_atendimentos.json":
                        st.text(f"📄 {arq}")
        else:
            st.info("Nenhuma pasta de cliente registrada ainda.")
    else:
        st.info("Diretório de histórico vazio.")
