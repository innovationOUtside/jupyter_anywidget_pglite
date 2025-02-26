from IPython.display import display
import platform
import re

PLATFORM = platform.system().lower()

# SQLAlchemy imports
from sqlalchemy.engine import Engine
from sqlalchemy.pool import Pool
from sqlalchemy import types as sqltypes
from sqlalchemy.engine.default import DefaultDialect
from sqlalchemy.engine import Connection
from sqlalchemy.dialects.postgresql.base import (
    PGCompiler,
    PGDialect,
    PGInspector,
    PGDDLCompiler,
    PGIdentifierPreparer,
)
from sqlalchemy import inspect
from sqlalchemy.engine.reflection import Inspector
from sqlalchemy.engine.base import Transaction
from sqlalchemy.sql import insert, select
from sqlalchemy.sql.dml import Insert
from sqlalchemy.sql.selectable import Select
from sqlalchemy.sql.ddl import CreateTable, DropTable, CreateIndex

# from sqlalchemy.ext.compiler import compiles
# from sqlalchemy.sql.elements import BindParameter
# from sqlalchemy.sql.ddl import CreateTable, CreateIndex, CreateSchema
from sqlalchemy.sql.compiler import DDLCompiler

from sqlalchemy.sql.compiler import IdentifierPreparer
from sqlalchemy.sql.elements import quoted_name

import sqlalchemy
import logging
import warnings

logger = logging.getLogger(__name__)


def dry_run_sql(query, params):
    # Check if the query is an INSERT
    if isinstance(query, str):
        return query
    elif isinstance(query, CreateTable):
        return str(query)
    elif isinstance(query, DropTable):
        return str(query)
    elif isinstance(query, CreateIndex):
        return str(query)
    elif isinstance(query, Insert):
        # If params is a list of dicts, generate individual INSERT statements
        if isinstance(params, list):
            compiled_sqls = []
            for param in params:
                compiled_sql = query.values(**param).compile(
                    compile_kwargs={"literal_binds": True}
                )
                # Hackfix
                from sqlalchemy.exc import SAWarning
                warnings.filterwarnings("ignore", category=SAWarning)
                compiled_sql = str(compiled_sql).replace("= NULL", "IS NULL")
                compiled_sqls.append(compiled_sql)  # Convert to string
            return compiled_sqls
        else:
            # Handle single row insertion
            compiled_sql = query.values(**params).compile(
                compile_kwargs={"literal_binds": True}
            )
            return str(compiled_sql)  # Return the compiled SQL as string

    # Check if the query is a SELECT statement
    elif isinstance(query, Select):
        # If params is a dictionary, replace the placeholders with actual values
        compiled_sql = query.compile(compile_kwargs={"literal_binds": True})

        # Manually substitute parameters into the query if it's a SELECT
        if isinstance(params, dict):
            # Create the SQL string with parameters replaced by their actual values
            compiled_sql_str = str(compiled_sql)
            for key, value in params.items():
                # Replace placeholders like :param with actual values
                compiled_sql_str = compiled_sql_str.replace(f":{key}", str(value))
            return compiled_sql_str

        return str(
            compiled_sql
        )  # Return the compiled SQL as string if no params are given

    # Handle other types of queries, if needed (for example, DELETE or UPDATE)
    else:
        raise ValueError(f"Unsupported query type: {type(query)}")


class PGLiteIdentifierPreparer(PGIdentifierPreparer):
    def __init__(self, dialect):
        super().__init__(dialect, initial_quote='"', final_quote='"', escape_quote='"')


