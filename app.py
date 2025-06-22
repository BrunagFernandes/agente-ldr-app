# --- VERSÃO COM PADRONIZAÇÃO DE LOCALIDADE ATIVADA ---
import streamlit as st
import pandas as pd
import io
import json
import re
from urllib.parse import urlparse
import google.generativeai as genai

# --- FUNÇÕES DO AGENTE ---

def ler_csv_flexivel(arquivo_upado):
    try:
        arquivo_upado.seek(0)
        df = pd.read_csv(arquivo_upado, sep=';', encoding='utf-8', on_bad_lines='skip')
        if df.shape[1] == 1:
            arquivo_upado.seek(0)
            df = pd.read_csv(arquivo_upado, sep=',', encoding='utf-8', on_bad_lines='skip')
        df.columns = df.columns.str.strip()
        return df
    except Exception as e:
        st.error(f"Erro crítico ao ler o arquivo CSV: {e}")
        return None

def analisar_icp_com_ia_por_url(url_do_lead, criterios_icp):
    model = genai.GenerativeModel('gemini-1.5-flash-latest')
    info_base_comparacao = f"O site da minha empresa é: {criterios_icp.get('site_da_empresa_contratante', 'Não informado')}"
    if '[INSIRA' in str(criterios_icp.get('site_da_empresa_contratante', '')):
        info_base_comparacao = f"A minha empresa é descrita como: '{criterios_icp.get('descricao_da_empresa_contratante', 'Não informado')}'"
    prompt = f"""
    Você é um Analista de Leads Sênior. Visite a URL {url_do_lead} e responda em JSON.
    Critérios do ICP:
    - {info_base_comparacao}
    - Segmentos Válidos: [{criterios_icp.get('segmento_desejado_do_lead', 'N/A')}]
    Responda APENAS com um objeto JSON válido com as chaves: "is_concorrente", "motivo_concorrente", "is_segmento_correto", "motivo_segmento", "categoria_segmento".
    """
    try:
        response = model.generate_content(prompt, request_options={"timeout": 90})
        resposta_texto = response.text.replace('```json', '').replace('```', '').strip()
        return json.loads(resposta_texto)
    except Exception as e:
        return {"error": "Falha na análise da IA", "details": str(e)}

# --- FUNÇÕES DE PADRONIZAÇÃO ---
def title_case_com_excecoes(s, excecoes):
    palavras = s.split()
    resultado = []
    for i, palavra in enumerate(palavras):
        if i > 0 and palavra.lower() in excecoes:
            resultado.append(palavra.lower())
        else:
            resultado.append(palavra.capitalize())
    return ' '.join(resultado)

def padronizar_cidade(cidade):
    if pd.isna(cidade): return ''
    cidade_limpa = re.sub(r'[^a-zA-Z\s]', '', str(cidade)).strip()
    return title_case_com_excecoes(cidade_limpa, ['de', 'da', 'do', 'dos', 'das'])

def padronizar_estado(estado):
    if pd.isna(estado): return ''
    estado_limpo = str(estado).strip().lower()
    mapa_estados = {
        'ac': 'Acre', 'al': 'Alagoas', 'ap': 'Amapá', 'am': 'Amazonas',
        'ba': 'Bahia', 'ce': 'Ceará', 'df': 'Distrito Federal', 'es': 'Espírito Santo',
        'go': 'Goiás', 'ma': 'Maranhão', 'mt': 'Mato Grosso', 'ms': 'Mato Grosso do Sul',
        'mg': 'Minas Gerais', 'pa': 'Pará', 'pb': 'Paraíba', 'pr': 'Paraná',
        'pe': 'Pernambuco', 'pi': 'Piauí', 'rj': 'Rio de Janeiro', 'rn': 'Rio Grande do Norte',
        'rs': 'Rio Grande do Sul', 'ro': 'Rondônia', 'rr': 'Roraima', 'sc': 'Santa Catarina',
        'sp': 'São Paulo', 'se': 'Sergipe', 'to': 'Tocantins'
    }
    return mapa_estados.get(estado_limpo, title_case_com_excecoes(estado_limpo, ['de', 'do']))

def padronizar_pais(pais):
    if pd.isna(pais): return ''
    pais_limpo = str(pais).strip().lower()
    mapa_paises = { 'br': 'Brasil', 'bra': 'Brasil', 'brazil': 'Brasil' }
    return mapa_paises.get(pais_limpo, pais_limpo.capitalize())

