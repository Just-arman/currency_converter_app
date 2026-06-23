from app.users.models import Roles, Users
from app.dao.base import BaseDAO


class UsersDAO(BaseDAO):
    model = Users


class RolesDAO(BaseDAO):
    model = Roles
