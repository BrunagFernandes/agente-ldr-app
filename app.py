# --- FUNÇÃO DE LOCALIDADE CORRIGIDA (AGORA INCLUI O PAÍS) ---
def verificar_localidade(lead_row, locais_icp):
    """Verifica se a localidade do lead atende a múltiplos critérios ou regiões."""
    # Garante que sempre trabalhamos com uma lista, mesmo se o ICP tiver só um local
    if isinstance(locais_icp, str):
        locais_icp = [locais_icp]
    
    # Se a lista de locais for vazia ou conter 'brasil', aprova todos
    if not locais_icp or any(loc.strip().lower() == 'brasil' for loc in locais_icp):
        return True

    regioes = {
        'sudeste': ['sp', 'rj', 'es', 'mg'],
        'sul': ['pr', 'sc', 'rs'],
        'nordeste': ['ba', 'se', 'al', 'pe', 'pb', 'rn', 'ce', 'pi', 'ma'],
        'norte': ['ro', 'ac', 'am', 'rr', 'pa', 'ap', 'to'],
        'centro-oeste': ['ms', 'mt', 'go', 'df']
    }

    # Prepara os dados de localidade do lead (minúsculo e sem acentos para comparação)
    cidade_lead = str(lead_row.get('Cidade_Contato', '')).strip().lower()
    estado_lead = str(lead_row.get('Estado_Contato', '')).strip().lower()
    pais_lead = str(lead_row.get('Pais_Contato', '')).strip().lower() # <-- DADO DO PAÍS AGORA É LIDO
    
    # Verifica se o lead corresponde a QUALQUER UM dos locais permitidos
    for local_permitido in locais_icp:
        local_permitido_clean = local_permitido.lower()
        if local_permitido_clean in regioes:
            if estado_lead in regioes[local_permitido_clean]:
                return True 
        else:
            partes_requisito = [part.strip() for part in local_permitido_clean.split(',')]
            
            # --- LÓGICA DE COMPARAÇÃO CORRIGIDA ---
            # Agora a lista de comparação inclui a cidade, o estado E o país.
            lead_data_comparable = [cidade_lead, estado_lead, pais_lead]
            
            if all(parte in lead_data_comparable for parte in partes_requisito):
                return True

    return False