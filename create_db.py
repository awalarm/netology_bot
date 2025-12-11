import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.sql import text

load_dotenv()


# Создание базы данных если она не существует
def create_database():
    db_url = os.getenv("DATABASE_URL")
    db_name = "english_bot_db"

    # Подключаемся к postgres для создания БД
    engine = create_engine(db_url)
    conn = engine.connect()
    conn.execute(text("COMMIT"))

    # Проверяем, существует ли БД
    result = conn.execute(
        text(f"SELECT 1 FROM pg_database WHERE datname = '{db_name}'")
    )

    if not result.fetchone():
        print(f"Создаем базу данных '{db_name}'...")
        conn.execute(text(f"CREATE DATABASE {db_name}"))
        print(f"База данных '{db_name}' создана успешно!")
    else:
        print(f"База данных '{db_name}' уже существует.")

    conn.close()


if __name__ == "__main__":
    create_database()
