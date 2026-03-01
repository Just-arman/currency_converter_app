import re
from typing import Self
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator, computed_field
from app.auth.utils import get_password_hash


class EmailModel(BaseModel):
    email: EmailStr = Field(description="Электронная почта")

    model_config = ConfigDict(from_attributes=True)


class UserBase(EmailModel):
    phone_number: str = Field(description="Номер телефона в международном формате, начинающийся с '+'")
    first_name: str = Field(min_length=3, max_length=50, description="Имя, от 3 до 50 символов")
    last_name: str = Field(min_length=3, max_length=50, description="Фамилия, от 3 до 50 символов")

    # @field_validator("phone_number")
    # def validate_phone_number(cls, value: str) -> str:
    #     if not re.match(r'^\+\d{5,15}$', value):
    #         raise ValueError('Номер телефона должен начинаться с "+" и содержать от 5 до 15 цифр')
    #     return value


class SUserRegister(UserBase):
    password: str = Field(min_length=5, max_length=50, description="Пароль, от 5 до 50 знаков")
    confirm_password: str = Field(min_length=5, max_length=50, description="Повторите пароль")

    @model_validator(mode="after")
    def check_password(self) -> Self:
        if self.password != self.confirm_password:
            raise ValueError("Пароли не совпадают")
        self.password = get_password_hash(self.password)  # хешируем пароль до сохранения в базе данных
        return self


class SUserAddDB(UserBase):
    email: EmailStr = Field(description="Электронная почта")
    password: str = Field(min_length=5, description="Пароль в формате HASH-строки")
    
    model_config = ConfigDict(from_attributes=True)


class SUserAuth(EmailModel):
    password: str = Field(min_length=5, max_length=50, description="Пароль, от 5 до 50 знаков")


class UserDeleteId(BaseModel):
    id: int = Field(gt=0)


class RoleModel(BaseModel):
    id: int = Field(description="Идентификатор роли")
    name: str = Field(description="Название роли")

    model_config = ConfigDict(from_attributes=True)


class RoleModelUpdate(BaseModel):
    id: int | None = Field(None, description="Идентификатор роли")
    name: str | None = Field(None, description="Название роли")

    model_config = ConfigDict(from_attributes=True)

    # валидатор для приравнивания значения 0 к отсутствующему значению
    @field_validator("id", mode="before")
    @classmethod
    def normalize_zero_to_none(cls, v):
        if v in (0, "0", ""):
            return None
        return v

    # валидатор для допустимости значения None и любого регистра первой буквы названия роли
    @field_validator("name", mode="before")
    @classmethod
    def normalize_name(cls, v):
        if v is None:
            return None
        if isinstance(v, str) and not v.strip():
            return None
        return v.capitalize()


class RoleUpdateByID(BaseModel):
    role_id: int


class RoleUpdateByName(BaseModel):
    name: str


class UserID(BaseModel):
    id: int


class SUserInfo(UserBase):
    id: int = Field(description="Идентификатор пользователя")
    role: RoleModel = Field(exclude=True)

    @computed_field
    def role_name(self) -> str:
        return self.role.name

    @computed_field
    def role_id(self) -> int:
        return self.role.id
