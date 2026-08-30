import streamlit as st
import sqlite3
import hashlib
import os
import json
import zipfile
import tempfile
import pandas as pd
from datetime import datetime
from io import BytesIO

# Imports do ReportLab para PDF
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

# ==========================================
# 1. CONFIGURAÇÃO INICIAL DA PÁGINA
# ==========================================
st.set_page_config(
    page_title="Sistema de Gestão Técnica & Vistorias",
    page_icon="🛡️",
    layout="wide"
)

DB_PATH = "sistema.db"
JSON_STATE_PATH = "estado_sistema.json"

# ==========================================
# 2. SEGURANÇA E GERENCIAMENTO DE USUÁRIOS
# ==========================================

def init_db_usuarios():
    """Cria a tabela de usuários caso não exista e insere o usuário admin padrão."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            nome TEXT NOT NULL,
            senha_hash TEXT NOT NULL,
            salt TEXT NOT NULL,
            perfil TEXT NOT NULL -- 'Admin', 'Tecnico', 'Consulta'
        )
    ''')
    
    # Criar tabela de rascunhos/agenda se necessário
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS rascunhos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titulo TEXT,
            conteudo TEXT,
            data_criacao TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS agenda (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titulo TEXT,
            data_evento TEXT,
            descricao TEXT
        )
    ''')
    conn.commit()
    
    # Criar usuário admin padrão se a tabela de usuários estiver vazia
    cursor.execute("SELECT COUNT(*) FROM usuarios")
    if cursor.fetchone()[0] == 0:
        salt = os.urandom(16).hex()
        # Senha padrão inicial: admin123
        senha_hash = hashlib.sha256(("admin123" + salt).encode('utf-8')).hexdigest()
        cursor.execute(
            "INSERT INTO usuarios (username, nome, senha_hash, salt, perfil) VALUES (?, ?, ?, ?, ?)",
            ("admin", "Administrador do Sistema", senha_hash, salt, "Admin")
        )
        conn.commit()
    conn.close()

def hash_senha(senha: str, salt: str) -> str:
    """Gera o hash SHA-256 da senha combinada com o salt."""
    return hashlib.sha256((senha + salt).encode('utf-8')).hexdigest()

def autenticar_usuario(username, senha):
    """Verifica credenciais no SQLite."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT nome, senha_hash, salt, perfil FROM usuarios WHERE username = ?", (username.strip().lower(),))
    usuario = cursor.fetchone()
    conn.close()

    if usuario:
        nome, senha_hash, salt, perfil = usuario
        if hash_senha(senha, salt) == senha_hash:
            return {"username": username, "nome": nome, "perfil": perfil}
    return None

def cadastrar_usuario(username, nome, senha, perfil):
    """Cadastra um novo usuário no banco de dados."""
    salt = os.urandom(16).hex()
    senha_h = hash_senha(senha, salt)
    
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO usuarios (username, nome, senha_hash, salt, perfil) VALUES (?, ?, ?, ?, ?)",
            (username.strip().lower(), nome.strip(), senha_h, salt, perfil)
        )
        conn.commit()
        conn.close()
        return True, "Usuário cadastrado com sucesso!"
    except sqlite3.IntegrityError:
        return False, "Erro: Este nome de usuário já está em uso."
    except Exception as e:
        return False, f"Erro ao cadastrar usuário: {str(e)}"

def render_login():
    """Exibe o formulário de login na tela principal e gerencia a sessão."""
    init_db_usuarios()

    if "usuario_logado" not in st.session_state:
        st.session_state["usuario_logado"] = None

    if st.session_state["usuario_logado"] is None:
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.title("🔐 Acesso ao Sistema")
            with st.form("form_login"):
                usuario_input = st.text_input("Usuário")
                senha_input = st.text_input("Senha", type="password")
                btn_entrar = st.form_submit_button("Entrar", use_container_width=True)

                if btn_entrar:
                    user = autenticar_usuario(usuario_input, senha_input)
                    if user:
                        st.session_state["usuario_logado"] = user
                        st.success(f"Bem-vindo(a), {user['nome']}!")
                        st.rerun()
                    else:
                        st.error("Usuário ou senha incorretos.")
        return False
    
    # Barra lateral do usuário logado
    st.sidebar.markdown(f"👤 **Usuário:** {st.session_state['usuario_logado']['nome']}")
    st.sidebar.markdown(f"🏷️ **Perfil:** `{st.session_state['usuario_logado']['perfil']}`")
    
    if st.sidebar.button("🚪 Sair (Logout)", use_container_width=True):
        st.session_state["usuario_logado"] = None
        st.rerun()
        
    return True

