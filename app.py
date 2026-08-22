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
menu_admin = st.sidebar.radio(
    "Menu Principal",
    [
        "📋 Vistoria & Relatório Técnico",
        "🛠️ Vistoria Simples / Chamado",
        "💰 Orçamento Comercial",
        "🏢 Cadastro de Clientes & SDAI",
        "📂 Histórico & Pasta do Cliente",
        "🏢 Dados da Minha Empresa",
        "📋 Chamados",
        "👥 Gerenciar Usuários"
    ]
)

# --- ABA 3.1: VISTORIA & RELATÓRIO TÉCNICO ---
if "📋 Vistoria & Relatório Técnico" in menu_admin:
    st.header("📋 Inspeção Preventiva & Relatório NBR 17240")

    def processar_upload_rascunho():
        arquivo = st.session_state.get("uploader_rascunho")
        if arquivo is not None:
            try:
                rascunho_carregado = json.load(arquivo)
                for k, v in rascunho_carregado.items():
                    st.session_state[k] = v
                st.session_state["_sucesso_rascunho"] = True
            except Exception as e:
                st.session_state["_erro_rascunho"] = str(e)

    with st.expander("💾 Salvar / Carregar Rascunho do Relatório", expanded=True):
        col_rasc1, col_rasc2 = st.columns(2)
        
        with col_rasc1:
            st.write("**Exportar Rascunho Atual**")
            dados_rascunho = {}
            for k, v in st.session_state.items():
                if k not in ["logged_in", "user", "perfil"] and not k.startswith("uploader_") and not k.startswith("_"):
                    try:
                        json.dumps(v)
                        dados_rascunho[k] = v
                    except:
                        pass

            json_str = json.dumps(dados_rascunho, ensure_ascii=False, indent=4)
            st.download_button(
                label="📥 Baixar Arquivo de Rascunho (.json)",
                data=json_str,
                file_name=f"rascunho_vistoria_{datetime.now().strftime('%Y%m%d_%H%M')}.json",
                mime="application/json",
                use_container_width=True
            )
            
        with col_rasc2:
            st.write("**Importar Rascunho Salvo**")
            st.file_uploader(
                "Enviar arquivo .json salvo anteriormente", 
                type=["json"], 
                key="uploader_rascunho", 
                on_change=processar_upload_rascunho
            )
            if st.session_state.get("_sucesso_rascunho"):
                st.success("✅ Rascunho carregado e campos recuperados com sucesso!")
                st.session_state["_sucesso_rascunho"] = False
            if st.session_state.get("_erro_rascunho"):
                st.error(f"Erro ao ler rascunho: {st.session_state['_erro_rascunho']}")
                st.session_state["_erro_rascunho"] = None

    st.divider()
    
    if clientes_db:
        st.subheader("📁 Carregar Cliente Cadastrado")
        lista_clientes_nomes = ["-- Selecione --"] + list(clientes_db.keys())
        
        def ao_selecionar_cliente():
            cli_nome = st.session_state["select_carregar_cliente"]
            if cli_nome != "-- Selecione --" and cli_nome in clientes_db:
                c_info = clientes_db[cli_nome]
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

        st.selectbox("Selecione o Cliente", lista_clientes_nomes, key="select_carregar_cliente", on_change=ao_selecionar_cliente)

    st.divider()
    st.subheader("📝 Edição dos Dados Gerais da Visita")
    
    col1, col2 = st.columns(2)
    with col1:
        st.text_input("Cliente / Condomínio", key="cliente")
        st.text_input("CNPJ do Cliente", key="cnpj")
        st.text_input("Endereço", key="endereco")
        st.text_input("Cidade / UF", key="cidade_uf")
        st.text_input("Síndico", key="sindico")
        st.text_input("Zelador", key="zelador")
    with col2:
        st.text_input("Contato / Tel", key="contato")
        st.text_input("E-mail", key="email")
        st.text_input("Data da Visita (AAAA-MM-DD ou DD/MM/AAAA)", key="data_visita")
        st.text_input("Tipo de Visita", key="tipo_visita")
        st.text_input("Responsável Técnico", key="resp_tecnico")
        st.text_input("Acompanhante / Portaria", key="acompanhante")

    st.selectbox(
        "Status Geral / Parecer",
        ["CONFORME / SISTEMA OPERACIONAL", "CONFORME COM RESSALVAS", "NÃO CONFORME / INTERLIGADO COM FALHAS"],
        key="status_geral"
    )

    st.divider()
    st.subheader("⚙️ Características Técnicas do Sistema")
    col_t1, col_t2, col_t3 = st.columns(3)
    with col_t1:
        st.text_input("Central SDAI", key="central_sdai")
        st.text_input("Tipo Central", key="tipo_central")
    with col_t2:
        st.text_input("Qtd. Laços / Zonas", key="qtd_lacos")
        st.text_input("Detectores Fumaça/Térmicos", key="det_fumaca")
    with col_t3:
        st.text_input("Acionadores Manuais", key="acionadores")
        st.text_input("Avisadores Sonoros/Visuais", key="avisadores")

    col_t4, col_t5 = st.columns(2)
    with col_t4:
        st.text_input("Pressurização Escada (IT 13)", key="pressurizacao")
    with col_t5:
        st.text_input("Tensão & Baterias Nominais", key="tensao_baterias")

    st.divider()
    st.subheader("🔍 Verificação dos Itens Normativos (Checklist)")

    sec_nomes = {
        "sec3": "3. Verificação Física e Elétrica da Central e Fontes",
        "sec4": "4. Integridade das Linhas de Sinal (Laços)",
        "sec5": "5. Ensios Funcionais & Amostragem de Periféricos",
        "sec6": "6. Pressurização de Escadas de Segurança (IT 13)"
    }

    for sec_key, sec_title in sec_nomes.items():
        with st.expander(sec_title, expanded=False):
            for idx, item in enumerate(ITENS_SECOES[sec_key]):
                st.markdown(f"**{item[0]}** — *Ref: {item[1]}*")
                col_i1, col_i2, col_i3 = st.columns([1.5, 3, 1])
                with col_i1:
                    st.text_input(f"Valor Medido ({item[0]})", key=f"{sec_key}_{idx}_val")
                with col_i2:
                    st.text_input(f"Observação ({item[0]})", key=f"{sec_key}_{idx}_obs")
                with col_i3:
                    st.selectbox(f"Status ({item[0]})", ["CONFORME", "NÃO CONFORME", "N/A"], key=f"{sec_key}_{idx}_status")
                st.divider()

    st.subheader("📋 Conclusão e Orientações")
    st.text_area("Conclusão Técnica / Parecer", key="parecer", height=80)
    st.text_area("Orientações Operacionais", key="orientacoes", height=80)

    st.subheader("📸 Relatório Fotográfico Complementar")
    uploaded_fotos = st.file_uploader("Enviar Fotos da Vistoria", type=["png", "jpg", "jpeg"], accept_multiple_files=True, key="uploader_fotos")
    if uploaded_fotos:
        for foto in uploaded_fotos:
            f_path = os.path.join(PASTA_FOTOS_VISTORIA, foto.name)
            with open(f_path, "wb") as f:
                f.write(foto.getbuffer())
            if f_path not in st.session_state["fotos_carregadas"]:
                st.session_state["fotos_carregadas"].append(f_path)
        st.success("✅ Fotos carregadas com sucesso!")

    if st.session_state["fotos_carregadas"]:
        st.write(f"Total de fotos anexadas: {len(st.session_state['fotos_carregadas'])}")
        if st.button("🗑️ Limpar Fotos Anexadas"):
            st.session_state["fotos_carregadas"] = []
            st.rerun()

    st.divider()
    
    st.subheader("📄 Geração do Relatório PDF")
    pdf_bytes = gerar_pdf_preventiva()
    nome_arquivo_pdf = f"Relatorio_SDAI_{st.session_state['cliente'].replace(' ', '_') if st.session_state['cliente'] else 'Geral'}_{datetime.now().strftime('%Y%m%d')}.pdf"
    
    st.download_button(
        label="📄 GERAR, SALVAR NA PASTA E BAIXAR RELATÓRIO PDF",
        data=pdf_bytes,
        file_name=nome_arquivo_pdf,
        mime="application/pdf",
        type="primary",
        use_container_width=True
    )