class PGLiteCompiler(PGCompiler):
    bindtemplate = "$%(position)s"
    positional = True

    # Add this method to ensure positional parameters are used
    def _apply_numbered_params(self):
        # Force using numbered parameters
        return True

    def process(self, stmt, **kw):
        """Process the statement before compiling."""
        logger.debug(f"process statement: {type(stmt)}")
        result = super().process(stmt, **kw)
        logger.debug(f"preprocessed to: {result}")
        return result

    def visit_table(self, table, **kw):
        # Ensure table names are properly quoted
        if isinstance(table, str):
            return f'"{table}"'
        return f'"{table.name}"'

    def visit_insert(self, insert_stmt, **kw):
        # Get the table
        table = insert_stmt.table

        # Check if explicit parameters are given in kw
        parameters = kw.pop("parameters", {})

        # Check if this is a multi-values insert (common with pandas)
        if isinstance(insert_stmt.values, list):
            # Multi-row insert
            stmt = f'INSERT INTO "{table.name}" ('

            # Get column names (ensure safe handling)
            column_names = [c.key for c in insert_stmt.values[0].keys()]
            stmt += ", ".join(f'"{col}"' for col in column_names)
            stmt += ") VALUES "

            # Add parameter placeholders for each row
            values_clauses = []
            bind_index = 1
            for param_set in insert_stmt.values:
                value_clause = "("
                value_terms = []
                for col in column_names:
                    value_terms.append(f"${bind_index}")
                    bind_index += 1
                value_clause += ", ".join(value_terms) + ")"
                values_clauses.append(value_clause)

            stmt += ", ".join(values_clauses)

            # Create params dict (corresponding to each placeholder)
            params = {}
            bind_index = 1
            for param_set in insert_stmt.values:
                for col in column_names:
                    params[f"${bind_index}"] = param_set[col]
                    bind_index += 1

            return stmt, params
        else:
            # Handle single row insert with either positional or named parameters
            stmt = f'INSERT INTO "{table.name}" ('

            # Get column names (with safer handling)
            if hasattr(insert_stmt, "parameters") and insert_stmt.parameters:
                # Use provided parameters if available
                column_names = list(insert_stmt.parameters.keys())
            else:
                # Fall back to table columns
                column_names = [c.name for c in table.columns]

            stmt += ", ".join(f'"{col}"' for col in column_names)
            stmt += ") VALUES ("

            # Add parameter placeholders - use named parameters if available
            if kw.get("use_named_parameters", False):
                placeholders = [f":{col}" for col in column_names]
            else:
                placeholders = [f"${i+1}" for i in range(len(column_names))]

            stmt += ", ".join(placeholders)
            stmt += ")"

            # Construct parameters map
            if parameters:
                params = {
                    f"${i+1}": parameters[col] for i, col in enumerate(column_names)
                }
            else:
                # Default params: these will be extracted from the insert_stmt if no `parameters` are provided
                params = {
                    f"${i+1}": None for i in range(len(column_names))
                }  # placeholders only, real values come later

            return stmt, params

    def visit_array(self, array, **kw):
        """Compile an array"""
        return f"ARRAY[{', '.join(self.process(elem, **kw) for elem in array.clauses)}]"

    def visit_array_column(self, element, **kw):
        return "%s[%s]" % (
            self.process(element.get_children()[0]),
            self.process(element.get_children()[1]),
        )

    def render_literal_value(self, value, type_):
        if isinstance(value, list):
            return "ARRAY[%s]" % (
                ", ".join(self.render_literal_value(x, type_) for x in value)
            )
        # Handle other types
        return super().render_literal_value(value, type_)


class PGLiteDDLCompiler(PGDDLCompiler):
    def __init__(self, dialect, statement, **kw):
        # Remove 'checkfirst' if present before calling parent constructor
        checkfirst = kw.pop("checkfirst", None)
        super().__init__(dialect, statement, **kw)
        self.checkfirst = checkfirst

    def visit_table(self, table, **kw):
        """Visit a Table object."""
        return self.preparer.format_table(table)

    def visit_column(self, column, **kw):
        """Visit a Column object."""
        return self.preparer.format_column(column)

    # Other visit methods that might be needed
    def visit_index(self, index, **kw):
        """Visit an Index object."""
        return self.preparer.format_index(index)

    def visit_schema(self, schema, **kw):
        """Visit a Schema object."""
        return self.preparer.format_schema(schema)

    def visit_create_table(self, create, **kw):
        # Handle checkfirst parameter for table creation
        if getattr(create, "checkfirst", False):
            return f"""
                DO $$ 
                BEGIN
                    IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = '{create.element.name}') THEN
                        {super().visit_create_table(create, **kw)}
                    END IF;
                END $$;
            """
        else:
            return super().visit_create_table(create, **kw)


