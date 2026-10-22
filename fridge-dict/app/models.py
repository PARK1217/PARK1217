"""테이블 정의. JSON 컬럼은 SQLite에 문자열로 저장된다."""
from sqlalchemy import JSON, Boolean, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Recipe(Base):
    __tablename__ = "recipes"
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    seq: Mapped[int] = mapped_column(Integer, index=True)  # legacy 순서 유지용
    name: Mapped[str] = mapped_column(String(200))
    category: Mapped[str] = mapped_column(String(40))
    tags: Mapped[list] = mapped_column(JSON)
    comp: Mapped[list] = mapped_column(JSON)
    tools: Mapped[list] = mapped_column(JSON)
    time: Mapped[str] = mapped_column(String(40), default="")
    easy: Mapped[bool] = mapped_column(Boolean, default=False)
    base: Mapped[str] = mapped_column(String(80), default="")
    anchor: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    spicy: Mapped[str] = mapped_column(String(10), default="")  # "" | 안 매움 | 조절 가능 | 매움
    added: Mapped[str] = mapped_column(String(10))
    gist: Mapped[str] = mapped_column(Text)
    html: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[str] = mapped_column(String(32))
    source: Mapped[str] = mapped_column(String(16), default="seed")


class Swap(Base):
    __tablename__ = "swaps"
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    seq: Mapped[int] = mapped_column(Integer, index=True)
    name: Mapped[str] = mapped_column(String(200))
    category: Mapped[str] = mapped_column(String(40))
    tags: Mapped[list] = mapped_column(JSON)
    tools: Mapped[list] = mapped_column(JSON)
    time: Mapped[str] = mapped_column(String(40), default="")
    added: Mapped[str] = mapped_column(String(10))
    gist: Mapped[str] = mapped_column(Text)
    html: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[str] = mapped_column(String(32))
    source: Mapped[str] = mapped_column(String(16), default="seed")


class Favorite(Base):
    """즐겨찾기는 사람별. item_id는 레시피나 대체·보관 id (둘의 id는 겹치지 않는다)."""
    __tablename__ = "favorites"
    user_email: Mapped[str] = mapped_column(String(200), primary_key=True)
    item_id: Mapped[str] = mapped_column(String(80), primary_key=True)


class Setting(Base):
    """가구 공용 설정 (scale 등)."""
    __tablename__ = "settings"
    key: Mapped[str] = mapped_column(String(40), primary_key=True)
    value: Mapped[str] = mapped_column(String(200))


class MealLog(Base):
    __tablename__ = "meal_log"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[str] = mapped_column(String(10), index=True)  # YYYY-MM-DD
    name: Mapped[str] = mapped_column(String(200))
    comp: Mapped[list] = mapped_column(JSON)
    recipe_id: Mapped[str | None] = mapped_column(String(80), nullable=True)  # 사전에서 고른 경우
    created_at: Mapped[str] = mapped_column(String(32))


class Idea(Base):
    """해볼 것. 규칙상 레시피에 못 넣는 아이디어를 두는 곳. 해본 뒤 레시피로 옮긴다."""
    __tablename__ = "ideas"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    kind: Mapped[str] = mapped_column(String(8), default="recipe")  # recipe | swap
    name: Mapped[str] = mapped_column(String(200))
    note: Mapped[str] = mapped_column(Text, default="")
    source: Mapped[str] = mapped_column(String(16), default="web")
    created_at: Mapped[str] = mapped_column(String(32))
    done_at: Mapped[str | None] = mapped_column(String(32), nullable=True)


class Note(Base):
    """레시피·대체 항목에 붙는 메모 (해보고 느낀 점). 가구 공용."""
    __tablename__ = "notes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    kind: Mapped[str] = mapped_column(String(8))
    item_id: Mapped[str] = mapped_column(String(80), index=True)
    text: Mapped[str] = mapped_column(Text)
    user_email: Mapped[str] = mapped_column(String(200), default="")
    created_at: Mapped[str] = mapped_column(String(32))


class Plan(Base):
    """주간 식단 계획. 날짜에 요리를 배정한다."""
    __tablename__ = "plan"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[str] = mapped_column(String(10), index=True)
    recipe_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    name: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[str] = mapped_column(String(32))


class History(Base):
    """추가·수정 이력. update면 data에 '수정 전' 버전, create면 생성된 버전."""
    __tablename__ = "history"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    kind: Mapped[str] = mapped_column(String(8), index=True)  # recipe | swap
    item_id: Mapped[str] = mapped_column(String(80), index=True)
    action: Mapped[str] = mapped_column(String(8))  # create | update
    data: Mapped[dict] = mapped_column(JSON)
    source: Mapped[str] = mapped_column(String(16))  # web | mcp | seed
    user_email: Mapped[str] = mapped_column(String(200), default="")
    changed_at: Mapped[str] = mapped_column(String(32))
