# --- VERSÃO CORRETA PARA DEPURAÇÃO DO ENRIQUECIMENTO DE TELEFONE ---
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

def analisar_icp_e_telefone_com_ia(url_do_lead, criterios_icp):
    """Usa a IA para visitar a URL, fazer a análise completa E extrair o telefone."""
    model = genai.GenerativeModel('gemini-1.5-flash-latest')
    info_base_comparacao = f"O site da minha empresa é: {criterios_icp.get('site_da_empresa_contratante', 'Não informado')}"
    if '[INSIRA' in str(criterios_icp.get('site_da_empresa_contratante', '')):
        info_base_comparacao = f"A minha empresa é descrita como: '{criterios_icp.get('descricao_da_empresa_contratante', 'Não informado')}'"
    
    prompt = f"""
    Você é um Analista de Desenvolvimento de Leads Sênior. Sua tarefa é visitar um site, extrair todo o seu texto, e depois analisá-lo.

    **AJA EM DUAS ETAPAS INDEPENDENTES:**
    1.  **EXTRAÇÃO DE TEXTO:** Primeiro, acesse e extraia TODO o texto visível da página na seguinte URL: {url_do_lead}
    2.  **ANÁLISE E EXTRAÇÃO DE DADOS:** Com base no texto que você extraiu na Etapa 1, preencha o seguinte objeto JSON.

    **Critérios do ICP da Minha Empresa para a Análise:**
    - {info_base_comparacao}
    - Segmentos Válidos: [{criterios_icp.get('segmento_desejado_do_lead', 'N/A')}]

    **REGRAS RÍGIDAS PARA A RESPOSTA:**
    - O JSON deve conter uma chave "texto_extraido" com o texto completo da Etapa 1.
    - O JSON deve conter uma chave "telefone_encontrado". Procure pelo telefone de contato principal. Se não encontrar, retorne EXATAMENTE a string "N/A". NÃO INVENTE NÚMEROS.
    - As outras chaves devem ser preenchidas com base na sua análise do texto.

    **Sua Resposta (Obrigatório):**
    Responda APENAS com um objeto JSON válido com as chaves: "texto_extraido", "is_concorrente", "motivo_concorrente", "is_segmento_correto", "motivo_segmento", "categoria_segmento", "telefone_encontrado".
    """
    try:
        response = model.generate_content(prompt, request_options={"timeout": 90})
        resposta_texto = response.text.replace('```json', '').replace('```', '').strip()
        return json.loads(resposta_texto)
    except Exception as e:
        return {"error": f"Falha na análise da IA: {e}", "details": str(e)}

def verificar_cargo(cargo_lead, cargos_icp_str):
    """Verifica se o cargo do lead está na lista de interesse do ICP."""
    if pd.isna(cargos_icp_str) or str(cargos_icp_str).strip() == '': return False
    if pd.isna(cargo_lead) or str(cargo_lead).strip() == '': return False
    cargos_de_interesse = [cargo.strip().lower() for cargo in str(cargos_icp_str).split(',')]
    return str(cargo_lead).strip().lower() in cargos_de_interesse

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
            criterios_icp_raw = dict(zip(icp_raw_df['Campo_ICP'], icp_raw_df['Valor_ICP']))
            criterios_icp = {str(k).lower().strip(): v for k, v in criterios_icp_raw.items()}
            
            for col in ['classificacao_icp', 'motivo_classificacao', 'categoria_do_lead', 'telefone_enriquecido']:
                if col not in leads_df.columns:
                    leads_df[col] = ''

            st.info("Iniciando processamento...")
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            for index, lead in leads_df.iterrows():
                status_text.text(f"Analisando: {lead.get('Nome_Empresa', f'Linha {index+2}')}...")
                
                if not verificar_cargo(lead.get('Cargo'), criterios_icp.get('cargos_de_interesse_do_lead')):
                    leads_df.at[index, 'classificacao_icp'] = 'Fora do ICP'
                    leads_df.at[index, 'motivo_classificacao'] = 'Cargo fora do perfil'
                else:
                    site_url = lead.get('Site_Original')
                    if pd.notna(site_url) and str(site_url).strip() != '':
                        if not str(site_url).startswith(('http://', 'https://')):
                            site_url = 'https://' + str(site_url)
                        
                        analise = analisar_icp_e_telefone_com_ia(site_url, criterios_icp)
                        
                        # --- NOSSO INSPETOR ESTÁ AQUI ---
                        texto_extraido = analise.get('texto_extraido', 'A IA não retornou o texto extraído.')
                        with st.expander(f"Ver texto lido de {lead.get('Nome_Empresa')}"):
                            st.text_area("Texto usado para análise:", texto_extraido, height=200)

                        if "error" not in analise:
                            leads_df.at[index, 'categoria_do_lead'] = analise.get('categoria_segmento', 'N/A')
                            leads_df.at[index, 'telefone_enriquecido'] = analise.get('telefone_encontrado', 'N/A')
                            
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