class PGLiteInspector(PGInspector):
    def __init__(self, conn):
        super().__init__(conn)
        self.conn = conn
        self.dialect = conn.dialect
        self.info_cache = {}

    def _inspection_context(self):
        """Return a context for inspection."""

        # Create a simple context manager for the inspection
        class InspectionContext:
            def __init__(self, inspector):
                self.inspector = inspector

            def __enter__(self):
                return self.inspector

            def __exit__(self, exc_type, exc_val, exc_tb):
                pass

        return InspectionContext(self)

    def get_schema_names(self):
        query = "SELECT nspname FROM pg_namespace WHERE nspname !~ '^pg_' AND nspname != 'information_schema';"
        result = self.conn.execute(query)
        return [row[0] for row in result.fetchall()]

    def get_table_names(self, schema=None):
        schema = schema or "public"
        query = (
            f"SELECT tablename FROM pg_catalog.pg_tables WHERE schemaname = '{schema}';"
        )
        result = self.conn.execute(query)
        return [row[0] for row in result.fetchall()]

    def get_columns(self, table_name, schema=None):
        schema = schema or "public"
        query = f"""
        SELECT column_name, data_type, is_nullable, column_default 
        FROM information_schema.columns 
        WHERE table_name = '{table_name}'
        AND table_schema = '{schema}';
        """
        result = self.conn.execute(query)

        columns = []
        for row in result.fetchall():
            column = {
                "name": row[0],
                "type": self._get_column_type(row[1]),
                "nullable": row[2] == "YES",
                "default": row[3],
            }
            columns.append(column)

        return columns

    def _get_column_type(self, type_name):
        # Map PostgreSQL types to SQLAlchemy types
        if "char" in type_name or "text" in type_name:
            return sqltypes.String
        elif "int" in type_name:
            return sqltypes.Integer
        elif "float" in type_name or "double" in type_name or "numeric" in type_name:
            return sqltypes.Float
        elif "bool" in type_name:
            return sqltypes.Boolean
        elif "date" in type_name:
            return sqltypes.Date
        elif "time" in type_name and "without" in type_name:
            return sqltypes.Time
        elif "time" in type_name and "with" in type_name:
            return sqltypes.DateTime
        elif "bytea" in type_name:
            return sqltypes.LargeBinary
        # Add more type mappings as needed
        return sqltypes.String  # Default fallback

    def get_pk_constraint(self, table_name, schema=None):
        schema = schema or "public"
        query = f"""
        SELECT kcu.column_name
        FROM information_schema.table_constraints AS tc
        JOIN information_schema.key_column_usage AS kcu 
            ON tc.constraint_name = kcu.constraint_name
            AND tc.table_schema = kcu.table_schema
        WHERE tc.constraint_type = 'PRIMARY KEY' 
            AND kcu.table_name = '{table_name}'
            AND kcu.table_schema = '{schema}';
        """
        result = self.conn.execute(query)

        primary_keys = [row[0] for row in result.fetchall()]

        return {
            "constrained_columns": primary_keys,
            "name": f"pk_{table_name}" if primary_keys else None,
        }

    def get_foreign_keys(self, table_name, schema=None):
        schema = schema or "public"
        query = f"""
        SELECT 
            kcu.column_name, 
            ccu.table_schema, 
            ccu.table_name, 
            ccu.column_name,
            tc.constraint_name
        FROM information_schema.table_constraints AS tc
        JOIN information_schema.key_column_usage AS kcu 
            ON tc.constraint_name = kcu.constraint_name
            AND tc.table_schema = kcu.table_schema
        JOIN information_schema.constraint_column_usage AS ccu 
            ON ccu.constraint_name = tc.constraint_name
            AND ccu.table_schema = tc.table_schema
        WHERE tc.constraint_type = 'FOREIGN KEY' 
            AND kcu.table_name = '{table_name}'
            AND kcu.table_schema = '{schema}';
        """
        result = self.conn.execute(query)

        foreign_keys = []
        for row in result.fetchall():
            fk = {
                "name": row[4] if len(row) > 4 else f"fk_{table_name}_{row[0]}",
                "constrained_columns": [row[0]],
                "referred_schema": row[1] if row[1] else schema,
                "referred_table": row[2],
                "referred_columns": [row[3]],
            }
            foreign_keys.append(fk)

        return foreign_keys

    def get_indexes(self, table_name, schema=None):
        schema = schema or "public"
        # First get index names
        query = f"""
        SELECT indexname, indexdef
        FROM pg_indexes
        WHERE tablename = '{table_name}' AND schemaname = '{schema}';
        """
        result = self.conn.execute(query)

        indexes = []
        for row in result.fetchall():
            index_name = row[0]
            index_def = row[1]

            # Try to extract column names from index definition
            column_match = re.search(r"\((.*?)\)", index_def)
            column_names = []
            if column_match:
                column_str = column_match.group(1)
                column_names = [c.strip() for c in column_str.split(",")]

            index = {
                "name": index_name,
                "column_names": column_names,
                "unique": "UNIQUE" in index_def.upper(),
            }
            indexes.append(index)

        return indexes

    def has_table(self, table_name, schema=None):
        schema = schema or "public"
        try:
            # Use direct SQL query to check table existence
            query = f"""
            SELECT 1 FROM information_schema.tables 
            WHERE table_name = '{table_name}' AND table_schema = '{schema}';
            """
            result = self.conn.execute(query)
            return bool(result.fetchone())
        except Exception as e:
            logger.warning(f"Error checking table existence: {e}")
            return False

    def has_schema(self, schema_name):
        query = f"SELECT 1 FROM pg_namespace WHERE nspname = '{schema_name}';"
        result = self.conn.execute(query)
        return bool(result.fetchone())

    def get_view_names(self, schema=None):
        schema = schema or "public"
        query = (
            f"SELECT viewname FROM pg_catalog.pg_views WHERE schemaname = '{schema}';"
        )
        result = self.conn.execute(query)
        return [row[0] for row in result.fetchall()]

    def reflect_table(
        self, table, include_columns=None, exclude_columns=None, resolve_fks=False, **kw
    ):
        """Reflect a table from the database."""
        schema = table.schema or "public"
        table_name = table.name

        # Check if table exists
        if not self.has_table(table_name, schema):
            raise sqlalchemy.exc.NoSuchTableError(table_name)

        # Get table columns
        columns = self.get_columns(table_name, schema)
        if include_columns:
            columns = [c for c in columns if c["name"] in include_columns]
        if exclude_columns:
            columns = [c for c in columns if c["name"] not in exclude_columns]

        # Add columns to the table
        for column_info in columns:
            name = column_info["name"]
            if include_columns and name not in include_columns:
                continue
            if exclude_columns and name in exclude_columns:
                continue

            # Get column attributes
            type_ = column_info["type"]
            nullable = column_info.get("nullable", True)
            default = column_info.get("default")

            # Create SQLAlchemy Column object
            col_kw = {}
            if default is not None:
                col_kw["default"] = sqlalchemy.text(default)

            # Add the column to the table
            table.append_column(sqlalchemy.Column(name, type_, nullable=nullable, **col_kw))

        # Get primary key constraint
        pk_constraint = self.get_pk_constraint(table_name, schema)
        if pk_constraint:
            for col_name in pk_constraint["constrained_columns"]:
                if col_name in table.c:
                    table.c[col_name].primary_key = True

        # Get foreign keys if requested
        if resolve_fks:
            fks = self.get_foreign_keys(table_name, schema)
            for fk in fks:
                # Only create foreign keys for columns we've reflected
                if all(c in table.c for c in fk["constrained_columns"]):
                    sqlalchemy.ForeignKeyConstraint(
                        [table.c[cname] for cname in fk["constrained_columns"]],
                        [f"{fk['referred_table']}.{col}" for col in fk["referred_columns"]],
                        name=fk.get("name"),
                        onupdate=fk.get("onupdate"),
                        ondelete=fk.get("ondelete"),
                    )

        # Get indexes
        indexes = self.get_indexes(table_name, schema)
        for index_info in indexes:
            name = index_info["name"]
            columns = index_info["column_names"]
            unique = index_info.get("unique", False)

            # Create SQLAlchemy Index
            if all(col in table.c for col in columns):
                sqlalchemy.Index(name, *[table.c[col] for col in columns], unique=unique)


