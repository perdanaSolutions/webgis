import uuid
from database import Base
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func

class SysUploadLog(Base):
    __tablename__ = "sys_upload_log"

    upload_batch_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_type = Column(String(20), nullable=False)
    target_table = Column(String(50), nullable=False)
    source_name = Column(String(255))
    uploaded_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    record_count = Column(Integer, default=0)
    status = Column(String(20), default="IN_PROGRESS")
    error_message = Column(Text)
    meta_data = Column(JSONB)
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    finished_at = Column(DateTime(timezone=True))