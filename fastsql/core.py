# AUTOGENERATED! DO NOT EDIT! File to edit: ../nbs/00_core.ipynb.

# %% auto 0
__all__ = ['type_map', 'Database', 'DBTable', 'create_column']

# %% ../nbs/00_core.ipynb 4
from dataclasses import dataclass, is_dataclass, asdict
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Session

from fastcore.utils import *

__all__ = []

# %% ../nbs/00_core.ipynb 5
class Database:
    def __init__(self, conn_str):
        self.conn_str = conn_str
        self.engine = sa.create_engine(conn_str)
        self.metadata = sa.MetaData()
        self.metadata.create_all(self.engine)

    def __repr__(self):
        return f"Database({self.conn_str})"

# %% ../nbs/00_core.ipynb 7
class DBTable:
    def __init__(self, table: sa.Table, database: Database):
        self._table = table
        self._database = database

    def __getitem__(self, name: str) -> Any:
        return self._table.c.__getattribute__(name)
    
    def __str__(self):
        return self._table.name
    
    def __repr__(self) -> str:
        return self._table.name

# %% ../nbs/00_core.ipynb 9
type_map = {
    int: sa.Integer,
    str: sa.String,
    bool: sa.Boolean
}
def create_column(name, typ, primary=False):
    return sa.Column(name, type_map[typ], primary_key=primary)

# %% ../nbs/00_core.ipynb 12
def _create_column_from_dataclass_field(name, field, primary=False):
    return create_column(name, field.type, primary)

# %% ../nbs/00_core.ipynb 13
@patch
def create(self: Database, cls: dataclass, pk: str|None=None) -> DBTable:
    pkcol = None
    cols = {k: v for k,v in cls.__dataclass_fields__.items()}
    # Set primary key, popping from cols
    if pk is not None: pkcol = _create_column_from_dataclass_field(pk, cols.pop(pk), primary=True)
    columns = [_create_column_from_dataclass_field(k, v) for k,v in cols.items()]
    # Insert primary key at the beginning
    if pkcol is not None: columns.insert(0, pkcol)
    # return Table(cls.__name__, self.metadata, *columns)
    return DBTable(sa.Table(cls.__name__, self.metadata, *columns), self)

# %% ../nbs/00_core.ipynb 16
@patch
def insert(self: DBTable, **kwargs):
    with Session(self._database.engine) as session:
        stmt = sa.insert(self._table).values(**kwargs)
        result = session.execute(stmt)
        session.commit()
    return result