elif "🛠️ Vistoria Simples / Chamado" in menu_admin:
    st.header("🛠️ Relatório Simples de Vistoria / Chamado Técnico")
    st.info("Formulário simplificado com dados do cliente, informações do SDAI e um campo aberto para digitação do relato técnico e anexo opcional de fotos.")

    def processar_upload_rascunho_cs():
        arquivo = st.session_state.get("uploader_rascunho_cs")
        if arquivo is not None:
            try:
                rascunho_carregado = json.load(arquivo)
                for k, v in rascunho_carregado.items():
                    st.session_state[k] = v
                st.session_state["_sucesso_rascunho_cs"] = True
            except Exception as e:
                st.session_state["_erro_rascunho_cs"] = str(e)

    with st.expander("💾 Salvar / Carregar Rascunho deste Atendimento", expanded=True):
        col_rasc1, col_rasc2 = st.columns(2)
        with col_rasc1:
            st.write("**Exportar Rascunho Atual**")
            dados_rascunho_cs = {}
            for k, v in st.session_state.items():
                if k.startswith("cs_") or k in ["resp_tecnico"]:
                    try:
                        json.dumps(v)
                        dados_rascunho_cs[k] = v
                    except:
                        pass
            json_str_cs = json.dumps(dados_rascunho_cs, ensure_ascii=False, indent=4)
            st.download_button(
                label="📥 Baixar Rascunho (.json)",
                data=json_str_cs,
                file_name=f"rascunho_chamado_simples_{datetime.now().strftime('%Y%m%d_%H%M')}.json",
                mime="application/json",
                use_container_width=True
            )
        with col_rasc2:
            st.write("**Importar Rascunho Salvo**")
            st.file_uploader("Enviar arquivo .json", type=["json"], key="uploader_rascunho_cs", on_change=processar_upload_rascunho_cs)
            if st.session_state.get("_sucesso_rascunho_cs"):
                st.success("✅ Rascunho carregado com sucesso!")
                st.session_state["_sucesso_rascunho_cs"] = False
            if st.session_state.get("_erro_rascunho_cs"):
                st.error(f"Erro ao ler rascunho: {st.session_state['_erro_rascunho_cs']}")
                st.session_state["_erro_rascunho_cs"] = None

    st.divider()

    if clientes_db:
        st.subheader("📁 Puxar Dados de Cliente Cadastrado")
        lista_clientes_nomes_cs = ["-- Selecione --"] + list(clientes_db.keys())
        def ao_selecionar_cliente_cs():
            cli_nome = st.session_state["select_carregar_cliente_cs"]
            if cli_nome != "-- Selecione --" and cli_nome in clientes_db:
                c_info = clientes_db[cli_nome]
                st.session_state["cs_cliente"] = c_info.get("nome", "")
                st.session_state["cs_cnpj"] = c_info.get("cnpj", "")
                st.session_state["cs_endereco"] = c_info.get("endereco", "")
                st.session_state["cs_cidade_uf"] = c_info.get("cidade_uf", "")
                st.session_state["cs_central_sdai"] = c_info.get("central_sdai", "")
                st.session_state["cs_tipo_central"] = c_info.get("tipo_central", "")
                st.session_state["cs_qtd_lacos"] = c_info.get("qtd_lacos", "")
        st.selectbox("Selecione o Cliente", lista_clientes_nomes_cs, key="select_carregar_cliente_cs", on_change=ao_selecionar_cliente_cs)

    st.divider()
    st.subheader("📝 Dados Gerais")
    col_cs1, col_cs2 = st.columns(2)
    with col_cs1:
        st.text_input("Cliente / Empresa", key="cs_cliente")
        st.text_input("CNPJ", key="cs_cnpj")
        st.text_input("Endereço", key="cs_endereco")
        st.text_input("Cidade / UF", key="cs_cidade_uf")
    with col_cs2:
        st.text_input("Solicitante / Contato no Local", key="cs_acompanhante")
        st.text_input("Data do Atendimento", key="cs_data")
        st.text_input("Tipo de Atendimento", key="cs_tipo")
        st.text_input("Responsável Técnico", key="cs_resp_tecnico")

    st.divider()
    st.subheader("⚙️ Informações Técnicas do SDAI")
    col_tc1, col_tc2, col_tc3 = st.columns(3)
    with col_tc1:
        st.text_input("Central SDAI", key="cs_central_sdai")
    with col_tc2:
        st.text_input("Tipo Central", key="cs_tipo_central")
    with col_tc3:
        st.text_input("Qtd. Laços / Zonas", key="cs_qtd_lacos")

    st.divider()
    st.subheader("📄 Relato Técnico / Escopo Executado")
    st.text_area("Descreva detalhadamente a vistoria, o chamado ou os serviços executados:", key="cs_relato", height=150)

    st.subheader("📸 Registro Fotográfico do Atendimento")
    uploaded_fotos_cs = st.file_uploader("Enviar Fotos", type=["png", "jpg", "jpeg"], accept_multiple_files=True, key="uploader_fotos_cs")
    if uploaded_fotos_cs:
        for foto in uploaded_fotos_cs:
            f_path = os.path.join(PASTA_FOTOS_VISTORIA, foto.name)
            with open(f_path, "wb") as f:
                f.write(foto.getbuffer())
            if f_path not in st.session_state["cs_fotos_carregadas"]:
                st.session_state["cs_fotos_carregadas"].append(f_path)
        st.success("✅ Fotos carregadas com sucesso!")

    if st.session_state["cs_fotos_carregadas"]:
        st.write(f"Total de fotos anexadas: {len(st.session_state['cs_fotos_carregadas'])}")
        if st.button("🗑️ Limpar Fotos Anexadas", key="btn_limpar_fotos_cs"):
            st.session_state["cs_fotos_carregadas"] = []
            st.rerun()

    st.divider()
    pdf_bytes_cs = gerar_pdf_chamado_simples()
    nome_arq_cs = f"Relatorio_Simples_{st.session_state['cs_cliente'].replace(' ', '_') if st.session_state['cs_cliente'] else 'Geral'}_{datetime.now().strftime('%Y%m%d')}.pdf"
    
    st.download_button(
        label="📄 GERAR, SALVAR NA PASTA DO CLIENTE E BAIXAR PDF",
        data=pdf_bytes_cs,
        file_name=nome_arq_cs,
        mime="application/pdf",
        type="primary",
        use_container_width=True
    )

