import streamlit as st
import pandas as pd
import sqlite3
import os
import shutil
from datetime import datetime

st.set_page_config(page_title="Eli Sistemas - Gestão Completa", page_icon="⚡", layout="wide")

# Configuração do Banco de Dados SQLite
DB_FILE = "eli_sistemas.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Tabela de Relatórios e Vistorias
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
    
    # Tabela de Agenda (Diária, Semanal, Mensal)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS agenda (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task TEXT,
            category TEXT, 
            due_date TEXT,
            status TEXT
        )
    ''')
    
    # Tabela de Equipamentos / Quantidades
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS equipment (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client TEXT,
            equipment_type TEXT,
            quantity INTEGER,
            location TEXT,
            notes TEXT
        )
    ''')

    # Tabela de Chamados / Ordens de Serviço (Versão Antiga Integrada)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS service_calls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client TEXT,
            service_type TEXT,
            description TEXT,
            priority TEXT,
            status TEXT,
            date TEXT
        )
    ''')

    # Tabela de Cadastro de Clientes (Versão Antiga Integrada)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS clients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            cnpj TEXT,
            phone TEXT,
            address TEXT,
            notes TEXT
        )
    ''')
    
    conn.commit()
    conn.close()

init_db()

# Função para realizar backup do banco de dados
def perform_backup():
    backup_dir = "backups"
    os.makedirs(backup_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(backup_dir, f"backup_{timestamp}.db")
    if os.path.exists(DB_FILE):
        shutil.copyfile(DB_FILE, backup_path)
        return backup_path
    return None

# Menu lateral de navegação unificado
st.sidebar.markdown("### ⚡ Eli Sistemas")
st.sidebar.caption("Sistemas de Alarme e Segurança contra Incêndio")
st.sidebar.divider()

menu = st.sidebar.selectbox("Navegação", [
    "📅 Agenda Principal", 
    "📋 Relatórios e Vistorias", 
    "🔧 Controle de Equipamentos / Preventiva", 
    "📞 Chamados e Ordens de Serviço",
    "👥 Cadastro de Clientes",
    "💾 Backup Diário"
])

# Logotipo/Cabeçalho padrão para todos os documentos impressos
LOGO_HTML = '''
<div style="display: flex; align-items: center; justify-content: space-between; border-bottom: 2px solid #b71c1c; padding-bottom: 10px; margin-bottom: 20px;">
    <div>
        <h2 style="color: #b71c1c; margin: 0; font-size: 20px;">ELI SISTEMAS</h2>
        <p style="margin: 0; font-size: 11px; color: #555;">Sistemas de Alarme, Detecção e Segurança contra Incêndio</p>
    </div>
    <div style="text-align: right; font-size: 11px; color: #666;">
        <b>Documento Técnico Oficial</b><br>
        Emissão: {}
    </div>
</div>
'''.format(datetime.now().strftime("%d/%m/%Y %H:%M"))

# ==========================================
# 1. AGENDA PRINCIPAL
# ==========================================
if menu == "📅 Agenda Principal":
    st.title("📅 Agenda de Atividades")
    st.write("Gerencie suas tarefas diárias, semanais e mensais com controle de status e opção de exportação.")
    
    with st.form("new_task_form", clear_on_submit=True):
        st.subheader("Cadastrar Nova Tarefa")
        col1, col2, col3 = st.columns(3)
        with col1:
            task_name = st.text_input("Descrição da Tarefa / Serviço")
        with col2:
            category = st.selectbox("Categoria", ["Diária", "Semanal", "Mensal"])
        with col3:
            due_date = st.date_input("Data Alvo", value=datetime.today())
            
        submitted = st.form_submit_button("Cadastrar Tarefa")
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
    st.subheader("Lista de Tarefas da Agenda")
    
    conn = sqlite3.connect(DB_FILE)
    df_agenda = pd.read_sql("SELECT * FROM agenda ORDER BY due_date ASC", conn)
    conn.close()
    
    if not df_agenda.empty:
        filter_cat = st.selectbox("Filtrar por Categoria", ["Todas", "Diária", "Semanal", "Mensal"])
        filtered_df = df_agenda.copy()
        if filter_cat != "Todas":
            filtered_df = filtered_df[filtered_df["category"] == filter_cat]
            
        for index, row in filtered_df.iterrows():
            cols = st.columns([3, 1, 1, 1])
            with cols[0]:
                st.markdown(f"**{row['task']}**<br><small style='color:gray;'>Cat: {row['category']} | Data: {row['due_date']}</small>", unsafe_allow_html=True)
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
                st.write("")
                if st.button("Excluir", key=f"del_{row['id']}"):
                    conn = sqlite3.connect(DB_FILE)
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM agenda WHERE id = ?", (row['id'],))
                    conn.commit()
                    conn.close()
                    st.rerun()
    else:
        st.info("Nenhuma tarefa cadastrada na agenda.")

# ==========================================
# 2. RELATÓRIOS E VISTORIAS
# ==========================================
elif menu == "📋 Relatórios e Vistorias":
    st.title("📋 Emissão de Relatórios e Vistorias")
    st.write("Todos os relatórios gerados contêm o logotipo oficial da Eli Sistemas.")
    
    with st.form("report_form", clear_on_submit=True):
        st.subheader("Novo Relatório / Vistoria")
        rep_title = st.text_input("Título do Relatório (ex: Relatório de Vistoria de Alarme)")
        client = st.text_input("Cliente / Local da Obra")
        rep_type = st.selectbox("Tipo de Documento", ["Vistoria Técnica", "Manutenção Preventiva", "Auditoria de Sinalização"])
        content = st.text_area("Descrição Técnica, Equipamentos e Conclusão")
        
        gen_btn = st.form_submit_button("Gerar Relatório Oficial")
        if gen_btn and rep_title:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute("INSERT INTO reports (title, client, date, content, type) VALUES (?, ?, ?, ?, ?)",
                           (rep_title, client, datetime.now().strftime("%d/%m/%Y %H:%M"), content, rep_type))
            conn.commit()
            conn.close()
            st.success("Relatório gerado com sucesso!")

    st.divider()
    st.subheader("Histórico de Relatórios Salvos")
    conn = sqlite3.connect(DB_FILE)
    df_reports = pd.read_sql("SELECT * FROM reports ORDER BY id DESC", conn)
    conn.close()
    
    if not df_reports.empty:
        for idx, row in df_reports.iterrows():
            with st.expander(f"[{row['type']}] {row['title']} - Cliente: {row['client']} ({row['date']})"):
                preview_html = f'''
                <div style="border: 1px solid #ccc; padding: 25px; border-radius: 8px; background: white; color: black; font-family: Arial, sans-serif;">
                    {LOGO_HTML}
                    <h3 style="color: #222; margin-bottom: 5px;">{row['title']}</h3>
                    <p style="margin: 4px 0;"><b>Cliente / Local:</b> {row['client']}</p>
                    <p style="margin: 4px 0;"><b>Data de Emissão:</b> {row['date']}</p>
                    <hr style="border:0; border-top:1px solid #ddd; margin: 15px 0;">
                    <p style="margin: 4px 0;"><b>Tipo de Serviço:</b> {row['type']}</p>
                    <p style="white-space: pre-wrap; margin-top: 15px;">{row['content']}</p>
                    <br><br>
                    <div style="display: flex; justify-content: space-between; margin-top: 50px; font-size: 12px; color: #333;">
                        <div style="text-align: center;">____________________________________________<br>Eli Sistemas<br>Responsável Técnico</div>
                        <div style="text-align: center;">____________________________________________<br>Assinatura do Cliente / Contratante</div>
                    </div>
                </div>
                '''
                st.markdown(preview_html, unsafe_allow_html=True)
                st.download_button("📥 Baixar / Imprimir Relatório (HTML)", data=preview_html, file_name=f"relatorio_{row['id']}.html", mime="text/html", key=f"dl_{row['id']}")
    else:
        st.info("Nenhum relatório emitido até o momento.")

# ==========================================
# 3. CONTROLE DE EQUIPAMENTOS / PREVENTIVA
# ==========================================
elif menu == "🔧 Controle de Equipamentos / Preventiva":
    st.title("🔧 Controle de Equipamentos e Quantidades")
    st.write("Gerencie os equipamentos e quantidades instalados para controle de vistorias e manutenções.")
    
    with st.form("eq_form", clear_on_submit=True):
        st.subheader("Cadastrar Equipamento / Quantidade")
        eq_client = st.text_input("Cliente / Obra")
        eq_type = st.selectbox("Tipo de Equipamento", [
            "Central de Alarme de Incêndio", 
            "Detector de Fumaça / Térmico", 
            "Acionador Manual (Botoeira)", 
            "Sinalizador Audiovisual (Sirene/Strobe)", 
            "Placa Fotoluminescente (Sinalização)",
            "Eletroímã de Porta / Retenedor",
            "Outro"
        ])
        eq_qty = st.number_input("Quantidade Total", min_value=1, value=1)
        eq_loc = st.text_input("Localização / Pavimento / Setor")
        eq_notes = st.text_area("Observações Técnicas")
        
        eq_submit = st.form_submit_button("Salvar Equipamento")
        if eq_submit and eq_client:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute("INSERT INTO equipment (client, equipment_type, quantity, location, notes) VALUES (?, ?, ?, ?, ?)",
                           (eq_client, eq_type, eq_qty, eq_loc, eq_notes))
            conn.commit()
            conn.close()
            st.success("Equipamento cadastrado com sucesso!")

    st.divider()
    st.subheader("Equipamentos Cadastrados")
    conn = sqlite3.connect(DB_FILE)
    df_eq = pd.read_sql("SELECT * FROM equipment ORDER BY id DESC", conn)
    conn.close()
    
    if not df_eq.empty:
        st.dataframe(df_eq, use_container_width=True)
    else:
        st.info("Nenhum equipamento cadastrado.")

# ==========================================
# 4. CHAMADOS E ORDENS DE SERVIÇO
# ==========================================
elif menu == "📞 Chamados e Ordens de Serviço":
    st.title("📞 Gestão de Chamados e O.S.")
    st.write("Abra e acompanhe chamados técnicos, manutenções corretivas e ordens de serviço.")

    with st.form("call_form", clear_on_submit=True):
        st.subheader("Novo Chamado / Ordem de Serviço")
        c_client = st.text_input("Cliente / Empresa")
        c_type = st.selectbox("Tipo de Atendimento", ["Manutenção Corretiva", "Chamado Técnico URGENTE", "Instalação", "Visita de Diagnóstico"])
        c_desc = st.text_area("Descrição do Problema ou Solicitação")
        c_priority = st.selectbox("Prioridade", ["Baixa", "Média", "Alta", "Urgente"])
        
        c_submit = st.form_submit_button("Registrar Chamado")
        if c_submit and c_client:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute("INSERT INTO service_calls (client, service_type, description, priority, status, date) VALUES (?, ?, ?, ?, ?, ?)",
                           (c_client, c_type, c_desc, c_priority, "Aberto", datetime.now().strftime("%d/%m/%Y %H:%M")))
            conn.commit()
            conn.close()
            st.success("Chamado registrado com sucesso!")

    st.divider()
    st.subheader("Chamados Registrados")
    conn = sqlite3.connect(DB_FILE)
    df_calls = pd.read_sql("SELECT * FROM service_calls ORDER BY id DESC", conn)
    conn.close()

    if not df_calls.empty:
        for idx, row in df_calls.iterrows():
            with st.expander(f"[{row['status']}] O.S. #{row['id']} - {row['client']} ({row['service_type']})"):
                st.write(f"**Prioridade:** {row['priority']}")
                st.write(f"**Data:** {row['date']}")
                st.write(f"**Descrição:** {row['description']}")
                
                new_call_status = st.selectbox("Alterar Status", ["Aberto", "Em Andamento", "Concluído"], key=f"c_status_{row['id']}", index=["Aberto", "Em Andamento", "Concluído"].index(row['status']))
                if new_call_status != row['status']:
                    conn = sqlite3.connect(DB_FILE)
                    cursor = conn.cursor()
                    cursor.execute("UPDATE service_calls SET status = ? WHERE id = ?", (new_call_status, row['id']))
                    conn.commit()
                    conn.close()
                    st.rerun()
    else:
        st.info("Nenhum chamado registrado.")

# ==========================================
# 5. CADASTRO DE CLIENTES
# ==========================================
elif menu == "👥 Cadastro de Clientes":
    st.title("👥 Cadastro de Clientes")
    st.write("Gerencie os dados cadastrais dos seus clientes e locais atendidos.")

    with st.form("client_form", clear_on_submit=True):
        st.subheader("Novo Cliente")
        cl_name = st.text_input("Nome da Empresa / Cliente")
        cl_cnpj = st.text_input("CNPJ / CPF")
        cl_phone = st.text_input("Telefone de Contato")
        cl_address = st.text_input("Endereço Completo")
        cl_notes = st.text_area("Observações / Contornos Importantes")

        cl_submit = st.form_submit_button("Salvar Cliente")
        if cl_submit and cl_name:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute("INSERT INTO clients (name, cnpj, phone, address, notes) VALUES (?, ?, ?, ?, ?)",
                           (cl_name, cl_cnpj, cl_phone, cl_address, cl_notes))
            conn.commit()
            conn.close()
            st.success("Cliente cadastrado com sucesso!")

    st.divider()
    st.subheader("Clientes Cadastrados")
    conn = sqlite3.connect(DB_FILE)
    df_clients = pd.read_sql("SELECT * FROM clients ORDER BY id DESC", conn)
    conn.close()

    if not df_clients.empty:
        st.dataframe(df_clients, use_container_width=True)
    else:
        st.info("Nenhum cliente cadastrado.")

# ==========================================
# 6. BACKUP DIÁRIO
# ==========================================
elif menu == "💾 Backup Diário":
    st.title("💾 Central de Backup do Sistema")
    st.write("Faça o backup imediato ou configure cópias de segurança de todo o banco de dados do aplicativo.")
    
    col_b1, col_b2 = st.columns(2)
    with col_b1:
        if st.button("Executar Backup Agora", type="primary"):
            b_path = perform_backup()
            if b_path:
                st.success("Backup gerado com sucesso!")
                with open(b_path, "rb") as f:
                    st.download_button("Baixar Arquivo de Backup (.db)", f, file_name=os.path.basename(b_path), mime="application/octet-stream")
            else:
                st.error("Erro ao gerar arquivo de backup.")
    
    st.divider()
    st.subheader("Histórico de Backups Anteriores")
    if os.path.exists("backups"):
        backups = os.listdir("backups")
        if backups:
            for b in sorted(backups, reverse=True):
                b_full_path = os.path.join("backups", b)
                cols_bk = st.columns([3, 1])
                with cols_bk[0]:
                    st.text(b)
                with cols_bk[1]:
                    with open(b_full_path, "rb") as f:
                        st.download_button("Baixar", f, file_name=b, key=f"down_{b}")
        else:
            st.info("Nenhum backup encontrado na pasta.")
    else:
        st.info("Nenhum diretório de backup criado ainda.")
