from sqlalchemy import create_engine, String, ForeignKey
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from sqlalchemy.sql.sqltypes import Boolean, DateTime
from sqlalchemy.testing.schema import mapped_column
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB
from flask_login import UserMixin
import bcrypt
from datetime import datetime

PGUSER = 'USER'
PGPASSWORD = 'PASSWORD'

engine = create_engine(f"postgresql+psycopg2://{PGUSER}:{PGPASSWORD}@localhost:5432/online_restaurant", echo=True)
Session = sessionmaker(bind=engine)

class Base(DeclarativeBase):
    pass

class Users(Base, UserMixin):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    nickname: Mapped[str] = mapped_column(String(100), unique=True)
    password: Mapped[str] = mapped_column(String(200))
    email: Mapped[str] = mapped_column(String(50), unique=True)

    reservations = relationship("Reservations", foreign_keys="Reservations.user_id", back_populates="user")
    orders = relationship("Orders", foreign_keys="Orders.user_id", back_populates="user")

    def set_password(self, password: str):
        self.password = bcrypt.hashpw(password.encode("utf8"), bcrypt.gensalt()).decode('utf8')

    def check_password(self, password: str) -> bool:
        return bcrypt.checkpw(password.encode("utf8"), self.password.encode("utf8"))

class Menu(Base):
    __tablename__ = "menu"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String)
    weight: Mapped[int] = mapped_column(String)
    ingredients: Mapped[str] = mapped_column(String)
    description: Mapped[str] = mapped_column(String)
    price: Mapped[int] = mapped_column(String)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    file_name: Mapped[str] = mapped_column(String)

class Reservations(Base):
    __tablename__ = "reservations"
    id: Mapped[int] = mapped_column(primary_key=True)
    time_start: Mapped[datetime] = mapped_column(DateTime)
    type_table: Mapped[str] = mapped_column(String(20))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))

    user = relationship("Users", back_populates="reservations")

class Orders(Base):
    __tablename__ = "orders"
    id: Mapped[int] = mapped_column(primary_key=True)
    order_list: Mapped[str] = mapped_column(JSONB)
    order_time: Mapped[datetime] = mapped_column(DateTime)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))

    user = relationship("Users", back_populates="orders")

if __name__ == "__main__":
    Base.metadata.create_all(engine)