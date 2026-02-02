from sqlalchemy import (
    Column, Integer, String, Text, Boolean, ForeignKey, DateTime, func
)
from sqlalchemy.orm import relationship
from .db import Base

class Quiz(Base):
    __tablename__ = "quizzes"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    questions = relationship("Question", back_populates="quiz", cascade="all, delete-orphan")

class Question(Base):
    __tablename__ = "questions"
    id = Column(Integer, primary_key=True, index=True)
    quiz_id = Column(Integer, ForeignKey("quizzes.id"), nullable=False, index=True)

    # scale | single_choice | multi_choice | open
    type = Column(String(30), nullable=False)

    title = Column(String(500), nullable=False)      # 题干
    help_text = Column(Text, nullable=True)          # 提示/说明
    order = Column(Integer, nullable=False, default=0)
    required = Column(Boolean, default=True)

    # 量表题专用（例如 1~5）
    scale_min = Column(Integer, nullable=True)
    scale_max = Column(Integer, nullable=True)
    scale_step = Column(Integer, nullable=True)

    quiz = relationship("Quiz", back_populates="questions")
    options = relationship("Option", back_populates="question", cascade="all, delete-orphan")

class Option(Base):
    __tablename__ = "options"
    id = Column(Integer, primary_key=True, index=True)
    question_id = Column(Integer, ForeignKey("questions.id"), nullable=False, index=True)

    key = Column(String(50), nullable=True)          # A/B/C 或 1/2/3（可空）
    text = Column(String(500), nullable=False)       # 选项内容
    value = Column(String(100), nullable=True)       # 可选：存分值/标签
    order = Column(Integer, nullable=False, default=0)

    question = relationship("Question", back_populates="options")
