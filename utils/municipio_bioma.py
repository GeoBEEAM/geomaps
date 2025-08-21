# Mapeamento exemplo: município -> bioma
# Adicione mais municípios conforme necessário
MUNICIPIO_BIOMA = {
    "São Luís": "Amazônia",
    "Viana": "Amazônia",
    "Belo Horizonte": "Mata Atlântica",
    "Campo Grande": "Pantanal",
    "Brasília": "Cerrado",
    "Alta Floresta D'Oeste": "Amazônia",  # Adicionado para teste
    # ... outros municípios ...
}

def get_bioma_by_municipio(nome_municipio: str) -> str:
    return MUNICIPIO_BIOMA.get(nome_municipio)
