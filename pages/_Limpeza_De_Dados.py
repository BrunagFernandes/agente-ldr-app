# --- CARREGAMENTO DOS DADOS DE MUNICÍPIOS (FEITO UMA SÓ VEZ) ---
@st.cache_data
def carregar_mapa_cidades_e_estados():
    """Carrega e prepara mapas otimizados de cidades e estados brasileiros usando py-ibge."""
    try:
        from py_ibge import municipios
        # A biblioteca retorna uma lista de dicionários, um para cada cidade
        lista_municipios = municipios()
        
        # Cria um mapa de busca otimizado para cidades: {'saopaulo': 'São Paulo'}
        mapa_cidades = {
            normalizar_texto_para_comparacao(m.nome): m.nome
            for m in lista_municipios
        }
        
        # Cria um mapa de busca para estados: {'sp': 'São Paulo'}
        mapa_estados = {
            m.uf.sigla.lower(): m.uf.nome
            for m in lista_municipios
        }
        # Adiciona nomes completos dos estados ao mapa
        for sigla, nome_completo in mapa_estados.items():
             mapa_estados[normalizar_texto_para_comparacao(nome_completo)] = nome_completo

        return mapa_cidades, mapa_estados
    except Exception as e:
        st.error(f"Não foi possível carregar a lista de municípios: {e}")
        return {}, {}

MAPA_CIDADES, MAPA_ESTADOS = carregar_mapa_cidades_e_estados()

# --- FUNÇÃO DE LOCALIDADE ATUALIZADA PARA USAR A BIBLIOTECA CORRETA ---
def padronizar_localidade_geral(valor, tipo):
    """Padroniza Cidades, Estados e Países, mantendo acentos."""
    if pd.isna(valor): return ''
    
    mapa_paises = { 'br': 'Brasil', 'bra': 'Brasil', 'brazil': 'Brasil' }
    
    # Chave de busca normalizada (sem acento, minúscula, sem "State of")
    chave_busca = normalizar_texto_para_comparacao(str(valor))
    chave_busca = re.sub(r'state of ', '', chave_busca).strip()

    if tipo == 'cidade':
        # Procura a cidade normalizada no nosso mapa e retorna o nome oficial com acento
        return MAPA_CIDADES.get(chave_busca, title_case_com_excecoes(str(valor), ['de', 'da', 'do', 'dos', 'das']))
    elif tipo == 'estado':
        # Procura a chave (seja sigla ou nome completo) no mapa e retorna o valor correto
        return MAPA_ESTADOS.get(chave_busca, title_case_com_excecoes(str(valor), ['de', 'do']))
    elif tipo == 'pais':
        return mapa_paises.get(chave_busca, str(valor).capitalize())
    return valor
