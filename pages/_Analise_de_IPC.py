# pages/2_Analise_de_ICP.py
import streamlit as st
import pandas as pd
import io
import json
import re
import unicodedata
import time
import google.generativeai as genai

st.set_page_config(layout="wide", page_title="Estação 2: Análise")

# --- FUNÇÕES DE QUALIFICAÇÃO ---

def ler_csv_flexivel(arquivo_upado):
    try:
        arquivo_upado.seek(0)
        df = pd.read_csv(arquivo_upado, sep=';', encoding='utf-8', on_bad_lines='skip', low_memory=False)
        return df
    except Exception as e:
        st.error(f"Erro ao ler o arquivo CSV: {e}")
        return None

def analisar_icp_com_ia(texto_ou_url, icp_resumido, is_url=True):
    model = genai.GenerativeModel('gemini-1.5-flash-latest')
    parte_analise = f"Visite a URL {texto_ou_url} e analise seu conteúdo." if is_url else f"Analise o seguinte resumo de negócio: '{texto_ou_url}'."
    prompt = f"""
    Analise o seguinte material: "{texto_ou_url}".
    Compare com este resumo do meu Perfil de Cliente Ideal (ICP): "{icp_resumido}"
    Responda APENAS com um JSON com as chaves: "is_segmento_correto" (boolean) e "motivo_segmento" (string).
    """
    try:
        time.sleep(1.2)
        response = model.generate_content(prompt, request_options={"timeout": 90 if is_url else 30})
        return json.loads(response.text.replace('```json', '').replace('```', '').strip())
    except Exception as e: return {"error": f"Falha: {e}"}

def resumir_icp_com_ia(criterios_icp_texto):
    st.info("Otimizando ICP para análise...")
    model = genai.GenerativeModel('gemini-1.5-flash-latest')
    prompt = f"Crie um resumo conciso e otimizado deste ICP em formato de texto para ser usado em futuros prompts: {criterios_icp_texto}"
    try:
        time.sleep(1.2)
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        st.error(f"Falha ao criar o resumo do ICP: {e}")
        return None

def verificar_funcionarios(funcionarios_lead, faixa_icp_str):
    if pd.isna(faixa_icp_str) or str(faixa_icp_str).strip() == '': return True
    if pd.isna(funcionarios_lead): return False
    try:
        funcionarios_str = str(funcionarios_lead).strip().lower().replace('.', '').replace(',', '')
        if 'k' in funcionarios_str:
            funcionarios_num = float(funcionarios_str.replace('k', '')) * 1000
        else:
            funcionarios_num = pd.to_numeric(funcionarios_str)
        if pd.isna(funcionarios_num): return False
    except (ValueError, TypeError): return False
    faixa_str = str(faixa_icp_str).lower()
    numeros = [int(s) for s in re.findall(r'\d+', faixa_str)]
    if not numeros: return False
    if "acima" in faixa_str or "maior" in faixa_str: return funcionarios_num > numeros[0]
    elif "abaixo" in faixa_str or "menor" in faixa_str: return funcionarios_num < numeros[0]
    elif "-" in faixa_str and len(numeros) == 2: return numeros[0] <= funcionarios_num <= numeros[1]
    elif len(numeros) == 1: return funcionarios_num >= numeros[0]
    return False

# --- INTERFACE DA ESTAÇÃO 2 ---
st.title("🔬 Estação 2: Análise de ICP")
st.write("Defina seu Perfil de Cliente Ideal (ICP) no formulário abaixo e suba a lista de leads já limpa para iniciar a qualificação.")

# --- Formulário para o ICP ---
st.header("1. Defina seu Perfil de Cliente Ideal (ICP)")
with st.form("icp_form"):
    st.write("Descreva os critérios para qualificar seus leads.")
    segmentos = st.text_area("Segmentos Desejados (palavras-chave separadas por vírgula)", "Serviços financeiros, Saúde, Varejo, E-commerce, Logística, Tecnologia, BPO")
    funcionarios = st.text_input("Número de Funcionários (Ex: acima de 50, 100-500)", "acima de 50")
    observacoes = st.text_area("Outras Observações Importantes (Ex: concorrentes)", "Não pode ser do setor governamental")
    
    submitted_icp = st.form_submit_button("Salvar ICP e Iniciar Análise")

st.header("2. Arquivo e Resultados")

leads_df = None
if 'df_limpo' in st.session_state:
    st.success("Arquivo de leads limpo recebido da Estação 1!")
    leads_df = st.session_state['df_limpo']
else:
    st.write("Suba o arquivo de leads limpo para iniciar.")
    uploaded_file = st.file_uploader("Selecione o arquivo de DADOS limpo (.csv)", type="csv")
    if uploaded_file:
        leads_df = ler_csv_flexivel(uploaded_file)

if submitted_icp and leads_df is not None:
    try:
        genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
    except (KeyError, AttributeError):
        st.error("Chave de API do Google não configurada.")
        st.stop()
    
    criterios_icp_texto = f"Segmentos: {segmentos}. Observações: {observacoes}"
    icp_resumido = resumir_icp_com_ia(criterios_icp_texto)
    
    if icp_resumido:
        st.success(f"Resumo do ICP para análise: **{icp_resumido}**")
        
        # Inicializa colunas de resultado se não existirem
        for col in ['classificacao_icp', 'motivo_classificacao']:
            if col not in leads_df.columns:
                leads_df[col] = ''

        progress_bar = st.progress(0)
        status_text = st.empty()

        total_leads = len(leads_df)
        for index, lead in leads_df.iterrows():
            status_text.text(f"Analisando: {lead.get('Nome_Empresa', f'Linha {index+2}')}...")
            
            if not verificar_funcionarios(lead.get('Numero_Funcionarios'), funcionarios):
                leads_df.at[index, 'classificacao_icp'] = 'Fora do ICP'
                leads_df.at[index, 'motivo_classificacao'] = 'Porte da empresa fora do perfil'
            else:
                site_url = lead.get('Site_Original')
                analise = None
                if pd.notna(site_url) and str(site_url).strip() != '':
                    analise = analisar_icp_com_ia(site_url, icp_resumido)
                else:
                    analise = {"error": "Site não informado"}
                
                if "error" not in analise:
                    if analise.get('is_segmento_correto'):
                        leads_df.at[index, 'classificacao_icp'] = 'Dentro do ICP'
                        leads_df.at[index, 'motivo_classificacao'] = analise.get('motivo_segmento')
                    else:
                        leads_df.at[index, 'classificacao_icp'] = 'Fora do ICP'
                        leads_df.at[index, 'motivo_classificacao'] = analise.get('motivo_segmento')
                else:
                    leads_df.at[index, 'classificacao_icp'] = 'Erro na Análise'
                    leads_df.at[index, 'motivo_classificacao'] = analise.get('details', 'Site não informado ou inacessível')
            
            progress_bar.progress((index + 1) / total_leads)
            
        st.success("Análise completa!")
        st.dataframe(leads_df.astype(str))
        
        csv = leads_df.to_csv(sep=';', index=False, encoding='utf-8-sig').encode('utf-8-sig')
        st.download_button(label="⬇️ Baixar Resultado Final", data=csv, file_name='leads_analisados_final.csv', mime='text/csv')

elif submitted_icp and leads_df is None:
    st.warning("Por favor, suba um arquivo de leads para analisar.")