elif "💰 Orçamento Comercial" in menu_admin:
    st.header("💰 Elaboração de Orçamento Comercial")
    st.info("Puxe os dados cadastrados do cliente, defina o escopo de serviços/materiais, os valores e as condições de pagamento.")

    def processar_upload_rascunho_orc():
        arquivo = st.session_state.get("uploader_rascunho_orc")
        if arquivo is not None:
            try:
                rascunho_carregado = json.load(arquivo)
                for k, v in rascunho_carregado.items():
                    st.session_state[k] = v
                st.session_state["_sucesso_rascunho_orc"] = True
            except Exception as e:
                st.session_state["_erro_rascunho_orc"] = str(e)

    with st.expander("💾 Salvar / Carregar Rascunho do Orçamento", expanded=True):
        col_rasc1, col_rasc2 = st.columns(2)
        with col_rasc1:
            st.write("**Exportar Rascunho Atual**")
            dados_rascunho_orc = {}
            for k, v in st.session_state.items():
                if k.startswith("orc_"):
                    try:
                        json.dumps(v)
                        dados_rascunho_orc[k] = v
                    except:
                        pass
            json_str_orc = json.dumps(dados_rascunho_orc, ensure_ascii=False, indent=4)
            st.download_button(
                label="📥 Baixar Rascunho (.json)",
                data=json_str_orc,
                file_name=f"rascunho_orcamento_{datetime.now().strftime('%Y%m%d_%H%M')}.json",
                mime="application/json",
                use_container_width=True
            )
        with col_rasc2:
            st.write("**Importar Rascunho Salvo**")
            st.file_uploader("Enviar arquivo .json", type=["json"], key="uploader_rascunho_orc", on_change=processar_upload_rascunho_orc)
            if st.session_state.get("_sucesso_rascunho_orc"):
                st.success("✅ Rascunho carregado com sucesso!")
                st.session_state["_sucesso_rascunho_orc"] = False
            if st.session_state.get("_erro_rascunho_orc"):
                st.error(f"Erro ao ler rascunho: {st.session_state['_erro_rascunho_orc']}")
                st.session_state["_erro_rascunho_orc"] = None

    st.divider()

    if clientes_db:
        st.subheader("📁 Puxar Dados do Cliente Cadastrado")
        lista_clientes_nomes_orc = ["-- Selecione --"] + list(clientes_db.keys())
        def ao_selecionar_cliente_orc():
            cli_nome = st.session_state["select_carregar_cliente_orc"]
            if cli_nome != "-- Selecione --" and cli_nome in clientes_db:
                c_info = clientes_db[cli_nome]
                st.session_state["orc_cliente"] = c_info.get("nome", "")
                st.session_state["orc_cnpj"] = c_info.get("cnpj", "")
                st.session_state["orc_endereco"] = f"{c_info.get('endereco', '')} - {c_info.get('cidade_uf', '')}"
                st.session_state["orc_contato"] = c_info.get("contato", "")
                st.session_state["orc_email"] = c_info.get("email", "")
        st.selectbox("Selecione o Cliente", lista_clientes_nomes_orc, key="select_carregar_cliente_orc", on_change=ao_selecionar_cliente_orc)

    st.divider()
    st.subheader("📝 Dados Comerciais")
    col_orc1, col_orc2 = st.columns(2)
    with col_orc1:
        st.text_input("Cliente / Condomínio", key="orc_cliente")
        st.text_input("CNPJ", key="orc_cnpj")
        st.text_input("Endereço Completo", key="orc_endereco")
    with col_orc2:
        st.text_input("Telefone de Contato", key="orc_contato")
        st.text_input("E-mail", key="orc_email")
        st.text_input("Data da Proposta", key="orc_data")
        st.text_input("Validade da Proposta", key="orc_validade")
        st.text_input("Responsável Técnico / Emissor", key="orc_resp_tecnico")

    st.divider()
    st.subheader("🛠️ Escopo dos Serviços e Fornecimento")
    st.text_area("Descreva detalhadamente o escopo técnico, equipamentos, materiais e mão de obra inclusos:", key="orc_escopo", height=150)

    st.subheader("💵 Valores e Condições de Pagamento")
    st.text_input("Valor Total (Ex: R$ 3.500,00)", key="orc_valores")
    st.text_area("Prazo de Execução e Condições de Pagamento (Ex: 50% de entrada e 50% após conclusão; Prazo de entrega: 5 dias úteis)", key="orc_pagamento", height=80)

    st.divider()
    pdf_bytes_orc = gerar_pdf_orcamento()
    nome_arq_orc = f"Orcamento_{st.session_state['orc_cliente'].replace(' ', '_') if st.session_state['orc_cliente'] else 'Geral'}_{datetime.now().strftime('%Y%m%d')}.pdf"
    
    st.download_button(
        label="📄 GERAR, SALVAR NA PASTA DO CLIENTE E BAIXAR ORÇAMENTO PDF",
        data=pdf_bytes_orc,
        file_name=nome_arq_orc,
        mime="application/pdf",
        type="primary",
        use_container_width=True
    )

