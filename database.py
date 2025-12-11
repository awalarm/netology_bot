from datetime import datetime
from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    ForeignKey,
    Boolean,
    false,
    true,
)
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, nullable=False)
    username = Column(String(100))
    first_name = Column(String(100))
    last_name = Column(String(100))
    created_at = Column(String, default=lambda: datetime.now().isoformat())

    # Связи
    user_words = relationship(
        "UserWord", back_populates="user", cascade="all, delete-orphan"
    )

    @hybrid_property
    def total_words(self):
        return len([uw for uw in self.user_words if not uw.deleted])


class Word(Base):
    __tablename__ = "words"

    id = Column(Integer, primary_key=True)
    english = Column(String(100), nullable=False)
    russian = Column(String(100), nullable=False)
    is_default = Column(
        Boolean, default=False
    )  # слова по умолчанию для всех пользователей

    # Связи
    user_words = relationship("UserWord", back_populates="word")


# Связь пользователь-слово (многие-ко-многим с дополнительными полями)
class UserWord(Base):
    __tablename__ = "user_words"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    word_id = Column(Integer, ForeignKey("words.id"), nullable=False)
    deleted = Column(Boolean, default=False)
    added_at = Column(String, default=lambda: datetime.now().isoformat())

    # Связи
    user = relationship("User", back_populates="user_words")
    word = relationship("Word", back_populates="user_words")


