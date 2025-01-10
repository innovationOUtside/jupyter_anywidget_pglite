from sqlalchemy.engine import Engine, Connection
from sqlalchemy.pool import Pool
from sqlalchemy.dialects import registry
from sqlalchemy.engine import default
from sqlalchemy import types as sqltypes
from sqlalchemy.engine.default import DefaultDialect
from sqlalchemy.sql import compiler
from sqlalchemy.engine.cursor import CursorResult
from sqlalchemy import text


class PGLiteCompiler(compiler.SQLCompiler):
    def visit_bindparam(self, bindparam, **kw):
        return "$" + str(self.bindtemplate % bindparam.position)


class PGLiteDialect(DefaultDialect):
    name = "pglite"
    driver = "widget"

    supports_alter = True
    supports_pk_autoincrement = True
    supports_default_values = True
    supports_empty_insert = True
    supports_unicode_statements = True
    supports_unicode_binds = True
    returns_unicode_strings = True
    description_encoding = None
    supports_native_boolean = True

    statement_compiler = PGLiteCompiler
    poolclass = Pool

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    @classmethod
    def dbapi(cls):
        return None

    def create_connect_args(self, url):
        return [], {}

    def do_ping(self, dbapi_connection):
        return True

    def get_columns(self, connection, table_name, schema=None, **kw):
        return []

    def get_table_names(self, connection, schema=None, **kw):
        return []

    def get_view_names(self, connection, schema=None, **kw):
        return []

    def get_pk_constraint(self, connection, table_name, schema=None, **kw):
        return {}

    def get_foreign_keys(self, connection, table_name, schema=None, **kw):
        return []

    def get_indexes(self, connection, table_name, schema=None, **kw):
        return []


class PGLiteEngine(Engine):
    def __init__(self, widget):
        self.widget = widget
        self.dialect = PGLiteDialect()
        self.url = None
        self._compiled_cache = {}

    def connect(self):
        return PGLiteConnection(self)

    def execution_options(self, **opt):
        return self

    def begin(self):
        return self.connect().begin()


class PGLiteConnection:
    def __init__(self, engine):
        self.engine = engine
        self.widget = engine.widget
        self._active_transaction = None
        self._closed = False
        self.dialect = engine.dialect

    def execute(self, statement, parameters=None, execution_options=None):
        if isinstance(statement, str):
            statement = text(statement)
        query = str(statement)

        result = self.widget.query(query, multi=False, autorespond=True)

        if result["status"] != "completed":
            raise Exception(
                f"Query failed: {result.get('error_message', 'Unknown error')}"
            )

        if result["response_type"] == "single":
            query_result = result["response"]
        else:
            query_result = result["response"][-1]

        rows = [tuple(row.values()) for row in query_result["rows"]]
        columns = [field["name"] for field in query_result["fields"]]

        return PGLiteResult(self, rows, columns)

    def exec_driver_sql(self, statement, parameters=None, execution_options=None):
        return self.execute(statement, parameters, execution_options)

    def close(self):
        if not self._closed:
            if self._active_transaction:
                self._active_transaction.rollback()
            self._closed = True

    def begin(self):
        if self._active_transaction is None or not self._active_transaction.is_active:
            self._active_transaction = PGLiteTransaction(self)
        return self._active_transaction

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


class PGLiteTransaction:
    def __init__(self, connection):
        self.connection = connection
        self.is_active = True
        self.connection.widget.query("BEGIN", autorespond=True)

    def commit(self):
        if self.is_active:
            self.connection.widget.query("COMMIT", autorespond=True)
            self.is_active = False

    def rollback(self):
        if self.is_active:
            self.connection.widget.query("ROLLBACK", autorespond=True)
            self.is_active = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None and self.is_active:
            self.commit()
        elif self.is_active:
            self.rollback()


class PGLiteResult:
    def __init__(self, connection, rows, columns):
        self.connection = connection
        self.rows = rows
        self.columns = columns
        self._index = 0

    def fetchall(self):
        return self.rows

    def fetchone(self):
        if self._index >= len(self.rows):
            return None
        row = self.rows[self._index]
        self._index += 1
        return row

    def keys(self):
        return self.columns

    def all(self):
        return self.fetchall()


def create_engine(widget):
    """Create a SQLAlchemy engine from a postgresWidget."""
    return PGLiteEngine(widget)