elif "🏢 Cadastro de Clientes & SDAI" in menu_admin:
    st.header("🏢 Gestão de Clientes e Equipamentos SDAI")
    tab_c1, tab_c2, tab_c3 = st.tabs([
        "➕ Adicionar / Editar Cliente", 
        "📋 Lista de Clientes Cadastrados", 
        "📊 Importar / Exportar Planilha"
    ])

    with tab_c1:
        with st.form("form_cad_cliente"):
            c_nome_cad = st.text_input("Nome do Condomínio / Empresa")
            c_cnpj_cad = st.text_input("CNPJ")
            c_end_cad = st.text_input("Endereço")
            c_cid_cad = st.text_input("Cidade / UF", value="Ribeirão Preto - SP")
            c_sind_cad = st.text_input("Síndico / Administração")
            c_zel_cad = st.text_input("Zelador")
            c_tel_cad = st.text_input("Telefone de Contato")
            c_email_cad = st.text_input("E-mail")
            
            st.markdown("---")
            st.subheader("Configuração do SDAI do Cliente")
            c_csdai = st.text_input("Central SDAI (Modelo/Marca)")
            c_tsdai = st.text_input("Tipo de Central", value="SISTEMA ENDEREÇÁVEL")
            c_qlacos = st.text_input("Qtd. Laços / Zonas", value="01 LAÇO")
            c_dfum = st.text_input("Detectores de Fumaça / Térmicos", value="0 UN")
            c_acion = st.text_input("Acionadores Manuais", value="0 un")
            c_avis = st.text_input("Avisadores Sonoros/Visuais", value="0 un")
            c_press = st.text_input("Pressurização Escada", value="Sim (IT 13)")
            c_bat = st.text_input("Tensão & Baterias Nominais", value="220 Vac nominal | Baterias 24 Vcc")

            if st.form_submit_button("💾 Salvar Cliente no Sistema"):
                if c_nome_cad:
                    clientes_db[c_nome_cad] = {
                        "nome": c_nome_cad, "cnpj": c_cnpj_cad, "endereco": c_end_cad,
                        "cidade_uf": c_cid_cad, "sindico": c_sind_cad, "zelador": c_zel_cad,
                        "contato": c_tel_cad, "email": c_email_cad, "central_sdai": c_csdai,
                        "tipo_central": c_tsdai, "qtd_lacos": c_qlacos, "det_fumaca": c_dfum,
                        "acionadores": c_acion, "avisadores": c_avis, "pressurizacao": c_press,
                        "tensao_baterias": c_bat,
                    }
                    salvar_json(CLIENTES_FILE, clientes_db)
                    st.success(f"✅ Cliente {c_nome_cad} salvo com sucesso!")
                else:
                    st.warning("O nome do cliente é obrigatório.")

    with tab_c2:
        st.subheader("Clientes Cadastrados")
        if not clientes_db:
            st.info("Nenhum cliente cadastrado.")
        else:
            for cl_nome, cl_data in list(clientes_db.items()):
                with st.expander(f"🏢 {cl_nome} (CNPJ: {cl_data.get('cnpj', '')})"):
                    st.write(f"**Endereço:** {cl_data.get('endereco', '')} - {cl_data.get('cidade_uf', '')}")
                    st.write(f"**Síndico:** {cl_data.get('sindico', '')} | **Zelador:** {cl_data.get('zelador', '')}")
                    st.write(f"**Contato:** {cl_data.get('contato', '')} | **E-mail:** {cl_data.get('email', '')}")
                    st.write(f"**Central SDAI:** {cl_data.get('central_sdai', '')} ({cl_data.get('tipo_central', '')})")
                    if st.button(f"🗑️ Excluir Cliente", key=f"del_cli_{cl_nome}"):
                        del clientes_db[cl_nome]
                        salvar_json(CLIENTES_FILE, clientes_db)
                        st.success(f"Cliente {cl_nome} excluído!")
                        st.rerun()

    with tab_c3:
        st.subheader("📊 Importar e Exportar Planilha de Clientes")
        
        st.write("### 📥 Baixar Planilha Cadastral (Separada por Colunas)")
        st.info("Baixe a planilha estruturada para Excel/Google Planilhas (separada por colunas utilizando ponto e vírgula ';', pronta para visualização, edição e impressão).")
        
        if clientes_db:
            lista_para_df = []
            for nome_cli, dados_cli in clientes_db.items():
                lista_para_df.append(dados_cli)
            df_clientes_export = pd.DataFrame(lista_para_df)
            
            csv_dados = df_clientes_export.to_csv(index=False, sep=';', encoding='utf-8-sig').encode('utf-8-sig')
            st.download_button(
                label="📥 Baixar Planilha em Colunas (CSV / Excel)",
                data=csv_dados,
                file_name=f"base_clientes_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
                use_container_width=True
            )
        else:
            st.warning("Não há clientes cadastrados para exportar no momento.")

        st.divider()

        st.write("### 📤 Atualizar / Enviar Planilha de Clientes")
        st.info("Envie um arquivo CSV atualizado para sincronizar com o sistema.")
        
        arquivo_upload_clientes = st.file_uploader("Escolha o arquivo CSV de clientes atualizado", type=["csv"], key="upload_clientes_csv")
        
        if arquivo_upload_clientes is not None:
            if st.button("Confirmar e Sincronizar Base de Clientes", type="primary"):
                try:
                    try:
                        df_novo_upload = pd.read_csv(arquivo_upload_clientes, sep=';')
                        if len(df_novo_upload.columns) <= 1:
                            arquivo_upload_clientes.seek(0)
                            df_novo_upload = pd.read_csv(arquivo_upload_clientes, sep=',')
                    except:
                        arquivo_upload_clientes.seek(0)
                        df_novo_upload = pd.read_csv(arquivo_upload_clientes)
                    
                    novo_db = {}
                    for _, row in df_novo_upload.iterrows():
                        nome_cliente = str(row.get("nome", ""))
                        if nome_cliente and nome_cliente != "nan":
                            novo_db[nome_cliente] = row.to_dict()
                    
                    clientes_db.clear()
                    clientes_db.update(novo_db)
                    salvar_json(CLIENTES_FILE, clientes_db)
                    
                    st.success("✅ Base de clientes atualizada e importada com sucesso!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao processar o arquivo enviado: {e}")