# Класс для работы с базой данных
class Database:
    def __init__(self, db_url):
        self.engine = create_engine(db_url)
        self.Session = sessionmaker(bind=self.engine)

    def create_tables(self):
        """Создание всех таблиц в БД"""
        Base.metadata.create_all(self.engine)
        print("Таблицы успешно созданы!")

    def init_default_words(self):
        """Инициализация базовых слов по умолчанию"""
        session = self.Session()

        default_words = [
            {"english": "red", "russian": "красный"},
            {"english": "blue", "russian": "синий"},
            {"english": "green", "russian": "зеленый"},
            {"english": "yellow", "russian": "желтый"},
            {"english": "black", "russian": "черный"},
            {"english": "I", "russian": "я"},
            {"english": "you", "russian": "ты"},
            {"english": "he", "russian": "он"},
            {"english": "she", "russian": "она"},
            {"english": "it", "russian": "оно"},
            {"english": "hello", "russian": "привет"},
            {"english": "goodbye", "russian": "до свидания"},
            {"english": "thank you", "russian": "спасибо"},
            {"english": "please", "russian": "пожалуйста"},
            {"english": "sorry", "russian": "извините"},
        ]

        try:
            # Проверяем, есть ли уже слова по умолчанию
            existing_count = session.query(Word).filter_by(is_default=True).count()
            if existing_count == 0:
                for word_data in default_words:
                    word = Word(
                        english=word_data["english"],
                        russian=word_data["russian"],
                        is_default=True,
                    )
                    session.add(word)
                session.commit()
                print(f"Добавлено {len(default_words)} слов по умолчанию")
            else:
                print(f"Слова по умолчанию уже существуют ({existing_count} слов)")

        except Exception as e:
            session.rollback()
            print(f"Ошибка при добавлении слов по умолчанию: {e}")
        finally:
            session.close()

    def get_or_create_user(
        self, telegram_id, username=None, first_name=None, last_name=None
    ):
        """Получение или создание пользователя"""
        session = self.Session()
        try:
            user = session.query(User).filter_by(telegram_id=telegram_id).first()
            if not user:
                user = User(
                    telegram_id=telegram_id,
                    username=username,
                    first_name=first_name,
                    last_name=last_name,
                )
                session.add(user)
                session.commit()
                session.refresh(user)

                # Добавляем слова по умолчанию новому пользователю
                self._add_default_words_to_user(user.id)

            return user
        finally:
            session.close()

    def _add_default_words_to_user(self, user_id):
        """Добавление слов по умолчанию пользователю"""
        session = self.Session()
        try:
            # Получаем все слова по умолчанию
            default_words = session.query(Word).filter_by(is_default=True).all()

            # Добавляем их пользователю
            for word in default_words:
                user_word = UserWord(user_id=user_id, word_id=word.id, deleted=False)
                session.add(user_word)

            session.commit()
        finally:
            session.close()

    def get_user_words(self, user_id, include_deleted=False, include_default=False):
        """Получение слов пользователя"""
        session = self.Session()
        try:
            query = (
                session.query(Word).join(UserWord).filter(UserWord.user_id == user_id)
            )

            if not include_deleted:
                query = query.filter(UserWord.deleted == false())

            # По умолчанию возвращаем только НЕ дефолтные слова
            if not include_default:
                query = query.filter(Word.is_default == false())

            return query.all()
        finally:
            session.close()

    def get_user_default_words(self, user_id, include_deleted=False):
        """Получение только дефолтных слов пользователя"""
        session = self.Session()
        try:
            query = (
                session.query(Word)
                .join(UserWord)
                .filter(UserWord.user_id == user_id, Word.is_default == true())
            )

            if not include_deleted:
                query = query.filter(UserWord.deleted == false())

            return query.all()
        finally:
            session.close()

    def get_all_user_words(self, user_id, include_deleted=False):
        """Получение всех слов пользователя (включая дефолтные)"""
        session = self.Session()
        try:
            query = (
                session.query(Word).join(UserWord).filter(UserWord.user_id == user_id)
            )

            if not include_deleted:
                query = query.filter(UserWord.deleted == false())

            return query.all()
        finally:
            session.close()

    def get_random_words_for_test(self, user_id, count=4):
        """Получение случайных слов для теста"""
        session = self.Session()
        try:
            # Получаем активные слова пользователя
            user_words = (
                session.query(Word)
                .join(UserWord)
                .filter(UserWord.user_id == user_id, UserWord.deleted == false())
                .all()
            )

            if len(user_words) < count:
                # Если у пользователя недостаточно слов, добавляем слова по умолчанию
                return self._get_default_words_for_test(session, count)

            # Выбираем случайное слово как правильный ответ
            import random

            target_word = random.choice(user_words)

            # Выбираем другие слова как неправильные варианты
            other_words = [w for w in user_words if w.id != target_word.id]
            if len(other_words) >= count - 1:
                other_words = random.sample(other_words, count - 1)
            else:
                # Если не хватает слов, дополняем словами по умолчанию
                default_words = (
                    session.query(Word)
                    .filter(
                        Word.is_default == true(),
                        Word.id.notin_([w.id for w in user_words]),
                    )
                    .all()
                )
                other_words.extend(
                    random.sample(default_words, count - 1 - len(other_words))
                )

            # Собираем все варианты ответов
            all_words = [target_word] + other_words
            random.shuffle(all_words)

            return target_word, all_words

        finally:
            session.close()

    def _get_default_words_for_test(self, session, count=4):
        """Получение слов по умолчанию для теста"""
        default_words = session.query(Word).filter_by(is_default=True).all()
        import random

        if len(default_words) < count:
            # Если вообще нет слов, возвращаем тестовые
            test_words = [
                Word(english="hello", russian="привет"),
                Word(english="goodbye", russian="до свидания"),
                Word(english="thank you", russian="спасибо"),
                Word(english="please", russian="пожалуйста"),
            ]
            target_word = test_words[0]
            return target_word, test_words

        target_word = random.choice(default_words)
        other_words = [w for w in default_words if w.id != target_word.id]
        other_words = random.sample(other_words, count - 1)

        all_words = [target_word] + other_words
        random.shuffle(all_words)

        return target_word, all_words

    def add_word_to_user(self, user_id, english, russian):
        """Добавление нового слова пользователю"""
        session = self.Session()
        try:
            english_lower = english.lower().strip()
            russian_lower = russian.lower().strip()

            # Проверяем, существует ли уже такое слово
            word = (
                session.query(Word)
                .filter_by(english=english_lower, russian=russian_lower)
                .first()
            )

            if not word:
                # Создаем новое слово
                word = Word(
                    english=english_lower, russian=russian_lower, is_default=False
                )
                session.add(word)
                session.flush()  # Получаем ID без коммита

            # Проверяем, не добавлено ли уже это слово пользователю
            existing_user_word = (
                session.query(UserWord)
                .filter_by(user_id=user_id, word_id=word.id)
                .first()
            )

            if existing_user_word:
                if existing_user_word.deleted:
                    # Если слово было удалено, восстанавливаем его
                    existing_user_word.deleted = False
                    session.commit()
                    return (
                        word.english,
                        word.russian,
                        False,
                    )  # False - слово восстановлено
                else:
                    return (
                        word.english,
                        word.russian,
                        None,
                    )  # None - слово уже существует

            # Добавляем слово пользователю
            user_word = UserWord(user_id=user_id, word_id=word.id, deleted=False)
            session.add(user_word)
            session.commit()

            # Перезагружаем слово из БД чтобы получить актуальные данные
            word_refreshed = session.query(Word).filter_by(id=word.id).first()
            return (
                word_refreshed.english,
                word_refreshed.russian,
                True,
            )  # True - слово добавлено

        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    def delete_word_from_user(self, user_id, word_id):
        """Удаление слова у пользователя (только НЕ дефолтные слова)"""
        session = self.Session()
        try:
            # Получаем слово
            word = session.query(Word).filter_by(id=word_id).first()

            # Проверяем, является ли слово дефолтным
            if word and word.is_default:
                return False, "Нельзя удалять слова по умолчанию"

            # Находим связь пользователя с этим словом
            user_word = (
                session.query(UserWord)
                .filter_by(user_id=user_id, word_id=word_id)
                .first()
            )

            if user_word:
                # Удаляем связь (мягкое удаление)
                user_word.deleted = True
                session.commit()
                return True, "Слово удалено"
            else:
                return False, "Слово не найдено у пользователя"

        except Exception as e:
            session.rollback()
            return False, f"Ошибка: {str(e)}"
        finally:
            session.close()

    def get_word_by_id(self, word_id):
        """Получение слова по ID"""
        session = self.Session()
        try:
            return session.query(Word).filter_by(id=word_id).first()
        finally:
            session.close()

    def get_user_word_count(self, user_id):
        """Получение только пользовательских слов (не дефолтных)"""
        session = self.Session()
        try:
            words = (
                session.query(Word)
                .join(UserWord)
                .filter(
                    UserWord.user_id == user_id,
                    Word.is_default == false(),
                    UserWord.deleted == false(),
                )
                .all()
            )
            return words
        finally:
            session.close()
