# --- VERSÃO FINAL COM ENRIQUECIMENTO DE SITE ---
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

# --- NOVA FUNÇÃO DE ENRIQUECIMENTO DE SITE ---
def enriquecer_site_com_ia(nome_empresa, cidade, estado):
    """Pede para a IA encontrar o site oficial de uma empresa."""
    model = genai.GenerativeModel('gemini-1.5-flash-latest')
    prompt = f"""
    Encontre o site oficial da empresa chamada "{nome_empresa}", localizada aproximadamente em "{cidade}, {estado}".
    Priorize domínios corporativos (.com, .com.br) e evite redes sociais (LinkedIn, Facebook) ou diretórios (Apontador, etc.).
    Responda APENAS com a URL do site no formato "www.exemplo.com.br" ou com a palavra "N/A" se não encontrar um site oficial confiável.
    """
    try:
        response = model.generate_content(prompt)
        site = response.text.strip()
        # Validação simples para ver se a resposta parece uma URL
        if '.' in site and len(site) > 4:
            return site
        else:
            return "N/A"
    except Exception:
        return "N/A"

def analisar_icp_com_ia_por_url(url_do_lead, criterios_icp):
    """Usa a IA para visitar a URL e fazer a análise completa do ICP."""
    model = genai.GenerativeModel('gemini-1.5-flash-latest')
    info_base_comparacao = f"O site da minha empresa é: {criterios_icp.get('site_da_empresa_contratante')}"
    if '[INSIRA O SITE' in info_base_comparacao or not criterios_icp.get('site_da_empresa_contratante'):
        info_base_comparacao = f"A minha empresa é descrita como: '{criterios_icp.get('descricao_da_empresa_contratante')}'"
    
    prompt = f"""
    Você é um Analista de Desenvolvimento de Leads Sênior. Sua tarefa é analisar o site de um lead e compará-lo com os critérios do meu ICP.
    AJA EM DUAS ETAPAS:
    1. Primeiro, acesse e leia o conteúdo principal da seguinte URL: {url_do_lead}
    2. Depois, com base no conteúdo lido, analise o site conforme os critérios abaixo.

    Critérios do ICP da Minha Empresa:
    - {info_base_comparacao}
    - Segmentos Válidos: [{criterios_icp.get('segmento_desejado_do_lead', 'N/A')}]

    REGRAS RÍGIDAS:
    - NÃO INVENTE DADOS. Se a informação não for clara, indique isso.

    Sua Resposta (Obrigatório):
    Responda APENAS com um objeto JSON válido com as chaves: "is_concorrente", "motivo_concorrente", "is_segmento_correto", "motivo_segmento", "categoria_segmento".
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
            criterios_icp_raw = dict(zip(icp_raw_df['Campo_ICP'], icp_raw_df['Valor_ICP']))
            criterios_icp = {str(k).lower().strip(): v for k, v in criterios_icp_raw.items()}
            
            site_contratante = str(criterios_icp.get('site_da_empresa_contratante', '')).strip()
            desc_contratante = str(criterios_icp.get('descricao_da_empresa_contratante', '')).strip()
            is_site_valid = (len(site_contratante) > 4 and '.' in site_contratante and '[INSIRA' not in site_contratante)
            is_desc_valid = (len(desc_contratante) > 10 and '[Descreva' not in desc_contratante)
            if not is_site_valid and not is_desc_valid:
                st.error("ERRO DE CONFIGURAÇÃO: Preencha o campo 'Site_da_Empresa_Contratante' OU 'Descricao_da_Empresa_Contratante' no seu arquivo ICP.")
                st.stop()

            # Inicializa colunas de resultado
            for col in ['classificacao_icp', 'motivo_classificacao', 'categoria_do_lead', 'site_enriquecido', 'cargo_dentro_do_icp']:
                if col not in leads_df.columns:
                    leads_df[col] = ''
            leads_df['cargo_dentro_do_icp'] = False

            st.info("Iniciando processamento...")
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            for index, lead in leads_df.iterrows():
                status_text.text(f"Analisando: {lead.get('Nome_Empresa', 'Empresa Desconhecida')}...")
                
                # 1. Qualificação de Cargo
                leads_df.at[index, 'cargo_dentro_do_icp'] = verificar_cargo(lead.get('Cargo'), criterios_icp.get('cargos_de_interesse_do_lead'))
                
                # 2. Enriquecimento e Análise da Empresa
                site_url = lead.get('Site_Original')
                
                # Se o site estiver faltando, tenta enriquecer
                if pd.isna(site_url) or site_url.strip() == '':
                    status_text.text(f"Site não informado para {lead.get('Nome_Empresa')}. Buscando com IA...")
                    site_enriquecido = enriquecer_site_com_ia(lead.get('Nome_Empresa'), lead.get('Cidade_Empresa'), lead.get('Estado_Empresa'))
                    if site_enriquecido != "N/A":
                        leads_df.at[index, 'site_enriquecido'] = site_enriquecido
                        site_url = site_enriquecido # Usa o novo site para a análise
                    else:
                        leads_df.at[index, 'classificacao_icp'] = 'Ponto de Atenção'
                        leads_df.at[index, 'motivo_classificacao'] = 'Site não informado e não encontrado'
                        progress_bar.progress((index + 1) / len(leads_df))
                        continue # Pula para o próximo lead se não encontrou o site

                # Prossegue para a análise se tiver uma URL (original ou enriquecida)
                if pd.notna(site_url) and site_url.strip() != '':
                    if not site_url.startswith(('http://', 'https://')): site_url = 'https://' + site_url
                    
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

                progress_bar.progress((index + 1) / len(leads_df))
            
            status_text.success("Processamento completo!")
            st.dataframe(leads_df)
            
            csv = leads_df.to_csv(sep=';', index=False, encoding='utf-8-sig').encode('utf-8-sig')
            st.download_button(label="⬇️ Baixar resultado completo (.csv)", data=csv, file_name='leads_analisados_final.csv', mime='text/csv')
    else:
        st.warning("Por favor, faça o upload dos dois arquivos CSV para continuar.")