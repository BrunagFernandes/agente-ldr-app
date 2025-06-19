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
        df = pd.read_csv(arquivo_upado, sep=';', encoding='utf-8')
        if df.shape[1] == 1:
            arquivo_upado.seek(0)
            df = pd.read_csv(arquivo_upado, sep=',', encoding='utf-8')
        return df
    except Exception as e:
        st.error(f"Erro ao ler o arquivo CSV: {e}")
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

def analisar_icp_com_ia(texto_do_site, criterios_icp):
    """
    Envia o texto de um site e os critérios do ICP para a IA do Google e retorna uma análise
    estruturada, usando a lista de segmentos do ICP para qualificar e categorizar.
    """
    prompt = f"""
    Você é um Analista de Desenvolvimento de Leads Sênior. Sua tarefa é analisar o 'Texto do Site do Lead'
    e compará-lo com os 'Critérios do Cliente Ideal (ICP)' da minha empresa.

    **Critérios do ICP da Minha Empresa:**
    - Site da Minha Empresa (para análise de concorrente): {criterios_icp.get('Site_da_Empresa_Contratante', 'N/A')}
    - Segmentos Válidos (use esta lista para qualificar e categorizar): [{criterios_icp.get('Segmento_Desejado_do_Lead', 'N/A')}]

    **Texto do Site do Lead para Análise:**
    ---
    {texto_do_site[:6000]}
    ---

    **Sua Resposta (Obrigatório):**
    Responda APENAS com um objeto JSON válido, contendo as seguintes chaves:
    - "is_concorrente": coloque true se o lead for um concorrente direto da minha empresa, senão false.
    - "motivo_concorrente": explique em uma frase curta por que você considera (ou não) um concorrente.
    - "is_segmento_correto": coloque true se o lead parece pertencer a um dos 'Segmentos Válidos' listados acima, senão false.
    - "motivo_segmento": explique em uma frase curta por que o segmento se encaixa (ou não), citando o segmento que você identificou.
    - "categoria_segmento": se "is_segmento_correto" for true, retorne EXATAMENTE qual dos 'Segmentos Válidos' da lista acima melhor descreve o lead. Se nenhuma das opções da lista for adequada mas o lead ainda for do segmento geral, retorne "Outros". Se "is_segmento_correto" for false, retorne "N/A".
    """
    try:
        model = genai.GenerativeModel('gemini-1.5-flash-latest')
        response = model.generate_content(prompt)
        resposta_texto = response.text.replace('```json', '').replace('```', '').strip()
        return json.loads(resposta_texto)
    except Exception as e:
        print(f"Ocorreu um erro na chamada ou processamento da IA: {e}")
        return {"error": "Falha na análise da IA", "details": str(e)}

# -- Funções de Padronização e Edição --
def padronizar_nome_contato(row):
    """Cria um nome completo padronizado."""
    nome = row.get('Nome_Lead', '')
    sobrenome = row.get('Sobrenome_Lead', '')
    if pd.isna(nome) or nome.strip() == '': return ''
    nome_completo = f"{nome} {sobrenome}".strip()
    return nome_completo.title()

def padronizar_nome_empresa(nome_empresa):
    """Remove siglas societárias e padroniza o nome da empresa."""
    if pd.isna(nome_empresa): return ''
    siglas = [r'\sS/A', r'\sS\.A', r'\sSA', r'\sLTDA', r'\sLtda', r'\sME', r'\sEIRELI', r'\sEPP', r'\sMEI']
    for sigla in siglas:
        nome_empresa = re.sub(sigla, '', nome_empresa, flags=re.IGNORECASE)
    return nome_empresa.strip().title()

def padronizar_telefone(telefone):
    """Formata um número de telefone para o padrão brasileiro."""
    if pd.isna(telefone): return ''
    apenas_digitos = re.sub(r'\D', '', str(telefone))
    if len(apenas_digitos) > 11 and apenas_digitos.startswith('55'):
        apenas_digitos = apenas_digitos[2:]
    if len(apenas_digitos) == 11 and apenas_digitos.startswith('0'):
        apenas_digitos = apenas_digitos[1:]
    if len(apenas_digitos) == 11:
        return f"({apenas_digitos[:2]}) {apenas_digitos[2:7]}-{apenas_digitos[7:]}"
    elif len(apenas_digitos) == 10:
        return f"({apenas_digitos[:2]}) {apenas_digitos[2:6]}-{apenas_digitos[6:]}"
    else:
        return str(telefone)

# -- Funções de Qualificação Local --
def verificar_cargo(cargo_lead, cargos_icp_str):
    """Verifica se o cargo do lead está na lista de interesse do ICP."""
    if pd.isna(cargo_lead) or cargo_lead.strip() == '' or pd.isna(cargos_icp_str): return False
    cargos_de_interesse = [cargo.strip().lower() for cargo in cargos_icp_str.split(',')]
    return cargo_lead.strip().lower() in cargos_de_interesse

