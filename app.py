# --- VERSÃO FINAL COM ENRIQUECIMENTO DE TELEFONE ---
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
    """Usa a IA para visitar a URL, fazer a análise completa e enriquecer o telefone."""
    model = genai.GenerativeModel('gemini-1.5-flash-latest')
    info_base_comparacao = f"O site da minha empresa é: {criterios_icp.get('site_da_empresa_contratante')}"
    if '[INSIRA O SITE' in info_base_comparacao or not criterios_icp.get('site_da_empresa_contratante'):
        info_base_comparacao = f"A minha empresa é descrita como: '{criterios_icp.get('descricao_da_empresa_contratante')}'"
    
    prompt = f"""
    Você é um Analista de Desenvolvimento de Leads Sênior. Sua tarefa é analisar o site de um lead e compará-lo com os critérios do meu ICP.

    AJA EM DUAS ETAPAS:
    1. Primeiro, acesse e leia o conteúdo principal do site na seguinte URL: {url_do_lead}
    2. Depois, com base no conteúdo que você leu, analise o site e extraia as informações conforme as regras abaixo.

    Critérios do ICP da Minha Empresa:
    - {info_base_comparacao}
    - Segmentos Válidos (para qualificação e categorização): [{criterios_icp.get('segmento_desejado_do_lead', 'N/A')}]

    REGRAS RÍGIDAS:
    - NÃO INVENTE DADOS.

    Sua Resposta (Obrigatório):
    Responda APENAS com um objeto JSON válido, contendo as seguintes chaves:
    - "is_concorrente": coloque true se o lead for um concorrente direto, senão false.
    - "motivo_concorrente": explique em uma frase curta o motivo.
    - "is_segmento_correto": coloque true se o lead pertence a um dos 'Segmentos Válidos', senão false.
    - "motivo_segmento": explique em uma frase curta o motivo.
    - "categoria_segmento": se "is_segmento_correto" for true, retorne EXATAMENTE qual dos 'Segmentos Válidos' da lista acima melhor descreve o lead. Se for false, retorne "N/A".
    - "telefone_encontrado": procure pelo principal número de telefone de contato comercial no texto do site. Se encontrar, retorne o número. Se não encontrar, retorne "N/A".
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
            
            # (Bloco de validação do ICP permanece aqui)
            
            # Inicializa colunas de resultado
            for col in ['classificacao_icp', 'motivo_classificacao', 'categoria_do_lead', 'telefone_enriquecido']:
                if col not in leads_df.columns:
                    leads_df[col] = ''
            leads_df['cargo_dentro_do_icp'] = False

            st.info("Iniciando processamento com IA...")
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            for index, lead in leads_df.iterrows():
                status_text.text(f"Analisando e Enriquecendo: {lead.get('Nome_Empresa', 'Empresa Desconhecida')}...")
                
                leads_df.at[index, 'cargo_dentro_do_icp'] = verificar_cargo(lead.get('Cargo'), criterios_icp.get('cargos_de_interesse_do_lead'))
                
                site_url = lead.get('Site_Original') # Usaremos apenas o site original para análise
                
                if pd.notna(site_url) and site_url.strip() != '':
                    if not site_url.startswith(('http://', 'https://')): site_url = 'https://' + site_url
                    
                    analise = analisar_icp_com_ia_por_url(site_url, criterios_icp)
                    
                    if "error" not in analise:
                        # Preenche todas as colunas com os resultados da IA
                        leads_df.at[index, 'categoria_do_lead'] = analise.get('categoria_segmento', 'N/A')
                        leads_df.at[index, 'telefone_enriquecido'] = analise.get('telefone_encontrado', 'N/A')
                        
                        if analise.get('is_segmento_correto') and not analise.get('is_concorrente'):
                            leads_df.at[index, 'classificacao_icp'] = 'Dentro do ICP'
                            leads_df.at[index, 'motivo_classificacao'] = analise.get('motivo_segmento')
                        else:
                            leads_df.at[index, 'classificacao_icp'] = 'Fora do ICP'
                            leads_df.at[index, 'motivo_classificacao'] = f"Concorrente: {analise.get('is_concorrente')}" if analise.get('is_concorrente') else f"Segmento incorreto: {analise.get('motivo_segmento')}"
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
            st.download_button(label="⬇️ Baixar resultado completo (.csv)", data=csv, file_name='leads_processados_final.csv', mime='text/csv')
    else:
        st.warning("Por favor, faça o upload dos dois arquivos CSV para continuar.")