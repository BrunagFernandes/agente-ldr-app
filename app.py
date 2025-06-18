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

# --- FASE 2: FUNÇÕES DO AGENTE (NOSSO "MOTOR") ---

# Esta função de limpeza será usada pela função de extração de texto
def limpar_texto(texto):
    """Converte para minúsculas, remove pontuação e palavras comuns."""
    nltk.download('punkt', quiet=True)
    nltk.download('stopwords', quiet=True)
    texto = texto.lower()
    texto = re.sub(r'[^a-zA-Z\s]', '', texto)
    tokens = word_tokenize(texto)
    stop_words = set(stopwords.words('portuguese'))
    palavras_filtradas = [palavra for palavra in tokens if palavra not in stop_words]
    return " ".join(palavras_filtradas)

# Função para extrair texto de um site usando Selenium
def extrair_texto_com_selenium(url):
    """Usa Selenium para acessar um site, clicar no banner de cookies e extrair todo o texto."""
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
            pass # Se não encontrar o botão, apenas continua
        
        html_content = driver.page_source
        soup = BeautifulSoup(html_content, 'html.parser')
        return soup.get_text(separator=' ', strip=True)
    finally:
        if driver:
            driver.quit()

# Função principal de análise com a IA
def analisar_icp_com_ia(texto_do_site, criterios_icp):
    """Envia o texto e os critérios para a IA e retorna a análise."""
    prompt = f"""
    Você é um Analista de Desenvolvimento de Leads Sênior. Analise o 'Texto do Site do Lead' com base nos 'Critérios do Cliente Ideal (ICP)'.

    **Critérios do ICP:**
    - Segmento Desejado: {criterios_icp.get('Segmento_Desejado_do_Lead', 'N/A')}
    - Site da Minha Empresa (para análise de concorrente): {criterios_icp.get('Site_da_Empresa_Contratante', 'N/A')}
    - Observações e Palavras-chave: {criterios_icp.get('Observacoes_Gerais_do_Lead_Ideal', 'N/A')}

    **Texto do Site do Lead para Análise:**
    ---
    {texto_do_site[:4000]}
    ---

    Responda APENAS com um objeto JSON válido com as chaves: "is_concorrente" (boolean), "motivo_concorrente" (string), "is_segmento_correto" (boolean), "motivo_segmento" (string).
    """
    try:
        model = genai.GenerativeModel('gemini-1.5-flash-latest')
        response = model.generate_content(prompt)
        resposta_json = response.text.replace('```json', '').replace('```', '').strip()
        return json.loads(resposta_json)
    except Exception:
        return {"error": "Falha na análise da IA"}

# --- FASE 3: INTERFACE DO APLICATIVO (STREAMLIT) ---

st.set_page_config(layout="wide", page_title="Agente LDR de IA")

st.title("🤖 Agente LDR com Inteligência Artificial")
st.write("Faça o upload dos seus arquivos para iniciar a qualificação, enriquecimento e análise de leads.")

# Colunas para os uploads
col1, col2 = st.columns(2)

with col1:
    arquivo_dados = st.file_uploader("1. Selecione o arquivo de DADOS (.csv)", type="csv")

with col2:
    arquivo_icp = st.file_uploader("2. Selecione o arquivo de ICP (.csv)", type="csv")

if st.button("🚀 Iniciar Processamento Completo"):
    if arquivo_dados and arquivo_icp:
        # Configurar a API Key (deve ser adicionada como um segredo no Streamlit)
        try:
            genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
        except Exception:
            st.error("Chave de API do Google não configurada. Adicione-a nos 'Secrets' do seu aplicativo Streamlit.")
            st.stop()
            
        st.info("Lendo e preparando os arquivos...")
        leads_df = pd.read_csv(arquivo_dados, sep=';')
        icp_raw_df = pd.read_csv(arquivo_icp, sep=';')
        criterios_icp = dict(zip(icp_raw_df['Campo_ICP'], icp_raw_df['Valor_ICP']))
        
        # Criar colunas para os resultados
        leads_df['classificacao_ia'] = ''
        leads_df['motivo_analise'] = ''

        st.info("Iniciando análise com IA. Isso pode levar alguns minutos...")
        progress_bar = st.progress(0)
        
        # Loop para analisar cada lead
        for index, lead in leads_df.iterrows():
            st.write(f"Analisando: {lead['Nome_Empresa']}...")
            site_url = lead.get('Site_Original')
            
            if pd.notna(site_url) and site_url.strip() != '':
                texto_site = extrair_texto_com_selenium(f"https://{site_url}")
                if texto_site:
                    analise = analisar_icp_com_ia(texto_site, criterios_icp)
                    # Aqui você preencheria as colunas do seu dataframe com a resposta da IA
                    leads_df.at[index, 'classificacao_ia'] = f"Segmento Correto: {analise.get('is_segmento_correto')}, Concorrente: {analise.get('is_concorrente')}"
                    leads_df.at[index, 'motivo_analise'] = f"Segmento: {analise.get('motivo_segmento')} | Concorrência: {analise.get('motivo_concorrente')}"
                else:
                    leads_df.at[index, 'classificacao_ia'] = "Site não acessível ou sem texto"
            else:
                leads_df.at[index, 'classificacao_ia'] = "Site não informado"
            
            progress_bar.progress((index + 1) / len(leads_df))

        st.success("Análise com IA concluída com sucesso!")
        st.dataframe(leads_df)
        
        # Botão de Download
        csv = leads_df.to_csv(sep=';', index=False).encode('utf-8')
        st.download_button(
            label="⬇️ Baixar resultado (.csv)",
            data=csv,
            file_name='leads_analisados_com_ia.csv',
            mime='text/csv',
        )
    else:
        st.warning("Por favor, faça o upload dos dois arquivos CSV para continuar.")