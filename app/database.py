from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

AZURE_SQL_SERVER = os.getenv("AZURE_SQL_SERVER")
AZURE_SQL_DATABASE = os.getenv("AZURE_SQL_DATABASE")
AZURE_SQL_USERNAME = os.getenv("AZURE_SQL_USERNAME")
AZURE_SQL_PASSWORD = os.getenv("AZURE_SQL_PASSWORD")

CONNECTION_STRING = (
    f"mssql+pyodbc://{AZURE_SQL_USERNAME}:{AZURE_SQL_PASSWORD}"
    f"@{AZURE_SQL_SERVER}/{AZURE_SQL_DATABASE}"
    f"?driver=ODBC+Driver+18+for+SQL+Server"
    f"&TrustServerCertificate=yes"
)

engine = create_engine(CONNECTION_STRING, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    username = Column(String(100), nullable=True)
    github_username = Column(String(100), nullable=True)
    password_hash = Column(String(255), nullable=False)
    email_verified = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    repos = relationship("UserRepo", back_populates="owner")


class UserRepo(Base):
    """
    Table de liaison entre un utilisateur et ses repos GitHub
    Un utilisateur peut avoir plusieurs repos, verifies via OAuth GitHub
    """
    __tablename__ = "user_repos"

    id = Column(Integer, primary_key=True, index=True)
    repo_full_name = Column(String(255), nullable=False, index=True)
    owner_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    added_at = Column(DateTime, default=datetime.utcnow)

    owner = relationship("User", back_populates="repos")


def init_db():
    """
    Cree les tables dans la base de donnees si elles n'existent pas
    """
    Base.metadata.create_all(bind=engine)
    print("Tables creees avec succes")


def get_db():
    """
    Fournit une session de base de donnees pour chaque requete
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()