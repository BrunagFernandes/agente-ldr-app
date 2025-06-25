# pages/1_Limpeza_de_Dados.py
import streamlit as st
import pandas as pd
import io
import re
import unicodedata

st.set_page_config(layout="wide", page_title="Estação 1: Limpeza")

# --- FUNÇÕES DE LIMPEZA E PADRONIZAÇÃO ---

def ler_csv_flexivel(arquivo_upado):
    try:
        arquivo_upado.seek(0)
        df = pd.read_csv(arquivo_upado, sep=',', encoding='utf-8', on_bad_lines='skip', low_memory=False)
        if df.shape[1] == 1:
            arquivo_upado.seek(0)
            df = pd.read_csv(arquivo_upado, sep=';', encoding='utf-8', on_bad_lines='skip', low_memory=False)
        df.columns = df.columns.str.strip()
        return df
    except Exception as e:
        st.error(f"Erro ao ler o arquivo CSV: {e}")
        return None

def title_case_com_excecoes(s, excecoes):
    palavras = str(s).split()
    resultado = []
    for i, palavra in enumerate(palavras):
        if i > 0 and palavra.lower() in excecoes:
            resultado.append(palavra.lower())
        else:
            resultado.append(palavra.capitalize())
    return ' '.join(resultado)

def padronizar_nome_contato(row, df_columns):
    nome_col = next((col for col in df_columns if col.strip().lower() in ['first name', 'nome_lead']), None)
    sobrenome_col = next((col for col in df_columns if col.strip().lower() in ['last name', 'sobrenome_lead']), None)
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

def padronizar_localidade_geral(valor, tipo):
    if pd.isna(valor): return ''
    mapa_estados = {'acre': 'Acre', 'alagoas': 'Alagoas', 'amapa': 'Amapá', 'amazonas': 'Amazonas', 'bahia': 'Bahia', 'ceara': 'Ceará', 'distrito federal': 'Distrito Federal', 'espirito santo': 'Espírito Santo', 'goias': 'Goiás', 'maranhao': 'Maranhão', 'mato grosso': 'Mato Grosso', 'mato grosso do sul': 'Mato Grosso do Sul', 'minas gerais': 'Minas Gerais', 'para': 'Pará', 'paraiba': 'Paraíba', 'parana': 'Paraná', 'pernambuco': 'Pernambuco', 'piaui': 'Piauí', 'rio de janeiro': 'Rio de Janeiro', 'rio grande do norte': 'Rio Grande do Norte', 'rio grande do sul': 'Rio Grande do Sul', 'rondonia': 'Rondônia', 'roraima': 'Roraima', 'santa catarina': 'Santa Catarina', 'sao paulo': 'São Paulo', 'state of sao paulo': 'São Paulo', 'sergipe': 'Sergipe', 'tocantins': 'Tocantins'}
    mapa_paises = { 'br': 'Brasil', 'bra': 'Brasil', 'brazil': 'Brasil' }
    
    s_norm = ''.join(c for c in unicodedata.normalize('NFD', str(valor).lower().strip()) if unicodedata.category(c) != 'Mn')

    if tipo == 'cidade':
        return title_case_com_excecoes(str(valor).strip(), ['de', 'da', 'do', 'dos', 'das'])
    elif tipo == 'estado':
        return mapa_estados.get(s_norm, title_case_com_excecoes(str(valor), ['de', 'do']))
    elif tipo == 'pais':
        return mapa_paises.get(s_norm, str(valor).capitalize())
    return valor

# --- INTERFACE DA ESTAÇÃO 1 ---
st.title("⚙️ Estação 1: Limpeza e Preparação de Dados")
st.write("Faça o upload do seu arquivo de leads (exportado do Apollo ou similar) para limpá-lo e padronizá-lo.")

uploaded_file = st.file_uploader("1. Selecione o arquivo de DADOS brutos (.csv)", type="csv")

if st.button("🧹 Limpar e Padronizar Arquivo"):
    if uploaded_file is not None:
        with st.spinner('Lendo e processando o arquivo... Por favor, aguarde.'):
            df = ler_csv_flexivel(uploaded_file)
            
            if df is not None:
                # ETAPA 1: Seleção e Mapeamento de Colunas
                mapa_colunas = {
                    'First Name': 'Nome_Lead', 'Last Name': 'Sobrenome_Lead', 'Title': 'Cargo', 
                    'Company': 'Nome_Empresa', 'Email': 'Email_Lead', 'Phone': 'Telefone_Original',
                    'Industry': 'Segmento_Original', 'City': 'Cidade_Empresa', 'State': 'Estado_Empresa', 
                    'Country': 'Pais_Empresa', 'Website': 'Site_Original', 'Employees': 'Numero_Funcionarios',
                    'Person Linkedin Url': 'Linkedin_Contato', 'Company Linkedin Url': 'LinkedIn_Empresa', 
                    'Facebook Url': 'Facebook_Empresa'
                }
                
                colunas_para_renomear = {k: v for k, v in mapa_colunas.items() if k in df.columns}
                df_limpo = df.rename(columns=colunas_para_renomear)
                
                colunas_finais = [v for k, v in mapa_colunas.items() if k in df.columns]
                df_limpo = df_limpo[colunas_finais].copy()
                
                # ETAPA 2: Padronização e Reestruturação
                df_cols = list(df_limpo.columns)

                df_limpo['Nome_Completo'] = df_limpo.apply(lambda row: padronizar_nome_contato(row, df_cols), axis=1)
                df_limpo.drop(columns=['Nome_Lead', 'Sobrenome_Lead'], inplace=True, errors='ignore')

                col_map_padronizacao = {
                    'Nome_Empresa': padronizar_nome_empresa,
                    'Cidade_Empresa': lambda x: padronizar_localidade_geral(x, 'cidade'),
                    'Estado_Empresa': lambda x: padronizar_localidade_geral(x, 'estado'),
                    'Pais_Empresa': lambda x: padronizar_localidade_geral(x, 'pais'),
                }

                for col, func in col_map_padronizacao.items():
                    if col in df_limpo.columns:
                        df_limpo[col] = df_limpo[col].astype(str).apply(func)

                st.success("Arquivo limpo e padronizado com sucesso!")
                st.dataframe(df_limpo.head(10))

                st.session_state['df_limpo'] = df_limpo

# --- BOTÕES DE AÇÃO PÓS-LIMPEZA ---
if 'df_limpo' in st.session_state:
    st.write("---")
    
    col1, col2 = st.columns(2)
    
    with col1:
        csv = st.session_state['df_limpo'].to_csv(sep=';', index=False, encoding='utf-8-sig').encode('utf-8-sig')
        st.download_button(
            label="⬇️ Baixar CSV Limpo", data=csv, file_name='leads_limpos.csv', 
            mime='text/csv', use_container_width=True
        )
        
    with col2:
        if st.button("➡️ Enviar para Análise (Estação 2)", use_container_width=True):
            st.switch_page("pages/2_Analise_de_ICP.py")