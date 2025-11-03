"""
Core routines
"""
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from ..db.database import get_db
from ..db.models.db_course import Course, CourseStatus  # Your SQLAlchemy model
from ..services.settings_service import refresh_dynamic_settings_cache


