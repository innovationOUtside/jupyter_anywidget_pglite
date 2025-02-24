from IPython.display import display
import platform

PLATFORM = platform.system().lower()

# Via: claude.ai
from sqlalchemy.engine import Engine, Connection
from sqlalchemy.pool import Pool
from sqlalchemy.dialects import registry
from sqlalchemy.engine import default
from sqlalchemy import types as sqltypes
from sqlalchemy.engine.default import DefaultDialect
from sqlalchemy.sql import compiler
from sqlalchemy.engine.cursor import CursorResult
from sqlalchemy import text

import re

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

    def schema_for_object(self, obj):
        """Return the schema for an object (e.g., table) in the database."""
        # This is typically a method that returns the schema name of the object
        # You can fetch it from `information_schema.tables` or set a default schema.

        # If the object has a __tablename__ attribute, you can use that to check.
        if hasattr(obj, "__tablename__"):
            table_name = obj.__tablename__
            query = f"""
            SELECT table_schema
            FROM information_schema.tables 
            WHERE table_name = '{table_name}' 
            AND table_type = 'BASE TABLE';
            """
            # Replace this with an actual SQL query to retrieve the schema.
            # In this example, it's assuming 'public' schema as default.
            return "public"  # or fetch the actual schema from the query result
        return "public"  # Default to 'public' schema

    def get_columns(self, connection, table_name, schema=None, **kw):
        query = f"""
        SELECT column_name, data_type, is_nullable, column_default 
        FROM information_schema.columns 
        WHERE table_name = '{table_name}';
        """
        result = connection.execute(query)

        columns = []
        for row in result.fetchall():
            column = {
                "name": row[0],
                "type": (
                    sqltypes.String if "char" in row[1] else sqltypes.Integer
                ),  # Map SQL types
                "nullable": row[2] == "YES",
                "default": row[3],
            }
            columns.append(column)

        return columns

    def get_table_names(self, connection, schema=None, **kw):
        query = (
            "SELECT tablename FROM pg_catalog.pg_tables WHERE schemaname = 'public';"
        )
        result = connection.execute(query)
        return [row[0] for row in result.fetchall()]

    def get_pk_constraint(self, connection, table_name, schema=None, **kw):
        query = f"""
        SELECT kcu.column_name
        FROM information_schema.table_constraints AS tc
        JOIN information_schema.key_column_usage AS kcu 
            ON tc.constraint_name = kcu.constraint_name
            AND tc.table_schema = kcu.table_schema
        WHERE tc.constraint_type = 'PRIMARY KEY' 
            AND kcu.table_name = '{table_name}';
        """
        result = connection.execute(query)

        primary_keys = [row[0] for row in result.fetchall()]

        return {
            "constrained_columns": primary_keys,
            "name": f"pk_{table_name}" if primary_keys else None,
        }


    def get_foreign_keys(self, connection, table_name, schema=None, **kw):
        query = f"""
        SELECT kcu.column_name, ccu.table_schema AS referred_schema, 
            ccu.table_name AS foreign_table, ccu.column_name AS foreign_column
        FROM information_schema.table_constraints AS tc
        JOIN information_schema.key_column_usage AS kcu 
            ON tc.constraint_name = kcu.constraint_name
            AND tc.table_schema = kcu.table_schema
        JOIN information_schema.constraint_column_usage AS ccu 
            ON ccu.constraint_name = tc.constraint_name
            AND ccu.table_schema = tc.table_schema
        WHERE tc.constraint_type = 'FOREIGN KEY' 
            AND kcu.table_name = '{table_name}';
        """
        result = connection.execute(query)

        foreign_keys = []
        for row in result.fetchall():
            fk = {
                "name": f"fk_{table_name}_{row[0]}",
                "constrained_columns": [row[0]],
                "referred_schema": (
                    row[1] if len(row) > 1 else schema or "public"
                ),  # Add this line
                "referred_table": (
                    row[2] if len(row) > 2 else row[1]
                ),  # Adjust index based on query
                "referred_columns": [
                    row[3] if len(row) > 3 else row[2]
                ],  # Adjust index based on query
            }
            foreign_keys.append(fk)

        return foreign_keys

    def get_indexes(self, connection, table_name, schema=None, **kw):
        # Get basic index information
        query = f"""
        SELECT indexname, indexdef
        FROM pg_indexes
        WHERE tablename = '{table_name}' AND schemaname = 'public';
        """
        result = connection.execute(query)

        indexes = []
        for row in result.fetchall():
            # This is a simplified approach - you might need to improve the parsing
            # based on your specific index definitions
            indexdef = row[1]
            column_match = re.search(r"\((.*?)\)", indexdef)
            column_names = []
            if column_match:
                column_str = column_match.group(1)
                column_names = [c.strip() for c in column_str.split(",")]

            index = {
                "name": row[0],
                "column_names": column_names,  # Required by SQLAlchemy
                "unique": "UNIQUE" in indexdef.upper(),
            }
            indexes.append(index)

        return indexes


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

    def __getattr__(self, name):
        # Delegate attribute access to the dialect if not found in connection
        if hasattr(self.dialect, name):
            return getattr(self.dialect, name)
        raise AttributeError(f"'PGLiteConnection' object has no attribute '{name}'")

    def in_transaction(self):
        """Return True if a transaction is active."""
        return (
            self._active_transaction is not None and self._active_transaction.is_active
        )

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
            self.connection._active_transaction = None

    def rollback(self):
        if self.is_active:
            self.connection.widget.query("ROLLBACK", autorespond=True)
            self.is_active = False
            self.connection._active_transaction = None

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
    if PLATFORM == "emscripten":
        display(
            "SQLAlchemy connections not currently available on emscripten platforms."
        )
        return
    return PGLiteEngine(widget)
