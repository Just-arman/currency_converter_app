from sqlalchemy import ForeignKey, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.dao.database import Base, str_uniq
from app.logger import log


class Users(Base):
    __tablename__ = "users"

    first_name: Mapped[str]
    last_name: Mapped[str]
    phone_number: Mapped[str_uniq]
    email: Mapped[str_uniq]
    password: Mapped[str]
    role_id: Mapped[int] = mapped_column(ForeignKey('roles.id'), default=1, server_default=text("1"))
    
    role: Mapped["Roles"] = relationship(back_populates="users", lazy="selectin")

    def __repr__(self):
        return f"ORM data: {self.__class__.__name__}(id={self.id}, name={self.first_name}, role={self.role})"
    

class Roles(Base):
    __tablename__ = "roles"

    name: Mapped[str_uniq]

    users: Mapped[list["Users"]] = relationship(back_populates="role")

    def __repr__(self):
        log.info(f"это __repr__")
        return f"{self.name}"
    
    # def __repr__(self):
    #     return f"Roles(name={self.name!r})"

    @property
    def users_list(self):
        users = [f"{user.first_name} {user.last_name}" for user in self.users]
        if len(users) > 5:
            return ", ".join(users[:5]) + f" и ещё {len(users) - 5} польз."
        return ", ".join(users)
