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


def create_access_token(user_id: int, email: str, username: str = None) -> str:
    """
    Cree un token de session (JWT) pour un utilisateur connecte
    """
    expire = datetime.utcnow() + timedelta(hours=TOKEN_EXPIRE_HOURS)
    payload = {
        "user_id": user_id,
        "email": email,
        "username": username,
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

from azure.communication.email import EmailClient
import secrets as py_secrets

EMAIL_CONNECTION_STRING = os.getenv("AZURE_COMMUNICATION_CONNECTION_STRING")
EMAIL_SENDER = os.getenv("AZURE_COMMUNICATION_SENDER_EMAIL")

# Stockage temporaire des tokens de reinitialisation (en memoire)
# Format : { token: {"user_id": X, "expires": datetime} }
reset_tokens = {}


def generate_reset_token(user_id: int) -> str:
    """
    Genere un token unique et temporaire pour la reinitialisation de mot de passe
    """
    token = py_secrets.token_urlsafe(32)
    expire = datetime.utcnow() + timedelta(hours=1)
    reset_tokens[token] = {"user_id": user_id, "expires": expire}
    return token


def verify_reset_token(token: str) -> int:
    """
    Verifie qu'un token de reinitialisation est valide et non expire
    Retourne le user_id associe, ou None si invalide
    """
    data = reset_tokens.get(token)
    if not data:
        return None
    if datetime.utcnow() > data["expires"]:
        del reset_tokens[token]
        return None
    return data["user_id"]


def consume_reset_token(token: str):
    """
    Supprime un token apres utilisation (usage unique)
    """
    if token in reset_tokens:
        del reset_tokens[token]


def send_reset_email(to_email: str, reset_link: str) -> bool:
    """
    Envoie un email de reinitialisation de mot de passe via Azure Communication Services
    """
    try:
        client = EmailClient.from_connection_string(EMAIL_CONNECTION_STRING)

        message = {
            "senderAddress": EMAIL_SENDER,
            "recipients": {
                "to": [{"address": to_email}]
            },
            "content": {
                "subject": "Reinitialisation de votre mot de passe - Agent Revue de Code",
                "html": f"""
                <div style="font-family: Arial, sans-serif; max-width: 500px; margin: 0 auto;">
                    <h2 style="color: #2B5797;">Reinitialisation de mot de passe</h2>
                    <p>Vous avez demande la reinitialisation de votre mot de passe.</p>
                    <p><a href="{reset_link}" style="background: #2B5797; color: white; padding: 12px 24px; text-decoration: none; border-radius: 8px; display: inline-block;">Reinitialiser mon mot de passe</a></p>
                    <p style="color: #666; font-size: 13px;">Ce lien expire dans 1 heure. Si vous n'avez pas demande cette reinitialisation, ignorez cet email.</p>
                </div>
                """
            }
        }

        poller = client.begin_send(message)
        result = poller.result()
        return True
    except Exception as e:
        print(f"Erreur envoi email : {str(e)}")
        return False

# Stockage temporaire des tokens de verification d'email (en memoire)
email_verification_tokens = {}


def generate_email_verification_token(user_id: int) -> str:
    """
    Genere un token unique pour la verification d'email
    """
    token = py_secrets.token_urlsafe(32)
    expire = datetime.utcnow() + timedelta(hours=24)
    email_verification_tokens[token] = {"user_id": user_id, "expires": expire}
    return token


def verify_email_token(token: str) -> int:
    """
    Verifie qu'un token de confirmation d'email est valide et non expire
    Retourne le user_id associe, ou None si invalide
    """
    data = email_verification_tokens.get(token)
    if not data:
        return None
    if datetime.utcnow() > data["expires"]:
        del email_verification_tokens[token]
        return None
    return data["user_id"]


def consume_email_verification_token(token: str):
    """
    Supprime un token apres utilisation (usage unique)
    """
    if token in email_verification_tokens:
        del email_verification_tokens[token]


def send_verification_email(to_email: str, verification_link: str) -> bool:
    """
    Envoie un email de confirmation d'inscription via Azure Communication Services
    """
    try:
        client = EmailClient.from_connection_string(EMAIL_CONNECTION_STRING)

        message = {
            "senderAddress": EMAIL_SENDER,
            "recipients": {
                "to": [{"address": to_email}]
            },
            "content": {
                "subject": "Confirmez votre compte - Agent Revue de Code",
                "html": f"""
                <div style="font-family: Arial, sans-serif; max-width: 500px; margin: 0 auto;">
                    <h2 style="color: #2B5797;">Bienvenue !</h2>
                    <p>Merci de vous être inscrit. Confirmez votre adresse email pour activer votre compte :</p>
                    <p><a href="{verification_link}" style="background: #2B5797; color: white; padding: 12px 24px; text-decoration: none; border-radius: 8px; display: inline-block;">Confirmer mon email</a></p>
                    <p style="color: #666; font-size: 13px;">Ce lien expire dans 24 heures.</p>
                </div>
                """
            }
        }

        poller = client.begin_send(message)
        result = poller.result()
        return True
    except Exception as e:
        print(f"Erreur envoi email de verification : {str(e)}")
        return False

# Stockage temporaire des inscriptions EN ATTENTE de confirmation (en memoire)
pending_registrations = {}


def create_pending_registration(email: str, username: str, password_hash: str) -> str:
    """
    Stocke temporairement les infos d'inscription (PAS encore en base de donnees)
    en attendant la confirmation de l'email
    """
    token = py_secrets.token_urlsafe(32)
    expire = datetime.utcnow() + timedelta(hours=24)
    pending_registrations[token] = {
        "email": email,
        "username": username,
        "password_hash": password_hash,
        "expires": expire
    }
    return token


def get_pending_registration(token: str) -> dict:
    """
    Recupere les infos d'inscription en attente, ou None si invalide/expire
    """
    data = pending_registrations.get(token)
    if not data:
        return None
    if datetime.utcnow() > data["expires"]:
        del pending_registrations[token]
        return None
    return data


def consume_pending_registration(token: str):
    """
    Supprime l'inscription en attente apres utilisation (usage unique)
    """
    if token in pending_registrations:
        del pending_registrations[token]