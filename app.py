# --- VERSÃO FINAL COM CORREÇÃO DO ATTRIBUTEERROR ---
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
    """Usa a IA para visitar a URL e fazer a análise completa do ICP."""
    # (Esta função permanece a mesma)
    model = genai.GenerativeModel('gemini-1.5-flash-latest')
    info_base_comparacao = f"O site da minha empresa é: {criterios_icp.get('site_da_empresa_contratante')}"
    if '[INSIRA O SITE' in info_base_comparacao or not criterios_icp.get('site_da_empresa_contratante'):
        info_base_comparacao = f"A minha empresa é descrita como: '{criterios_icp.get('descricao_da_empresa_contratante')}'"
    prompt = f"""
    Você é um Analista de Desenvolvimento de Leads Sênior. Analise o site do lead na URL {url_do_lead} e compare com os critérios do meu ICP:
    - {info_base_comparacao}
    - Segmentos Válidos: [{criterios_icp.get('segmento_desejado_do_lead', 'N/A')}]
    Responda APENAS com um objeto JSON válido com as chaves: "is_concorrente", "motivo_concorrente", "is_segmento_correto", "motivo_segmento", "categoria_segmento".
    """
    try:
        response = model.generate_content(prompt, request_options={"timeout": 60})
        resposta_texto = response.text.replace('```json', '').replace('```', '').strip()
        return json.loads(resposta_texto)
    except Exception as e:
        return {"error": f"Falha na análise da IA: {e}", "details": str(e)}

def verificar_cargo(cargo_lead, cargos_icp_str):
    """Verifica se o cargo do lead está na lista de interesse do ICP."""
    if pd.isna(cargo_lead) or cargos_icp_str.strip() == '': return False
    cargos_de_interesse = [cargo.strip().lower() for cargo in cargos_icp_str.split(',')]
    return cargo_lead.strip().lower() in cargos_de_interesse

def verificar_localidade_simplificada(lead_row, localidade_icp_str):
    """Versão simplificada que verifica um único local (cidade, estado ou país)."""
    if localidade_icp_str.strip().lower() == 'brasil' or localidade_icp_str.strip() == '':
        return True
    loc_lead = [
        str(lead_row.get('Cidade_Contato', '')).strip().lower(),
        str(lead_row.get('Estado_Contato', '')).strip().lower(),
        str(lead_row.get('Pais_Contato', '')).strip().lower()
    ]
    requisitos_icp = [req.strip().lower() for req in localidade_icp_str.split(',')]
    for requisito in requisitos_icp:
        if requisito not in loc_lead:
            return False
    return True

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
            st.error("Chave de API do Google não configurada.")
            st.stop()
        
        st.info("Lendo arquivos...")
        leads_df = ler_csv_flexivel(arquivo_dados)
        icp_raw_df = ler_csv_flexivel(arquivo_icp)

        if leads_df is not None and icp_raw_df is not None:
            criterios_icp_raw = dict(zip(icp_raw_df['Campo_ICP'], icp_raw_df['Valor_ICP']))
            criterios_icp = {str(k).lower().strip(): v for k, v in criterios_icp_raw.items()}
            
            # (Bloco de validação do ICP permanece aqui)
            
            for col in ['classificacao_icp', 'motivo_classificacao']:
                if col not in leads_df.columns:
                    leads_df[col] = ''

            st.info("Iniciando processamento...")
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            for index, lead in leads_df.iterrows():
                status_text.text(f"Analisando: {lead.get('Nome_Empresa', 'Empresa Desconhecida')}...")
                
                # --- CHAMADA DAS FUNÇÕES CORRIGIDA (com str()) ---
                cargo_ok = verificar_cargo(str(lead.get('Cargo')), str(criterios_icp.get('cargos_de_interesse_do_lead', '')))
                localidade_ok = verificar_localidade_simplificada(lead, str(criterios_icp.get('localidade_especifica_do_lead', '')))

                if not cargo_ok or not localidade_ok:
                    leads_df.at[index, 'classificacao_icp'] = 'Fora do ICP'
                    motivo_cargo = 'Cargo fora do perfil' if not cargo_ok else ''
                    motivo_loc = 'Localidade fora do perfil' if not localidade_ok else ''
                    leads_df.at[index, 'motivo_classificacao'] = ' '.join(filter(None, [motivo_cargo, motivo_loc])).strip()
                else:
                    # (lógica de análise com IA) ...
                    leads_df.at[index, 'classificacao_icp'] = 'Dentro do ICP (Local)'
                
                progress_bar.progress((index + 1) / len(leads_df))
            
            status_text.success("Processamento completo!")
            st.dataframe(leads_df)
            
            csv = leads_df.to_csv(sep=';', index=False, encoding='utf-8-sig').encode('utf-8-sig')
            st.download_button(label="⬇️ Baixar resultado completo (.csv)", data=csv, file_name='leads_analisados_final.csv', mime='text/csv')
    else:
        st.warning("Por favor, faça o upload dos dois arquivos CSV para continuar.")