def padronizar_nome_contato(row, df_columns):
    nome_col = next((col for col in df_columns if col.strip().lower() == 'nome_lead'), None)
    sobrenome_col = next((col for col in df_columns if col.strip().lower() == 'sobrenome_lead'), None)
    if not nome_col or pd.isna(row[nome_col]): return ''
    primeiro_nome = str(row[nome_col]).split()[0]
    sobrenome_completo = str(row.get(sobrenome_col, ''))
    conectivos = ['de', 'da', 'do', 'dos', 'das']
    partes_sobrenome = [p for p in sobrenome_completo.split() if p.lower() not in conectivos]
    ultimo_sobrenome = partes_sobrenome[-1] if partes_sobrenome else ''
    nome_final = f"{primeiro_nome} {ultimo_sobrenome}".strip()
    return nome_final.title()

def padronizar_nome_empresa(nome_empresa):
    if pd.isna(nome_empresa): return ''
    nome_limpo = str(nome_empresa)
    siglas = [r'\sS/A', r'\sS\.A', r'\sSA\b', r'\sLTDA', r'\sLtda', r'\sME\b', r'\sEIRELI', r'\sEPP', r'\sMEI\b']
    for sigla in siglas:
        nome_limpo = re.sub(sigla, '', nome_limpo, flags=re.IGNORECASE)
    return title_case_com_excecoes(nome_limpo.strip(), ['de', 'da', 'do', 'dos', 'das', 'e'])

def padronizar_site(site):
    if pd.isna(site) or str(site).strip() == '': return ''
    site_limpo = str(site).strip()
    site_limpo = re.sub(r'^(https?://)?', '', site_limpo)
    site_limpo = site_limpo.rstrip('/')
    if not site_limpo.lower().startswith('www.'):
        site_limpo = 'www.' + site_limpo
    return site_limpo
    
def padronizar_telefone(telefone):
    if pd.isna(telefone): return ''
    apenas_digitos = re.sub(r'\D', '', str(telefone))
    if apenas_digitos.startswith('0800'): return ''
    if apenas_digitos.startswith('55') and len(apenas_digitos) > 11: apenas_digitos = apenas_digitos[2:]
    if len(apenas_digitos) == 11 and apenas_digitos.startswith('0'): apenas_digitos = apenas_digitos[1:]
    if len(apenas_digitos) not in [10, 11]: return ''
    if len(apenas_digitos) == 11: return f"({apenas_digitos[:2]}) {apenas_digitos[2:7]}-{apenas_digitos[7:]}"
    elif len(apenas_digitos) == 10: return f"({apenas_digitos[:2]}) {apenas_digitos[2:6]}-{apenas_digitos[6:]}"
    return ''

# (O restante das funções de verificação permanecem as mesmas)
def verificar_cargo(cargo_lead, cargos_icp_str):
    if pd.isna(cargos_icp_str) or str(cargos_icp_str).strip() == '': return True
    if pd.isna(cargo_lead) or str(cargo_lead).strip() == '': return False
    cargos_de_interesse = [cargo.strip().lower() for cargo in str(cargos_icp_str).split(',')]
    return str(cargo_lead).strip().lower() in cargos_de_interesse

def verificar_funcionarios(funcionarios_lead, faixa_icp_str):
    if pd.isna(faixa_icp_str) or str(faixa_icp_str).strip() == '': return True
    if pd.isna(funcionarios_lead): return False
    try:
        funcionarios_str = str(funcionarios_lead).strip().lower().replace('.', '').replace(',', '')
        if 'k' in funcionarios_str:
            funcionarios_num = float(funcionarios_str.replace('k', '')) * 1000
        else:
            funcionarios_num = pd.to_numeric(funcionarios_str)
        if pd.isna(funcionarios_num): return False
    except (ValueError, TypeError): return False
    faixa_str = str(faixa_icp_str).lower()
    numeros = [int(s) for s in re.findall(r'\d+', faixa_str)]
    if not numeros: return False
    if "acima" in faixa_str or "maior" in faixa_str: return funcionarios_num > numeros[0]
    elif "abaixo" in faixa_str or "menor" in faixa_str: return funcionarios_num < numeros[0]
    elif "-" in faixa_str and len(numeros) == 2: return numeros[0] <= funcionarios_num <= numeros[1]
    elif len(numeros) == 1: return funcionarios_num >= numeros[0]
    return False

