# database.py
from sqlalchemy import create_engine, Column, Integer, Float, String, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime

DATABASE_URL = "postgresql://triage_user:triage2024@localhost/triage_db"
engine = create_engine(DATABASE_URL)
Base = declarative_base()

class Patient(Base):
    __tablename__ = 'patients'
    id                = Column(Integer, primary_key=True, autoincrement=True)
    nom               = Column(String(100), nullable=False)
    prenom            = Column(String(100))
    numero_cin        = Column(String(20))
    temperature       = Column(Float)
    spo2              = Column(Float)
    frequence_card    = Column(Float)
    tension_syst      = Column(Float)
    tension_diast     = Column(Float)
    douleur           = Column(Integer)
    niveau_triage     = Column(Integer, nullable=False)
    motif_triage      = Column(String(200))
    statut            = Column(String(20), default='EN_ATTENTE')
    heure_arrivee     = Column(DateTime, default=datetime.now)

Base.metadata.create_all(engine)
SessionLocal = sessionmaker(bind=engine)