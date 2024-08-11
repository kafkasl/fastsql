# AUTOGENERATED! DO NOT EDIT! File to edit: ../00_core.ipynb.

# %% auto 0
__all__ = ['Database', 'DBTable', 'NotFoundError']

# %% ../00_core.ipynb 2
from dataclasses import dataclass,is_dataclass,asdict,MISSING,fields
import sqlalchemy as sa
from sqlalchemy.orm import Session
from fastcore.utils import *
from fastcore.test import test_fail,test_eq
from itertools import starmap

# %% ../00_core.ipynb 6
class Database:
    "A connection to a SQLAlchemy database"
    def __init__(self, conn_str):
        self.conn_str = conn_str
        self.engine = sa.create_engine(conn_str)
        self.meta = sa.MetaData()
        self.meta.reflect(bind=self.engine)
        self.meta.bind = self.engine
        self.conn = self.engine.connect()
        self.meta.conn = self.conn
    
    def execute(self, st, params=None, opts=None): return self.conn.execute(st, params, execution_options=opts)

    def __repr__(self): return f"Database({self.conn_str})"

# %% ../00_core.ipynb 8
class DBTable:
    "A connection to a SQLAlchemy table, created if needed"
    def __init__(self, table: sa.Table, database: Database, cls):
        self.table,self.db,self.cls,self.xtra_id = table,database,cls,{}
        table.create(self.db.engine, checkfirst=True)

    def __repr__(self) -> str: return self.table.name
    
    @property
    def t(self)->tuple: return self.table,self.table.c
    
    @property
    def pks(self)-> tuple: return tuple(self.table.primary_key) + tuple(self.table.c[o] for o in self.xtra_id.keys())
    
    @property
    def conn(self): return self.db.conn

    def xtra(self, **kwargs):
        "Set `xtra_id`"
        self.xtra_id = kwargs

# %% ../00_core.ipynb 9
_type_map = {int: sa.Integer, str: sa.String, bool: sa.Boolean}
def _column(name, typ, primary=False): return sa.Column(name, _type_map[typ], primary_key=primary)

# %% ../00_core.ipynb 10
@patch
def create(self:Database, cls:type, pk='id', name:str|None=None):
    "Get a table object, creating in DB if needed"
    pk = listify(pk)
    mk_dataclass(cls)
    if name is None: name = camel2snake(cls.__name__)
    cols = [_column(o.name, o.type, primary=o.name in pk) for o in fields(cls)]
    tbl = sa.Table(name, self.meta, *cols, extend_existing=True)
    return DBTable(tbl, self, cls)

# %% ../00_core.ipynb 12
@patch
def schema(self:Database):
    "Show all tables and columns"
    inspector = sa.inspect(self.engine)
    res = ''
    for table_name in inspector.get_table_names():
        res += f"Table: {table_name}\n"
        pk_cols = inspector.get_pk_constraint(table_name)['constrained_columns']
        for column in inspector.get_columns(table_name):
            pk_marker = '*' if column['name'] in pk_cols else '-'
            res += f"  {pk_marker} {column['name']}: {column['type']}\n"
    return res

# %% ../00_core.ipynb 14
@patch
def exists(self:DBTable):
    "Check if this table exists in the DB"
    return sa.inspect(self.db.engine).has_table(self.table.name)

# %% ../00_core.ipynb 17
def _wanted(obj): return {k:v for k,v in asdict(obj).items() if v not in (None,MISSING)}

# %% ../00_core.ipynb 18
@patch
def insert(self:DBTable, obj):
    "Insert an object into this table, and return it"
    d = {**_wanted(obj), **self.xtra_id}
    result = self.conn.execute(sa.insert(self.table).values(**d).returning(*self.table.columns))
    row = result.one()  # Consume the result set
    self.conn.commit()
    return self.cls(**row._asdict())

