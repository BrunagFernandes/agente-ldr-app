# --- VERSÃO FINAL COM INSPETOR DE TEXTO PARA DEPURAÇÃO ---
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
    """Usa a IA para visitar a URL, fazer a análise e enriquecer o telefone."""
    model = genai.GenerativeModel('gemini-1.5-flash-latest')
    info_base_comparacao = f"O site da minha empresa é: {criterios_icp.get('site_da_empresa_contratante')}"
    if '[INSIRA O SITE' in info_base_comparacao or not criterios_icp.get('site_da_empresa_contratante'):
        info_base_comparacao = f"A minha empresa é descrita como: '{criterios_icp.get('descricao_da_empresa_contratante')}'"
    
    prompt = f"""
    Você é um Analista de Desenvolvimento de Leads Sênior. Sua tarefa é visitar um site, extrair um telefone de contato e depois analisar a empresa.

    **AJA EM TRÊS ETAPAS, NESTA ORDEM:**
    1. Primeiro, acesse e leia o conteúdo principal do site na seguinte URL: {url_do_lead}. Retorne todo o texto que encontrar.
    2. Segundo, com base no conteúdo lido, EXTRAIA o principal número de telefone para contato comercial. Priorize telefones de Vendas ou Geral. Se nenhum número de telefone comercial claro for encontrado, use EXATAMENTE a string "N/A".
    3. Terceiro, faça a análise do site de acordo com os critérios abaixo.

    Critérios do ICP da Minha Empresa:
    - {info_base_comparacao}
    - Segmentos Válidos: [{criterios_icp.get('segmento_desejado_do_lead', 'N/A')}]

    Sua Resposta (Obrigatório):
    Responda APENAS com um objeto JSON válido com as chaves: "is_concorrente", "motivo_concorrente", "is_segmento_correto", "motivo_segmento", "categoria_segmento", e "telefone_encontrado" (com o resultado da Etapa 2).
    """
    try:
        # Pede para a IA extrair o texto primeiro
        extracao_model = genai.GenerativeModel('gemini-pro') # Usando um modelo otimizado para extração
        response_extracao = extracao_model.generate_content(f"Acesse a URL {url_do_lead} e extraia todo o texto visível da página principal. Responda apenas com o texto extraído.")
        texto_site = response_extracao.text
        
        # Agora, faz a análise com o texto extraído
        analise_model = genai.GenerativeModel('gemini-1.5-flash-latest')
        response_analise = analise_model.generate_content(prompt.replace(f"Acesse e leia o conteúdo principal do site na seguinte URL: {url_do_lead}", f"Analise o seguinte texto: {texto_site[:7000]}"))
        
        resposta_texto = response_analise.text.replace('```json', '').replace('```', '').strip()
        
        # Adiciona o texto extraído ao resultado para depuração
        resultado_final = json.loads(resposta_texto)
        resultado_final['texto_extraido_debug'] = texto_site
        return resultado_final

    except Exception as e:
        return {"error": f"Falha na análise da IA: {e}", "details": str(e)}

# (As outras funções como verificar_cargo permanecem as mesmas)
def verificar_cargo(cargo_lead, cargos_icp_str):
    if pd.isna(cargo_lead) or pd.isna(cargos_icp_str) or str(cargos_icp_str).strip() == '': return False
    cargos_de_interesse = [cargo.strip().lower() for cargo in str(cargos_icp_str).split(',')]
    return str(cargo_lead).strip().lower() in cargos_de_interesse

# --- INTERFACE DO APLICATIVO (STREAMLIT) ---
st.set_page_config(layout="wide", page_title="Agente LDR de IA")
st.title("🤖 Agente LDR com Inteligência Artificial")
# (O restante da interface permanece o mesmo)
# ... (código do st.file_uploader, st.button, etc.)
if st.button("🚀 Iniciar Análise Inteligente"):
    if arquivo_dados and arquivo_icp:
        # ... (código de configuração da API Key)
        st.info("Lendo arquivos...")
        leads_df = ler_csv_flexivel(arquivo_dados)
        icp_raw_df = ler_csv_flexivel(arquivo_icp)

        if leads_df is not None and icp_raw_df is not None:
            criterios_icp = dict(zip(icp_raw_df['Campo_ICP'], icp_raw_df['Valor_ICP']))
            criterios_icp = {str(k).lower().strip(): v for k, v in criterios_icp.items()}
            
            # ... (código de inicialização de colunas)

            for index, lead in leads_df.iterrows():
                # ... (lógica de verificação de cargo, etc.)
                
                site_url = lead.get('Site_Original')
                if pd.notna(site_url) and str(site_url).strip() != '':
                    if not str(site_url).startswith(('http://', 'https://')):
                        site_url = 'https://' + str(site_url)
                    
                    analise = analisar_icp_com_ia_por_url(site_url, criterios_icp)
                    
                    # --- NOSSO INSPETOR ESTÁ AQUI ---
                    texto_extraido = analise.get('texto_extraido_debug', 'Nenhum texto foi extraído.')
                    with st.expander(f"Ver texto extraído de {lead.get('Nome_Empresa')}"):
                        st.text_area("Texto enviado para análise:", texto_extraido, height=200)

                    # (O restante da lógica para preencher o dataframe)
                    # ...
            st.dataframe(leads_df)