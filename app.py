# --- VERSÃO FINAL E ESTÁVEL ---
import streamlit as st
import pandas as pd
import io
import json
import re
import unicodedata
import google.generativeai as genai
from urllib.parse import urlparse

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

def analisar_presenca_online(nome_empresa, cidade):
    model = genai.GenerativeModel('gemini-1.5-flash-latest')
    prompt = f"""
    Você é um detetive de negócios online. Investigue a empresa '{nome_empresa}' de '{cidade}'.
    AÇÕES: 1. Faça uma busca na internet, priorizando o perfil da empresa no LinkedIn. 2. Responda ao JSON abaixo.
    REGRAS: Para 'ativa', procure por posts/notícias nos últimos 12 meses. Se não houver, considere 'inativa'.
    Responda APENAS com um objeto JSON válido com as chaves: "resumo_negocio", "is_ativa", "fonte_informacao".
    """
    try:
        response = model.generate_content(prompt, request_options={"timeout": 60})
        resposta_texto = response.text.replace('```json', '').replace('```', '').strip()
        return json.loads(resposta_texto)
    except Exception as e:
        return {"error": "Falha na análise de presença online", "details": str(e)}

def analisar_icp_com_ia(texto_ou_url, criterios_icp, is_url=True):
    model = genai.GenerativeModel('gemini-1.5-flash-latest')
    info_base_comparacao = f"O site da minha empresa é: {criterios_icp.get('site_da_empresa_contratante', 'Não informado')}"
    if '[INSIRA' in str(criterios_icp.get('site_da_empresa_contratante', '')):
        info_base_comparacao = f"A minha empresa é descrita como: '{criterios_icp.get('descricao_da_empresa_contratante', 'Não informado')}'"
    
    parte_analise = f"Visite a URL {texto_ou_url} e analise seu conteúdo." if is_url else f"Analise o seguinte resumo de negócio: '{texto_ou_url}'."

    prompt = f"""
    Você é um Analista de Leads Sênior. {parte_analise}
    Compare o que você leu com os critérios do meu ICP:
    - {info_base_comparacao}
    - Segmentos Válidos: [{criterios_icp.get('segmento_desejado_do_lead', 'N/A')}]
    Responda APENAS com um objeto JSON válido com as chaves: "is_concorrente", "motivo_concorrente", "is_segmento_correto", "motivo_segmento", "categoria_segmento".
    """
    try:
        timeout = 90 if is_url else 30
        response = model.generate_content(prompt, request_options={"timeout": timeout})
        resposta_texto = response.text.replace('```json', '').replace('```', '').strip()
        return json.loads(resposta_texto)
    except Exception as e:
        return {"error": "Falha na análise da IA", "details": str(e)}

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

def title_case_com_excecoes(s, excecoes):
    palavras = str(s).split()
    resultado = []
    for i, palavra in enumerate(palavras):
        if i > 0 and palavra.lower() in excecoes:
            resultado.append(palavra.lower())
        else:
            resultado.append(palavra.capitalize())
    return ' '.join(resultado)

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
    if tipo == 'cidade':
        cidade_limpa = re.sub(r'[^a-zA-Z\s]', '', str(valor)).strip()
        return title_case_com_excecoes(cidade_limpa, ['de', 'da', 'do', 'dos', 'das'])
    elif tipo == 'estado':
        estado_limpo = str(valor).strip().lower()
        mapa_estados = {'ac': 'Acre', 'al': 'Alagoas', 'ap': 'Amapá', 'am': 'Amazonas', 'ba': 'Bahia', 'ce': 'Ceará', 'df': 'Distrito Federal', 'es': 'Espírito Santo', 'go': 'Goiás', 'ma': 'Maranhão', 'mt': 'Mato Grosso', 'ms': 'Mato Grosso do Sul', 'mg': 'Minas Gerais', 'pa': 'Pará', 'pb': 'Paraíba', 'pr': 'Paraná', 'pe': 'Pernambuco', 'pi': 'Piauí', 'rj': 'Rio de Janeiro', 'rn': 'Rio Grande do Norte', 'rs': 'Rio Grande do Sul', 'ro': 'Rondônia', 'rr': 'Roraima', 'sc': 'Santa Catarina', 'sp': 'São Paulo', 'se': 'Sergipe', 'to': 'Tocantins'}
        return mapa_estados.get(estado_limpo, title_case_com_excecoes(estado_limpo, ['de', 'do']))
    elif tipo == 'pais':
        pais_limpo = str(valor).strip().lower()
        mapa_paises = { 'br': 'Brasil', 'bra': 'Brasil', 'brazil': 'Brasil' }
        return mapa_paises.get(pais_limpo, pais_limpo.capitalize())
    return valor

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

