# --- VERSÃO ESTÁVEL COM REIMPLANTAÇÃO DO ENRIQUECIMENTO DE TELEFONE ---
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

def enriquecer_telefone_social_com_ia(nome_empresa, cidade):
    """Pede para a IA buscar o telefone em presenças online, como o LinkedIn."""
    model = genai.GenerativeModel('gemini-1.5-flash-latest')
    prompt = f"""
    Encontre o principal número de telefone comercial para a empresa '{nome_empresa}' de '{cidade}'.
    Faça uma busca focada no perfil oficial da empresa no LinkedIn ou em outras redes sociais profissionais.
    REGRAS: O número deve ser encontrado explicitamente. Não deduza ou invente. Se não encontrar, retorne "N/A".
    Responda APENAS com o número de telefone ou "N/A".
    """
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
    """Usa a IA para visitar a URL, fazer a análise e enriquecer o telefone."""
    model = genai.GenerativeModel('gemini-1.5-flash-latest')
    info_base_comparacao = f"O site da minha empresa é: {criterios_icp.get('site_da_empresa_contratante')}"
    if '[INSIRA' in str(criterios_icp.get('site_da_empresa_contratante', '')):
        info_base_comparacao = f"A minha empresa é descrita como: '{criterios_icp.get('descricao_da_empresa_contratante')}'"
    
    prompt = f"""
    Você é um Analista de Desenvolvimento de Leads Sênior. Analise o site do lead na URL {url_do_lead}.

    AJA EM TRÊS ETAPAS, NESTA ORDEM:
    1.  Acesse e leia o conteúdo principal do site.
    2.  EXTRAIA o principal número de telefone para contato comercial. Se não encontrar um telefone claro, use EXATAMENTE a string "N/A".
    3.  FAÇA A ANÁLISE do site conforme os critérios abaixo.

    Critérios do ICP da Minha Empresa:
    - {info_base_comparacao}
    - Segmentos Válidos: [{criterios_icp.get('segmento_desejado_do_lead', 'N/A')}]

    Sua Resposta (Obrigatório):
    Responda APENAS com um objeto JSON válido com as chaves: "is_concorrente", "motivo_concorrente", "is_segmento_correto", "motivo_segmento", "categoria_segmento", e "telefone_encontrado" (com o resultado da Etapa 2).
    """
    try:
        response = model.generate_content(prompt, request_options={"timeout": 90})
        resposta_texto = response.text.replace('```json', '').replace('```', '').strip()
        return json.loads(resposta_texto)
    except Exception as e:
        return {"error": "Falha na análise da IA", "details": str(e)}

def verificar_cargo(cargo_lead, cargos_icp_str):
    """Verifica se o cargo do lead está na lista de interesse do ICP."""
    if pd.isna(cargo_lead) or pd.isna(cargos_icp_str) or str(criterios_icp_str).strip() == '': return False
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
            
            # Inicializa colunas de resultado
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
                        # Preenche os resultados da análise principal
                        leads_df.at[index, 'categoria_do_lead'] = analise.get('categoria_segmento', 'N/A')
                        if analise.get('is_segmento_correto') and not analise.get('is_concorrente'):
                            leads_df.at[index, 'classificacao_icp'] = 'Dentro do ICP'
                            leads_df.at[index, 'motivo_classificacao'] = analise.get('motivo_segmento')
                        else:
                            leads_df.at[index, 'classificacao_icp'] = 'Fora do ICP'
                            leads_df.at[index, 'motivo_classificacao'] = f"Concorrente: {analise.get('is_concorrente')}" if analise.get('is_concorrente') else f"Segmento incorreto: {analise.get('motivo_segmento')}"
                        
                        # Lógica de enriquecimento de telefone em cascata
                        telefone_site = analise.get('telefone_encontrado', 'N/A')
                        if telefone_site != 'N/A' and telefone_site:
                            leads_df.at[index, 'telefone_enriquecido'] = telefone_site
                        else:
                            status_text.text(f"Telefone não encontrado no site. Buscando em redes sociais para {lead.get('Nome_Empresa')}...")
                            telefone_social = enriquecer_telefone_social_com_ia(lead.get('Nome_Empresa'), lead.get('Cidade_Empresa'))
                            leads_df.at[index, 'telefone_enriquecido'] = telefone_social
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