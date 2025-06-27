# --- ESTAÇÃO 1: LIMPEZA E PADRONIZAÇÃO DE DADOS (VERSÃO FINAL CORRIGIDA) ---
import streamlit as st
import pandas as pd
import io
import re
import unicodedata
import requests # <-- Adicionado para fazer a chamada à API do IBGE
from dados_traducao import DICIONARIO_SEGMENTOS

# --- FUNÇÃO DE APOIO PARA NORMALIZAÇÃO ---
def normalizar_texto_para_comparacao(texto):
    """Remove acentos e converte para minúsculo para comparações internas."""
    if pd.isna(texto): return ""
    s = str(texto).lower().strip()
    return ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')

# --- CARREGAMENTO DOS DADOS DE MUNICÍPIOS (FEITO UMA SÓ VEZ) ---
@st.cache_data
def carregar_dados_ibge():
    """Carrega e prepara mapas otimizados de cidades e estados da API do IBGE."""
    try:
        st.info("Carregando lista oficial de localidades do IBGE... (só na primeira vez)")
        url_municipios = "https://servicodados.ibge.gov.br/api/v1/localidades/municipios"
        response_municipios = requests.get(url_municipios)
        response_municipios.raise_for_status()
        municipios_json = response_municipios.json()
        
        mapa_cidades = {
            normalizar_texto_para_comparacao(m['nome']): m['nome']
            for m in municipios_json if 'nome' in m
        }
        
        mapa_estados = {}
        for m in municipios_json:
            try:
                # Acesso seguro aos dados aninhados
                uf_data = m['microrregiao']['mesorregiao']['UF']
                sigla = uf_data['sigla'].lower()
                nome = uf_data['nome']
                mapa_estados[sigla] = nome
                mapa_estados[normalizar_texto_para_comparacao(nome)] = nome
            except (KeyError, TypeError):
                continue # Ignora entradas malformadas na API do IBGE

        return mapa_cidades, mapa_estados
    except Exception as e:
        st.error(f"Não foi possível carregar a lista de localidades do IBGE: {e}")
        return {}, {}

MAPA_CIDADES, MAPA_ESTADOS = carregar_dados_ibge()


# --- DEMAIS FUNÇÕES DE PADRONIZAÇÃO ---

def ler_csv_flexivel(arquivo_upado):
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
    palavras = str(s).split()
    if not palavras:
        return ""
    resultado = [palavras[0].capitalize()]
    for palavra in palavras[1:]:
        if palavra.lower() in excecoes:
            resultado.append(palavra.lower())
        else:
            resultado.append(palavra.capitalize())
    return ' '.join(resultado)

def padronizar_nome_contato(row, df_columns):
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

def padronizar_localidade_geral(valor, tipo):
    if pd.isna(valor): return ''
    mapa_paises = { 'br': 'Brasil', 'bra': 'Brasil', 'brazil': 'Brasil' }
    
    chave_busca = normalizar_texto_para_comparacao(str(valor))
    
    if tipo == 'cidade':
        return MAPA_CIDADES.get(chave_busca, title_case_com_excecoes(str(valor), ['de', 'da', 'do', 'dos', 'das']))
    elif tipo == 'estado':
        chave_busca_estado = re.sub(r'state of ', '', chave_busca).strip()
        return MAPA_ESTADOS.get(chave_busca_estado, title_case_com_excecoes(str(valor), ['de', 'do']))
    elif tipo == 'pais':
        return mapa_paises.get(chave_busca, str(valor).capitalize())
    return valor

def padronizar_site(site):
    if pd.isna(site) or str(site).strip() == '': return ''
    site_limpo = str(site).strip()
    site_limpo = re.sub(r'^(https?://)?', '', site_limpo)
    site_limpo = site_limpo.rstrip('/')
    if not site_limpo.lower().startswith('www.'):
        site_limpo = 'www.' + site_limpo
    return site_limpo

    
def padronizar_telefone(telefone):
    """Filtra e formata um número de telefone para o padrão brasileiro, seguindo a lógica de verificação em etapas."""
    if pd.isna(telefone):
        return ''
    
    tel_str = str(telefone).strip()

    # Etapa 1: Verifica se é um número internacional (começa com '+' mas não '+55')
    if tel_str.startswith('+') and not tel_str.startswith('+55'):
        return ''

    # Limpa todos os caracteres não numéricos para a próxima etapa
    apenas_digitos = re.sub(r'\D', '', tel_str)

    # Etapa 2: Se o número original começava com '+55', remove o '55'
    if tel_str.startswith('+55'):
        apenas_digitos = apenas_digitos[2:]
    
    # Etapa 3: Verifica se é 0800
    if apenas_digitos.startswith('0800'):
        return ''

    # Etapa 4: Validação de tamanho e segunda chance para remover o '55'
    if len(apenas_digitos) > 11:
        if apenas_digitos.startswith('55'):
            apenas_digitos = apenas_digitos[2:]
    
    # Etapa 5: Verificação final de tamanho
    if len(apenas_digitos) not in [10, 11]:
        return ''

    # Etapa 6: Formatação final para números válidos
    if len(apenas_digitos) == 11:
        return f"({apenas_digitos[:2]}) {apenas_digitos[2:7]}-{apenas_digitos[7:]}"
    elif len(apenas_digitos) == 10:
        return f"({apenas_digitos[:2]}) {apenas_digitos[2:6]}-{apenas_digitos[6:]}"
        
    return '' 

def padronizar_segmento(segmento):
    """Traduz o segmento usando o dicionário interno."""
    if pd.isna(segmento): return ''
    # Normaliza o segmento do arquivo para fazer a busca no dicionário
    segmento_norm = str(segmento).lower().strip()
    # Retorna a tradução do dicionário, ou o próprio segmento com a primeira letra maiúscula se não encontrar
    return DICIONARIO_SEGMENTOS.get(segmento_norm, title_case_com_excecoes(segmento, []))
    
    return '' # Caso de segurança

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
                mapa_colunas = {
                    'First Name': 'Nome_Lead', 'Last Name': 'Sobrenome_Lead', 'Title': 'Cargo', 
                    'Company': 'Nome_Empresa', 'Email': 'Email_Lead', 'Corporate Phone': 'Telefone_Original',
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

                df_cols = list(df_limpo.columns)
                if 'Nome_Lead' in df_cols and 'Sobrenome_Lead' in df_cols:
                    df_limpo['Nome_Completo'] = df_limpo.apply(lambda row: padronizar_nome_contato(row, df_cols), axis=1)
                
                colunas_para_padronizar = {
                    'Nome_Empresa': padronizar_nome_empresa, 'Site_Original': padronizar_site,
                    'Telefone_Original': padronizar_telefone,
                    'Segmento_Original': padronizar_segmento, 
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
                for col in df_limpo.columns:
                    df_limpo[col] = df_limpo[col].astype(str).replace('nan', '')

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