class PGLiteDialect(PGDialect):
    name = "pglite"
    driver = "widget"
    paramstyle = "numeric"
    positional = True

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
    ddl_compiler = PGLiteDDLCompiler
    poolclass = Pool
    preparer = PGLiteIdentifierPreparer

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    @classmethod
    def dbapi(cls):
        return None

    def create_connect_args(self, url):
        return [], {}

    def do_ping(self, dbapi_connection):
        return True

    def _get_server_version_info(self, connection):
        query = "SELECT version();"
        result = connection.execute(query)

        # Fetch the first row, which contains the version string
        version_string = result.fetchone()[0]

        # Adjust regex to handle the format in your example
        version_match = re.search(r"PostgreSQL (\d+)\.(\d+)", version_string)

        if version_match:
            # Extract version numbers and return as a tuple (major, minor)
            major = int(version_match.group(1))
            minor = int(version_match.group(2))
            return (major, minor)
        else:
            # If the version string doesn't match, guess
            return (16, 4)

    def get_schema_names(self, connection, **kw):
        query = "SELECT nspname FROM pg_namespace WHERE nspname !~ '^pg_' AND nspname != 'information_schema';"
        result = connection.execute(query)
        return [row[0] for row in result.fetchall()]

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

    def has_schema(self, connection, schema_name, **kw):
        query = f"SELECT 1 FROM pg_namespace WHERE nspname = '{schema_name}';"
        result = connection.execute(query)
        return bool(result.fetchone())

    def has_table(self, connection, table_name, schema=None, **kw):
        schema = schema or "public"
        query = f"""
        SELECT 1 FROM information_schema.tables 
        WHERE table_name = '{table_name}' AND table_schema = '{schema}';
        """
        result = connection.execute(query)
        return bool(result.fetchone())

    def has_sequence(self, connection, sequence_name, schema=None, **kw):
        schema = schema or "public"
        query = f"""
        SELECT 1 FROM information_schema.sequences 
        WHERE sequence_name = '{sequence_name}' AND sequence_schema = '{schema}';
        """
        result = connection.execute(query)
        return bool(result.fetchone())

    def get_table_names(self, connection, schema=None, **kw):
        schema = schema or "public"
        query = (
            f"SELECT tablename FROM pg_catalog.pg_tables WHERE schemaname = '{schema}';"
        )
        result = connection.execute(query)
        return [row[0] for row in result.fetchall()]

    def get_view_names(self, connection, schema=None, **kw):
        schema = schema or "public"
        query = (
            f"SELECT viewname FROM pg_catalog.pg_views WHERE schemaname = '{schema}';"
        )
        result = connection.execute(query)
        return [row[0] for row in result.fetchall()]

    def get_columns(self, connection, table_name, schema=None, **kw):
        schema = schema or "public"
        query = f"""
        SELECT column_name, data_type, is_nullable, column_default 
        FROM information_schema.columns 
        WHERE table_name = '{table_name}'
        AND table_schema = '{schema}';
        """
        result = connection.execute(query)

        columns = []
        for row in result.fetchall():
            column = {
                "name": row[0],
                "type": self._get_column_type(row[1]),
                "nullable": row[2] == "YES",
                "default": row[3],
            }
            columns.append(column)

        return columns

    def _get_column_type(self, type_name):
        # Map PostgreSQL types to SQLAlchemy types
        if "char" in type_name or "text" in type_name:
            return sqltypes.String()
        elif "int" in type_name:
            return sqltypes.Integer()
        elif "float" in type_name or "double" in type_name or "numeric" in type_name:
            return sqltypes.Float()
        elif "bool" in type_name:
            return sqltypes.Boolean()
        elif "date" in type_name:
            return sqltypes.Date()
        elif "time" in type_name and "without" in type_name:
            return sqltypes.Time()
        elif "time" in type_name and "with" in type_name:
            return sqltypes.DateTime()
        elif "bytea" in type_name:
            return sqltypes.LargeBinary()
        # Add more type mappings as needed
        return sqltypes.String()  # Default fallback

    def get_pk_constraint(self, connection, table_name, schema=None, **kw):
        schema = schema or "public"
        query = f"""
        SELECT kcu.column_name
        FROM information_schema.table_constraints AS tc
        JOIN information_schema.key_column_usage AS kcu 
            ON tc.constraint_name = kcu.constraint_name
            AND tc.table_schema = kcu.table_schema
        WHERE tc.constraint_type = 'PRIMARY KEY' 
            AND kcu.table_name = '{table_name}'
            AND kcu.table_schema = '{schema}';
        """
        result = connection.execute(query)

        primary_keys = [row[0] for row in result.fetchall()]

        return {
            "constrained_columns": primary_keys,
            "name": f"pk_{table_name}" if primary_keys else None,
        }

    def get_foreign_keys(self, connection, table_name, schema=None, **kw):
        schema = schema or "public"
        query = f"""
        SELECT 
            kcu.column_name, 
            ccu.table_schema, 
            ccu.table_name, 
            ccu.column_name,
            tc.constraint_name
        FROM information_schema.table_constraints AS tc
        JOIN information_schema.key_column_usage AS kcu 
            ON tc.constraint_name = kcu.constraint_name
            AND tc.table_schema = kcu.table_schema
        JOIN information_schema.constraint_column_usage AS ccu 
            ON ccu.constraint_name = tc.constraint_name
            AND ccu.table_schema = tc.table_schema
        WHERE tc.constraint_type = 'FOREIGN KEY' 
            AND kcu.table_name = '{table_name}'
            AND kcu.table_schema = '{schema}';
        """
        result = connection.execute(query)

        foreign_keys = []
        for row in result.fetchall():
            fk = {
                "name": row[4] if len(row) > 4 else f"fk_{table_name}_{row[0]}",
                "constrained_columns": [row[0]],
                "referred_schema": row[1] if row[1] else schema,
                "referred_table": row[2],
                "referred_columns": [row[3]],
            }
            foreign_keys.append(fk)

        return foreign_keys

    def get_indexes(self, connection, table_name, schema=None, **kw):
        schema = schema or "public"
        # First get index names
        query = f"""
        SELECT indexname, indexdef
        FROM pg_indexes
        WHERE tablename = '{table_name}' AND schemaname = '{schema}';
        """
        result = connection.execute(query)

        indexes = []
        for row in result.fetchall():
            index_name = row[0]
            index_def = row[1]

            # Try to extract column names from index definition
            column_match = re.search(r"\((.*?)\)", index_def)
            column_names = []
            if column_match:
                column_str = column_match.group(1)
                column_names = [c.strip() for c in column_str.split(",")]

            index = {
                "name": index_name,
                "column_names": column_names,
                "unique": "UNIQUE" in index_def.upper(),
            }
            indexes.append(index)

        return indexes

    def get_unique_constraints(self, connection, table_name, schema=None, **kw):
        schema = schema or "public"
        query = f"""
        SELECT tc.constraint_name, kcu.column_name
        FROM information_schema.table_constraints AS tc
        JOIN information_schema.key_column_usage AS kcu
            ON tc.constraint_name = kcu.constraint_name
        WHERE tc.constraint_type = 'UNIQUE'
            AND tc.table_name = '{table_name}'
            AND tc.table_schema = '{schema}'
        ORDER BY tc.constraint_name, kcu.ordinal_position;
        """
        result = connection.execute(query)

        constraints = {}
        for constraint_name, column_name in result.fetchall():
            if constraint_name not in constraints:
                constraints[constraint_name] = {
                    "name": constraint_name,
                    "column_names": [],
                }
            constraints[constraint_name]["column_names"].append(column_name)

        return list(constraints.values())

    def get_table_comment(self, connection, table_name, schema=None, **kw):
        schema = schema or "public"
        query = f"""
        SELECT obj_description(c.oid)
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE c.relname = '{table_name}'
        AND n.nspname = '{schema}';
        """
        result = connection.execute(query)
        comment = result.fetchone()

        return {"text": comment[0] if comment and comment[0] else ""}

    def get_check_constraints(self, connection, table_name, schema=None, **kw):
        schema = schema or "public"
        query = f"""
        SELECT conname, pg_get_expr(conbin, conrelid) AS consrc
        FROM pg_constraint
        WHERE conrelid = (
            SELECT oid
            FROM pg_class
            WHERE relname = '{table_name}'
            AND relnamespace = (
                SELECT oid
                FROM pg_namespace
                WHERE nspname = '{schema}'
            )
        )
        AND contype = 'c';
        """
        result = connection.execute(query)

        check_constraints = []
        for row in result.fetchall():
            constraint = {
                "name": row[0],
                "sqltext": row[1],
            }
            check_constraints.append(constraint)

        return check_constraints


    def visit_drop_table(self, connection, table_name, schema=None, **kw):
        """Drop a table from the database."""
        schema = schema or "public"

        # Create the DROP TABLE statement
        drop_stmt = f'DROP TABLE IF EXISTS "{schema}"."{table_name}"'

        # Execute the statement
        connection.execute(drop_stmt)
        return True


