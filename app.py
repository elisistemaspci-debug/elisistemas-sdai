import streamlit as st
import json
import os
import base64
from fpdf import FPDF
import tempfile

# -----------------------------------------------------------------------------
# 1. CLASSE DE GERAÇÃO DO PDF (FPDF COM LOGO)
# -----------------------------------------------------------------------------
class RelatorioPDF(FPDF):
    def __init__(self, logo_path=None):
        super().__init__()
        self.logo_path = logo_path

    def header(self):
        # Se houver logo cadastrado, exibe no canto superior esquerdo
        if self.logo_path and os.path.exists(self.logo_path):
            self.image(self.logo_path, x=10, y=8, w=30)
            self.set_x(45)
            self.set_font("Arial", "B", 12)
            self.cell(0, 12, "RELATÓRIO TÉCNICO DE VISTORIA - SDAI", border=True, ln=True, align="C")
        else:
            self.set_font("Arial", "B", 12)
            self.cell(0, 10, "RELATÓRIO TÉCNICO DE VISTORIA - SDAI", border=True, ln=True, align="C")
        self.ln(8)

    def footer(self):
        self.set_y(-15)
        self.set_font("Arial", "I", 8)
        self.cell(0, 10, f"Página {self.page_no()}/{{nb}}", align="C")

def gerar_pdf(dados, fotos_bytes, logo_bytes):
    # Trata o salvamento temporário do Logo para inserção no PDF
    logo_temp_path = None
    if logo_bytes is not None:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp_logo:
            tmp_logo.write(logo_bytes.getvalue())
            logo_temp_path = tmp_logo.name

    pdf = RelatorioPDF(logo_path=logo_temp_path)
    pdf.alias_nb_pages()
    pdf.add_page()
    pdf.set_font("Arial", size=10)

    # --- Seção 6: Pressurização ---
    pdf.set_font("Arial", "B", 10)
    pdf.cell(0, 8, "6. PRESSURIZAÇÃO DE ESCADAS DE SEGURANÇA & INTERLIGAÇÕES (IT 13)", ln=True)
    pdf.set_font("Arial", size=9)
    pdf.multi_cell(0, 6, f"Pressurização Escadas: {dados.get('pressurizacao', 'N/A')}\nPortas Corta-Fogo: {dados.get('portas_cf', 'N/A')}")
    pdf.ln(4)

    # --- Seção 7: Conclusão Técnica e Orientações ---
    pdf.set_font("Arial", "B", 10)
    pdf.cell(0, 8, "7. CONCLUSÃO TÉCNICA E ORIENTAÇÕES OPERACIONAIS", ln=True)
    
    pdf.set_font("Arial", "B", 9)
    pdf.cell(0, 6, "Parecer Técnico / Conclusão:", ln=True)
    pdf.set_font("Arial", size=9)
    pdf.multi_cell(0, 5, dados.get('parecer_tecnico', 'Sem observações.'))
    pdf.ln(2)

    pdf.set_font("Arial", "B", 9)
    pdf.cell(0, 6, "Orientações Operacionais:", ln=True)
    pdf.set_font("Arial", size=9)
    pdf.multi_cell(0, 5, dados.get('orientacoes_ops', 'Sem orientações.'))
    pdf.ln(4)

    # --- Seção 8: Validação e Assinaturas ---
    pdf.set_font("Arial", "B", 10)
    pdf.cell(0, 8, "8. VALIDAÇÃO E ASSINATURAS TÉCNICAS", ln=True)
    pdf.set_font("Arial", size=9)
    pdf.cell(95, 6, f"Responsável Técnico: {dados.get('resp_tecnico', '')}", border=0)
    pdf.cell(95, 6, f"Responsável / Síndico: {dados.get('resp_cliente', '')}", ln=True)
    pdf.ln(10)
    pdf.cell(95, 6, "____________________________________", border=0)
    pdf.cell(95, 6, "____________________________________", ln=True)
    pdf.cell(95, 6, "Assinatura do Técnico", border=0)
    pdf.cell(95, 6, "Assinatura do Cliente / Recebedor", ln=True)

    # --- Anexo Fotográfico ---
    if fotos_bytes:
        pdf.add_page()
        pdf.set_font("Arial", "B", 11)
        pdf.cell(0, 8, "ANEXO FOTOGRÁFICO", ln=True, align="C")
        pdf.ln(5)

        for foto in fotos_bytes:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp_foto:
                tmp_foto.write(foto.getvalue())
                tmp_foto_path = tmp_foto.name

            pdf.image(tmp_foto_path, w=80)
            pdf.ln(5)
            os.remove(tmp_foto_path)

    # Limpa arquivo temporário do logo
    if logo_temp_path and os.path.exists(logo_temp_path):
        os.remove(logo_temp_path)

    return pdf.output(dest='S').encode('latin-1')


