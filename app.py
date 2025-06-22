# --- VERSÃO COM CORREÇÃO DO NAMEERROR ---
import streamlit as st
import pandas as pd
import io
import json
import re
import google.generativeai as genai

# --- FUNÇÕES DO AGENTE ---

def ler_csv_flexivel(arquivo_upado):
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

def enriquecer_site_com_ia(nome_empresa, cidade, estado):
    model = genai.GenerativeModel('gemini-1.5-flash-latest')
    prompt = f"""
    Sua única tarefa é agir como um especialista em busca na web para encontrar a URL do site oficial da empresa chamada "{nome_empresa}", localizada aproximadamente em "{cidade}, {estado}".
    REGRAS: FOCO TOTAL em encontrar o site principal (.com, .com.br). EVITE redes sociais ou diretórios.
    Responda APENAS com a URL limpa (ex: www.empresa.com.br) ou com a palavra "N/A" se não encontrar.
    """
    try:
        response = model.generate_content(prompt, request_options={"timeout": 60})
        site = response.text.strip()
        if '.' in site and len(site) > 4 and ' ' not in site and site != "N/A":
            return site
        else:
            return "N/A"
    except Exception:
        return "N/A"

def analisar_presenca_online(nome_empresa, cidade):
    model = genai.GenerativeModel('gemini-1.5-flash-latest')
    prompt = f"""
    Você é um detetive de negócios online. Investigue a empresa '{nome_empresa}' de '{cidade}'.
    AÇÕES: 1. Faça uma busca na internet, priorizando o perfil da empresa no LinkedIn. 2. Responda ao JSON abaixo.
    REGRAS: Para 'ativa', procure por posts/notícias nos últimos 12 meses. Se não houver, considere 'inativa'.
    Responda APENAS com um objeto JSON válido com as chaves: "resumo_negocio", "is_ativa", "fonte_informacao".
    """
    try:
        response = model.generate_content(prompt, request_options={"timeout": 60})
        resposta_texto = response.text.replace('```json', '').replace('```', '').strip()
        return json.loads(resposta_texto)
    except Exception as e:
        return {"error": "Falha na análise de presença online", "details": str(e)}

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

def analisar_icp_com_ia_por_resumo(resumo_negocio, criterios_icp):
    """Usa a IA para analisar um RESUMO DE NEGÓCIO."""
    model = genai.GenerativeModel('gemini-1.5-flash-latest')
    info_base_comparacao = f"O site da minha empresa é: {criterios_icp.get('site_da_empresa_contratante', 'Não informado')}"
    if '[INSIRA' in str(criterios_icp.get('site_da_empresa_contratante', '')):
        info_base_comparacao = f"A minha empresa é descrita como: '{criterios_icp.get('descricao_da_empresa_contratante', 'Não informado')}'"
    
    prompt = f"""
    Você é um Analista de Leads Sênior. Analise o seguinte resumo de negócio: '{resumo_negocio}'.
    Compare o que você leu com os critérios do meu ICP:
    - {info_base_comparacao}
    - Segmentos Válidos: [{criterios_icp.get('segmento_desejado_do_lead', 'N/A')}]
    Responda APENAS com um objeto JSON válido com as chaves: "is_concorrente", "motivo_concorrente", "is_segmento_correto", "motivo_segmento", "categoria_segmento".
    """
    try:
        response = model.generate_content(prompt, request_options={"timeout": 30})
        resposta_texto = response.text.replace('```json', '').replace('```', '').strip()
        return json.loads(resposta_texto)
    except Exception as e:
        return {"error": "Falha na análise da IA", "details": str(e)}

def verificar_cargo(cargo_lead, cargos_icp_str):
    if pd.isna(cargos_icp_str) or str(cargos_icp_str).strip() == '': return True
    if pd.isna(cargo_lead) or str(cargo_lead).strip() == '': return False
    cargos_de_interesse = [cargo.strip().lower() for cargo in str(cargos_icp_str).split(',')]
    return str(cargo_lead).strip().lower() in cargos_de_interesse

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

def verificar_localidade(lead_row, locais_icp):
    if isinstance(locais_icp, str): locais_icp = [locais_icp]
    if not locais_icp or any(loc.strip().lower() == 'brasil' for loc in locais_icp): return True
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
            if estado_lead in regioes[local_permitido_clean]: return True 
        else:
            partes_requisito = [part.strip().lower() for part in local_permitido_clean.split(',')]
            lead_data_comparable = [cidade_lead, estado_lead, pais_lead]
            if all(parte in lead_data_comparable for parte in partes_requisito): return True
    return False

# --- INTERFACE DO APLICATIVO (STREAMLIT) ---
st.set_page_config(layout="wide", page_title="Agente LDR de IA")
st.title("🤖 Agente LDR com Inteligência Artificial")
st.write("Faça o upload dos seus arquivos para qualificação e enriquecimento de leads.")

arquivo_dados = st.file_uploader("1. Selecione o arquivo de DADOS (.csv)", type="csv")
arquivo_icp = st.file_uploader("2. Selecione o arquivo de ICP (.csv)", type="csv")

