from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
import datetime
from database import Base

class Team(Base):
    __tablename__ = "teams"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    code = Column(String, unique=True, index=True) # e.g., ARG, FRA
    logo_url = Column(String, nullable=True)

class Match(Base):
    __tablename__ = "matches"

    id = Column(Integer, primary_key=True, index=True)
    home_team_id = Column(Integer, ForeignKey("teams.id"))
    away_team_id = Column(Integer, ForeignKey("teams.id"))
    match_date = Column(DateTime)
    status = Column(String) # SCHEDULED, LIVE, FINISHED

    home_team = relationship("Team", foreign_keys=[home_team_id])
    away_team = relationship("Team", foreign_keys=[away_team_id])
    odds = relationship("Odd", back_populates="match")

class Odd(Base):
    __tablename__ = "odds"

    id = Column(Integer, primary_key=True, index=True)
    match_id = Column(Integer, ForeignKey("matches.id"))
    bookmaker = Column(String, index=True) # e.g., 1xBet
    market = Column(String) # e.g., 1X2, Over/Under 2.5
    selection = Column(String) # e.g., Home, Draw, Away, Over
    price = Column(Float)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)

    match = relationship("Match", back_populates="odds")

class PaperBet(Base):
    __tablename__ = "paper_bets"

    id = Column(Integer, primary_key=True, index=True)
    odd_id = Column(Integer, ForeignKey("odds.id"))
    amount = Column(Float) # The simulated stake
    status = Column(String) # PENDING, WON, LOST
    result_profit = Column(Float, nullable=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
