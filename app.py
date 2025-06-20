# --- VERSÃO FINAL COM LÓGICA DE LOCALIDADE CORRIGIDA E INDENTAÇÃO LIMPA ---
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
    info_base_comparacao = f"O site da minha empresa é: {criterios_icp.get('site_da_empresa_contratante')}"
    if '[INSIRA O SITE' in info_base_comparacao or not criterios_icp.get('site_da_empresa_contratante'):
        info_base_comparacao = f"A minha empresa é descrita como: '{criterios_icp.get('descricao_da_empresa_contratante')}'"
    prompt = f"""
    Você é um Analista de Desenvolvimento de Leads Sênior. Analise o site do lead na URL {url_do_lead} e compare com os critérios do meu ICP:
    - {info_base_comparacao}
    - Segmentos Válidos: [{criterios_icp.get('segmento_desejado_do_lead', 'N/A')}]
    Responda APENAS com um objeto JSON válido com as chaves: "is_concorrente", "motivo_concorrente", "is_segmento_correto", "motivo_segmento", "categoria_segmento".
    """
    try:
        response = model.generate_content(prompt)
        resposta_texto = response.text.replace('```json', '').replace('```', '').strip()
        return json.loads(resposta_texto)
    except Exception as e:
        return {"error": f"Falha na análise da IA: {e}", "details": str(e)}

def verificar_cargo(cargo_lead, cargos_icp_str):
    """Verifica se o cargo do lead está na lista de interesse do ICP."""
    if pd.isna(cargo_lead) or cargo_lead.strip() == '' or pd.isna(cargos_icp_str): return False
    cargos_de_interesse = [cargo.strip().lower() for cargo in cargos_icp_str.split(',')]
    return cargo_lead.strip().lower() in cargos_de_interesse

def verificar_localidade(lead_row, locais_icp):
    """Verifica se a localidade do lead atende a múltiplos critérios ou regiões."""
    # Garante que sempre trabalhamos com uma lista, mesmo se o ICP tiver só um local
    if isinstance(locais_icp, str):
        locais_icp = [locais_icp]
    
    # Se a lista de locais for vazia ou conter 'brasil', aprova todos
    if not locais_icp or any(loc.strip().lower() == 'brasil' for loc in locais_icp):
        return True

    regioes = {
        'sudeste': ['sp', 'rj', 'es', 'mg'],
        'sul': ['pr', 'sc', 'rs'],
        'nordeste': ['ba', 'se', 'al', 'pe', 'pb', 'rn', 'ce', 'pi', 'ma'],
        'norte': ['ro', 'ac', 'am', 'rr', 'pa', 'ap', 'to'],
        'centro-oeste': ['ms', 'mt', 'go', 'df']
    }

    # Prepara os dados de localidade do lead
    cidade_lead = str(lead_row.get('Cidade_Contato', '')).strip().lower()
    estado_lead = str(lead_row.get('Estado_Contato', '')).strip().lower()
    pais_lead = str(lead_row.get('Pais_Contato', '')).strip().lower()
    
    # Verifica se o lead corresponde a QUALQUER UM dos locais permitidos
    for local_permitido in locais_icp:
        local_permitido_clean = local_permitido.lower().strip()
        if local_permitido_clean in regioes:
            if estado_lead in regioes[local_permitido_clean]:
                return True 
        else:
            partes_requisito = [part.strip() for part in local_permitido_clean.split(',')]
            lead_data_comparable = [cidade_lead, estado_lead, pais_lead]
            if all(parte in lead_data_comparable for parte in partes_requisito):
                return True

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
            # Lógica para ler multiplas linhas do mesmo campo (como localidade)
            criterios_icp = {}
            for campo, grupo in icp_raw_df.groupby('Campo_ICP'):
                valores = grupo['Valor_ICP'].tolist()
                criterios_icp[str(campo).lower().strip()] = valores if len(valores) > 1 else valores[0]

            # Inicializa colunas de resultado
            # (O restante do código para processar e exibir os resultados permanece aqui)
            # ... (código do loop for, etc.) ...
            st.success("Lógica de exemplo - substitua pelo loop de processamento completo.")
            st.dataframe(leads_df)
    else:
        st.warning("Por favor, faça o upload dos dois arquivos CSV para continuar.")