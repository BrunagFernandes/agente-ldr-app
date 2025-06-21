# --- VERSÃO FINAL COM CORREÇÃO DA FUNÇÃO VERIFICAR_CARGO ---
import streamlit as st
import pandas as pd
import io
import json
import google.generativeai as genai

# --- FUNÇÕES DO AGENTE ---

def ler_csv_flexivel(arquivo_upado):
    """Lê um arquivo CSV com separador flexível."""
    try:
        arquivo_upado.seek(0)
        df = pd.read_csv(arquivo_upado, sep=';', encoding='utf-8', on_bad_lines='skip')
        if df.shape[1] == 1:
            arquivo_upado.seek(0)
            df = pd.read_csv(arquivo_upado, sep=',', encoding='utf-8', on_bad_lines='skip')
        return df
    except Exception as e:
        st.error(f"Erro crítico ao ler o arquivo CSV: {e}")
        return None

def analisar_icp_com_ia_por_url(url_do_lead, criterios_icp):
    """Usa a IA para visitar a URL e fazer a análise completa do ICP."""
    model = genai.GenerativeModel('gemini-1.5-flash-latest')
    info_base_comparacao = f"O site da minha empresa é: {criterios_icp.get('site_da_empresa_contratante', 'Não informado')}"
    if '[INSIRA' in str(criterios_icp.get('site_da_empresa_contratante', '')):
        info_base_comparacao = f"A minha empresa é descrita como: '{criterios_icp.get('descricao_da_empresa_contratante', 'Não informado')}'"
    
    prompt = f"""
    Você é um Analista de Desenvolvimento de Leads Sênior. Analise o site do lead na URL {url_do_lead} e compare com os critérios do meu ICP.
    Responda APENAS com um objeto JSON válido com as chaves: "is_concorrente", "motivo_concorrente", "is_segmento_correto", "motivo_segmento", "categoria_segmento".
    """
    try:
        response = model.generate_content(prompt, request_options={"timeout": 60})
        resposta_texto = response.text.replace('```json', '').replace('```', '').strip()
        return json.loads(resposta_texto)
    except Exception as e:
        return {"error": f"Falha na análise da IA: {e}", "details": str(e)}

# --- FUNÇÃO DE CARGO CORRIGIDA ---
def verificar_cargo(cargo_lead, cargos_icp_str):
    """Verifica se o cargo do lead está na lista de interesse do ICP, tratando strings."""
    # Nova verificação, segura para strings: checa se os valores são nulos ou vazios
    if not cargo_lead or not cargos_icp_str:
        return False
    
    # Garante que ambos são strings antes de prosseguir
    cargo_lead_str = str(cargo_lead).strip().lower()
    cargos_icp_str_flat = str(cargos_icp_str)
    
    if not cargo_lead_str or not cargos_icp_str_flat:
        return False

    cargos_de_interesse = [cargo.strip().lower() for cargo in cargos_icp_str_flat.split(',')]
    return cargo_lead_str in cargos_de_interesse

# (As outras funções como verificar_localidade permanecem as mesmas)
def verificar_localidade(lead_row, locais_icp):
    if isinstance(locais_icp, str):
        locais_icp = [locais_icp]
    if not locais_icp or any(loc.strip().lower() == 'brasil' for loc in locais_icp):
        return True
    regioes = { 'sudeste': ['sp', 'rj', 'es', 'mg'], 'sul': ['pr', 'sc', 'rs'], 'nordeste': ['ba', 'se', 'al', 'pe', 'pb', 'rn', 'ce', 'pi', 'ma'], 'norte': ['ro', 'ac', 'am', 'rr', 'pa', 'ap', 'to'], 'centro-oeste': ['ms', 'mt', 'go', 'df'] }
    cidade_lead = str(lead_row.get('Cidade_Contato', '')).strip().lower()
    estado_lead = str(lead_row.get('Estado_Contato', '')).strip().lower()
    pais_lead = str(lead_row.get('Pais_Contato', '')).strip().lower()
    for local_permitido in locais_icp:
        local_permitido_clean = local_permitido.lower().strip()
        if local_permitido_clean in regioes:
            if estado_lead in regioes[local_permitido_clean]: return True 
        else:
            partes_requisito = [part.strip() for part in local_permitido_clean.split(',')]
            lead_data_comparable = [cidade_lead, estado_lead, pais_lead]
            if all(parte in lead_data_comparable for parte in partes_requisito): return True
    return False

# --- INTERFACE DO APLICATIVO (STREAMLIT) ---
st.set_page_config(layout="wide", page_title="Agente LDR de IA")
st.title("🤖 Agente LDR com Inteligência Artificial")
st.write("Faça o upload dos seus arquivos para qualificação e análise de leads.")

arquivo_dados = st.file_uploader("1. Selecione o arquivo de DADOS (.csv)", type="csv")
arquivo_icp = st.file_uploader("2. Selecione o arquivo de ICP (.csv)", type="csv")

if st.button("🚀 Iniciar Análise Inteligente"):
    if arquivo_dados and arquivo_icp:
        try:
            genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
        except (KeyError, AttributeError):
            st.error("Chave de API do Google não configurada.")
            st.stop()
        
        st.info("Lendo arquivos...")
        leads_df = ler_csv_flexivel(arquivo_dados)
        icp_raw_df = ler_csv_flexivel(arquivo_icp)

        if leads_df is not None and icp_raw_df is not None:
            criterios_icp_raw = dict(zip(icp_raw_df.groupby('Campo_ICP')['Valor_ICP'].apply(lambda x: list(x) if len(x) > 1 else x.iloc[0])))
            criterios_icp = {str(k).lower().strip(): v for k, v in criterios_icp_raw.items()}
            
            for col in ['classificacao_icp', 'motivo_classificacao']:
                if col not in leads_df.columns:
                    leads_df[col] = ''

            st.info("Iniciando processamento...")
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            for index, lead in leads_df.iterrows():
                status_text.text(f"Analisando: {lead.get('Nome_Empresa', 'Empresa Desconhecida')}...")
                
                # A chamada da função agora é mais segura
                cargo_ok = verificar_cargo(lead.get('Cargo'), criterios_icp.get('cargos_de_interesse_do_lead'))
                localidade_ok = verificar_localidade(lead, criterios_icp.get('localidade_especifica_do_lead', []))

                if not cargo_ok or not localidade_ok:
                    leads_df.at[index, 'classificacao_icp'] = 'Fora do ICP'
                    # ... (lógica de motivo) ...
                else:
                    # ... (lógica de análise com IA) ...
                    leads_df.at[index, 'classificacao_icp'] = 'Dentro do ICP (Local)' # Placeholder
                
                progress_bar.progress((index + 1) / len(leads_df))
            
            status_text.success("Processamento completo!")
            st.dataframe(leads_df)
            
            csv = leads_df.to_csv(sep=';', index=False, encoding='utf-8-sig').encode('utf-8-sig')
            st.download_button(label="⬇️ Baixar resultado completo (.csv)", data=csv, file_name='leads_analisados_final.csv', mime='text/csv')
    else:
        st.warning("Por favor, faça o upload dos dois arquivos CSV para continuar.")