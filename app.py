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

def ler_csv_flexivel(arquivo_upado):
    """
    Lê um arquivo CSV que foi upado, tentando detectar automaticamente
    se o separador é ponto e vírgula ou vírgula.
    """
    try:
        # Volta ao início do arquivo para garantir que a leitura comece do zero
        arquivo_upado.seek(0)
        # Tenta ler com ponto e vírgula primeiro, nosso padrão ideal
        df = pd.read_csv(arquivo_upado, sep=';')
        
        # Se, após a leitura, o dataframe tiver apenas uma coluna, é um forte indício
        # de que o separador estava errado.
        if df.shape[1] == 1:
            # Volta ao início do arquivo novamente para uma nova tentativa
            arquivo_upado.seek(0)
            # Tenta ler com vírgula
            df = pd.read_csv(arquivo_upado, sep=',')
            
        return df
    except Exception as e:
        st.error(f"Erro ao ler o arquivo CSV: {e}")
        return None

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

def extrair_texto_com_selenium(url):
    """Usa Selenium para acessar um site, clicar no banner de cookies e extrair todo o texto."""
    # Nota: A instalação do Selenium e ChromeDriver é feita no requirements.txt para o Streamlit Cloud
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

# Cole esta função no lugar da antiga

def analisar_icp_com_ia(texto_do_site, criterios_icp):
    """
    Envia o texto de um site e os critérios do ICP para a IA do Google
    e retorna uma análise estruturada em formato de dicionário.
    """
    prompt = f"""
    Você é um Analista de Desenvolvimento de Leads Sênior. Sua tarefa é analisar o texto de um site de uma empresa (LEAD)
    e compará-lo com os Critérios do Cliente Ideal (ICP) da minha empresa.

    **Critérios do ICP da Minha Empresa:**
    - Segmento Desejado: {criterios_icp.get('Segmento_Desejado_do_Lead', 'N/A')}
    - Site da Minha Empresa (para análise de concorrente): {criterios_icp.get('Site_da_Empresa_Contratante', 'N/A')}
    - Observações e Palavras-chave: {criterios_icp.get('Observacoes_Gerais_do_Lead_Ideal', 'N/A')}

    **Texto do Site do Lead para Análise:**
    ---
    {texto_do_site[:4000]}
    ---

    **Sua Resposta (Obrigatório):**
    Responda APENAS com um objeto JSON válido, contendo as seguintes chaves:
    - "is_concorrente": coloque true se o lead for um concorrente direto da minha empresa, senão false.
    - "motivo_concorrente": explique em uma frase curta por que você considera (ou não) um concorrente.
    - "is_segmento_correto": coloque true se o lead pertence ao segmento desejado, senão false.
    - "motivo_segmento": explique em uma frase curta por que o segmento se encaixa (ou não).
    """
    try:
        model = genai.GenerativeModel('gemini-1.5-flash-latest')
        response = model.generate_content(prompt)
        # Limpa a resposta para garantir que seja um JSON válido
        resposta_texto = response.text.replace('```json', '').replace('```', '').strip()
        return json.loads(resposta_texto)
    except Exception as e:
        # Se algo der errado (na chamada da IA ou na conversão do JSON), retorna um erro
        print(f"Ocorreu um erro na chamada ou processamento da IA: {e}")
        return {"error": "Falha na análise da IA", "details": str(e)}