# ==========================================
# 3. GERENCIAMENTO DE JSON E CACHE
# ==========================================

@st.cache_data
def carregar_json_cached():
    """Carrega as configurações salvas em formato JSON."""
    if os.path.exists(JSON_STATE_PATH):
        try:
            with open(JSON_STATE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def salvar_json(dados):
    """Salva dados no arquivo JSON e limpa o cache."""
    with open(JSON_STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=4)
    carregar_json_cached.clear()

def restaurar_backup_completo(zip_file):
    """Extrai e restaura os arquivos contidos em um backup .zip."""
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            zip_path = os.path.join(temp_dir, "backup.zip")
            with open(zip_path, "wb") as f:
                f.write(zip_file.getbuffer())
            
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(".")
        
        carregar_json_cached.clear()
        return True, "Backup restaurado com sucesso!"
    except Exception as e:
        return False, f"Erro ao restaurar backup: {str(e)}"

# ==========================================
# 4. GERAÇÃO DE PDF (REPORTLAB)
# ==========================================

def gerar_pdf_relatorio(titulo_doc, dados_tabela, observacoes=""):
    """Gera um relatório técnico formatado em PDF."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'TitleStyle',
        parent=styles['Heading1'],
        fontSize=16,
        alignment=1,
        spaceAfter=20
    )
    normal_style = styles['Normal']
    
    story = []
    story.append(Paragraph(f"<b>{titulo_doc}</b>", title_style))
    story.append(Spacer(1, 10))
    
    if dados_tabela:
        t = Table(dados_tabela)
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1e3d59")),
            ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,-1), 9),
            ('BOTTOMPADDING', (0,0), (-1,0), 8),
            ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ]))
        story.append(t)
    
    if observacoes:
        story.append(Spacer(1, 15))
        story.append(Paragraph(f"<b>Observações Gerais:</b> {observacoes}", normal_style))
    
    # Bloco de Assinaturas (evita quebra de página isolada)
    story.append(Spacer(1, 30))
    assinatura_data = [
        ["___________________________________", "___________________________________"],
        ["Técnico Responsável", "Cliente / Contratante"]
    ]
    t_ass = Table(assinatura_data, colWidths=[250, 250])
    t_ass.setStyle(TableStyle([
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('FONTSIZE', (0,0), (-1,-1), 9),
    ]))
    
    story.append(KeepTogether([t_ass]))
    
    doc.build(story)
    buffer.seek(0)
    return buffer

# ==========================================
# 5. PAINÉIS DE CONTEÚDO DA APLICAÇÃO
# ==========================================

def render_painel_usuarios():
    """Painel de administração para cadastrar e listar usuários (RBAC)."""
    st.header("👥 Gerenciamento de Usuários e Permissões")
    
    if st.session_state["usuario_logado"]["perfil"] != "Admin":
        st.error("⚠️ Acesso restrito apenas a usuários com perfil 'Admin'.")
        return

    tab1, tab2 = st.tabs(["➕ Cadastrar Novo Usuário", "📋 Usuários Cadastrados"])

    with tab1:
        with st.form("form_novo_usuario"):
            novo_user = st.text_input("Nome de Usuário (login)")
            novo_nome = st.text_input("Nome Completo")
            nova_senha = st.text_input("Senha", type="password")
            novo_perfil = st.selectbox("Perfil de Acesso", ["Admin", "Tecnico", "Consulta"])
            btn_cadastrar = st.form_submit_button("Cadastrar Usuário")

            if btn_cadastrar:
                if not novo_user or not novo_nome or not nova_senha:
                    st.warning("Preencha todos os campos obrigatórios.")
                else:
                    sucesso, msg = cadastrar_usuario(novo_user, novo_nome, nova_senha, novo_perfil)
                    if sucesso:
                        st.success(msg)
                    else:
                        st.error(msg)

    with tab2:
        conn = sqlite3.connect(DB_PATH)
        df_users = pd.read_sql_query("SELECT id, username, nome, perfil FROM usuarios", conn)
        conn.close()
        st.dataframe(df_users, use_container_width=True)

def render_painel_relatorios():
    """Geração e exportação de relatórios em PDF."""
    st.header("📄 Emissão de Relatórios Técnicos")
    
    titulo = st.text_input("Título do Relatório", "Relatório de Vistoria de Segurança")
    obs = st.text_area("Observações Adicionais", "Instalação em conformidade com as normas técnicas vigentes.")
    
    # Exemplo de dados para tabela
    st.subheader("Itens da Vistoria")
    dados_exemplo = [
        ["Item", "Descrição", "Status"],
        ["01", "Central de Alarme de Incêndio", "Aprovado"],
        ["02", "Sinalização Fotoluminescente", "Aprovado"],
        ["03", "Iluminação de Emergência", "Pendente"],
    ]
    st.table(dados_exemplo)
    
    if st.button("🔴 Gerar PDF"):
        pdf_bytes = gerar_pdf_relatorio(titulo, dados_exemplo, obs)
        st.download_button(
            label="💾 Baixar PDF Gerado",
            data=pdf_bytes,
            file_name=f"relatorio_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
            mime="application/pdf"
        )

def render_painel_backup():
    """Gerenciamento de backups do sistema."""
    st.header("💾 Backup e Restauração de Dados")
    
    if st.session_state["usuario_logado"]["perfil"] != "Admin":
        st.warning("Apenas administradores podem fazer operações de restauração.")
    
    st.subheader("Exportar Backup")
    if st.button("Criar Arquivo de Backup (.zip)"):
        buffer = BytesIO()
        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            if os.path.exists(DB_PATH):
                zip_file.write(DB_PATH)
            if os.path.exists(JSON_STATE_PATH):
                zip_file.write(JSON_STATE_PATH)
        
        buffer.seek(0)
        st.download_button(
            label="Baixar Backup",
            data=buffer,
            file_name=f"backup_sistema_{datetime.now().strftime('%Y%m%d')}.zip",
            mime="application/zip"
        )
        
    st.divider()
    
    st.subheader("Restaurar Backup")
    uploaded_file = st.file_uploader("Envie o arquivo .zip de backup", type=["zip"])
    if uploaded_file and st.button("Restaurar Sistema"):
        sucesso, msg = restaurar_backup_completo(uploaded_file)
        if sucesso:
            st.success(msg)
        else:
            st.error(msg)

# ==========================================
# 6. FLUXO PRINCIPAL DA APLICAÇÃO
# ==========================================

def main():
    # 1. Verifica autenticação de usuário (Bloqueia o app caso deslogado)
    if not render_login():
        st.stop()

    # 2. Navegação Lateral
    st.sidebar.title("📌 Navegação")
    menu_opcoes = ["Dashboard", "Relatórios PDF", "Gerenciar Usuários", "Backup & Sistema"]
    escolha = st.sidebar.radio("Selecione o Módulo", menu_opcoes)

    # 3. Roteamento de telas
    if escolha == "Dashboard":
        st.title("🛡️ Painel Principal")
        st.write(f"Olá, **{st.session_state['usuario_logado']['nome']}**! Selecione uma opção no menu à esquerda.")
        
        # Exemplo de Cards rápidos
        col1, col2, col3 = st.columns(3)
        col1.metric("Status do Sistema", "Operacional", "100%")
        col2.metric("Perfil de Acesso", st.session_state['usuario_logado']['perfil'])
        col3.metric("Banco de Dados", "SQLite Activo")
        
    elif escolha == "Relatórios PDF":
        render_painel_relatorios()
        
    elif escolha == "Gerenciar Usuários":
        render_painel_usuarios()
        
    elif escolha == "Backup & Sistema":
        render_painel_backup()

if __name__ == "__main__":
    main()