if st.button("🚀 Iniciar Análise e Enriquecimento"):
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
            
            if 'Site_Original' not in leads_df.columns:
                leads_df['Site_Original'] = ''
            
            for col in ['classificacao_icp', 'motivo_classificacao', 'categoria_do_lead', 'cargo_valido']:
                if col not in leads_df.columns:
                    leads_df[col] = ''
            
            st.info("Iniciando processamento...")
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            for index, lead in leads_df.iterrows():
                status_text.text(f"Analisando: {lead.get('Nome_Empresa', f'Linha {index+2}')}...")
                
                if not verificar_funcionarios(lead.get('Numero_Funcionarios'), criterios_icp.get('numero_de_funcionarios_desejado_do_lead')):
                    leads_df.at[index, 'classificacao_icp'] = 'Fora do ICP'
                    leads_df.at[index, 'motivo_classificacao'] = 'Porte da empresa fora do perfil'
                    progress_bar.progress((index + 1) / len(leads_df))
                    continue
                if not verificar_localidade(lead, criterios_icp.get('localidade_especifica_do_lead', [])):
                    leads_df.at[index, 'classificacao_icp'] = 'Fora do ICP'
                    leads_df.at[index, 'motivo_classificacao'] = 'Localidade fora do perfil'
                    progress_bar.progress((index + 1) / len(leads_df))
                    continue

                leads_df.at[index, 'cargo_valido'] = verificar_cargo(lead.get('Cargo'), criterios_icp.get('cargos_de_interesse_do_lead'))
                
                site_para_analise = lead.get('Site_Original')
                
                if pd.isna(site_para_analise) or str(site_para_analise).strip() == '':
                    status_text.text(f"Site não informado. Enriquecendo para {lead.get('Nome_Empresa')}...")
                    site_enriquecido = enriquecer_site_com_ia(lead.get('Nome_Empresa'), lead.get('Cidade_Empresa'), lead.get('Estado_Empresa'))
                    if site_enriquecido != "N/A":
                        leads_df.at[index, 'Site_Original'] = site_enriquecido
                        site_para_analise = site_enriquecido
                
                analise = None
                if pd.notna(site_para_analise) and str(site_para_analise).strip() != '' and site_para_analise != 'N/A':
                    if not str(site_para_analise).startswith(('http://', 'https://')):
                        site_para_analise = 'https://' + str(site_para_analise)
                    
                    # --- CHAMADA CORRIGIDA ---
                    analise = analisar_icp_com_ia_por_url(site_para_analise, criterios_icp)
                else:
                    status_text.text(f"Nenhum site encontrado. Buscando presença online para {lead.get('Nome_Empresa')}...")
                    presenca_online = analisar_presenca_online(lead.get('Nome_Empresa'), lead.get('Cidade_Empresa'))
                    if presenca_online and "error" not in presenca_online and presenca_online.get('is_ativa'):
                        resumo = presenca_online.get('resumo_negocio')
                        status_text.text(f"Presença online encontrada. Analisando resumo...")
                        # --- CHAMADA CORRIGIDA ---
                        analise = analisar_icp_com_ia_por_resumo(resumo, criterios_icp)
                        if analise and "error" not in analise:
                           analise['motivo_segmento'] = f"{analise.get('motivo_segmento')} (Baseado em resumo online: {presenca_online.get('fonte_informacao')})"
                    else:
                        leads_df.at[index, 'classificacao_icp'] = 'Fora do ICP'
                        leads_df.at[index, 'motivo_classificacao'] = 'Nenhuma informação conclusiva encontrada online'

                if analise and "error" not in analise:
                    leads_df.at[index, 'categoria_do_lead'] = analise.get('categoria_segmento', 'N/A')
                    if analise.get('is_segmento_correto') and not analise.get('is_concorrente'):
                        leads_df.at[index, 'classificacao_icp'] = 'Dentro do ICP'
                        leads_df.at[index, 'motivo_classificacao'] = analise.get('motivo_segmento')
                    else:
                        leads_df.at[index, 'classificacao_icp'] = 'Fora do ICP'
                        motivo = f"Concorrente: {analise.get('is_concorrente')}" if analise.get('is_concorrente') else f"Segmento incorreto: {analise.get('motivo_segmento')}"
                        leads_df.at[index, 'motivo_classificacao'] = motivo
                elif analise and "error" in analise:
                    leads_df.at[index, 'classificacao_icp'] = 'Erro na Análise'
                    leads_df.at[index, 'motivo_classificacao'] = analise.get('details', 'Erro desconhecido da IA.')
                
                progress_bar.progress((index + 1) / len(leads_df))
            
            status_text.success("Processamento completo!")
            st.dataframe(leads_df)
            
            csv = leads_df.to_csv(sep=';', index=False, encoding='utf-8-sig').encode('utf-8-sig')
            st.download_button(label="⬇️ Baixar resultado completo (.csv)", data=csv, file_name='leads_analisados_final.csv', mime='text/csv')
    else:
        st.warning("Por favor, faça o upload dos dois arquivos CSV para continuar.")