elif "📂 Histórico & Pasta do Cliente" in menu_admin:
    st.header("📂 Pasta Digital e Histórico Completo por Cliente")
    st.info("Aqui ficam centralizados todos os relatórios gerados e chamados técnicos vinculados a cada cliente.")
    
    if not clientes_db:
        st.info("Nenhum cliente cadastrado.")
    else:
        lista_nomes_hist = list(clientes_db.keys())
        cliente_selecionado_hist = st.selectbox("Selecione o Cliente", lista_nomes_hist, key="hist_cli_select_main")
        
        if cliente_selecionado_hist:
            nome_pasta_cliente = "".join(c for c in cliente_selecionado_hist if c.isalnum() or c in (' ', '_', '-')).strip()
            cliente_dir = os.path.join(HISTORICO_CLIENTES_DIR, nome_pasta_cliente)
            
            c_info = clientes_db[cliente_selecionado_hist]
            with st.expander("🏢 Informações Cadastrais e SDAI", expanded=False):
                st.write(f"**CNPJ:** {c_info.get('cnpj', '')} | **Contato:** {c_info.get('contato', '')}")
                st.write(f"**Endereço:** {c_info.get('endereco', '')} - {c_info.get('cidade_uf', '')}")
                st.write(f"**Síndico:** {c_info.get('sindico', '')} | **Zelador:** {c_info.get('zelador', '')}")
                st.write(f"**Central SDAI:** {c_info.get('central_sdai', '')} ({c_info.get('tipo_central', '')})")

            st.divider()
            st.write(f"### Atendimentos, Relatórios e Chamados de: {cliente_selecionado_hist}")
            
            if os.path.exists(cliente_dir):
                historico_path = os.path.join(cliente_dir, "historico_atendimentos.json")
                atendimentos = []
                if os.path.exists(historico_path):
                    try:
                        with open(historico_path, "r", encoding="utf-8") as f:
                            atendimentos = json.load(f)
                    except:
                        pass
                
                if atendimentos:
                    for idx, at in enumerate(reversed(atendimentos)):
                        tipo_item = at.get('tipo', 'Atendimento')
                        st.markdown(f"**📌 [{tipo_item}]** — *Data: {at.get('data')}*")
                        
                        if "Relatório" in tipo_item or "Proposta" in tipo_item:
                            st.write(f"Resp. Técnico: {at.get('resp_tecnico')}")
                            caminho_pdf_salvo = os.path.join(cliente_dir, at.get('arquivo_pdf', ''))
                            if os.path.exists(caminho_pdf_salvo):
                                with open(caminho_pdf_salvo, "rb") as f_pdf_down:
                                    st.download_button(
                                        label=f"📥 Baixar Arquivo PDF Salvo ({at.get('data')})",
                                        data=f_pdf_down.read(),
                                        file_name=at.get('arquivo_pdf'),
                                        mime="application/pdf",
                                        key=f"down_hist_main_{nome_pasta_cliente}_{idx}"
                                    )
                        elif "Chamado" in tipo_item:
                            st.write(f"**Problema:** {at.get('problema')}")
                            st.write(f"**Status do Chamado:** {at.get('status')} | **Contato:** {at.get('contato')}")
                        
                        st.divider()
                else:
                    st.info("Nenhum registro de relatório ou chamado encontrado para este cliente.")
            else:
                st.info("Ainda não há histórico criado para este cliente.")

