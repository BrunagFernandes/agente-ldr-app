# app.py (Página Principal)
import streamlit as st

st.set_page_config(
    page_title="Agente LDR de IA",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("🤖 Agente LDR com Inteligência Artificial v2.0")
st.write("Bem-vindo! Esta é a central de operações para qualificação e limpeza de leads.")
st.write("---")

st.header("Fluxo de Trabalho em 2 Estações:")
st.markdown("""
1.  **Comece na Estação 1 - Limpeza de Dados:**
    * No menu à esquerda, selecione **"1_Limpeza_de_Dados"**.
    * Use esta página para subir seu arquivo bruto (exportado do Apollo ou similar).
    * O agente irá limpar, padronizar e preparar seus dados.
    * Ao final, você poderá baixar a lista limpa ou enviá-la diretamente para a análise.

2.  **Continue na Estação 2 - Análise de ICP:**
    * No menu à esquerda, selecione **"2_Analise_de_ICP"**.
    * Nesta página, você irá definir seu Perfil de Cliente Ideal (ICP) usando um formulário interativo.
    * O agente usará os dados limpos e os critérios do seu ICP para fazer a qualificação completa com a IA.
""")