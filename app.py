# --- VERSÃO FINAL COM REQUESTS-HTML ---
import streamlit as st
import pandas as pd
import io
import json
import time
import re
import nltk
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
from bs4 import BeautifulSoup
import google.generativeai as genai
from requests_html import HTMLSession # Nova biblioteca

# --- FUNÇÕES DO AGENTE ---

def ler_csv_flexivel(arquivo_upado):
    """Lê um arquivo CSV com separador flexível."""
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

# --- NOVA FUNÇÃO DE EXTRAÇÃO, MAIS LEVE ---
def extrair_texto_com_requests_html(url):
    """Usa requests-html para renderizar JavaScript e extrair o texto."""
    try:
        session = HTMLSession()
        r = session.get(url, timeout=15)
        # Renderiza o JavaScript da página. O timeout é importante.
        r.html.render(sleep=5, timeout=20)
        # Usa BeautifulSoup para uma extração de texto mais limpa
        soup = BeautifulSoup(r.html.html, 'html.parser')
        return soup.get_text(separator=' ', strip=True)
    except Exception as e:
        st.error(f"Erro ao acessar a URL {url}: {e}")
        return None

def analisar_icp_com_ia(texto_do_site, criterios_icp):
    """Envia o texto e os critérios para a IA e retorna a análise."""
    prompt = f"""
    Você é um Analista de Desenvolvimento de Leads Sênior. Analise o 'Texto do Site do Lead'
    com base nos 'Critérios do Cliente Ideal (ICP)' da minha empresa.
    **Critérios do ICP da Minha Empresa:**
    - Site da Minha Empresa (para análise de concorrente): {criterios_icp.get('Site_da_Empresa_Contratante', 'N/A')}
    - Segmentos Válidos (use esta lista para qualificar e categorizar): [{criterios_icp.get('Segmento_Desejado_do_Lead', 'N/A')}]
    **Texto do Site do Lead para Análise:**
    ---
    {texto_do_site[:6000]}
    ---
    **Sua Resposta (Obrigatório):**
    Responda APENAS com um objeto JSON válido com as chaves: "is_concorrente" (boolean), "motivo_concorrente" (string), "is_segmento_correto" (boolean), "motivo_segmento" (string), "categoria_segmento" (string, um dos Segmentos Válidos ou 'N/A').
    """
    try:
        model = genai.GenerativeModel('gemini-1.5-flash-latest')
        response = model.generate_content(prompt)
        resposta_texto = response.text.replace('```json', '').replace('```', '').strip()
        return json.loads(resposta_texto)
    except Exception as e:
        return {"error": "Falha na análise da IA", "details": str(e)}

# (As funções de padronização e verificação de cargo continuam as mesmas)
def padronizar_nome_contato(row):
    nome = row.get('Nome_Lead', '')
    sobrenome = row.get('Sobrenome_Lead', '')
    if pd.isna(nome) or nome.strip() == '': return ''
    nome_completo = f"{nome} {sobrenome}".strip()
    return nome_completo.title()

def padronizar_nome_empresa(nome_empresa):
    if pd.isna(nome_empresa): return ''
    siglas = [r'\sS/A', r'\sS\.A', r'\sSA', r'\sLTDA', r'\sLtda', r'\sME', r'\sEIRELI', r'\sEPP', r'\sMEI']
    for sigla in siglas:
        nome_empresa = re.sub(sigla, '', nome_empresa, flags=re.IGNORECASE)
    return nome_empresa.strip().title()

def padronizar_telefone(telefone):
    if pd.isna(telefone): return ''
    apenas_digitos = re.sub(r'\D', '', str(telefone))
    if len(apenas_digitos) > 11 and apenas_digitos.startswith('55'): apenas_digitos = apenas_digitos[2:]
    if len(apenas_digitos) == 11 and apenas_digitos.startswith('0'): apenas_digitos = apenas_digitos[1:]
    if len(apenas_digitos) == 11: return f"({apenas_digitos[:2]}) {apenas_digitos[2:7]}-{apenas_digitos[7:]}"
    elif len(apenas_digitos) == 10: return f"({apenas_digitos[:2]}) {apenas_digitos[2:6]}-{apenas_digitos[6:]}"
    else: return str(telefone)

