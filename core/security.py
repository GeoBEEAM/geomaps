from passlib.context import CryptContext

CRIPTO = CryptContext(schemes=["bcrypt"], deprecated="auto")

"""
    Função para verificar se a senha está correta, 
    comparando o plain text com o hash que 
    estará salvo no banco de dados durante a criação do usuário.
"""
def verify_password(plain_password: str, hashed_password: str) -> bool:
    return CRIPTO.verify(plain_password, hashed_password)


"""
    Função para criar um hash da senha do usuário.
    A senha será salva no banco de dados como um hash.
"""
def generate_password_hash(password: str) -> str:
    return CRIPTO.hash(password)