# --- FUNÇÃO DE APOIO E FUNÇÃO DE LOCALIDADE CORRIGIDAS ---
def normalizar_texto(texto):
    if pd.isna(texto): return ""
    s = str(texto).lower().strip()
    s = ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')
    return s

def verificar_localidade(lead_row, locais_icp):
    """
    Verifica se a localidade do lead atende a múltiplos critérios ou regiões, 
    de forma flexível, insensível a acentos, maiúsculas/minúsculas e siglas.
    """
    # Helper function interna para evitar NameError e garantir consistência
    def _normalizar(texto):
        if pd.isna(texto): return ""
        s = str(texto).lower().strip()
        return ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')

    # Dicionários de mapeamento
    mapa_estados = {
        'acre': 'ac', 'alagoas': 'al', 'amapa': 'ap', 'amazonas': 'am', 'bahia': 'ba', 'ceara': 'ce', 
        'distrito federal': 'df', 'espirito santo': 'es', 'goias': 'go', 'maranhao': 'ma', 'mato grosso': 'mt', 
        'mato grosso do sul': 'ms', 'minas gerais': 'mg', 'para': 'pa', 'paraiba': 'pb', 'parana': 'pr', 
        'pernambuco': 'pe', 'piaui': 'pi', 'rio de janeiro': 'rj', 'rio grande do norte': 'rn', 
        'rio grande do sul': 'rs', 'rondonia': 'ro', 'roraima': 'rr', 'santa catarina': 'sc', 
        'sao paulo': 'sp', 'sergipe': 'se', 'tocantins': 'to'
    }
    mapa_siglas = {v: k for k, v in mapa_estados.items()}
    
    regioes = {
        'sudeste': ['sp', 'rj', 'es', 'mg'], 'sul': ['pr', 'sc', 'rs'],
        'nordeste': ['ba', 'se', 'al', 'pe', 'pb', 'rn', 'ce', 'pi', 'ma'],
        'norte': ['ro', 'ac', 'am', 'rr', 'pa', 'ap', 'to'],
        'centro-oeste': ['ms', 'mt', 'go', 'df']
    }

    # Tratamento da regra do ICP
    if not isinstance(locais_icp, list):
        locais_icp = [locais_icp]
    
    if not locais_icp or pd.isna(locais_icp).all():
        return True
        
    if len(locais_icp) == 1 and _normalizar(locais_icp[0]) == 'brasil':
        return True

    # 1. Normaliza os dados do lead
    cidade_lead = _normalizar(lead_row.get('Cidade_Contato', ''))
    estado_lead = _normalizar(lead_row.get('Estado_Contato', ''))
    
    # 2. Cria um conjunto com todas as representações possíveis da localidade do lead
    estado_lead_sigla = mapa_estados.get(estado_lead, estado_lead)
    estado_lead_nome_completo = mapa_siglas.get(estado_lead_sigla, estado_lead_sigla) # <-- CORREÇÃO ESTAVA AQUI

    locais_possiveis_lead = {cidade_lead, estado_lead_sigla, estado_lead_nome_completo}
    locais_possiveis_lead.discard('')
    
    # 3. Loop de verificação
    for local_permitido_icp in locais_icp:
        regra_normalizada = _normalizar(local_permitido_icp)
        
        if regra_normalizada in regioes:
            if estado_lead_sigla in regioes[regra_normalizada]:
                return True
            continue

        # Se a regra for um local específico (Cidade, Estado, etc.)
        partes_requisito = {_normalizar(part.strip()) for part in str(local_permitido_icp).split(',')}
        partes_requisito.discard('brasil')
        partes_requisito.discard('')

        # VERIFICAÇÃO FINAL: Todas as partes da regra do ICP estão contidas nos locais possíveis do lead?
        if partes_requisito.issubset(locais_possiveis_lead):
            return True # Encontrou uma regra correspondente
            
    return False # Nenhuma regra do ICP correspondeu ao lead

