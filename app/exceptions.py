from fastapi import HTTPException, status


# Пользователь уже существует
UserAlreadyExistsException = HTTPException(
    status_code=status.HTTP_409_CONFLICT,
    detail='Пользователь с такими данными уже зарегистрирован в системе'
)

# Неверная почта или пароль
IncorrectEmailOrPasswordException = HTTPException(
    status_code=status.HTTP_400_BAD_REQUEST,
    detail='Неверная почта или пароль'
)

# Некорректная почта
EmailIncorrectException = HTTPException(
    status_code=status.HTTP_400_BAD_REQUEST,
    detail='Почта указана некорректно'
)

# Токен истек
TokenExpiredException = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail='Токен истек'
)

# Невалидный формат токена
InvalidTokenFormatException = HTTPException(
    status_code=status.HTTP_400_BAD_REQUEST,
    detail='Невалидный формат токена'
)

# Токен отсутствует в заголовке
TokenNoFound = HTTPException(
    status_code=status.HTTP_400_BAD_REQUEST,
    detail='Токен отсутствует в заголовке'
)

# Невалидный JWT токен
NoJwtException = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail='Токен невалидный'
)

# Не найден ID пользователя
UserNotFoundByIDException = HTTPException(
    status_code=status.HTTP_404_NOT_FOUND,
    detail='Не найден пользователь с таким ID'
)

# Недостаточно прав
ForbiddenException = HTTPException(
    status_code=status.HTTP_403_FORBIDDEN,
    detail='Недостаточно прав. Только админы имеют право на такое действие.'
)

# Банк не найден
BankNotFoundException = HTTPException(
    status_code=status.HTTP_404_NOT_FOUND,
    detail="Банк не найден."
)

# Банк не активен
BankIsInactiveException = HTTPException(
    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
    detail="Пока что не можем предоставить валюту данного банка, выберите другой"
)