# %% ../00_core.ipynb 21
@patch
def __call__(
    self:DBTable,
    where:str|None=None,  # SQL where fragment to use, for example `id > ?`
    where_args: Iterable|dict|NoneType=None, # Parameters to use with `where`; iterable for `id>?`, or dict for `id>:id`
    order_by: str|None=None, # Column or fragment of SQL to order by
    limit:int|None=None, # Number of rows to limit to
    offset:int|None=None, # SQL offset
    select:str = "*", # Comma-separated list of columns to select
    **kw  # Combined with `where_args`
)->list:
    "Result of `select` query on the table"
    if select == "*": query = sa.select(self.table)
    else:
        columns = [sa.text(col.strip()) for col in select.split(',')]
        query = sa.select(*columns).select_from(self.table)
    if where_args: kw = {**kw, **where_args}
    xtra = self.xtra_id
    if xtra:
        xw = ' and '.join(f"[{k}] = {v!r}" for k,v in xtra.items())
        where = f'{xw} and {where}' if where else xw
    if where:
        where = sa.text(where)
        if kw: where = where.bindparams(**kw)
        query = query.where(where)
    if order_by: query = query.order_by(sa.text(order_by))
    if limit is not None: query = query.limit(limit)
    if offset is not None: query = query.offset(offset)
    rows = self.conn.execute(query).all()
    return [self.cls(**row._asdict()) for row in rows]

# %% ../00_core.ipynb 28
@patch
def _pk_where(self:DBTable, meth,key):
    if not isinstance(key,tuple): key = (key,)
    xtra = getattr(self, 'xtra_id', {})
    pkv = zip(self.pks, key + tuple(xtra.values()))
    cond = sa.and_(*[col==val for col,val in pkv])
#     print(cond.compile(compile_kwargs={"literal_binds": True}))
    return getattr(self.table,meth)().where(cond)

# %% ../00_core.ipynb 29
class NotFoundError(Exception): pass

# %% ../00_core.ipynb 30
@patch
def __getitem__(self:DBTable, key):
    "Get item with PK `key`"
    qry = self._pk_where('select', key)
    result = self.conn.execute(qry).first()
    if not result: raise NotFoundError()
    return self.cls(**result._asdict())

# %% ../00_core.ipynb 33
@patch
def update(self:DBTable, obj):
    d = _wanted(obj)
    pks = tuple(d[k.name] for k in self.table.primary_key)
    qry = self._pk_where('update', pks).values(**d).returning(*self.table.columns)
    result = self.conn.execute(qry)
    row = result.one()
    self.conn.commit()
    return self.cls(**row._asdict())

# %% ../00_core.ipynb 36
@patch
def delete(self:DBTable, key):
    "Delete item with PK `key` and return count deleted"
    result = self.conn.execute(self._pk_where('delete', key))
    self.conn.commit()
    return result.rowcount

# %% ../00_core.ipynb 39
from fastcore.net import urlsave

from collections import namedtuple
from sqlalchemy import create_engine,text,MetaData,Table,Column,engine,sql
from sqlalchemy.sql.base import ReadOnlyColumnCollection
from sqlalchemy.engine.base import Connection
from sqlalchemy.engine.cursor import CursorResult

# %% ../00_core.ipynb 40
@patch
def __dir__(self:MetaData): return self._orig___dir__() + list(self.tables)

@patch
def __dir__(self:ReadOnlyColumnCollection): return self._orig___dir__() + self.keys()

def _getattr_(self, n):
    if n[0]=='_': raise AttributeError
    if n in self.tables: return self.tables[n]
    raise AttributeError

MetaData.__getattr__ = _getattr_

# %% ../00_core.ipynb 45
@patch
def tuples(self:CursorResult, nm='Row'):
    "Get all results as named tuples"
    rs = self.mappings().fetchall()
    nt = namedtuple(nm, self.keys())
    return [nt(**o) for o in rs]

@patch
def sql(self:Connection, statement, nm='Row', *args, **kwargs):
    "Execute `statement` string and return results (if any)"
    if isinstance(statement,str): statement=text(statement)
    t = self.execute(statement)
    return t.tuples()

@patch
def sql(self:MetaData, statement, *args, **kwargs):
    "Execute `statement` string and return `DataFrame` of results (if any)"
    return self.conn.sql(statement, *args, **kwargs)

# %% ../00_core.ipynb 47
@patch
def get(self:Table, where=None, limit=None):
    "Select from table, optionally limited by `where` and `limit` clauses"
    return self.metadata.conn.sql(self.select().where(where).limit(limit))

# %% ../00_core.ipynb 51
@patch
def close(self:MetaData):
    "Close the connection"
    self.conn.close()