elif "🏢 Dados da Minha Empresa" in menu_admin:
    st.header("🏢 Configurações da Empresa Prestadora")
    with st.form("form_empresa"):
        e_nome = st.text_input("Nome da Empresa", value=empresa_db.get("nome", ""))
        e_cnpj = st.text_input("CNPJ", value=empresa_db.get("cnpj", ""))
        e_crea = st.text_input("CREA / Registro", value=empresa_db.get("crea", ""))
        e_end = st.text_input("Endereço", value=empresa_db.get("endereco", ""))
        e_tel = st.text_input("Telefone", value=empresa_db.get("telefone", ""))
        e_email = st.text_input("E-mail", value=empresa_db.get("email", ""))
        e_resp = st.text_input("Responsável Técnico", value=empresa_db.get("resp_tecnico", ""))
        
        logo_up = st.file_uploader("Logo da Empresa (PNG)", type=["png", "jpg", "jpeg"], key="uploader_logo")

        if st.form_submit_button("💾 Salvar Dados da Empresa"):
            empresa_db["nome"] = e_nome
            empresa_db["cnpj"] = e_cnpj
            empresa_db["crea"] = e_crea
            empresa_db["endereco"] = e_end
            empresa_db["telefone"] = e_tel
            empresa_db["email"] = e_email
            empresa_db["resp_tecnico"] = e_resp
            
            if logo_up:
                with open(LOGO_PATH, "wb") as f:
                    f.write(logo_up.getbuffer())
                empresa_db["logo_path"] = LOGO_PATH

            salvar_json(EMPRESA_FILE, empresa_db)
            st.success("✅ Dados da empresa atualizados com sucesso!")
            st.rerun()

