from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.sql.expression import update
from typing import List
from pydantic import BaseModel
import logging
from app.dao.base import BaseDAO


logger = logging.getLogger(__name__)

class CurrencyRateDAO(BaseDAO):
    model = None