def verificar_cargo(cargo_lead, cargos_icp_str):
    if pd.isna(cargo_lead) or cargo_lead.strip() == '' or pd.isna(cargos_icp_str): return False
    cargos_de_interesse = [cargo.strip().lower() for cargo in cargos_icp_str.split(',')]
    return cargo_lead.strip().lower() in cargos_de_interesse

# --- INTERFACE DO APLICATIVO (STREAMLIT) ---
st.set_page_config(layout="wide", page_title="Agente LDR de IA")
st.title("🤖 Agente LDR com Inteligência Artificial")
st.write("Faça o upload dos seus arquivos para qualificação, enriquecimento e padronização de leads.")
arquivo_dados = st.file_uploader("1. Selecione o arquivo de DADOS (.csv)", type="csv")
arquivo_icp = st.file_uploader("2. Selecione o arquivo de ICP (.csv)", type="csv")

if st.button("🚀 Iniciar Processamento Completo"):
    if arquivo_dados and arquivo_icp:
        try:
            genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
        except KeyError:
            st.error("Chave de API do Google não configurada. Adicione-a nos 'Secrets' do seu aplicativo Streamlit.")
            st.stop()
        
        st.info("Lendo arquivos...")
        leads_df = ler_csv_flexivel(arquivo_dados)
        icp_raw_df = ler_csv_flexivel(arquivo_icp)

        if leads_df is not None and icp_raw_df is not None:
            criterios_icp = dict(zip(icp_raw_df['Campo_ICP'], icp_raw_df['Valor_ICP']))
            
            leads_df['classificacao_icp'] = 'Aguardando Análise'
            leads_df['motivo_classificacao'] = ''
            leads_df['categoria_do_lead'] = ''

            st.info("Iniciando processamento... Isso pode levar alguns minutos.")
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            for index, lead in leads_df.iterrows():
                status_text.text(f"Analisando: {lead['Nome_Empresa']}...")
                if not verificar_cargo(lead.get('Cargo'), criterios_icp.get('Cargos_de_Interesse_do_Lead')):
                    leads_df.at[index, 'classificacao_icp'] = 'Fora do ICP'
                    leads_df.at[index, 'motivo_classificacao'] = 'Cargo fora do perfil'
                else:
                    site_url = lead.get('Site_Original')
                    if pd.notna(site_url) and site_url.strip() != '':
                        if not site_url.startswith(('http://', 'https://')): site_url = 'https://' + site_url
                        
                        # Usando a nova função de extração leve
                        texto_site = extrair_texto_com_requests_html(site_url)
                        
                        if texto_site:
                            analise = analisar_icp_com_ia(texto_site, criterios_icp)
                            leads_df.at[index, 'categoria_do_lead'] = analise.get('categoria_segmento', 'N/A')
                            if analise.get('is_segmento_correto') and not analise.get('is_concorrente'):
                                leads_df.at[index, 'classificacao_icp'] = 'Dentro do ICP'
                                leads_df.at[index, 'motivo_classificacao'] = analise.get('motivo_segmento')
                            else:
                                leads_df.at[index, 'classificacao_icp'] = 'Fora do ICP'
                                leads_df.at[index, 'motivo_classificacao'] = f"Concorrente: {analise.get('is_concorrente')}" if analise.get('is_concorrente') else f"Segmento incorreto: {analise.get('motivo_segmento')}"
                        else:
                            leads_df.at[index, 'classificacao_icp'] = 'Ponto de Atenção'
                            leads_df.at[index, 'motivo_classificacao'] = 'Extração de texto falhou'
                    else:
                        leads_df.at[index, 'classificacao_icp'] = 'Ponto de Atenção'
                        leads_df.at[index, 'motivo_classificacao'] = 'Site não informado'
                
                progress_bar.progress((index + 1) / len(leads_df))
            
            status_text.text("Análise de qualificação concluída!")
            # (O resto do código de padronização e download continua aqui...)
            st.dataframe(leads_df)
            csv = leads_df.to_csv(sep=';', index=False, encoding='utf-8-sig').encode('utf-8-sig')
            st.download_button( "⬇️ Baixar resultado completo (.csv)", data=csv, file_name='leads_processados_final.csv', mime='text/csv',)
    else:
        st.warning("Por favor, faça o upload dos dois arquivos CSV para continuar.")