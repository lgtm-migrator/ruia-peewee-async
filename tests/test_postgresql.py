# -*- coding: utf-8 -*-
import asyncio
from random import randint

import pytest
from peewee import CharField

from ruia_peewee_async import TargetDB, after_start, create_model

from .common import Insert, Update


class PostgresqlInsert(Insert):
    async def parse(self, response):
        async for item in super().parse(response):
            yield item


class PostgresqlUpdate(Update):
    async def parse(self, response):
        async for item in super().parse(response):
            yield item


def basic_setup(postgresql):
    postgresql.update(
        {
            "model": {
                "table_name": "ruia_postgres",
                "title": CharField(),
                "url": CharField(),
            }
        }
    )
    return postgresql


class TestPostgreSQL:
    @pytest.mark.dependency()
    async def test_postgres_insert(self, postgresql, event_loop):
        postgresql = basic_setup(postgresql)
        spider_ins = await PostgresqlInsert.async_start(
            loop=event_loop,
            after_start=after_start(postgres=postgresql),
            target_db=TargetDB.POSTGRES,
        )
        count = await spider_ins.postgres_manager.count(
            spider_ins.postgres_model.select()
        )
        assert count >= 10, "Should insert 10 rows in PostgreSQL."

    @pytest.mark.dependency(depends=["TestPostgreSQL::test_postgres_insert"])
    async def test_postgres_filters_insert(self, postgresql, event_loop, caplog):
        postgresql = basic_setup(postgresql)
        spider_ins = await PostgresqlInsert.async_start(
            loop=event_loop,
            after_start=after_start(postgres=postgresql),
            target_db=TargetDB.POSTGRES,
            filters="url",
        )
        assert "was filtered by filters" in caplog.text
        spider_ins = await PostgresqlInsert.async_start(
            loop=event_loop,
            after_start=after_start(postgres=postgresql),
            target_db=TargetDB.POSTGRES,
            filters=["url", "title"],
        )
        assert "was filtered by filters" in caplog.text
        spider_ins = await PostgresqlInsert.async_start(
            loop=event_loop,
            after_start=after_start(postgres=postgresql),
            target_db=TargetDB.POSTGRES,
            filters="url",
            yield_origin=False,
        )
        assert "wasn't filtered by filters" in caplog.text
        one = await spider_ins.postgres_manager.get(
            spider_ins.postgres_model, url="http://testinginsert.com"
        )
        assert one.url == "http://testinginsert.com"

    @pytest.mark.dependency(depends=["TestPostgreSQL::test_postgres_filters_insert"])
    async def test_postgres_not_update_when_exists(self, postgresql, event_loop):
        postgresql = basic_setup(postgresql)
        spider_ins = await PostgresqlUpdate.async_start(
            loop=event_loop,
            after_start=after_start(postgres=postgresql),
            not_update_when_exists=True,
            target_db=TargetDB.POSTGRES,
        )
        one = await spider_ins.postgres_manager.get(
            spider_ins.postgres_model, id=randint(1, 10)
        )
        assert one.url != "http://testing.com"

    @pytest.mark.dependency(
        depends=["TestPostgreSQL::test_postgres_not_update_when_exists"]
    )
    async def test_postgres_filters(self, postgresql, event_loop, caplog):
        postgresql = basic_setup(postgresql)
        spider_ins = await PostgresqlUpdate.async_start(
            loop=event_loop,
            after_start=after_start(postgres=postgresql),
            filters="url",
            not_update_when_exists=True,
            target_db=TargetDB.POSTGRES,
        )
        assert "wasn't filtered by filters" in caplog.text
        rows = await spider_ins.postgres_manager.count(
            spider_ins.postgres_model.select()
        )
        assert rows == 20
        spider_ins = await PostgresqlUpdate.async_start(
            loop=event_loop,
            after_start=after_start(postgres=postgresql),
            filters=["url", "title"],
            not_update_when_exists=True,
            target_db=TargetDB.POSTGRES,
            yield_origin=True,
        )
        assert "was filtered by filters" in caplog.text
        rows = await spider_ins.postgres_manager.count(
            spider_ins.postgres_model.select()
        )
        assert rows == 20

    @pytest.mark.dependency(
        depends=["TestPostgreSQL::test_postgres_not_update_when_exists"]
    )
    async def test_postgres_update(self, postgresql, event_loop):
        postgresql = basic_setup(postgresql)
        spider_ins = await PostgresqlUpdate.async_start(
            loop=event_loop,
            after_start=after_start(postgres=postgresql),
            target_db=TargetDB.POSTGRES,
            not_update_when_exists=False,
        )
        for pid in range(1, 11):
            one = await spider_ins.postgres_manager.get(
                spider_ins.postgres_model, id=pid
            )
            assert one.url == "http://testing.com"
        spider_ins.postgres_model.truncate_table()

    @pytest.mark.dependency(depends=["TestPostgreSQL::test_postgres_update"])
    async def test_postgres_dont_create_when_not_exists(self, postgresql, event_loop):
        postgresql = basic_setup(postgresql)
        model, _ = create_model(create_table=True, postgres=postgresql)
        rows_before = model.select().count()
        assert rows_before == 0
        spider_ins = await PostgresqlUpdate.async_start(
            loop=event_loop,
            after_start=after_start(postgres=postgresql),
            create_when_not_exists=False,
            target_db=TargetDB.POSTGRES,
        )
        while not spider_ins.request_session.closed:
            await asyncio.sleep(1)
        rows_after = await spider_ins.postgres_manager.count(
            spider_ins.postgres_model.select()
        )
        assert rows_after == 0

    @pytest.mark.dependency(
        depends=["TestPostgreSQL::test_postgres_dont_create_when_not_exists"]
    )
    async def test_postgres_create_when_not_exists(self, postgresql, event_loop):
        postgresql = basic_setup(postgresql)
        # postgresql["model"]["table_name"] = "ruia_postgres_notexist"
        model, _ = create_model(create_table=True, postgres=postgresql)
        rows_before = model.select().count()
        assert rows_before == 0
        spider_ins = await PostgresqlUpdate.async_start(
            loop=event_loop,
            after_start=after_start(postgres=postgresql),
            target_db=TargetDB.POSTGRES,
        )
        while not spider_ins.request_session.closed:
            await asyncio.sleep(1)
        rows_after = 0
        while rows_after == 0:
            rows_after = await spider_ins.postgres_manager.count(
                spider_ins.postgres_model.select()
            )
            await asyncio.sleep(1)
        assert rows_after == 10
