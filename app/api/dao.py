import logging
from app.api.models import CurrencyRate
from app.dao.base import BaseDAO


logger = logging.getLogger(__name__)


class CurrencyRateDAO(BaseDAO):
    model = CurrencyRate