class PGLiteEngine(Engine):
    def __init__(self, widget):
        self.widget = widget
        self.dialect = PGLiteDialect()
        self.url = None
        self._compiled_cache = {}
        self.dialect.server_version_info = (16, 4) #Hack

    def connect(self):
        return PGLiteConnection(self)

    def execution_options(self, **opt):
        return self

    def begin(self):
        return self.connect().begin()

    def _execute_context(
        self, dialect, constructor, statement, parameters, *args, **kw
    ):
        """Custom execute context method to handle compilation."""
        connection = self.connect()
        try:
            if not isinstance(statement, str):
                compiled = statement.compile(dialect=self.dialect)
                statement = str(compiled)
                if parameters is None:
                    parameters = compiled.params
            return connection.execute(statement, parameters)
        finally:
            connection.close()

class PGLiteConnection(Connection):
    def __init__(self, engine):

        self.engine = engine
        self.widget = engine.widget
        self._active_transaction = None
        self._closed = False
        self.dialect = engine.dialect
        self._inspector = None
        self._execution_options = {}

    def _form_result(self, result):
        """Create a response object from a query."""
        if result["status"] != "completed":
            logger.error(f"Query failed with result: {result}")
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

    def _execute_clauseelement(
        self, elem, multiparams=None, params=None, execution_options=None
    ):
        """Execute a clause element (like a Table, Select, Insert, etc.)."""
        if multiparams is not None or params is not None:
            # If parameters are provided, use them
            return self.execute(elem, multiparams or params, execution_options)
        else:
            # Otherwise, just execute the element
            return self.execute(elem, execution_options=execution_options)

    def _execute_compiled(self, compiled, parameters, **kwargs):
        """Execute a compiled SQL statement with parameters."""
        if parameters is not None:
            # Here you would normally bind parameters, but for simplicity:
            statement = str(compiled)
            return self.execute(statement, parameters)
        else:
            return self.execute(str(compiled))

    def _handle_dbapi_exception(self, e, statement, parameters, cursor, context):
        """Handle exceptions raised by the DBAPI."""
        # In a real implementation, you'd want proper error handling here
        raise e

    def __getattr__(self, name):
        # Delegate attribute access to the dialect if not found in connection
        if hasattr(self.dialect, name):
            return getattr(self.dialect, name)
        raise AttributeError(f"'PGLiteConnection' object has no attribute '{name}'")

    def _run_ddl_visitor(self, visitorcallable, element, **kwargs):
        """Run a DDL visitor on an element."""
        # Create the visitor with self as the connection
        visitor = visitorcallable(self.dialect, self)

        # Traverse the element to collect all DDL statements
        visitor.traverse(element)

        if hasattr(visitor, "collected_ddl"):
            # For each DDL statement (like CreateTable) collected by the visitor
            for stmt in visitor.collected_ddl:
                # Compile the statement using the dialect's DDL compiler
                compiled = stmt.compile(dialect=self.dialect)

                # Convert to a string and execute
                sql_string = compiled
                # sql_string = str(compiled)
                logger.debug("_run_ddl_visitor sql: {sql_string}")
                self.execute(sql_string)

    def _run_visitor(self, visitorcallable, element, **kwargs):
        """Run a visitor on an element."""
        visitorcallable(self.dialect, element, **kwargs).traverse_single(element)
        return element

    def in_transaction(self):
        """Return True if a transaction is active."""
        return (
            self._active_transaction is not None and self._active_transaction.is_active
        )

    def execute(self, statement, parameters=None, execution_options=None, *args, **kwargs):
        logger.debug(f"Preparing to execute statement of type: {type(statement)}")
        logger.debug(f"Positional arguments (args): {args}")
        logger.debug(f"Keyword arguments (kwargs): {kwargs}")

        # Handle DROP TABLE statements specifically
        if isinstance(statement, str) and statement.upper().startswith("DROP TABLE"):
            logger.debug(f"Executing DROP TABLE: {statement}")
            # Make sure your widget correctly handles this command
            result = self.widget.query(statement, autorespond=True)
            if result["status"] != "completed":
                logger.error(f"DROP TABLE failed with result: {result}")
                raise Exception(
                    f"DROP TABLE failed: {result.get('error_message', 'Unknown error')}"
                )

            # Return empty result for successful DROP TABLE
            return PGLiteResult(self, [], [])

        # Handle CREATE TABLE statements better
        if isinstance(statement, str) and statement.upper().startswith("CREATE TABLE"):
            logger.debug(f"Handling CREATE TABLE: {statement}")
            result = self.widget.query(statement, autorespond=True)
            if result["status"] != "completed":
                logger.error(f"CREATE TABLE failed with result: {result}")
                raise Exception(
                    f"CREATE TABLE failed: {result.get('error_message', 'Unknown error')}"
                )

            # Return empty result for successful CREATE TABLE
            return PGLiteResult(self, [], [])

        if isinstance(statement, quoted_name):
            # Handle quoted_name instances
            # query = statement.quote
            # TO DO - this is not gettimng handled
            logger.debug(
                f"How to handle quoted_name? Params: {parameters}; execution options: {execution_options}"
            )
            query = statement.quote
            logger.debug(f"Handled quoted_name instance: {str(statement)} /  {query}")

        elif not isinstance(statement, str):
            # Create a proper compile context with positional parameters
            compiled = statement.compile(
                dialect=self.dialect, compile_kwargs={"literal_binds": False}
            )

            # Get the SQL string
            query = compiled.statement
            logger.debug(f"Compiled to {query}")
            # query = str(compiled)
            # query = compiled[0]
            # logger.debug(f"Compiled statement to query: {query}")

            # Convert parameters to positional format
            if parameters is None and hasattr(compiled, "params"):
                parameters = compiled.params

            # Handle parameter conversion
            if parameters:
                logger.debug(f"THERE ARE PARAMETERS {parameters}")

                # query = dry_run_sql(query, parameters)
                # logger.debug(f"Modified query: {query}")
            else:
                logger.debug(f"THERE ARE NO PARAMETERS")
        else:
            query = str(statement)
            logger.debug(f"Statement is already a string: {query}")

        if query is None:
            logger.debug("Query is None after processing statement")
            return

        logger.debug(f"Executing query: {query}, {type(query)}")
        logger.debug(f"With parameters: {parameters}")
        logger.debug("Calling widget query...")
        result = self.widget.query(
            query, params=parameters, multi=False, autorespond=True
        )
        logger.debug(f"Out of widget query... {result}")
        result = self._form_result(result)
        return result

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

    # Additional methods to support sqlalchemy's inspection API
    def get_inspector(self):
        if not self._inspector:
            self._inspector = PGLiteInspector(self)
        return self._inspector

    def scalars(self, statement, parameters=None, **kwargs):
        """
        Execute a statement and return scalar results.

        This method is needed for pandas to_sql with if_exists='replace'.
        """
        result = self.execute(statement, parameters, **kwargs)
        # Return just the values, not the entire result objects
        if isinstance(result, list):
            return [
                row[0] if isinstance(row, (list, tuple)) and len(row) > 0 else row
                for row in result
            ]
        return result


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

    def _run_ddl_visitor(self, visitorcallable, element, **kwargs):
        return self.connection._run_ddl_visitor(visitorcallable, element, **kwargs)

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
        self.rowcount = len(rows)

    def __iter__(self):
        return iter(self.rows)
    
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

    def mappings(self):
        # Convert each row to a dictionary using columns as keys
        return [dict(zip(self.columns, row)) for row in self.rows]