# -----------------------------------------------------------------------------
# 2. INTERFACE STREAMLIT & GERENCIAMENTO DE RASCUNHO / CADASTRO
# -----------------------------------------------------------------------------
st.set_page_config(page_title="Eli Sistemas - Vistoria SDAI", layout="wide")

st.title("⚡ Vistoria & Relatório Técnico NBR")

RASCUNHO_FILE = "rascunho_relatorio.json"

def inicializar_estado():
    defaults = {
        "pressurizacao": "OK - Conforme",
        "portas_cf": "N/A",
        "parecer_tecnico": "",
        "orientacoes_ops": "",
        "resp_tecnico": "Eli Silva",
        "resp_cliente": ""
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val

inicializar_estado()

# Botões de Ação do Rascunho
col_btn1, col_btn2, col_btn3 = st.columns([1, 1, 2])

with col_btn1:
    if st.button("💾 Salvar Rascunho"):
        dados_salvar = {
            "pressurizacao": st.session_state.get("pressurizacao", ""),
            "portas_cf": st.session_state.get("portas_cf", ""),
            "parecer_tecnico": st.session_state.get("parecer_tecnico", ""),
            "orientacoes_ops": st.session_state.get("orientacoes_ops", ""),
            "resp_tecnico": st.session_state.get("resp_tecnico", ""),
            "resp_cliente": st.session_state.get("resp_cliente", "")
        }
        with open(RASCUNHO_FILE, "w", encoding="utf-8") as f:
            json.dump(dados_salvar, f, ensure_ascii=False, indent=4)
        st.success("Rascunho salvo com sucesso!")

with col_btn2:
    if st.button("📂 Carregar Rascunho"):
        if os.path.exists(RASCUNHO_FILE):
            with open(RASCUNHO_FILE, "r", encoding="utf-8") as f:
                dados_carregados = json.load(f)
                for key, val in dados_carregados.items():
                    st.session_state[key] = val
            st.rerun()
        else:
            st.warning("Nenhum rascunho encontrado.")

st.divider()

# --- ABA DE CONFIGURAÇÕES / EMPRESA ---
with st.expander("🏢 Cadastro da Empresa (Logotipo)", expanded=False):
    logo_file = st.file_uploader("Upload da Logomarca da Empresa", type=["png", "jpg", "jpeg"])
    if logo_file:
        st.image(logo_file, caption="Logotipo Carregado", width=150)

# --- FORMULÁRIO ---
st.subheader("🔍 Verificação dos Itens Normativos (Checklist)")

with st.expander("6. Pressurização/IT13", expanded=True):
    st.session_state["pressurizacao"] = st.text_input(
        "6.1 Pressurização de Escadas", 
        value=st.session_state["pressurizacao"]
    )
    st.session_state["portas_cf"] = st.text_input(
        "6.2 Portas Corta-Fogo / Eletroímãs", 
        value=st.session_state["portas_cf"]
    )

with st.expander("7. Conclusão Técnica e Orientações Operacionais", expanded=True):
    st.session_state["parecer_tecnico"] = st.text_area(
        "Parecer Técnico / Conclusão", 
        value=st.session_state["parecer_tecnico"],
        height=100
    )
    st.session_state["orientacoes_ops"] = st.text_area(
        "Orientações Operacionais", 
        value=st.session_state["orientacoes_ops"],
        height=100
    )

with st.expander("Anexo Fotográfico", expanded=True):
    fotos_uploaded = st.file_uploader(
        "Selecione as imagens do relatório", 
        type=["png", "jpg", "jpeg"], 
        accept_multiple_files=True
    )

with st.expander("8. Validação e Assinaturas", expanded=True):
    st.session_state["resp_tecnico"] = st.text_input(
        "Responsável Técnico", 
        value=st.session_state["resp_tecnico"]
    )
    st.session_state["resp_cliente"] = st.text_input(
        "Responsável / Síndico / Portaria", 
        value=st.session_state["resp_cliente"]
    )

st.divider()

# --- GERAÇÃO DO PDF ---
if st.button("📄 GERAR E BAIXAR RELATÓRIO PDF", type="primary"):
    dados_relatorio = {
        "pressurizacao": st.session_state["pressurizacao"],
        "portas_cf": st.session_state["portas_cf"],
        "parecer_tecnico": st.session_state["parecer_tecnico"],
        "orientacoes_ops": st.session_state["orientacoes_ops"],
        "resp_tecnico": st.session_state["resp_tecnico"],
        "resp_cliente": st.session_state["resp_cliente"],
    }
    
    pdf_bytes = gerar_pdf(dados_relatorio, fotos_uploaded, logo_file)
    
    st.download_button(
        label="📥 Clique aqui para baixar o PDF",
        data=pdf_bytes,
        file_name="Relatorio_Vistoria.pdf",
        mime="application/pdf"
    )
