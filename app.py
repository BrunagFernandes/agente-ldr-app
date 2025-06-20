# --- FASE 1: IMPORTAÇÃO DAS FERRAMENTAS ---
import streamlit as st
import pandas as pd
import io
import json
import time
import re
import nltk
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from bs4 import BeautifulSoup
import google.generativeai as genai

# --- FASE 2: DEFINIÇÃO DE TODAS AS FUNÇÕES DO AGENTE ---

# -- Funções de Leitura e Análise --
def ler_csv_flexivel(arquivo_upado):
    """Lê um arquivo CSV com separador flexível (ponto e vírgula ou vírgula)."""
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

def extrair_texto_com_selenium(url):
    """Usa Selenium para acessar um site, clicar no banner de cookies e extrair o texto."""
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument("window-size=1280,800")
    
    driver = None
    try:
        driver = webdriver.Chrome(options=chrome_options)
        driver.get(url)
        time.sleep(5)
        try:
            xpath_aceitar_robusto = "//*[self::button or self::a][contains(., 'Aceitar') or contains(., 'Aceito') or contains(., 'Concordo') or contains(., 'Entendi')]"
            wait = WebDriverWait(driver, 10)
            botao_aceitar = wait.until(EC.element_to_be_clickable((By.XPATH, xpath_aceitar_robusto)))
            botao_aceitar.click()
            time.sleep(2)
        except TimeoutException:
            pass
        
        html_content = driver.page_source
        soup = BeautifulSoup(html_content, 'html.parser')
        return soup.get_text(separator=' ', strip=True)
    finally:
        if driver:
            driver.quit()

def analisar_icp_com_ia_por_url(url_do_lead, criterios_icp):
    """
    Usa a IA para visitar a URL e fazer a análise, com regras rígidas para
    evitar "alucinações" se os dados do ICP estiverem incompletos.
    """
    # Define a base da comparação: prioriza o site, senão usa a descrição.
    info_base_comparacao = f"O site da minha empresa é: {criterios_icp.get('Site_da_Empresa_Contratante')}"
    # Verifica se o site é um placeholder
    if '[INSIRA O SITE' in info_base_comparacao:
        info_base_comparacao = f"A minha empresa é descrita como: '{criterios_icp.get('Descricao_da_Empresa_Contratante')}'"

    model = genai.GenerativeModel('gemini-1.5-flash-latest')
    prompt = f"""
    Você é um Analista de Desenvolvimento de Leads Sênior. Sua tarefa é analisar o site de um lead e compará-lo com os critérios do meu ICP.

    **AJA EM DUAS ETAPAS:**
    1.  Primeiro, acesse e leia o conteúdo principal do site na seguinte URL: {url_do_lead}
    2.  Depois, com base no conteúdo que você leu, analise o site de acordo com os critérios abaixo.

    **Critérios do ICP da Minha Empresa:**
    - {info_base_comparacao}
    - Segmentos Válidos (para qualificação e categorização): [{criterios_icp.get('Segmento_Desejado_do_Lead', 'N/A')}]

    **REGRAS RÍGIDAS PARA SUA RESPOSTA:**
    - NÃO FAÇA suposições ou inferências se a informação não for clara.
    - Se a informação sobre a minha empresa (seja o site ou a descrição) não for suficiente para uma comparação de concorrência real, retorne 'is_concorrente' como false e explique no motivo que a informação de base era insuficiente.
    - NÃO INVENTE DADOS EM HIPÓTESE ALGUMA.

    **Sua Resposta (Obrigatório):**
    Responda APENAS com um objeto JSON válido, contendo as seguintes chaves:
    - "is_concorrente": coloque true se, com base na informação fornecida, o lead for um concorrente direto. Senão, false.
    - "motivo_concorrente": explique em uma frase curta o motivo.
    - "is_segmento_correto": coloque true se o lead pertence a um dos 'Segmentos Válidos', senão false.
    - "motivo_segmento": explique em uma frase curta o motivo.
    - "categoria_segmento": se "is_segmento_correto" for true, retorne EXATAMENTE qual dos 'Segmentos Válidos' da lista acima melhor descreve o lead. Se for false, retorne "N/A".
    """
    try:
        response = model.generate_content(prompt)
        resposta_texto = response.text.replace('```json', '').replace('```', '').strip()
        return json.loads(resposta_texto)
    except Exception as e:
        return {"error": "Falha na análise da IA", "details": str(e)}

# -- Funções de Qualificação e Padronização --
def verificar_cargo(cargo_lead, cargos_icp_str):
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
            criterios_icp = dict(zip(icp_raw_df['Campo_ICP'], icp_raw_df['Valor_ICP']))
            
            # --- NOVA BARREIRA DE VALIDAÇÃO ---
            site_contratante = criterios_icp.get('Site_da_Empresa_Contratante', '')
            desc_contratante = criterios_icp.get('Descricao_da_Empresa_Contratante', '')
            site_valido = site_contratante and '[INSIRA O SITE' not in site_contratante
            desc_valida = desc_contratante and '[Descreva sua empresa' not in desc_contratante
            if not site_valido and not desc_valida:
                st.error("ERRO DE CONFIGURAÇÃO: Para a análise de concorrência funcionar, por favor, preencha o campo 'Site_da_Empresa_Contratante' ou o novo campo 'Descricao_da_Empresa_Contratante' no seu arquivo ICP.")
                st.stop()
            # --- FIM DA BARREIRA ---
            
            leads_df['classificacao_icp'] = 'Aguardando Análise'
            leads_df['motivo_classificacao'] = ''
            leads_df['categoria_do_lead'] = ''

            st.info("Iniciando processamento com IA... Isso pode levar alguns minutos.")
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            for index, lead in leads_df.iterrows():
                status_text.text(f"Analisando: {lead.get('Nome_Empresa', 'Empresa Desconhecida')}...")
                if not verificar_cargo(lead.get('Cargo'), criterios_icp.get('Cargos_de_Interesse_do_Lead')):
                    leads_df.at[index, 'classificacao_icp'] = 'Fora do ICP'
                    leads_df.at[index, 'motivo_classificacao'] = 'Cargo fora do perfil'
                else:
                    site_url = lead.get('Site_Original')
                    if pd.notna(site_url) and site_url.strip() != '':
                        if not site_url.startswith(('http://', 'https://')):
                            site_url = 'https://' + site_url
                        
                        analise = analisar_icp_com_ia_por_url(site_url, criterios_icp)
                        
                        if "error" not in analise:
                            leads_df.at[index, 'categoria_do_lead'] = analise.get('categoria_segmento', 'N/A')
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
            
            status_text.success("Processamento completo! Padronização não foi aplicada nesta versão.")
            st.dataframe(leads_df)
            
            csv = leads_df.to_csv(sep=';', index=False, encoding='utf-8-sig').encode('utf-8-sig')
            st.download_button(label="⬇️ Baixar resultado (.csv)", data=csv, file_name='leads_analisados_final.csv', mime='text/csv')
    else:
        st.warning("Por favor, faça o upload dos dois arquivos CSV para continuar.")