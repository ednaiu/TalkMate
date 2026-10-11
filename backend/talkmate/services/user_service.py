from ..errors import ApiError
from ..repositories import UserRepository
from .auth_service import validate_email, validate_name


class UserService:
    """Редактирование пользователя администратором: только имя и email, как в диаграмме вариантов использования."""

    def __init__(self, db):
        self.db = db
        self.users = UserRepository(db)

    def list(self):
        return self.users.all()

    def edit(self, user_id, data):
        user = self.users.get(user_id)
        if user is None:
            raise ApiError(404, "not_found", "Пользователь не найден")
        if "name" in data:
            user.name = validate_name(data["name"])
        if "email" in data:
            email = validate_email(data["email"])
            if self.users.by_email(email, exclude_id=user.id) is not None:
                raise ApiError(409, "email_taken", "Этот email уже занят другим пользователем")
            user.email = email
        self.db.commit()
        return user
