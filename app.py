# --- VERSÃO FINAL E COMPLETA - ENRIQUECIMENTO EM 3 ETAPAS ---
import streamlit as st
import pandas as pd
import io
import json
import google.generativeai as genai
from urllib.parse import urljoin

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

def encontrar_pagina_contato(url_principal, criterios_icp):
    """(PLANO B) Pede para a IA encontrar a URL da página de contato."""
    model = genai.GenerativeModel('gemini-1.5-flash-latest')
    prompt = f"Visite o site '{url_principal}'. Encontre o link para a página de 'Contato', 'Fale Conosco' ou similar. Responda APENAS com a URL completa da página. Se não encontrar, responda 'N/A'."
    try:
        response = model.generate_content(prompt, request_options={"timeout": 60})
        link_contato = response.text.strip()
        if link_contato.lower().startswith('http'):
            return link_contato
        elif link_contato.startswith('/'):
            return urljoin(url_principal, link_contato)
        else:
            return "N/A"
    except Exception:
        return "N/A"

def extrair_telefone_de_pagina_especifica(url_pagina, criterios_icp):
    """(PLANO C) Pede para a IA extrair um telefone de uma página específica."""
    model = genai.GenerativeModel('gemini-1.5-flash-latest')
    prompt = f"Sua única tarefa é encontrar o principal número de telefone comercial na página '{url_pagina}'. Inspecione o texto e o código HTML. Responda APENAS com o número de telefone que encontrar ou com 'N/A'."
    try:
        response = model.generate_content(prompt, request_options={"timeout": 60})
        telefone = response.text.strip()
        if any(char.isdigit() for char in telefone):
            return telefone
        else:
            return "N/A"
    except Exception:
        return "N/A"

def analisar_icp_com_ia_por_url(url_do_lead, criterios_icp):
    """(PLANO A) Usa a IA para visitar a URL, fazer a análise principal e uma primeira tentativa de pegar o telefone."""
    model = genai.GenerativeModel('gemini-1.5-flash-latest')
    info_base_comparacao = f"O site da minha empresa é: {criterios_icp.get('site_da_empresa_contratante', 'Não informado')}"
    if '[INSIRA' in str(criterios_icp.get('site_da_empresa_contratante', '')):
        info_base_comparacao = f"A minha empresa é descrita como: '{criterios_icp.get('descricao_da_empresa_contratante', 'Não informado')}'"
    
    prompt = f"""
    Você é um Analista de Leads Sênior. Visite a URL {url_do_lead} e responda em JSON.
    Critérios do ICP:
    - {info_base_comparacao}
    - Segmentos Válidos: [{criterios_icp.get('segmento_desejado_do_lead', 'N/A')}]
    - Descrição da minha solução: [{criterios_icp.get('observacoes_gerais_do_lead_ideal', 'N/A')}]
    
    Regras da Resposta JSON:
    1. is_concorrente: true apenas se o produto do lead resolve o MESMO problema que a 'Descrição da minha solução'.
    2. telefone_encontrado: Procure pelo telefone principal no texto da página inicial. DEVE ser uma citação direta. Se não encontrar, retorne "N/A". NÃO INVENTE.
    3. Preencha as outras chaves com base na sua análise.
    
    Responda APENAS com um objeto JSON válido com as chaves: "is_concorrente", "motivo_concorrente", "is_segmento_correto", "motivo_segmento", "categoria_segmento", "telefone_encontrado".
    """
    try:
        response = model.generate_content(prompt, request_options={"timeout": 90})
        resposta_texto = response.text.replace('```json', '').replace('```', '').strip()
        return json.loads(resposta_texto)
    except Exception as e:
        return {"error": "Falha na análise da IA", "details": str(e)}

def verificar_cargo(cargo_lead, cargos_icp_str):
    """Verifica se o cargo do lead está na lista de interesse do ICP."""
    if pd.isna(cargos_icp_str) or str(cargos_icp_str).strip() == '': return False
    if pd.isna(cargo_lead) or str(cargo_lead).strip() == '': return False
    cargos_de_interesse = [cargo.strip().lower() for cargo in str(cargos_icp_str).split(',')]
    return str(cargo_lead).strip().lower() in cargos_de_interesse

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
            criterios_icp_raw = dict(zip(icp_raw_df['Campo_ICP'], icp_raw_df['Valor_ICP']))
            criterios_icp = {str(k).lower().strip(): v for k, v in criterios_icp_raw.items()}
            
            for col in ['classificacao_icp', 'motivo_classificacao', 'categoria_do_lead', 'telefone_enriquecido', 'cargo_valido']:
                if col not in leads_df.columns:
                    leads_df[col] = ''
            leads_df['cargo_valido'] = False

            st.info("Iniciando processamento...")
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            for index, lead in leads_df.iterrows():
                status_text.text(f"Analisando e Enriquecendo: {lead.get('Nome_Empresa', f'Linha {index+2}')}...")
                
                leads_df.at[index, 'cargo_valido'] = verificar_cargo(lead.get('Cargo'), criterios_icp.get('cargos_de_interesse_do_lead'))
                
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
                        
                        telefone_encontrado = analise.get('telefone_encontrado', 'N/A')
                        if telefone_encontrado != 'N/A' and telefone_encontrado:
                            leads_df.at[index, 'telefone_enriquecido'] = telefone_encontrado
                        else:
                            status_text.text(f"Telefone não encontrado no site... buscando página de contato...")
                            url_contato = encontrar_pagina_contato(site_url, criterios_icp)
                            if url_contato != "N/A":
                                status_text.text(f"Página de contato encontrada! Extraindo telefone...")
                                telefone_final = extrair_telefone_de_pagina_especifica(url_contato, criterios_icp)
                                leads_df.at[index, 'telefone_enriquecido'] = telefone_final
                            else:
                                leads_df.at[index, 'telefone_enriquecido'] = 'N/A'
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