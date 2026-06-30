import re
from typing import Self

from pydantic import (
    BaseModel, 
    ConfigDict, 
    EmailStr, 
    Field, 
    computed_field,
    field_validator, 
    model_validator
)


class SUserEmail(BaseModel):
    email: EmailStr = Field(description="Электронная почта")

    model_config = ConfigDict(from_attributes=True)


class SUserBase(SUserEmail):
    phone_number: str = Field(description="Номер телефона в международном формате, начинающийся с '+'")
    first_name: str = Field(min_length=3, max_length=50, description="Имя, от 3 до 50 символов")
    last_name: str = Field(min_length=3, max_length=50, description="Фамилия, от 3 до 50 символов")

    # валидатор для проверки номера телефона на соответствие установленным требованиям
    # @field_validator("phone_number")
    def validate_phone_number(cls, value: str) -> str:
        if not re.match(r'^\+\d{5,15}$', value):
            raise ValueError('Номер телефона должен начинаться с "+" и содержать от 5 до 15 цифр')
        return value


class SUserRegister(SUserBase):
    password: str = Field(min_length=5, max_length=50, description="Пароль, от 5 до 50 знаков")
    confirm_password: str = Field(min_length=5, max_length=50, description="Повторите пароль")

    # валидатор для проверки первоначального и повторного паролей
    @model_validator(mode="after")
    def check_password(self) -> Self:
        if self.password != self.confirm_password:
            raise ValueError("Пароли не совпадают")
        return self


class SUserAddDB(SUserBase):
    email: EmailStr = Field(description="Электронная почта")
    password: str = Field(min_length=5, description="Пароль в формате HASH-строки")
    
    model_config = ConfigDict(from_attributes=True)


class SUserAuth(SUserEmail):
    password: str = Field(min_length=5, max_length=50, description="Пароль, от 5 до 50 знаков")


class SAuthResponse(BaseModel):
    ok: bool
    message: str
    

class SRole(BaseModel):
    id: int = Field(description="Идентификатор роли")
    name: str = Field(description="Название роли")

    model_config = ConfigDict(from_attributes=True)


class SUserRoleUpdate(BaseModel):
    name: str = Field(description="Название роли")

    model_config = ConfigDict(from_attributes=True)

    # валидатор для допустимости любого регистра первой буквы названия роли
    # и проверка на пустое значение
    @field_validator("name", mode="before")
    @classmethod
    def normalize_name(cls, v):
        if not isinstance(v, str) or not v.strip() or v == "string":
            raise ValueError("Название роли не может быть пустым")
        return v.capitalize()
    

class SRoleUpdateByID(BaseModel):
    role_id: int


class SUserRoleRead(SUserBase):
    id: int = Field(description="Идентификатор пользователя")
    role: SRole = Field(exclude=True)

    @computed_field
    def role_name(self) -> str:
        return self.role.name

    @computed_field
    def role_id(self) -> int:
        return self.role.id