def verificar_localidade(lead_row, locais_icp):
    if isinstance(locais_icp, str): locais_icp = [locais_icp]
    if not locais_icp or any(loc.strip().lower() == 'brasil' for loc in locais_icp): return True
    regioes = {
        'sudeste': ['sp', 'rj', 'es', 'mg'], 'sul': ['pr', 'sc', 'rs'],
        'nordeste': ['ba', 'se', 'al', 'pe', 'pb', 'rn', 'ce', 'pi', 'ma'],
        'norte': ['ro', 'ac', 'am', 'rr', 'pa', 'ap', 'to'],
        'centro-oeste': ['ms', 'mt', 'go', 'df']
    }
    cidade_lead = str(lead_row.get('Cidade_Contato', '')).strip().lower()
    estado_lead = str(lead_row.get('Estado_Contato', '')).strip().lower()
    pais_lead = str(lead_row.get('Pais_Contato', '')).strip().lower()
    for local_permitido in locais_icp:
        local_permitido_clean = local_permitido.lower().strip()
        if local_permitido_clean in regioes:
            if estado_lead in regioes[local_permitido_clean]: return True 
        else:
            partes_requisito = [part.strip().lower() for part in local_permitido_clean.split(',')]
            lead_data_comparable = [cidade_lead, estado_lead, pais_lead]
            if all(parte in lead_data_comparable for parte in partes_requisito): return True
    return False

# --- INTERFACE DO APLICATIVO (STREAMLIT) ---
st.set_page_config(layout="wide", page_title="Agente LDR de IA")
st.title("🤖 Agente LDR com Inteligência Artificial")
st.write("Faça o upload dos seus arquivos para qualificação e padronização de leads.")

arquivo_dados = st.file_uploader("1. Selecione o arquivo de DADOS (.csv)", type="csv")
arquivo_icp = st.file_uploader("2. Selecione o arquivo de ICP (.csv)", type="csv")

if st.button("🚀 Iniciar Análise e Padronização"):
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
            criterios_icp_raw = icp_raw_df.groupby('Campo_ICP')['Valor_ICP'].apply(lambda x: list(x) if len(x) > 1 else x.iloc[0]).to_dict()
            criterios_icp = {str(k).lower().strip(): v for k, v in criterios_icp_raw.items()}
            
            for col in ['classificacao_icp', 'motivo_classificacao', 'categoria_do_lead']:
                if col not in leads_df.columns:
                    leads_df[col] = ''
            
            st.info("Iniciando qualificação...")
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            for index, lead in leads_df.iterrows():
                status_text.text(f"Analisando: {lead.get('Nome_Empresa', f'Linha {index+2}')}...")
                
                # (A lógica de qualificação e análise com IA permanece a mesma)
                if not verificar_funcionarios(lead.get('Numero_Funcionarios'), criterios_icp.get('numero_de_funcionarios_desejado_do_lead')):
                    leads_df.at[index, 'classificacao_icp'] = 'Fora do ICP'
                    leads_df.at[index, 'motivo_classificacao'] = 'Porte da empresa fora do perfil'
                    progress_bar.progress((index + 1) / len(leads_df))
                    continue
                # ... (restante do loop)

                progress_bar.progress((index + 1) / len(leads_df))
            
            status_text.info("Qualificação concluída! Iniciando padronização final dos dados...")
            
            # --- APLICAÇÃO DA PADRONIZAÇÃO - AGORA ATIVADA ---
            df_cols = list(leads_df.columns)

            nome_completo_col = 'nome_completo_padronizado'
            leads_df[nome_completo_col] = leads_df.apply(lambda row: padronizar_nome_contato(row, df_cols), axis=1)

            if 'Nome_Empresa' in df_cols:
                leads_df['nome_empresa_padronizado'] = leads_df['Nome_Empresa'].apply(padronizar_nome_empresa)
            
            if 'Site_Original' in df_cols:
                leads_df['site_padronizado'] = leads_df['Site_Original'].apply(padronizar_site)

            # Padronização de Localidade
            if 'Cidade_Contato' in df_cols:
                leads_df['cidade_padronizada'] = leads_df['Cidade_Contato'].apply(padronizar_cidade)
            if 'Estado_Contato' in df_cols:
                leads_df['estado_padronizado'] = leads_df['Estado_Contato'].apply(padronizar_estado)
            if 'Pais_Contato' in df_cols:
                leads_df['pais_padronizado'] = leads_df['Pais_Contato'].apply(padronizar_pais)

            # Padronização de Telefones
            for col in df_cols:
                if 'telefone' in col.lower():
                    leads_df[f'{col}_padronizado'] = leads_df[col].apply(padronizar_telefone)

            status_text.success("Processamento completo!")
            st.dataframe(leads_df)
            
            csv = leads_df.to_csv(sep=';', index=False, encoding='utf-8-sig').encode('utf-8-sig')
            st.download_button(label="⬇️ Baixar resultado completo (.csv)", data=csv, file_name='leads_analisados_final.csv', mime='text/csv')
    else:
        st.warning("Por favor, faça o upload dos dois arquivos CSV para continuar.")
