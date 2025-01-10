# ---------
# DBAPI2 wrapper via claude.ai
from IPython.display import display
import platform

PLATFORM = platform.system().lower()

class PGLiteCursor:
    def __init__(self, widget):
        self.widget = widget
        self.description = None
        self.rowcount = -1
        self._rows = None
        self._current_row = 0

    def execute(self, operation, parameters=None):
        """Execute a database operation (query or command)."""
        if parameters:
            # TODO: Implement parameter substitution
            # Could use psycopg2.sql.SQL for proper escaping
            pass

        result = self.widget.query(operation, multi=False, autorespond=True)

        if result["status"] == "completed":
            if result["response_type"] == "single":
                query_result = result["response"]
                self._rows = query_result["rows"]
                self.rowcount = query_result.get("affectedRows", len(self._rows))

                # Set description based on column info
                if "fields" in query_result:
                    self.description = [
                        (
                            field["name"],
                            field.get("dataTypeID"),
                            None,
                            None,
                            None,
                            None,
                            None,
                        )
                        for field in query_result["fields"]
                    ]
            else:
                # For multi-statement queries, we'll use only the last result
                # as that's what pandas typically expects
                query_result = result["response"][-1]
                self._rows = query_result["rows"]
                self.rowcount = query_result.get("affectedRows", len(self._rows))

                if "fields" in query_result:
                    self.description = [
                        (
                            field["name"],
                            field.get("dataTypeID"),
                            None,
                            None,
                            None,
                            None,
                            None,
                        )
                        for field in query_result["fields"]
                    ]
        else:
            # Handle error case
            self._rows = []
            self.rowcount = 0
            self.description = None
            raise Exception(
                f"Query failed: {result.get('error_message', 'Unknown error')}"
            )

        return self

    def fetchone(self):
        """Fetch the next row of a query result set."""
        if not self._rows or self._current_row >= len(self._rows):
            return None
        row = self._rows[self._current_row]
        self._current_row += 1
        return tuple(row.values())  # Convert dict to tuple of values

    def fetchall(self):
        """Fetch all remaining rows of a query result set."""
        if not self._rows:
            return []
        remaining = self._rows[self._current_row :]
        self._current_row = len(self._rows)
        return [tuple(row.values()) for row in remaining]  # Convert dicts to tuples

    def fetchmany(self, size=None):
        """Fetch the next set of rows of a query result set."""
        if not self._rows:
            return []
        if size is None:
            size = self.arraysize if hasattr(self, "arraysize") else 1
        end = min(self._current_row + size, len(self._rows))
        rows = self._rows[self._current_row : end]
        self._current_row = end
        return [tuple(row.values()) for row in rows]  # Convert dicts to tuples

    def close(self):
        """Close the cursor."""
        self._rows = None
        self._current_row = 0


class PGLiteConnection:
    def __init__(self, widget):
        """Initialize with a postgresWidget instance."""
        self.widget = widget
        self._closed = False

    def cursor(self):
        """Return a new Cursor Object using the connection."""
        if self._closed:
            raise Exception("Connection is closed")
        return PGLiteCursor(self.widget)

    def commit(self):
        """Commit any pending transaction."""
        if self._closed:
            raise Exception("Connection is closed")
        self.widget.query("COMMIT", autorespond=True)

    def rollback(self):
        """Rollback pending transaction."""
        if self._closed:
            raise Exception("Connection is closed")
        self.widget.query("ROLLBACK", autorespond=True)

    def close(self):
        """Close the connection."""
        if not self._closed:
            self._closed = True

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# Helper function to create a connection
def create_connection(widget):
    """Create a DB-API 2.0 compliant connection from a postgresWidget."""
    if PLATFORM=="emscripten":
        display("DBAPI2 connections not currently available on emscripten platforms.")
        return
    return PGLiteConnection(widget)
