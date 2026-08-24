import streamlit as st
import json
import os
from fpdf import FPDF
import tempfile

# -----------------------------------------------------------------------------
# 1. CONFIGURAÇÃO E AUTENTICAÇÃO
# -----------------------------------------------------------------------------
st.set_page_config(page_title="Eli Sistemas - SDAI", layout="wide")

RASCUNHO_FILE = "rascunho_relatorio.json"

# Inicializa o estado de autenticação
if "autenticado" not in st.session_state:
    st.session_state["autenticado"] = False

# -----------------------------------------------------------------------------
# TELA DE LOGIN (SÓ MOSTRA SE NÃO ESTIVER AUTENTICADO)
# -----------------------------------------------------------------------------
if not st.session_state["autenticado"]:
    st.title("🔑 Login do Sistema - Eli Sistemas")
    
    col_login, _ = st.columns([1, 1])
    with col_login:
        usuario = st.text_input("Usuário", key="user_login")
        senha = st.text_input("Senha", type="password", key="pass_login")
        
        if st.button("Entrar", type="primary"):
            # Validação simples (pode alterar o usuário e senha aqui)
            if usuario.strip() != "" and senha.strip() != "":
                st.session_state["autenticado"] = True
                st.session_state["usuario"] = usuario
                st.rerun()
            else:
                st.error("Por favor, preencha o usuário e a senha.")

