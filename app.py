# --- VERSÃO COM PROMPT "ANTI-ALUCINAÇÃO" ---
import streamlit as st
import pandas as pd
import io
import json
import google.generativeai as genai

# --- FUNÇÕES DO AGENTE ---
# A função ler_csv_flexivel permanece a mesma.
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

def analisar_icp_com_ia_por_url(url_do_lead, criterios_icp):
    """Usa a IA para visitar a URL e fazer a análise, com prompt aprimorado."""
    model = genai.GenerativeModel('gemini-1.5-flash-latest')
    
    # Prepara a base de comparação, usando site ou descrição
    info_base_comparacao = ""
    site_contratante = criterios_icp.get('site_da_empresa_contratante', '')
    desc_contratante = criterios_icp.get('descricao_da_empresa_contratante', '')
    if site_contratante and '[INSIRA' not in site_contratante:
        info_base_comparacao = f"O site da minha empresa é: {site_contratante}"
    elif desc_contratante and '[Descreva' not in desc_contratante:
        info_base_comparacao = f"A minha empresa é descrita como: '{desc_contratante}'"

    prompt = f"""
    Você é um Analista de Negócios Cético e Focado em Fatos. Sua tarefa é analisar o conteúdo de um site e responder a perguntas sobre ele, seguindo regras rígidas.

    **ETAPA 1: COLETA DE DADOS**
    Acesse e leia o conteúdo da URL: {url_do_lead}

    **ETAPA 2: ANÁLISE E EXTRAÇÃO (BASEADA ESTRITAMENTE NO TEXTO COLETADO)**
    Com base no texto da Etapa 1, responda às perguntas abaixo.

    **Critérios da Minha Empresa para Comparação:**
    - {info_base_comparacao}
    - Segmentos Válidos: [{criterios_icp.get('segmento_desejado_do_lead', 'N/A')}]
    - Descrição da minha solução: [{criterios_icp.get('observacoes_gerais_do_lead_ideal', 'N/A')}]

    **REGRAS DE ANÁLISE:**
    1.  **Concorrência:** O lead só é um concorrente se o produto principal dele resolver EXATAMENTE o mesmo problema que a 'Descrição da minha solução' indica. Não o considere concorrente apenas por estar no mesmo segmento.
    2.  **Telefone:** O telefone DEVE ser uma citação direta do texto do site. Se você não puder copiar e colar um número de telefone do texto, você DEVE retornar "N/A". É proibido usar conhecimento externo ou inventar.
    3.  **Fidelidade:** Todas as suas respostas DEVEM ser baseadas unicamente no texto que você leu do site. Se a informação não estiver lá, admita.

    **Sua Resposta (Obrigatório):**
    Responda APENAS com um objeto JSON válido com as seguintes chaves: "is_concorrente", "motivo_concorrente", "is_segmento_correto", "motivo_segmento", "categoria_segmento", "telefone_encontrado".
    """
    try:
        response = model.generate_content(prompt, request_options={"timeout": 90})
        resposta_texto = response.text.replace('```json', '').replace('```', '').strip()
        return json.loads(resposta_texto)
    except Exception as e:
        return {"error": "Falha na análise da IA", "details": str(e)}

# (O restante das funções e da interface do Streamlit permanece o mesmo)
# ... (verificar_cargo, interface, loop principal, etc.) ...
# O código completo está abaixo para garantir
def verificar_cargo(cargo_lead, cargos_icp_str):
    if pd.isna(cargo_lead) or pd.isna(cargos_icp_str) or str(cargos_icp_str).strip() == '': return False
    if str(cargo_lead).strip() == '': return False
    cargos_de_interesse = [cargo.strip().lower() for cargo in str(cargos_icp_str).split(',')]
    return str(cargo_lead).strip().lower() in cargos_de_interesse

st.set_page_config(layout="wide", page_title="Agente LDR de IA")
st.title("🤖 Agente LDR com Inteligência Artificial")
st.write("Faça o upload dos seus arquivos para qualificação, enriquecimento e padronização de leads.")

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

            for col in ['classificacao_icp', 'motivo_classificacao', 'categoria_do_lead', 'telefone_enriquecido', 'cargo_valido']:
                if col not in leads_df.columns:
                    leads_df[col] = ''
            leads_df['cargo_valido'] = False

            st.info("Iniciando processamento...")
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            for index, lead in leads_df.iterrows():
                status_text.text(f"Analisando: {lead.get('Nome_Empresa', f'Linha {index+2}')}...")
                
                leads_df.at[index, 'cargo_valido'] = verificar_cargo(lead.get('Cargo'), criterios_icp.get('cargos_de_interesse_do_lead'))
                
                site_url = lead.get('Site_Original')
                
                if pd.notna(site_url) and str(site_url).strip() != '':
                    if not str(site_url).startswith(('http://', 'https://')):
                        site_url = 'https://' + str(site_url)
                    
                    analise = analisar_icp_com_ia_por_url(site_url, criterios_icp)
                    
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