import streamlit as st
import sqlite3
import pandas as pd
import datetime
import calendar

# Configuração da Página
st.set_page_config(
    page_title="Eli Sistemas - Gestão PCI",
    page_icon="⚡",
    layout="wide"
)

DB_FILE = "banco.db"

# -----------------------------------------------------------------------------
# FUNÇÕES DE BANCO DE DADOS
# -----------------------------------------------------------------------------
def init_db():
    """Garante que as tabelas existam sem alterar estrutura de colunas existentes."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS agenda (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task TEXT,
            category TEXT,
            due_date TEXT,
            status TEXT
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS rascunhos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente TEXT,
            data_visita TEXT,
            dados_json TEXT,
            atualizado_em TEXT
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            client TEXT,
            date TEXT,
            content TEXT,
            type TEXT
        )
    """)
    
    conn.commit()
    conn.close()

def get_agenda_data():
    """Busca direta sem nenhum filtro extra, garantindo 100% de leitura do banco antigo."""
    conn = sqlite3.connect(DB_FILE)
    try:
        df = pd.read_sql_query(
            "SELECT id AS ID, task AS Tarefa, category AS Categoria, due_date AS 'Data Prevista', status AS Status "
            "FROM agenda "
            "ORDER BY due_date ASC", 
            conn
        )
    except Exception:
        df = pd.DataFrame(columns=["ID", "Tarefa", "Categoria", "Data Prevista", "Status"])
    finally:
        conn.close()
    return df

def add_task(task, category, due_date, status="Não realizado"):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO agenda (task, category, due_date, status) VALUES (?, ?, ?, ?)",
        (task, category, str(due_date), status)
    )
    conn.commit()
    conn.close()

def update_task_status(task_id, new_status):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("UPDATE agenda SET status = ? WHERE id = ?", (new_status, task_id))
    conn.commit()
    conn.close()

def delete_task(task_id):
    """Deleta o registro diretamente do banco de dados."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM agenda WHERE id = ?", (task_id,))
    conn.commit()
    conn.close()

# Inicializa banco
init_db()

# -----------------------------------------------------------------------------
# BARRA LATERAL (SIDEBAR)
# -----------------------------------------------------------------------------
with st.sidebar:
    st.title("⚡ Eli Sistemas")
    st.caption("Usuário: **admin (MASTER)**")
    
    if st.button("🚪 Sair / Logout", type="primary", use_container_width=True):
        st.session_state.clear()
        st.rerun()

    st.markdown("---")
    st.write("**Navegação Principal**")
    
    menu = st.radio(
        "Selecione uma opção:",
        [
            "📋 Nova Vistoria / Laudo",
            "📁 Rascunhos de Vistoria",
            "📅 Agenda de Atividades",
            "📁 Clientes & Histórico",
            "🏢 Dados da Empresa",
            "👥 Gestão de Usuários",
            "💻 Chamados Técnicos",
            "💾 Backup & Restauração"
        ],
        index=2,
        label_visibility="collapsed"
    )

# -----------------------------------------------------------------------------
# TELA: AGENDA DE ATIVIDADES
# -----------------------------------------------------------------------------
if menu == "📅 Agenda de Atividades":
    st.header("📅 Agenda de Atividades")
    
    # Carrega dados do banco
    df_agenda = get_agenda_data()
    
    # Formulário para nova tarefa
    with st.expander("➕ Adicionar Nova Tarefa à Agenda"):
        with st.form("form_nova_tarefa", clear_on_submit=True):
            col_t1, col_t2, col_t3 = st.columns([3, 1.5, 1.5])
            with col_t1:
                nova_tarefa = st.text_input("Descrição da Tarefa")
            with col_t2:
                categoria = st.selectbox("Categoria", ["Diária", "Preventiva", "Corretiva", "Vistoria", "Financeiro"])
            with col_t3:
                data_prevista = st.date_input("Data Prevista", datetime.date.today())
            
            btn_salvar = st.form_submit_button("Salvar Tarefa")
            if btn_salvar and nova_tarefa:
                add_task(nova_tarefa, categoria, data_prevista)
                st.success("Tarefa registrada com sucesso!")
                st.rerun()

    # Seleção de Mês e Ano para o Calendário
    col_m1, col_m2 = st.columns([2, 4])
    with col_m1:
        hoje = datetime.date.today()
        mes_selecionado = st.selectbox("Mês", list(range(1, 13)), index=hoje.month - 1, format_func=lambda m: calendar.month_name[m])
        ano_selecionado = st.number_input("Ano", min_value=2020, max_value=2030, value=hoje.year)

    # Renderização do Calendário
    cal = calendar.monthcalendar(ano_selecionado, mes_selecionado)
    dias_semana = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
    
    cols_header = st.columns(7)
    for i, dia_nome in enumerate(dias_semana):
        cols_header[i].markdown(f"**{dia_nome}**")

    for semana in cal:
        cols_dia = st.columns(7)
        for i, dia in enumerate(semana):
            if dia == 0:
                cols_dia[i].write("")
            else:
                str_data = f"{ano_selecionado}-{mes_selecionado:02d}-{dia:02d}"
                tarefas_do_dia = df_agenda[df_agenda["Data Prevista"] == str_data]
                
                conteudo_dia = f"**{dia}**\n\n"
                if not tarefas_do_dia.empty:
                    for _, row in tarefas_do_dia.iterrows():
                        icone = "✅" if row["Status"] == "Realizado" else "📌"
                        conteudo_dia += f"{icone} `{row['Tarefa']}`\n\n"
                
                cols_dia[i].info(conteudo_dia)

    st.markdown("---")

    # Lista Completa de Tarefas
    with st.expander("📋 Ver Lista Completa de Tarefas e Gerenciar Status", expanded=True):
        if df_agenda.empty:
            st.warning("Nenhuma atividade encontrada na base de dados.")
        else:
            for idx, row in df_agenda.iterrows():
                col_c1, col_c2, col_c3, col_c4, col_c5 = st.columns([3, 1.5, 1.5, 1.5, 1])
                with col_c1:
                    st.write(f"**{row['Tarefa']}**")
                with col_c2:
                    st.caption(f"Categoria: {row['Categoria']}")
                with col_c3:
                    st.caption(f"Data: {row['Data Prevista']}")
                with col_c4:
                    status_atual = row["Status"]
                    novo_status = st.selectbox(
                        "Status", 
                        ["Não realizado", "Realizado"], 
                        index=0 if status_atual == "Não realizado" else 1,
                        key=f"status_{row['ID']}"
                    )
                    if novo_status != status_atual:
                        update_task_status(row["ID"], novo_status)
                        st.rerun()
                with col_c5:
                    if st.button("🗑️", key=f"del_{row['ID']}"):
                        delete_task(row["ID"])
                        st.rerun()
                st.divider()

else:
    st.title(menu)
    st.info("Módulo em desenvolvimento.")