# --- FASE 3: INTERFACE DO APLICATIVO (STREAMLIT) ---

st.set_page_config(layout="wide", page_title="Agente LDR de IA")
st.title("🤖 Agente LDR com Inteligência Artificial")
st.write("Faça o upload dos seus arquivos para qualificação, enriquecimento e padronização de leads.")

arquivo_dados = st.file_uploader("1. Selecione o arquivo de DADOS (.csv)", type="csv")
arquivo_icp = st.file_uploader("2. Selecione o arquivo de ICP (.csv)", type="csv")

if st.button("🚀 Iniciar Processamento Completo"):
    if arquivo_dados and arquivo_icp:
        try:
            genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
        except Exception:
            st.error("Chave de API do Google não configurada. Adicione-a nos 'Secrets' do seu aplicativo Streamlit.")
            st.stop()
        
        st.info("Lendo arquivos...")
        leads_df = ler_csv_flexivel(arquivo_dados)
        icp_raw_df = ler_csv_flexivel(arquivo_icp)

        if leads_df is not None and icp_raw_df is not None:
            criterios_icp = dict(zip(icp_raw_df['Campo_ICP'], icp_raw_df['Valor_ICP']))
            
            leads_df['classificacao_icp'] = 'Aguardando Análise'
            leads_df['motivo_classificacao'] = ''
            leads_df['categoria_do_lead'] = '' # Nova coluna para a categoria

            st.info("Iniciando processamento... Isso pode levar alguns minutos.")
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            for index, lead in leads_df.iterrows():
                status_text.text(f"Analisando: {lead['Nome_Empresa']}...")
                
                if not verificar_cargo(lead.get('Cargo'), criterios_icp.get('Cargos_de_Interesse_do_Lead')):
                    leads_df.at[index, 'classificacao_icp'] = 'Fora do ICP'
                    leads_df.at[index, 'motivo_classificacao'] = 'Cargo fora do perfil'
                    progress_bar.progress((index + 1) / len(leads_df))
                    continue 

                site_url = lead.get('Site_Original')
                if pd.notna(site_url) and site_url.strip() != '':
                    if not site_url.startswith(('http://', 'https://')):
                        site_url = 'https://' + site_url
                    
                    texto_site = extrair_texto_com_selenium(site_url)
                    
                    if texto_site:
                        analise = analisar_icp_com_ia(texto_site, criterios_icp)
                        leads_df.at[index, 'categoria_do_lead'] = analise.get('categoria_segmento', 'N/A') # Preenche a nova coluna

                        if analise.get('is_segmento_correto') and not analise.get('is_concorrente'):
                            leads_df.at[index, 'classificacao_icp'] = 'Dentro do ICP'
                            leads_df.at[index, 'motivo_classificacao'] = analise.get('motivo_segmento')
                        else:
                            leads_df.at[index, 'classificacao_icp'] = 'Fora do ICP'
                            leads_df.at[index, 'motivo_classificacao'] = f"Concorrente: {analise.get('is_concorrente')}" if analise.get('is_concorrente') else f"Segmento incorreto: {analise.get('motivo_segmento')}"
                    else:
                        leads_df.at[index, 'classificacao_icp'] = 'Ponto de Atenção'
                        leads_df.at[index, 'motivo_classificacao'] = 'Site não acessível ou sem texto'
                else:
                    leads_df.at[index, 'classificacao_icp'] = 'Ponto de Atenção'
                    leads_df.at[index, 'motivo_classificacao'] = 'Site não informado'
                
                progress_bar.progress((index + 1) / len(leads_df))
            
            status_text.text("Análise de qualificação concluída!")
            time.sleep(1)
            
            status_text.info("Iniciando padronização final dos dados...")
            time.sleep(1)

            leads_df['nome_completo_padronizado'] = leads_df.apply(lambda row: padronizar_nome_contato(row), axis=1)
            leads_df['nome_empresa_padronizado'] = leads_df['Nome_Empresa'].apply(padronizar_nome_empresa)
            leads_df['telefone_padronizado'] = leads_df['Telefone_Original'].apply(padronizar_telefone)
            
            status_text.success("Processamento completo!")
            st.dataframe(leads_df)
            
            csv = leads_df.to_csv(sep=';', index=False, encoding='utf-8-sig').encode('utf-8-sig')
            st.download_button(
                label="⬇️ Baixar resultado completo (.csv)",
                data=csv,
                file_name='leads_processados_final.csv',
                mime='text/csv',
            )
    else:
        st.warning("Por favor, faça o upload dos dois arquivos CSV para continuar.")