elif "📋 Chamados" in menu_admin:
    st.header("📋 Gestão de Chamados Técnicos")
    if not chamados_db:
        st.info("Nenhum chamado registrado.")
    else:
        for ch in reversed(chamados_db):
            with st.expander(f"Chamado #{ch['id']} - {ch['cliente']} (Status: {ch['status']})"):
                st.write(f"**Contato:** {ch.get('contato', 'N/A')} | **E-mail:** {ch.get('email', 'N/A')}")
                st.write(f"**Problema relatado:** {ch['problema']}")
                if ch.get('anexo') and os.path.exists(ch['anexo']):
                    st.image(ch['anexo'], width=300)
                
                novo_status = st.selectbox(
                    "Atualizar Status",
                    ["Pendente", "Em Andamento", "Concluído", "Cancelado"],
                    index=["Pendente", "Em Andamento", "Concluído", "Cancelado"].index(ch["status"]) if ch["status"] in ["Pendente", "Em Andamento", "Concluído", "Cancelado"] else 0,
                    key=f"status_ch_{ch['id']}"
                )
                
                if st.button("💾 Atualizar Status do Chamado", key=f"btn_ch_{ch['id']}"):
                    ch["status"] = novo_status
                    salvar_json(CHAMADOS_FILE, chamados_db)
                    
                    registrar_historico_cliente(
                        ch['cliente'],
                        f"Chamado Técnico #{ch['id']}",
                        {
                            "problema": ch['problema'],
                            "status": novo_status,
                            "contato": ch.get('contato', '')
                        }
                    )
                    
                    st.success("Status atualizado e vinculado ao histórico do cliente!")
                    st.rerun()
                
                if ch.get('feedback'):
                    st.info(f"**Feedback do Cliente:** {ch['feedback']}")

elif "👥 Gerenciar Usuários" in menu_admin:
    st.header("👥 Gestão de Usuários e Acessos")
    tab_u1, tab_u2 = st.tabs(["➕ Adicionar Usuário", "📋 Lista de Usuários"])

    with tab_u1:
        with st.form("form_novo_usuario"):
            u_login = st.text_input("Login / Nome de Usuário")
            u_senha = st.text_input("Senha", type="password")
            u_nome = st.text_input("Nome Completo / Empresa")
            u_perfil = st.selectbox("Perfil de Acesso", ["cliente", "master"], key="select_perfil_novo")

            if st.form_submit_button("💾 Cadastrar Usuário"):
                if u_login and u_senha:
                    usuarios[u_login] = {"senha": u_senha, "nome": u_nome, "perfil": u_perfil}
                    salvar_json(USUARIOS_FILE, usuarios)
                    st.success(f"✅ Usuário {u_login} cadastrado com sucesso!")
