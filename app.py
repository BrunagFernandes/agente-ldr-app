# --- FASE 1: IMPORTAÇÃO DAS FERRAMENTAS ---
import streamlit as st
import pandas as pd
import io
import json
import google.generativeai as genai

# --- FASE 2: DEFINIÇÃO DE TODAS AS FUNÇÕES DO AGENTE ---

def ler_csv_flexivel(arquivo_upado):
    """Lê um arquivo CSV com separador flexível (ponto e vírgula ou vírgula)."""
    try:
        arquivo_upado.seek(0)
        # Tenta ler com ponto e vírgula primeiro
        df = pd.read_csv(arquivo_upado, sep=';', encoding='utf-8', on_bad_lines='skip')
        # Se só encontrou uma coluna, é provável que o separador esteja errado.
        if df.shape[1] == 1:
            arquivo_upado.seek(0)
            # Tenta ler com vírgula
            df = pd.read_csv(arquivo_upado, sep=',', encoding='utf-8', on_bad_lines='skip')
        return df
    except Exception as e:
        st.error(f"Erro crítico ao ler o arquivo CSV: {e}")
        return None

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

    AJA EM DUAS ETAPAS:
    1.  Primeiro, acesse e leia o conteúdo principal do site na seguinte URL: {url_do_lead}
    2.  Depois, com base no conteúdo que você leu, analise o site de acordo com os critérios abaixo.

    Critérios do ICP da Minha Empresa:
    - {info_base_comparacao}
    - Segmentos Válidos (para qualificação e categorização): [{criterios_icp.get('Segmento_Desejado_do_Lead', 'N/A')}]

    REGRAS RÍGIDAS PARA SUA RESPOSTA:
    - NÃO FAÇA suposições ou inferências se a informação não for clara.
    - Se a informação sobre a minha empresa (seja o site ou a descrição) não for suficiente para uma comparação de concorrência real, retorne 'is_concorrente' como false e explique no motivo que a informação de base era insuficiente.
    - NÃO INVENTE DADOS EM HIPÓTESE ALGUMA.

    Sua Resposta (Obrigatório):
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
        return {"error": f"Falha na análise da IA: {e}", "details": str(e)}

def verificar_cargo(cargo_lead, cargos_icp_str):
    """Verifica se o cargo do lead está na lista de interesse do ICP."""
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
            
            # --- BARREIRA DE VALIDAÇÃO OBRIGATÓRIA (VERSÃO CORRETA COM "OU") ---
            site_contratante = criterios_icp.get('Site_da_Empresa_Contratante', '').strip()
            desc_contratante = criterios_icp.get('Descricao_da_Empresa_Contratante', '').strip()

            # Verifica se o site parece uma URL real
            is_site_valid = (len(site_contratante) > 4 and '.' in site_contratante and '[INSIRA' not in site_contratante)
            
            # Verifica se a descrição é significativa
            is_desc_valid = (len(desc_contratante) > 15 and '[Descreva' not in desc_contratante)

            # O processo para SOMENTE SE NENHUM DOS DOIS for válido
            if not is_site_valid and not is_desc_valid:
                st.error("ERRO DE CONFIGURAÇÃO: O processo foi interrompido. Para a análise de concorrência funcionar, preencha o campo 'Site_da_Empresa_Contratante' OU o campo 'Descricao_da_Empresa_Contratante' no seu arquivo ICP.")
                st.stop()
            # --- FIM DA BARREIRA ---

            # Inicializa colunas de resultado
            for col in ['classificacao_icp', 'motivo_classificacao', 'categoria_do_lead']:
                if col not in leads_df.columns:
                    leads_df[col] = 'Aguardando Análise'

            st.info("Iniciando processamento com IA... Isso pode levar alguns minutos.")
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            for index, lead in leads_df.iterrows():
                status_text.text(f"Analisando: {lead.get('Nome_Empresa', 'Empresa Desconhecida')}...")
                
                # 1. Qualificação Local
                if not verificar_cargo(lead.get('Cargo'), criterios_icp.get('Cargos_de_Interesse_do_Lead')):
                    leads_df.at[index, 'classificacao_icp'] = 'Fora do ICP'
                    leads_df.at[index, 'motivo_classificacao'] = 'Cargo fora do perfil'
                else:
                    # 2. Qualificação com IA
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
            
            status_text.success("Processamento completo!")
            st.dataframe(leads_df)
            
            # (As funções de padronização final seriam chamadas aqui antes de exibir/baixar)

            csv = leads_df.to_csv(sep=';', index=False, encoding='utf-8-sig').encode('utf-8-sig')
            st.download_button(
                label="⬇️ Baixar resultado completo (.csv)",
                data=csv,
                file_name='leads_analisados_final.csv',
                mime='text/csv',
            )
    else:
        st.warning("Por favor, faça o upload dos dois arquivos CSV para continuar.")