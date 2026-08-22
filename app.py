import streamlit as st
import json
from fpdf import FPDF

st.set_page_config(page_title="Assistente de Formulário", page_icon="📝", layout="centered")

st.title("📝 Assistente de Preenchimento")
st.write("Preencha as informações abaixo. Você pode salvar um rascunho a qualquer momento.")

CAMPOS = ["nome", "empresa", "equipamento", "quantidade", "observacoes"]

for campo in CAMPOS:
    if campo not in st.session_state:
        st.session_state[campo] = ""

st.sidebar.header("📁 Gerenciar Rascunho")

arquivo_rascunho = st.sidebar.file_uploader("Carregar Rascunho (.json)", type=["json"])
if arquivo_rascunho is not None:
    try:
        dados_carregados = json.load(arquivo_rascunho)
        for chave, valor in dados_carregados.items():
            if chave in CAMPOS:
                st.session_state[chave] = valor
        st.sidebar.success("✅ Rascunho carregado!")
    except Exception:
        st.sidebar.error("Erro ao ler o rascunho.")

aba1, aba2 = st.tabs(["1. Dados Gerais", "2. Detalhes do Serviço / Equipamento"])

with aba1:
    st.session_state["nome"] = st.text_input("Nome do Responsável", value=st.session_state["nome"])
    st.session_state["empresa"] = st.text_input("Empresa / Cliente / Local", value=st.session_state["empresa"])

with aba2:
    st.session_state["equipamento"] = st.text_input("Tipo de Equipamento / Serviço", value=st.session_state["equipamento"])
    st.session_state["quantidade"] = st.text_input("Quantidade de Itens", value=st.session_state["quantidade"])
    st.session_state["observacoes"] = st.text_area("Observações / Descrição", value=st.session_state["observacoes"])

st.markdown("---")

dados_atuais = {campo: st.session_state[campo] for campo in CAMPOS}

json_rascunho = json.dumps(dados_atuais, ensure_ascii=False, indent=4)
st.sidebar.download_button(
    label="💾 Salvar Rascunho (.json)",
    data=json_rascunho,
    file_name="rascunho_formulario.json",
    mime="application/json"
)

def limpar_texto(texto):
    return texto.encode('latin-1', 'replace').decode('latin-1')

def gerar_pdf_final(dados):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", style="B", size=16)
    pdf.cell(0, 10, limpar_texto("RELATÓRIO / FORMULÁRIO PREENCHIDO"), new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.ln(10)
    pdf.set_font("Helvetica", size=12)
    pdf.cell(0, 10, limpar_texto(f"Responsável: {dados['nome']}"), new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 10, limpar_texto(f"Empresa / Local: {dados['empresa']}"), new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 10, limpar_texto(f"Equipamento / Serviço: {dados['equipamento']}"), new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 10, limpar_texto(f"Quantidade: {dados['quantidade']}"), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(5)
    pdf.multi_cell(0, 10, limpar_texto(f"Observações:\n{dados['observacoes']}"))
    return bytes(pdf.output())

st.subheader("🏁 Finalizar")
if st.button("📄 Gerar PDF Final"):
    pdf_bytes = gerar_pdf_final(dados_atuais)
    st.download_button(
        label="⬇️ Baixar PDF Final",
        data=pdf_bytes,
        file_name="formulario_final.pdf",
        mime="application/pdf"
    )