# --- INTERFACE DO APLICATIVO ---
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
            criterios_icp_raw = dict(zip(icp_raw_df['Campo_ICP'], icp_raw_df['Valor_ICP']))
            criterios_icp = {str(k).lower().strip(): v for k, v in criterios_icp_raw.items()}
            
            for col in ['classificacao_icp', 'motivo_classificacao', 'categoria_do_lead']:
                if col not in leads_df.columns:
                    leads_df[col] = ''
            
            st.info("Iniciando qualificação...")
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            for index, lead in leads_df.iterrows():
                status_text.text(f"Analisando: {lead.get('Nome_Empresa', f'Linha {index+2}')}...")
                
                # --- FLUXO DE QUALIFICAÇÃO E ANÁLISE COMPLETO E CORRIGIDO ---
                analise = None
                
                if not verificar_funcionarios(lead.get('Numero_Funcionarios'), criterios_icp.get('numero_de_funcionarios_desejado_do_lead')):
                    leads_df.at[index, 'classificacao_icp'] = 'Fora do ICP'
                    leads_df.at[index, 'motivo_classificacao'] = 'Porte da empresa fora do perfil'
                elif not verificar_localidade(lead, criterios_icp.get('localidade_especifica_do_lead', [])):
                    leads_df.at[index, 'classificacao_icp'] = 'Fora do ICP'
                    leads_df.at[index, 'motivo_classificacao'] = 'Localidade fora do perfil'
                else:
                    site_url = lead.get('Site_Original')
                    if pd.notna(site_url) and str(site_url).strip() != '':
                        if not str(site_url).startswith(('http://', 'https://')):
                            site_url = 'https://' + str(site_url)
                        analise = analisar_icp_com_ia(site_url, criterios_icp)
                    else:
                        status_text.text(f"Site não informado. Buscando presença online para {lead.get('Nome_Empresa')}...")
                        presenca_online = analisar_presenca_online(lead.get('Nome_Empresa'), lead.get('Cidade_Empresa'))
                        if presenca_online and "error" not in presenca_online and presenca_online.get('is_ativa'):
                            resumo = presenca_online.get('resumo_negocio')
                            status_text.text(f"Presença online encontrada. Analisando resumo...")
                            analise = analisar_icp_com_ia(resumo, criterios_icp, is_url=False)
                            if analise and "error" not in analise:
                               analise['motivo_segmento'] = f"{analise.get('motivo_segmento')} (Baseado em resumo online: {presenca_online.get('fonte_informacao')})"
                        else:
                            leads_df.at[index, 'classificacao_icp'] = 'Fora do ICP'
                            leads_df.at[index, 'motivo_classificacao'] = 'Nenhuma informação conclusiva encontrada online'

                if analise and "error" not in analise:
                    leads_df.at[index, 'categoria_do_lead'] = analise.get('categoria_segmento', 'N/A')
                    if analise.get('is_segmento_correto') and not analise.get('is_concorrente'):
                        leads_df.at[index, 'classificacao_icp'] = 'Dentro do ICP'
                        leads_df.at[index, 'motivo_classificacao'] = analise.get('motivo_segmento')
                    else:
                        leads_df.at[index, 'classificacao_icp'] = 'Fora do ICP'
                        motivo = f"Concorrente: {analise.get('is_concorrente')}" if analise.get('is_concorrente') else f"Segmento incorreto: {analise.get('motivo_segmento')}"
                        leads_df.at[index, 'motivo_classificacao'] = motivo
                elif analise and "error" in analise:
                    leads_df.at[index, 'classificacao_icp'] = 'Erro na Análise'
                    leads_df.at[index, 'motivo_classificacao'] = analise.get('details', 'Erro desconhecido da IA.')

                progress_bar.progress((index + 1) / len(leads_df))

            status_text.info("Qualificação concluída! Iniciando padronização final dos dados...")
            
            df_cols = list(leads_df.columns)
            leads_df['nome_completo_padronizado'] = leads_df.apply(lambda row: padronizar_nome_contato(row, df_cols), axis=1)
            
            col_map = {
                'Nome_Empresa': ('nome_empresa_padronizado', padronizar_nome_empresa),
                'Site_Original': ('site_padronizado', padronizar_site),
                'Cidade_Contato': ('cidade_contato_padronizada', padronizar_localidade_geral, 'cidade'),
                'Estado_Contato': ('estado_contato_padronizado', padronizar_localidade_geral, 'estado'),
                'Pais_Contato': ('pais_contato_padronizado', padronizar_localidade_geral, 'pais'),
                'Cidade_Empresa': ('cidade_empresa_padronizada', padronizar_localidade_geral, 'cidade'),
                'Estado_Empresa': ('estado_empresa_padronizada', padronizar_localidade_geral, 'estado'),
                'Pais_Empresa': ('pais_empresa_padronizada', padronizar_localidade_geral, 'pais'),
            }

            for col, (nova_col, func, *args) in col_map.items():
                if col in df_cols:
                    if args:
                        leads_df[nova_col] = leads_df[col].apply(lambda x: func(x, args[0]))
                    else:
                        leads_df[nova_col] = leads_df[col].apply(func)

            for col in df_cols:
                if 'telefone' in col.lower():
                    leads_df[f'{col}_padronizado'] = leads_df[col].apply(padronizar_telefone)

            status_text.success("Processamento completo!")
            st.dataframe(leads_df)
            
            csv = leads_df.to_csv(sep=';', index=False, encoding='utf-8-sig').encode('utf-8-sig')
            st.download_button(label="⬇️ Baixar resultado completo (.csv)", data=csv, file_name='leads_analisados_final.csv', mime='text/csv')
    else:
        st.warning("Por favor, faça o upload dos dois arquivos CSV para continuar.")
