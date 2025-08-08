from sqlalchemy import Column, String, Text, Integer, Float, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class Recording(Base):
    __tablename__ = 'recordings'
    id = Column(String, primary_key=True)
    file_path = Column(Text, nullable=False)
    datetime = Column(Text, nullable=False)
    duration_sec = Column(Float, nullable=False)
    source = Column(Text, nullable=False)

    local_speakers = relationship('LocalSpeaker', back_populates='recording')
    snippets = relationship('Snippet', back_populates='recording')

class LocalSpeaker(Base):
    __tablename__ = 'local_speakers'
    id = Column(String, primary_key=True)
    recording_id = Column(String, ForeignKey('recordings.id'), nullable=False)
    provider = Column(Text, nullable=False)
    stream_key = Column(Text, nullable=False)
    path = Column(Text, nullable=False)
    sample_rate = Column(Integer, nullable=False)
    offset_sec = Column(Float, nullable=False, default=0.0)
    global_speaker_id = Column(String, nullable=True)

    recording = relationship('Recording', back_populates='local_speakers')
    snippets = relationship('Snippet', back_populates='local_speaker')

class Snippet(Base):
    __tablename__ = 'snippets'
    id = Column(String, primary_key=True)
    recording_id = Column(String, ForeignKey('recordings.id'), nullable=False)
    local_speaker_id = Column(String, ForeignKey('local_speakers.id'), nullable=False)
    start_local_sec = Column(Float, nullable=False)
    end_local_sec = Column(Float, nullable=False)
    start_sec = Column(Float, nullable=False)
    end_sec = Column(Float, nullable=False)
    vad_score = Column(Float, nullable=True)
    source = Column(Text, nullable=False)
    text = Column(Text, nullable=True)
    asr_confidence = Column(Float, nullable=True)

    recording = relationship('Recording', back_populates='snippets')
    local_speaker = relationship('LocalSpeaker', back_populates='snippets')

    __table_args__ = (
        UniqueConstraint('local_speaker_id', 'start_local_sec', 'end_local_sec', name='uix_local_speaker_segment'),
        Index('ix_snippets_recording_start_sec', 'recording_id', 'start_sec'),
    )

def create_all(engine):
    """Create database tables."""
    Base.metadata.create_all(engine)
