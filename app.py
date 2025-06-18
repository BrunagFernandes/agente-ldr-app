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
    """Envia o texto e os critérios para a IA e retorna a análise."""
    prompt = f"""
    Você é um Analista de Desenvolvimento de Leads Sênior. Analise o 'Texto do Site do Lead' com base nos 'Critérios do Cliente Ideal (ICP)'.

    **Critérios do ICP:**
    - Segmento Desejado: {criterios_icp.get('Segmento_Desejado_do_Lead', 'N/A')}
    - Site da Minha Empresa (para análise de concorrente): {criterios_icp.get('Site_da_Empresa_Contratante', 'N/A')}

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
    except Exception as e:
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
    if len(apenas_digitos) == 11 and apenas_digitos.startswith('0'): apenas_digitos = apenas_digitos[1:]
    if len(apenas_digitos) == 11: return f"({apenas_digitos[:2]}) {apenas_digitos[2:7]}-{apenas_digitos[7:]}"
    elif len(apenas_digitos) == 10: return f"({apenas_digitos[:2]}) {apenas_digitos[2:6]}-{apenas_digitos[6:]}"
    else: return str(telefone)

# -- Funções de Qualificação Local --
def verificar_cargo(cargo_lead, cargos_icp_str):
    """Verifica se o cargo do lead está na lista de interesse do ICP."""
    if pd.isna(cargo_lead) or cargo_lead.strip() == '': return False
    cargos_de_interesse = [cargo.strip().lower() for cargo in cargos_icp_str.split(',')]
    return cargo_lead.strip().lower() in cargos_de_interesse

# --- FASE 3: INTERFACE DO APLICATIVO (STREAMLIT) ---

st.set_page_config(layout="wide", page_title="Agente LDR de IA")
st.title("🤖 Agente LDR com Inteligência Artificial")
st.write("Faça o upload dos seus arquivos para qualificação, enriquecimento e padronização de leads.")

# Interface de Upload
arquivo_dados = st.file_uploader("1. Selecione o arquivo de DADOS (.csv)", type="csv")
arquivo_icp = st.file_uploader("2. Selecione o arquivo de ICP (.csv)", type="csv")

if st.button("🚀 Iniciar Processamento Completo"):
    if arquivo_dados and arquivo_icp:
        # Configurar a API Key
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
            
            # Criar colunas de resultado
            leads_df['classificacao_icp'] = 'Aguardando Análise'
            leads_df['motivo_classificacao'] = ''

            st.info("Iniciando processamento... Isso pode levar alguns minutos.")
            progress_bar = st.progress(0)
            
            # Loop de Qualificação e Enriquecimento
            for index, lead in leads_df.iterrows():
                # 1. Qualificação Local (Rápida)
                if not verificar_cargo(lead.get('Cargo'), criterios_icp.get('Cargos_de_Interesse_do_Lead')):
                    leads_df.at[index, 'classificacao_icp'] = 'Fora do ICP'
                    leads_df.at[index, 'motivo_classificacao'] = 'Cargo fora do perfil'
                    continue # Pula para o próximo lead
                
                # (Adicionar aqui outras verificações locais como nº de funcionários e localidade)

                # 2. Qualificação com IA (Apenas para quem passou nos filtros locais)
                st.write(f"Analisando com IA: {lead['Nome_Empresa']}...")
                site_url = lead.get('Site_Original')
                
                if pd.notna(site_url) and site_url.strip() != '':
                    if not site_url.startswith(('http://', 'https://')): site_url = 'https://' + site_url
                    
                    texto_site = extrair_texto_com_selenium(site_url)
                    
                    if texto_site:
                        analise = analisar_icp_com_ia(texto_site, criterios_icp)
                        if analise.get('is_segmento_correto') and not analise.get('is_concorrente'):
                            leads_df.at[index, 'classificacao_icp'] = 'Dentro do ICP'
                            leads_df.at[index, 'motivo_classificacao'] = analise.get('motivo_segmento')
                        else:
                            leads_df.at[index, 'classificacao_icp'] = 'Fora do ICP'
                            leads_df.at[index, 'motivo_classificacao'] = f"Concorrente: {analise.get('is_concorrente')}. Motivo: {analise.get('motivo_concorrente')}" if analise.get('is_concorrente') else f"Segmento incorreto. Motivo: {analise.get('motivo_segmento')}"
                    else:
                        leads_df.at[index, 'classificacao_icp'] = 'Ponto de Atenção'
                        leads_df.at[index, 'motivo_classificacao'] = 'Site não acessível ou sem texto para análise'
                else:
                    leads_df.at[index, 'classificacao_icp'] = 'Ponto de Atenção'
                    leads_df.at[index, 'motivo_classificacao'] = 'Site não informado'
                
                progress_bar.progress((index + 1) / len(leads_df))
            
            st.success("Análise de qualificação concluída!")
            st.info("Iniciando padronização final dos dados...")

            # Loop de Padronização (Aplica a todos)
            leads_df['nome_completo_padronizado'] = leads_df.apply(padronizar_nome_contato, axis=1)
            leads_df['nome_empresa_padronizado'] = leads_df['Nome_Empresa'].apply(padronizar_nome_empresa)
            leads_df['telefone_padronizado'] = leads_df['Telefone_Original'].apply(padronizar_telefone)
            # (Adicionar aqui outras colunas a serem padronizadas)

            st.success("Processamento completo!")
            st.dataframe(leads_df)
            
            # Botão de Download
            csv = leads_df.to_csv(sep=';', index=False, encoding='utf-8-sig').encode('utf-8-sig')
            st.download_button(
                label="⬇️ Baixar resultado completo (.csv)",
                data=csv,
                file_name='leads_processados_final.csv',
                mime='text/csv',
            )
    else:
        st.warning("Por favor, faça o upload dos dois arquivos CSV para continuar.")