# --- ESTAÇÃO 1: LIMPEZA E PADRONIZAÇÃO DE DADOS (VERSÃO CORRIGIDA) ---
import streamlit as st
import pandas as pd
import io
import re
import unicodedata
from municipios.municipios import CONSULTA

# --- CARREGAMENTO DOS DADOS DE MUNICÍPIOS (FEITO UMA SÓ VEZ) ---
@st.cache_data
def carregar_mapa_cidades():
    """Carrega e prepara um mapa otimizado de cidades brasileiras."""
    try:
        # A biblioteca retorna uma lista de dicionários, um para cada cidade
        lista_municipios = CONSULTA.get_list_of_all_cities()
        
        # Cria um mapa de busca otimizado: {'saopaulo': 'São Paulo', 'jundiai': 'Jundiaí'}
        mapa_cidades = {
            ''.join(c for c in unicodedata.normalize('NFD', m['nome']).lower() if unicodedata.category(c) != 'Mn'): m['nome']
            for m in lista_municipios
        }
        return mapa_cidades
    except Exception as e:
        st.error(f"Não foi possível carregar a lista de municípios: {e}")
        return {}

MAPA_CIDADES_NORMALIZADO = carregar_mapa_cidades()

# --- FUNÇÕES DE APOIO E PADRONIZAÇÃO ---

def ler_csv_flexivel(arquivo_upado):
    """Lê um arquivo CSV do Apollo, tentando diferentes separadores."""
    try:
        arquivo_upado.seek(0)
        df = pd.read_csv(arquivo_upado, sep=',', encoding='utf-8', on_bad_lines='skip', low_memory=False)
        if df.shape[1] <= 1:
            arquivo_upado.seek(0)
            df = pd.read_csv(arquivo_upado, sep=';', encoding='utf-8', on_bad_lines='skip', low_memory=False)
        df.columns = df.columns.str.strip()
        return df
    except Exception as e:
        st.error(f"Erro crítico ao ler o arquivo CSV: {e}")
        return None

def title_case_com_excecoes(s, excecoes):
    """Aplica capitalização inteligente, mantendo conectivos em minúsculo."""
    palavras = str(s).split()
    resultado = []
    for i, palavra in enumerate(palavras):
        if i > 0 and palavra.lower() in excecoes:
            resultado.append(palavra.lower())
        else:
            resultado.append(palavra.capitalize())
    return ' '.join(resultado)

def normalizar_texto_para_comparacao(texto):
    """Remove acentos e converte para minúsculo para comparações internas."""
    if pd.isna(texto): return ""
    s = str(texto).lower().strip()
    return ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')

def padronizar_nome_contato(row, df_columns):
    """Cria um nome completo com o primeiro nome e o último sobrenome."""
    nome_col = next((col for col in df_columns if 'first name' in col.lower() or 'nome_lead' in col.lower()), None)
    sobrenome_col = next((col for col in df_columns if 'last name' in col.lower() or 'sobrenome_lead' in col.lower()), None)
    if not nome_col or pd.isna(row.get(nome_col)): return ''
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

def padronizar_localidade_geral(valor, tipo):
    if pd.isna(valor): return ''
    mapa_estados = {'acre': 'Acre', 'alagoas': 'Alagoas', 'amapa': 'Amapá', 'amazonas': 'Amazonas', 'bahia': 'Bahia', 'ceara': 'Ceará', 'distrito federal': 'Distrito Federal', 'espirito santo': 'Espírito Santo', 'goias': 'Goiás', 'maranhao': 'Maranhão', 'mato grosso': 'Mato Grosso', 'mato grosso do sul': 'Mato Grosso do Sul', 'minas gerais': 'Minas Gerais', 'para': 'Pará', 'paraiba': 'Paraíba', 'parana': 'Paraná', 'pernambuco': 'Pernambuco', 'piaui': 'Piauí', 'rio de janeiro': 'Rio de Janeiro', 'rio grande do norte': 'Rio Grande do Norte', 'rs': 'Rio Grande do Sul', 'rondonia': 'Rondônia', 'roraima': 'Roraima', 'santa catarina': 'Santa Catarina', 'sao paulo': 'São Paulo', 'sergipe': 'Sergipe', 'tocantins': 'Tocantins', 'ac': 'Acre', 'al': 'Alagoas', 'ap': 'Amapá', 'am': 'Amazonas', 'ba': 'Bahia', 'ce': 'Ceará', 'df': 'Distrito Federal', 'es': 'Espírito Santo', 'go': 'Goiás', 'ma': 'Maranhão', 'mt': 'Mato Grosso', 'ms': 'Mato Grosso do Sul', 'mg': 'Minas Gerais', 'pa': 'Pará', 'pb': 'Paraíba', 'pr': 'Paraná', 'pe': 'Pernambuco', 'pi': 'Piauí', 'rj': 'Rio de Janeiro', 'rn': 'Rio Grande do Norte', 'rs': 'Rio Grande do Sul', 'ro': 'Rondônia', 'rr': 'Roraima', 'sc': 'Santa Catarina', 'sp': 'São Paulo', 'se': 'Sergipe', 'to': 'Tocantins'}
    mapa_paises = { 'br': 'Brasil', 'bra': 'Brasil', 'brazil': 'Brasil' }
    
    texto_norm = normalizar_texto_para_comparacao(str(valor))
    
    if tipo == 'cidade':
        return MAPA_CIDADES_NORMALIZADO.get(texto_norm, title_case_com_excecoes(str(valor), ['de', 'da', 'do', 'dos', 'das']))
    elif tipo == 'estado':
        estado_sem_prefixo = re.sub(r'state of ', '', str(valor).lower()).strip()
        estado_norm_sem_prefixo = normalizar_texto_para_comparacao(estado_sem_prefixo)
        return mapa_estados.get(estado_norm_sem_prefixo, title_case_com_excecoes(str(valor), ['de', 'do']))
    elif tipo == 'pais':
        return mapa_paises.get(texto_norm, str(valor).capitalize())
    return valor