# -----------------------------------------------------------------------------
# SISTEMA COMPLETO (SÓ CARREGA APÓS O LOGIN)
# -----------------------------------------------------------------------------
else:
    # --- MENU LATERAL (SIDEBAR) ---
    with st.sidebar:
        st.title("⚡ Eli Sistemas")
        st.write(f"Usuário: **{st.session_state.get('usuario', 'Admin')}**")
        
        opcao_menu = st.radio(
            "Navegação",
            ["Vistoria & Relatório Técnico NBR", "Cadastro da Empresa / Logo"]
        )
        
        st.divider()
        if st.button("🚪 Sair / Logout"):
            st.session_state["autenticado"] = False
            st.rerun()

    # -------------------------------------------------------------------------
    # GERADOR DE PDF (FPDF)
    # -------------------------------------------------------------------------
    class RelatorioPDF(FPDF):
        def __init__(self, logo_path=None):
            super().__init__()
            self.logo_path = logo_path

        def header(self):
            if self.logo_path and os.path.exists(self.logo_path):
                self.image(self.logo_path, x=10, y=8, w=25)
                self.set_x(40)
                self.set_font("Arial", "B", 11)
                self.cell(0, 10, "RELATÓRIO TÉCNICO DE VISTORIA - SDAI / NBR", border=True, ln=True, align="C")
            else:
                self.set_font("Arial", "B", 11)
                self.cell(0, 10, "RELATÓRIO TÉCNICO DE VISTORIA - SDAI / NBR", border=True, ln=True, align="C")
            self.ln(5)

        def footer(self):
            self.set_y(-15)
            self.set_font("Arial", "I", 8)
            self.cell(0, 10, f"Página {self.page_no()}/{{nb}}", align="C")

    def gerar_pdf_completo(dados, fotos_bytes, logo_bytes):
        logo_temp_path = None
        if logo_bytes is not None:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp_logo:
                tmp_logo.write(logo_bytes.getvalue())
                logo_temp_path = tmp_logo.name

        pdf = RelatorioPDF(logo_path=logo_temp_path)
        pdf.alias_nb_pages()
        pdf.add_page()

        colunas = ["Item / Periférico", "Parâmetro Normativo", "Valor Medido", "Status", "Observações"]

        if "secoes" in dados:
            for titulo_secao, itens in dados["secoes"].items():
                pdf.set_font("Arial", "B", 10)
                pdf.cell(0, 7, titulo_secao, ln=True)
                
                pdf.set_font("Arial", "B", 8)
                larguras = [45, 60, 20, 25, 40]
                for i, col in enumerate(colunas):
                    pdf.cell(larguras[i], 6, col, border=1, align="C")
                pdf.ln()

                pdf.set_font("Arial", size=8)
                for linha in itens:
                    pdf.cell(larguras[0], 6, str(linha.get("item", "")), border=1)
                    pdf.cell(larguras[1], 6, str(linha.get("parametro", "")), border=1)
                    pdf.cell(larguras[2], 6, str(linha.get("valor", "")), border=1, align="C")
                    pdf.cell(larguras[3], 6, str(linha.get("status", "")), border=1, align="C")
                    pdf.cell(larguras[4], 6, str(linha.get("obs", "")), border=1)
                    pdf.ln()
                pdf.ln(3)

        pdf.set_font("Arial", "B", 10)
        pdf.cell(0, 7, "7. CONCLUSÃO TÉCNICA E ORIENTAÇÕES OPERACIONAIS", ln=True)
        pdf.set_font("Arial", "B", 8)
        pdf.cell(0, 5, "Parecer Técnico / Conclusão:", ln=True)
        pdf.set_font("Arial", size=8)
        pdf.multi_cell(0, 4, dados.get("parecer_tecnico", "Sem observações."), border=1)
        pdf.ln(2)

        pdf.set_font("Arial", "B", 8)
        pdf.cell(0, 5, "Orientações Operacionais:", ln=True)
        pdf.set_font("Arial", size=8)
        pdf.multi_cell(0, 4, dados.get("orientacoes_ops", "Sem orientações."), border=1)
        pdf.ln(4)

        pdf.set_font("Arial", "B", 10)
        pdf.cell(0, 7, "8. VALIDAÇÃO E ASSINATURAS TÉCNICAS", ln=True)
        pdf.set_font("Arial", size=8)
        pdf.cell(95, 5, f"Responsável Técnico: {dados.get('resp_tecnico', '')}", border=0)
        pdf.cell(95, 5, f"Responsável / Síndico: {dados.get('resp_cliente', '')}", ln=True)
        pdf.ln(8)
        pdf.cell(95, 5, "____________________________________", border=0)
        pdf.cell(95, 5, "____________________________________", ln=True)
        pdf.cell(95, 5, "Assinatura do Técnico", border=0)
        pdf.cell(95, 5, "Assinatura do Cliente / Recebedor", ln=True)

        if fotos_bytes:
            pdf.add_page()
            pdf.set_font("Arial", "B", 11)
            pdf.cell(0, 8, "ANEXO FOTOGRÁFICO", ln=True, align="C")
            pdf.ln(4)

            for foto in fotos_bytes:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp_foto:
                    tmp_foto.write(foto.getvalue())
                    tmp_foto_path = tmp_foto.name

                pdf.image(tmp_foto_path, w=90)
                pdf.ln(4)
                os.remove(tmp_foto_path)

        if logo_temp_path and os.path.exists(logo_temp_path):
            os.remove(logo_temp_path)

        return pdf.output(dest='S').encode('latin-1')

    # -------------------------------------------------------------------------
    # NAVEGAÇÃO DE PÁGINAS (PÓS-LOGIN)
    # -------------------------------------------------------------------------
    if opcao_menu == "Cadastro da Empresa / Logo":
        st.title("🏢 Cadastro da Empresa e Logo")
        logo_file = st.file_uploader("Upload do Logo da Empresa", type=["png", "jpg", "jpeg"], key="logo_upload")
        if logo_file:
            st.session_state["logo_empresa"] = logo_file
            st.image(logo_file, width=150, caption="Logo Carregado")

    elif opcao_menu == "Vistoria & Relatório Técnico NBR":
        st.title("⚡ Vistoria & Relatório Técnico NBR")

        if "relatorio_data" not in st.session_state:
            st.session_state["relatorio_data"] = {
                "qtd_detectores": "0",
                "qtd_acionadores": "0",
                "qtd_avisadores": "0",
                "parecer_tecnico": "",
                "orientacoes_ops": "",
                "resp_tecnico": "Eli Silva",
                "resp_cliente": "Sr. Edson, portaria e vigia do plantão",
                "secoes": {
                    "3. Central & Fontes": [
                        {"item": "Painel Principal", "parametro": "Supervisão e Leds", "valor": "OK", "status": "CONFORME", "obs": "Operando"}
                    ],
                    "4. Laços": [
                        {"item": "Laço 01", "parametro": "Tensão de Comunicação", "valor": "24V", "status": "CONFORME", "obs": "Normal"}
                    ],
                    "5. Periféricos": [
                        {"item": "5.4 Módulos E/S", "parametro": "Endereçamento e Supervisão", "valor": "OK", "status": "CONFORME", "obs": "Operando"}
                    ],
                    "6. PRESSURIZAÇÃO DE ESCADAS DE SEGURANÇA & INTERLIGAÇÕES (IT 13)": [
                        {"item": "6.1 Pressurização Escadas", "parametro": "Acionamento p/ fluxostato/SDAI", "valor": "OK", "status": "CONFORME", "obs": "Todos os módulos atuaram normalmente"},
                        {"item": "6.2 Portas Corta-Fogo / Eletroímãs", "parametro": "Liberação automática eletroímãs", "valor": "NA", "status": "N/A", "obs": "NA"}
                    ]
                }
            }

        col_r1, col_r2, _ = st.columns([1, 1, 2])
        with col_r1:
            if st.button("💾 Salvar Rascunho"):
                with open(RASCUNHO_FILE, "w", encoding="utf-8") as f:
                    json.dump(st.session_state["relatorio_data"], f, ensure_ascii=False, indent=4)
                st.success("Rascunho salvo!")

        with col_r2:
            if st.button("📂 Carregar Rascunho"):
                if os.path.exists(RASCUNHO_FILE):
                    with open(RASCUNHO_FILE, "r", encoding="utf-8") as f:
                        st.session_state["relatorio_data"] = json.load(f)
                    st.success("Rascunho carregado!")
                    st.rerun()
                else:
                    st.warning("Nenhum rascunho encontrado.")

        st.divider()

        c1, c2, c3 = st.columns(3)
        with c1:
            st.session_state["relatorio_data"]["qtd_detectores"] = st.text_input("Qtd. Detectores Fumaça/Térmicos", st.session_state["relatorio_data"]["qtd_detectores"])
        with c2:
            st.session_state["relatorio_data"]["qtd_acionadores"] = st.text_input("Qtd. Acionadores Manuais", st.session_state["relatorio_data"]["qtd_acionadores"])
        with c3:
            st.session_state["relatorio_data"]["qtd_avisadores"] = st.text_input("Qtd. Avisadores Sonoros/Visuais", st.session_state["relatorio_data"]["qtd_avisadores"])

        st.subheader("🔍 Verificação dos Itens Normativos (Checklist)")

        for titulo_secao, itens in st.session_state["relatorio_data"]["secoes"].items():
            with st.expander(titulo_secao, expanded=False):
                for idx, item in enumerate(itens):
                    st.markdown(f"**Item: {item['item']}**")
                    col_a, col_b, col_c, col_d = st.columns([2, 1, 1, 2])
                    with col_a:
                        item["parametro"] = st.text_input(f"Parâmetro ({idx})", item["parametro"], key=f"p_{titulo_secao}_{idx}")
                    with col_b:
                        item["valor"] = st.text_input(f"Valor ({idx})", item["valor"], key=f"v_{titulo_secao}_{idx}")
                    with col_c:
                        item["status"] = st.selectbox(f"Status ({idx})", ["CONFORME", "NÃO CONFORME", "N/A"], index=0 if item["status"]=="CONFORME" else 2, key=f"s_{titulo_secao}_{idx}")
                    with col_d:
                        item["obs"] = st.text_input(f"Observação ({idx})", item["obs"], key=f"o_{titulo_secao}_{idx}")

        with st.expander("7. Conclusão Técnica e Orientações Operacionais", expanded=True):
            st.session_state["relatorio_data"]["parecer_tecnico"] = st.text_area(
                "Parecer Técnico / Conclusão",
                value=st.session_state["relatorio_data"]["parecer_tecnico"],
                height=100
            )
            st.session_state["relatorio_data"]["orientacoes_ops"] = st.text_area(
                "Orientações Operacionais",
                value=st.session_state["relatorio_data"]["orientacoes_ops"],
                height=100
            )

        with st.expander("📷 Anexo Fotográfico", expanded=True):
            fotos_uploaded = st.file_uploader("Selecione as fotos da vistoria", type=["png", "jpg", "jpeg"], accept_multiple_files=True)

        with st.expander("8. Validação e Assinaturas Técnicas", expanded=True):
            col_t1, col_t2 = st.columns(2)
            with col_t1:
                st.session_state["relatorio_data"]["resp_tecnico"] = st.text_input("Responsável Técnico", st.session_state["relatorio_data"]["resp_tecnico"])
            with col_t2:
                st.session_state["relatorio_data"]["resp_cliente"] = st.text_input("Responsável / Síndico / Portaria", st.session_state["relatorio_data"]["resp_cliente"])

        st.divider()

        if st.button("📄 GERAR E BAIXAR RELATÓRIO PDF", type="primary"):
            logo_salva = st.session_state.get("logo_empresa", None)
            pdf_bytes = gerar_pdf_completo(st.session_state["relatorio_data"], fotos_uploaded, logo_salva)
            
            st.download_button(
                label="📥 Clique aqui para baixar o PDF",
                data=pdf_bytes,
                file_name="Relatorio_Vistoria.pdf",
                mime="application/pdf"
            )
