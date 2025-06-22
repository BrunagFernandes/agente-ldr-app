# --- VERSÃO COM CORREÇÃO FINAL NA LÓGICA DE LOCALIDADE ---
import streamlit as st
import pandas as pd
import io
import json
import re
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
    Você é um Analista de Leads Sênior. Visite a URL {url_do_lead} e responda em JSON.
    Critérios do ICP:
    - {info_base_comparacao}
    - Segmentos Válidos: [{criterios_icp.get('segmento_desejado_do_lead', 'N/A')}]
    Responda APENAS com um objeto JSON válido com as chaves: "is_concorrente", "motivo_concorrente", "is_segmento_correto", "motivo_segmento", "categoria_segmento".
    """
    try:
        response = model.generate_content(prompt, request_options={"timeout": 90})
        resposta_texto = response.text.replace('```json', '').replace('```', '').strip()
        return json.loads(resposta_texto)
    except Exception as e:
        return {"error": "Falha na análise da IA", "details": str(e)}

def verificar_cargo(cargo_lead, cargos_icp_str):
    """Verifica se o cargo do lead está na lista de interesse do ICP."""
    if pd.isna(cargos_icp_str) or str(cargos_icp_str).strip() == '': return True
    if pd.isna(cargo_lead) or str(cargo_lead).strip() == '': return False
    cargos_de_interesse = [cargo.strip().lower() for cargo in str(cargos_icp_str).split(',')]
    return str(cargo_lead).strip().lower() in cargos_de_interesse

def verificar_funcionarios(funcionarios_lead, faixa_icp_str):
    """Verifica se o número de funcionários do lead está na faixa do ICP."""
    if pd.isna(faixa_icp_str) or str(faixa_icp_str).strip() == '':
        return True
    if pd.isna(funcionarios_lead):
        return False
    try:
        funcionarios_str = str(funcionarios_lead).strip().lower().replace('.', '').replace(',', '')
        if 'k' in funcionarios_str:
            funcionarios_num = float(funcionarios_str.replace('k', '')) * 1000
        else:
            funcionarios_num = pd.to_numeric(funcionarios_str)
        if pd.isna(funcionarios_num): return False
    except (ValueError, TypeError):
        return False
    faixa_str = str(faixa_icp_str).lower()
    numeros = [int(s) for s in re.findall(r'\d+', faixa_str)]
    if not numeros: return False
    if "acima" in faixa_str or "maior" in faixa_str:
        return funcionarios_num > numeros[0]
    elif "abaixo" in faixa_str or "menor" in faixa_str:
        return funcionarios_num < numeros[0]
    elif "-" in faixa_str and len(numeros) == 2:
        return numeros[0] <= funcionarios_num <= numeros[1]
    elif len(numeros) == 1:
        return funcionarios_num >= numeros[0]
    return False

# --- FUNÇÃO DE LOCALIDADE FINALMENTE CORRIGIDA ---
def verificar_localidade(lead_row, locais_icp):
    """Verifica se a localidade do lead atende a múltiplos critérios ou regiões."""
    if isinstance(locais_icp, str):
        locais_icp = [locais_icp]
    
    if not locais_icp: # Se a lista de locais for vazia, aprova todos.
        return True

    # Se a regra for apenas "brasil", aprova todos
    if len(locais_icp) == 1 and locais_icp[0].strip().lower() == 'brasil':
        return True

    regioes = {
        'sudeste': ['sp', 'rj', 'es', 'mg'], 'sul': ['pr', 'sc', 'rs'],
        'nordeste': ['ba', 'se', 'al', 'pe', 'pb', 'rn', 'ce', 'pi', 'ma'],
        'norte': ['ro', 'ac', 'am', 'rr', 'pa', 'ap', 'to'],
        'centro-oeste': ['ms', 'mt', 'go', 'df']
    }

    cidade_lead = str(lead_row.get('Cidade_Contato', '')).strip().lower()
    estado_lead = str(lead_row.get('Estado_Contato', '')).strip().lower()
    pais_lead = str(lead_row.get('Pais_Contato', '')).strip().lower()
    
    for local_permitido in locais_icp:
        local_permitido_clean = local_permitido.lower().strip()
        if local_permitido_clean in regioes:
            if estado_lead in regioes[local_permitido_clean]:
                return True 
        else:
            partes_requisito = [part.strip().lower() for part in local_permitido_clean.split(',')]
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
            criterios_icp_raw = icp_raw_df.groupby('Campo_ICP')['Valor_ICP'].apply(lambda x: list(x) if len(x) > 1 else x.iloc[0]).to_dict()
            criterios_icp = {str(k).lower().strip(): v for k, v in criterios_icp_raw.items()}
            
            for col in ['classificacao_icp', 'motivo_classificacao', 'categoria_do_lead', 'cargo_valido']:
                if col not in leads_df.columns:
                    leads_df[col] = ''
            leads_df['cargo_valido'] = False

            st.info("Iniciando processamento...")
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            for index, lead in leads_df.iterrows():
                status_text.text(f"Analisando: {lead.get('Nome_Empresa', f'Linha {index+2}')}...")
                
                # --- QUALIFICAÇÃO LOCAL HIERÁRQUICA ---
                funcionarios_ok = verificar_funcionarios(lead.get('Numero_Funcionarios'), criterios_icp.get('numero_de_funcionarios_desejado_do_lead'))
                if not funcionarios_ok:
                    leads_df.at[index, 'classificacao_icp'] = 'Fora do ICP'
                    leads_df.at[index, 'motivo_classificacao'] = 'Porte da empresa fora do perfil'
                    progress_bar.progress((index + 1) / len(leads_df))
                    continue

                localidade_ok = verificar_localidade(lead, criterios_icp.get('localidade_especifica_do_lead', []))
                if not localidade_ok:
                    leads_df.at[index, 'classificacao_icp'] = 'Fora do ICP'
                    leads_df.at[index, 'motivo_classificacao'] = 'Localidade fora do perfil'
                    progress_bar.progress((index + 1) / len(leads_df))
                    continue

                leads_df.at[index, 'cargo_valido'] = verificar_cargo(lead.get('Cargo'), criterios_icp.get('cargos_de_interesse_do_lead'))

                # --- ANÁLISE COM IA ---
                site_url = lead.get('Site_Original')
                if pd.notna(site_url) and str(site_url).strip() != '':
                    if not str(site_url).startswith(('http://', 'https://')):
                        site_url = 'https://' + str(site_url)
                    
                    analise = analisar_icp_com_ia_por_url(site_url, criterios_icp)
                    
                    if "error" not in analise:
                        leads_df.at[index, 'categoria_do_lead'] = analise.get('categoria_segmento', 'N/A')
                        if analise.get('is_segmento_correto') and not analise.get('is_concorrente'):
                            leads_df.at[index, 'classificacao_icp'] = 'Dentro do ICP'
                            leads_df.at[index, 'motivo_classificacao'] = analise.get('motivo_segmento')
                        else:
                            leads_df.at[index, 'classificacao_icp'] = 'Fora do ICP'
                            motivo = f"Concorrente: {analise.get('is_concorrente')}" if analise.get('is_concorrente') else f"Segmento incorreto: {analise.get('motivo_segmento')}"
                            leads_df.at[index, 'motivo_classificacao'] = motivo
                    else:
                        leads_df.at[index, 'classificacao_icp'] = 'Erro na Análise'
                        leads_df.at[index, 'motivo_classificacao'] = analise.get('details', 'Erro desconhecido da IA.')
                else:
                    leads_df.at[index, 'classificacao_icp'] = 'Ponto de Atenção'
                    leads_df.at[index, 'motivo_classificacao'] = 'Site não informado'
                
                progress_bar.progress((index + 1) / len(leads_df))
            
            status_text.success("Processamento completo!")
            st.dataframe(leads_df)
            
            csv = leads_df.to_csv(sep=';', index=False, encoding='utf-8-sig').encode('utf-8-sig')
            st.download_button(label="⬇️ Baixar resultado completo (.csv)", data=csv, file_name='leads_analisados_final.csv', mime='text/csv')
    else:
        st.warning("Por favor, faça o upload dos dois arquivos CSV para continuar.")