# --- INTERFACE DA ESTAÇÃO 1 ---
st.set_page_config(layout="wide", page_title="Estação 1: Limpeza")

st.title("⚙️ Estação 1: Limpeza e Preparação de Dados")
st.write("Faça o upload do seu arquivo de leads (exportado do Apollo ou similar) para limpá-lo e padronizá-lo.")

uploaded_file = st.file_uploader("1. Selecione o arquivo de DADOS brutos (.csv)", type="csv")

if st.button("🧹 Iniciar Limpeza e Padronização"):
    if uploaded_file is not None:
        with st.spinner('Lendo e processando o arquivo... Por favor, aguarde.'):
            df = ler_csv_flexivel(uploaded_file)
            
            if df is not None:
                st.success("Arquivo lido com sucesso!")
                
                mapa_colunas = {
                    'First Name': 'Nome_Lead', 'Last Name': 'Sobrenome_Lead', 'Title': 'Cargo', 
                    'Company': 'Nome_Empresa', 'Email': 'Email_Lead', 'Phone': 'Telefone_Original',
                    'Industry': 'Segmento_Original', 'City': 'Cidade_Contato', 'State': 'Estado_Contato', 
                    'Country': 'Pais_Contato', 'Company City': 'Cidade_Empresa', 'Company State': 'Estado_Empresa',
                    'Company Country': 'Pais_Empresa', 'Website': 'Site_Original', 'Employees': 'Numero_Funcionarios',
                    'Person Linkedin Url': 'Linkedin_Contato', 'Company Linkedin Url': 'LinkedIn_Empresa', 
                    'Facebook Url': 'Facebook_Empresa'
                }
                
                colunas_para_renomear = {k: v for k, v in mapa_colunas.items() if k in df.columns}
                df_limpo = df.rename(columns=colunas_para_renomear)
                
                colunas_finais = list(colunas_para_renomear.values())
                df_limpo = df_limpo[colunas_finais].copy()
                
                df_limpo['Nome_Completo'] = df_limpo.apply(lambda row: padronizar_nome_contato(row, df_limpo.columns), axis=1)
                
                colunas_para_padronizar = {
                    'Nome_Empresa': padronizar_nome_empresa, 'Site_Original': padronizar_site,
                    'Telefone_Original': padronizar_telefone,
                    'Cidade_Contato': lambda x: padronizar_localidade_geral(x, 'cidade'),
                    'Estado_Contato': lambda x: padronizar_localidade_geral(x, 'estado'),
                    'Pais_Contato': lambda x: padronizar_localidade_geral(x, 'pais'),
                    'Cidade_Empresa': lambda x: padronizar_localidade_geral(x, 'cidade'),
                    'Estado_Empresa': lambda x: padronizar_localidade_geral(x, 'estado'),
                    'Pais_Empresa': lambda x: padronizar_localidade_geral(x, 'pais'),
                }
                
                for col, func in colunas_para_padronizar.items():
                    if col in df_limpo.columns:
                        df_limpo[col] = df_limpo[col].astype(str).apply(func)
                
                cols_ordenadas = ['Nome_Completo'] + [col for col in colunas_finais if col not in ['Nome_Lead', 'Sobrenome_Lead']]
                df_limpo = df_limpo[cols_ordenadas]

                df_limpo.fillna('', inplace=True)
                df_limpo = df_limpo.astype(str).replace('nan', '')

                st.success("Arquivo limpo e padronizado com sucesso!")
                st.dataframe(df_limpo.head(10))

                st.session_state['df_limpo'] = df_limpo
    else:
        st.warning("Por favor, faça o upload de um arquivo para começar.")

if 'df_limpo' in st.session_state:
    st.write("---")
    st.header("Próximo Passo")
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
