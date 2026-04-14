import typing

import flask
import sqlalchemy
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import DATETIME, func, inspect, text
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Database model base class."""


db = SQLAlchemy(model_class=Base)


def get_tables() -> list[str]:
    """Get list of table names."""
    return inspect(db.engine).get_table_names()


def init_app(app: flask.Flask, echo: bool = False) -> None:
    """Initialise application."""
    app.config.setdefault("SQLALCHEMY_DATABASE_URI", app.config["DB_URL"])
    app.config.setdefault(
        "SQLALCHEMY_ENGINE_OPTIONS", {"pool_recycle": 3600, "echo": echo}
    )
    db.init_app(app)

    from .procrastinate_app import procrastinate_app

    with app.app_context():
        procrastinate_app.open(db.engine)


def get_old_place_list():
    sql = r"""
select place.place_id, place.osm_type, place.osm_id, place.added, size, display_name, state, count(changeset.id), max(place_matcher.start) as start
from place
    left outer join
changeset ON changeset.osm_id = place.osm_id and changeset.osm_type = place.osm_type
    left outer join
place_matcher ON place_matcher.osm_id = place.osm_id and place_matcher.osm_type = place.osm_type,
       (SELECT cast(substring(relname from '\d+') as integer) as place_id, pg_relation_size(C.oid) AS "size"
        FROM pg_class C
        WHERE relname like 'osm%polygon') a
where a.place_id = place.place_id and start < CURRENT_DATE - INTERVAL '2 months'
group by place.place_id, place.added, display_name, state, size order by start desc"""

    with db.engine.connect() as conn:
        return conn.execute(text(sql)).all()


def get_big_table_list():
    sql_big_polygon_tables = r"""
select place.place_id, place.osm_type, place.osm_id, place.added, size, display_name, state, count(changeset.id), max(place_matcher.start)
from place
    left outer join
changeset ON changeset.osm_id = place.osm_id and changeset.osm_type = place.osm_type
    left outer join
place_matcher ON place_matcher.osm_id = place.osm_id and place_matcher.osm_type = place.osm_type,
       (SELECT cast(substring(relname from '\d+') as integer) as place_id, pg_relation_size(C.oid) AS "size"
        FROM pg_class C
        WHERE relname like 'osm%polygon'
        ORDER BY pg_relation_size(C.oid) DESC
        LIMIT 200) a
where a.place_id = place.place_id
group by place.place_id, place.added, display_name, state, size order by size desc;"""

    with db.engine.connect() as conn:
        return conn.execute(text(sql_big_polygon_tables)).all()


DateTimeFunc = sqlalchemy.sql.functions.Function[DATETIME]


def now_utc() -> DateTimeFunc:
    """Database function to return the current time in the UTC timezone."""
    return typing.cast(DateTimeFunc, func.timezone("utc", func.now(), type_=DATETIME))
