# --- VERSÃO FINAL COM LÓGICA DE CARGO DESACOPLADA E AUTO-EXCLUSÃO APRIMORADA ---
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
    Você é um Analista de Desenvolvimento de Leads Sênior. Sua tarefa é analisar o site de um lead e compará-lo com os critérios do meu ICP.

    AJA EM DUAS ETAPAS:
    1. Primeiro, acesse e leia o conteúdo principal do site na seguinte URL: {url_do_lead}
    2. Depois, com base no conteúdo que você leu, analise o site de acordo com os critérios abaixo.

    Critérios do ICP da Minha Empresa:
    - {info_base_comparacao}
    - Segmentos Válidos (para qualificação e categorização): [{criterios_icp.get('segmento_desejado_do_lead', 'N/A')}]

    REGRAS RÍGIDAS PARA SUA RESPOSTA:
    - Se a informação sobre a minha empresa não for suficiente para uma comparação de concorrência real, retorne 'is_concorrente' como false e explique no motivo.
    - NÃO INVENTE DADOS.

    Sua Resposta (Obrigatório):
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
            st.error("Chave de API do Google não configurada. Adicione-a nos 'Secrets' do seu aplicativo Streamlit.")
            st.stop()
        
        st.info("Lendo arquivos...")
        leads_df = ler_csv_flexivel(arquivo_dados)
        icp_raw_df = ler_csv_flexivel(arquivo_icp)

        if leads_df is not None and icp_raw_df is not None:
            criterios_icp_raw = dict(zip(icp_raw_df['Campo_ICP'], icp_raw_df['Valor_ICP']))
            criterios_icp = {str(k).lower().strip(): v for k, v in criterios_icp_raw.items()}
            
            # Validação de dados do ICP
            site_contratante = str(criterios_icp.get('site_da_empresa_contratante', '')).strip()
            desc_contratante = str(criterios_icp.get('descricao_da_empresa_contratante', '')).strip()
            is_site_valid = (len(site_contratante) > 4 and '.' in site_contratante and '[INSIRA' not in site_contratante)
            is_desc_valid = (len(desc_contratante) > 10 and '[Descreva' not in desc_contratante)
            if not is_site_valid and not is_desc_valid:
                st.error("ERRO DE CONFIGURAÇÃO: Preencha o campo 'Site_da_Empresa_Contratante' OU 'Descricao_da_Empresa_Contratante' no seu arquivo ICP.")
                st.stop()
            
            # Inicializa colunas de resultado
            leads_df['empresa_classificacao'] = 'Aguardando Análise'
            leads_df['empresa_motivo'] = ''
            leads_df['empresa_categoria'] = ''
            leads_df['cargo_dentro_do_icp'] = False # Nova coluna para o cargo

            st.info("Iniciando processamento com IA...")
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            for index, lead in leads_df.iterrows():
                status_text.text(f"Analisando: {lead.get('Nome_Empresa', 'Empresa Desconhecida')}...")
                
                # 1. Qualificação de Cargo (agora é uma flag, não um filtro)
                leads_df.at[index, 'cargo_dentro_do_icp'] = verificar_cargo(lead.get('Cargo'), criterios_icp.get('cargos_de_interesse_do_lead'))

                # 2. Verificação de Auto-Exclusão (Site OU Nome)
                site_lead_clean = str(lead.get('Site_Original', '')).lower().replace('https://', '').replace('http://', '').replace('www.', '').strip('/')
                site_meu_clean = str(criterios_icp.get('site_da_empresa_contratante', '')).lower().replace('https://', '').replace('http://', '').replace('www.', '').strip('/')
                nome_lead_clean = str(lead.get('Nome_Empresa', '')).lower().strip()
                nome_meu_clean = str(criterios_icp.get('nome_da_empresa_contratante', '')).lower().strip()
                
                is_mesmo_site = site_lead_clean and site_meu_clean and site_lead_clean == site_meu_clean
                is_mesmo_nome = nome_lead_clean and nome_meu_clean and nome_lead_clean == nome_meu_clean

                if is_mesmo_site or is_mesmo_nome:
                    leads_df.at[index, 'empresa_classificacao'] = 'Auto-exclusão'
                    leads_df.at[index, 'empresa_motivo'] = 'Empresa é o próprio contratante'
                else:
                    # 3. Qualificação da Empresa com IA
                    site_url = lead.get('Site_Original')
                    if pd.notna(site_url) and site_url.strip() != '':
                        if not site_url.startswith(('http://', 'https://')): site_url = 'https://' + site_url
                        
                        analise = analisar_icp_com_ia_por_url(site_url, criterios_icp)
                        
                        if "error" not in analise:
                            leads_df.at[index, 'empresa_categoria'] = analise.get('categoria_segmento', 'N/A')
                            if analise.get('is_segmento_correto') and not analise.get('is_concorrente'):
                                leads_df.at[index, 'empresa_classificacao'] = 'Dentro do ICP'
                                leads_df.at[index, 'empresa_motivo'] = analise.get('motivo_segmento')
                            else:
                                leads_df.at[index, 'empresa_classificacao'] = 'Fora do ICP'
                                leads_df.at[index, 'empresa_motivo'] = f"Concorrente: {analise.get('is_concorrente')}" if analise.get('is_concorrente') else f"Segmento incorreto: {analise.get('motivo_segmento')}"
                        else:
                            leads_df.at[index, 'empresa_classificacao'] = 'Erro na Análise'
                            leads_df.at[index, 'empresa_motivo'] = analise.get('details', 'Erro desconhecido da IA.')
                    else:
                        leads_df.at[index, 'empresa_classificacao'] = 'Ponto de Atenção'
                        leads_df.at[index, 'empresa_motivo'] = 'Site não informado'
                
                progress_bar.progress((index + 1) / len(leads_df))
            
            status_text.success("Processamento concluído!")
            st.dataframe(leads_df)
            
            csv = leads_df.to_csv(sep=';', index=False, encoding='utf-8-sig').encode('utf-8-sig')
            st.download_button(label="⬇️ Baixar resultado (.csv)", data=csv, file_name='leads_analisados_final.csv', mime='text/csv')
    else:
        st.warning("Por favor, faça o upload dos dois arquivos CSV para continuar.")