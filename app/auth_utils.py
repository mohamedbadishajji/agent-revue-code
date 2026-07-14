from passlib.context import CryptContext
from jose import jwt, JWTError
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv

load_dotenv()

# Configuration du hashing des mots de passe (bcrypt = standard securise)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

SECRET_KEY = os.getenv("JWT_SECRET_KEY", "change-moi-en-production")
ALGORITHM = "HS256"
TOKEN_EXPIRE_HOURS = 24


def hash_password(password: str) -> str:
    """
    Transforme un mot de passe en clair en hash securise
    Tronque a 72 caracteres (limite technique de bcrypt)
    """
    return pwd_context.hash(password[:72])


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifie qu'un mot de passe correspond au hash stocke
    """
    return pwd_context.verify(plain_password[:72], hashed_password)


def create_access_token(user_id: int, email: str) -> str:
    """
    Cree un token de session (JWT) pour un utilisateur connecte
    Ce token sera stocke dans un cookie et verifie a chaque requete
    """
    expire = datetime.utcnow() + timedelta(hours=TOKEN_EXPIRE_HOURS)
    payload = {
        "user_id": user_id,
        "email": email,
        "exp": expire
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict:
    """
    Verifie et decode un token de session
    Retourne None si le token est invalide ou expire
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None