# Version-independent inspection registration
# Check SQLAlchemy version and use the appropriate method for registering inspection
SQLALCHEMY_VERSION = tuple(int(x) for x in sqlalchemy.__version__.split("."))

# For older versions of SQLAlchemy
if hasattr(inspect, "_inspects"):

    @inspect._inspects(PGLiteConnection)
    def _inspect_pglite_connection(conn):
        return conn.get_inspector()


# For SQLAlchemy 1.4+
elif hasattr(sqlalchemy, "inspection"):

    @sqlalchemy.inspection._inspects(PGLiteConnection)
    def _inspect_pglite_connection(conn):
        return conn.get_inspector()


# For very old versions - just define the function without decorator
else:

    def _inspect_pglite_connection(conn):
        return conn.get_inspector()

    # Try to manually register if possible
    try:
        # This is a fallback that may work in some versions
        sqlalchemy.inspection._registrars[PGLiteConnection] = _inspect_pglite_connection
    except (AttributeError, NameError):
        # If all else fails, we'll just rely on the get_inspector method
        pass


def create_engine(widget):
    """Create a SQLAlchemy engine from a postgresWidget."""
    if PLATFORM == "emscripten":
        display(
            "SQLAlchemy connections not currently available on emscripten platforms."
        )
        return
    return PGLiteEngine(widget)
