# This file provided by the anywidgets generator

import importlib.metadata
import pathlib

import anywidget
import traitlets
import sys
import warnings

import base64
import os
from pathlib import Path
import time

from IPython.display import display

import platform

PLATFORM = platform.system().lower()

try:
    from jupyter_ui_poll import ui_events

    WAIT_AVAILABLE = True
except:
    warnings.warn(
        "You must install jupyter_ui_poll if you want to return cell responses / blocking waits (not JupyerLite); install necessary packages then restart the notebook kernel:%pip install jupyter_ui_poll"
    )
    WAIT_AVAILABLE = False


# Make pandas a requirement
import pandas as pd

try:
    __version__ = importlib.metadata.version("jupyter_anywidget_pglite")
except importlib.metadata.PackageNotFoundError:
    __version__ = "unknown"

AVAILABLE_EXTENSIONS = ["fuzzystrmatch", "pg_trgm", "vector", "tablefunc", "isn"]


def load_datadump_from_file(file_path):

    # Open the file and read its content
    with open(file_path, "rb") as f:
        file_content = f.read()

    if file_path.endswith(".tar.gz") or file_path.endswith(".tgz"):
        file_type = "application/x-gzip"
    else:
        file_type = "application/octet-stream"

    # Get the file metadata
    file_info = {
        "name": os.path.basename(file_path),
        "size": os.path.getsize(file_path),
        "type": file_type,
        "lastModified": int(
            os.path.getmtime(file_path) * 1000
        ),  # Convert to milliseconds like JS
    }

    # Encode the file content as base64 (if you need to serialize it as a string)
    file_content_encoded = base64.b64encode(file_content).decode("utf-8")

    # Recreate the file_package dictionary
    file_package = {
        "file_info": file_info,
        "file_content": file_content_encoded,  # If you need to send it as a string, use base64
    }

    return file_package


class postgresWidget(anywidget.AnyWidget):
    _css = str(pathlib.Path(__file__).parent / "static" / "postgres.css")
    _esm = str(pathlib.Path(__file__).parent / "static" / "postgres.js")
    # Create a traitlet for the code content
    about = traitlets.Dict().tag(sync=True)
    code_content = traitlets.Unicode("").tag(sync=True)
    extensions = traitlets.List().tag(sync=True)
    response = traitlets.Dict().tag(sync=True)
    headless = traitlets.Bool(False).tag(sync=True)
    multiline = traitlets.Unicode("").tag(sync=True)
    multiexec = traitlets.Bool(False).tag(sync=True)
    datadump = traitlets.Unicode("").tag(sync=True)
    tarball = traitlets.Bytes(b"").tag(sync=True)
    idb = traitlets.Unicode("").tag(sync=True)
    file_package = traitlets.Dict().tag(sync=True)
    audio = traitlets.Bool(False).tag(sync=True)

    # file_info = traitlets.Dict().tag(sync=True)
    # file_content = traitlets.Unicode().tag(sync=True)
    def __init__(self, headless=False, idb="", data=None, extensions=None, **kwargs):
        super().__init__(**kwargs)
        self.response = {
            "status": "initialising",
        }
        self.headless = headless
        self.prefer_use_dataframe = False
        self.prefer_use_blocking = PLATFORM != "emscripten"  # False
        self.idb = ""
        if idb:
            self.idb = idb if idb.startswith("idb://") else f"idb://{idb}"
        self.extensions = extensions if extensions else []
        self.file_package = {}
        if isinstance(data, (str, Path)):
            p = Path(data)
            if p.exists() and p.is_file():
                data = load_datadump_from_file(data)
        # Could have more checks here about data validity
        if data:
            if (
                isinstance(data, dict)
                and "file_info" in data
                and "file_content" in data
            ):
                self.file_package = data
            else:
                display("That doesn't seem to be a valid datadump / datadump file")

    def _wait(self, timeout, conditions=("status", "completed")):
        if not WAIT_AVAILABLE or conditions[0] not in self.response:
            # No wait condition available
            return

        start_time = time.time()
        with ui_events() as ui_poll:
            while (self.response[conditions[0]] != conditions[1]) & (
                self.response["status"] != "error"
            ):
                ui_poll(10)
                if timeout and time.time() - start_time > timeout:
                    raise TimeoutError(
                        "Action not completed within the specified timeout."
                    )
                time.sleep(0.1)
        if self.response["status"] == "error":
            warnings.warn(self.response["error_message"])
        return

    def ready(self, timeout=5):
        self._wait(timeout, ("status", "ready"))

    def query(self, query, multi=False, autorespond=None, timeout=5, df=None):
        # The multi=True setting implies there are multiple query statements
        # If multi=True, we get mulitple response objects in a list
        # If multi=False, we get a single response object as a dict
        # Only multi=False can be used to return a dataframe
        # The autorespond will try to wait
        # The df return will only apply if wait is available
        if multi is not None:
            self.multiexec = multi
        self.set_code_content(query)
        autorespond = self.prefer_use_blocking if autorespond is None else autorespond
        df = self.prefer_use_dataframe if df is None else df
        if autorespond:
            timeout = timeout if timeout > 0 else 5
            response = self.blocking_reply(timeout)
            if df:
                response = self.df()
            return response

    def table_results(self):
        return [t["table_name"] for t in self.response["response"]["rows"]]

    def tables(self, autorespond=None, timeout=5):
        autorespond = self.prefer_use_blocking if autorespond is None else autorespond
        _tables = self.query(
            "SELECT * FROM information_schema.tables WHERE table_type = 'BASE TABLE' AND table_schema = 'public'",
            autorespond=autorespond,
            timeout=timeout,
        )

        if autorespond:
            return [t["table_name"] for t in _tables["response"]["rows"]]
        else:
            display("No autoresponse available. View results in response using .table_results()")

    def table_schema(self, table, autorespond=None, timeout=5):
        autorespond = self.prefer_use_blocking if autorespond is None else autorespond
        table_schema_query = f"""
    SELECT 
        column_name,
        data_type,
        character_maximum_length,
        is_nullable,
        column_default
    FROM 
        information_schema.columns
    WHERE 
        table_name = '{table}'
        AND table_schema = 'public';
    """

        _schema = self.query(
            table_schema_query,
            autorespond=autorespond,
            timeout=timeout,
        )
        if autorespond:
            return _schema
        else:
            display(
                "No autoresponse available. View response using .response() "
            )

    def set_code_content(self, value, split=""):
        self.multiline = split
        self.response = {"status": "processing"}
        self.code_content = ""
        self.code_content = value

    # Need to guard this out in JupyterLite (definitely in pyodide)
    def blocking_reply(self, timeout=None):
        self._wait(timeout)
        return self.response

    def create_data_dump(self, wait=False, timeout=None):
        self.datadump = ""
        self.datadump = "generate_dump"
        self.response = {"status": "generating_datadump"}
        if wait or timeout:
            self._wait(timeout, ("status", "datadump_ready"))

    def df(self, index="_id"):
        response = self.response["response"]
        if "pandas" in sys.modules:
            # TO DO - need to handle the multiresponse...
            # n The following only handles the simple, non-multi-response
            if isinstance(response, dict):
                # Extracting column names from the 'fields' list
                columns = [field["name"] for field in response["fields"]]
                # TO DO: types are also available if we have a lookup table...
                # Get the data rows
                data = self.response["response"]["rows"]
                # Create the dataframe
                if index and index in data:
                    _df = pd.DataFrame.from_records(data, columns=columns, index="id")
                else:
                    _df = pd.DataFrame.from_records(data, columns=columns)
                return _df
            display("pandas not available...")
        return response

    # Via ChatGPT
    def save_datadump_to_file(self, filename=""):
        d = self.file_package
        if d and "file_info" in d and "file_content" in d:
            # Extract the file info
            file_info = d["file_info"]
            file_name = filename if filename else file_info["name"]
            file_size = file_info["size"]
            file_type = file_info["type"]
            file_content = d["file_content"]

            # Decode the file content if it's base64-encoded
            try:
                file_data = base64.b64decode(file_content)
            except Exception:
                file_data = file_content  # If it's already binary data

            display(f"Saving as {file_name}")
            # Write the content to a file
            with open(file_name, "wb") as f:
                f.write(file_data)

            return file_name

    def insert_from_df(self, table, df, autorespond=None, timeout=5, debug=False):
        # Validate the DataFrame
        if not isinstance(df, pd.DataFrame):
            raise TypeError(f"'You need to provide data as a pandas DataFrame")

        # TO DO: test whether table exists
        # Generate the SQL statement
        columns = ", ".join(df.columns)
        values = ",\n    ".join(
            [
                f"({', '.join(repr(value) for value in row)})"
                for row in df.itertuples(index=False, name=None)
            ]
        )
        sql = f"INSERT INTO {table} ({columns})\nVALUES\n{values};"
        if debug:
            display(sql)
        # return sql  # self._run_query(args, sql)
        return self.query(sql, autorespond=autorespond, timeout=timeout)


from .magics import PGliteMagic


def load_ipython_extension(ipython):
    ipython.register_magics(PGliteMagic)


def pglite_headless(idb="", data=None, **kwargs):
    data = data if data else {}
    widget_ = postgresWidget(headless=True, idb=idb, data=data, **kwargs)
    display(widget_)
    return widget_


def pglite_inline(idb="", data=None, **kwargs):
    data = data if data else {}
    widget_ = postgresWidget(idb=idb, data=data, **kwargs)
    display(widget_)
    return widget_


from functools import wraps


# Create a decorator to simplify panel autolaunch
# First parameter on decorated function is optional title
# Second parameter on decorated function is optional anchor location
# Via Claude.ai


def create_panel(func):
    try:
        from sidecar import Sidecar
    except:
        warnings.warn(
            "Missing package (sidecar): run `pip install sidecar` before trying to access the panel."
        )

    @wraps(func)
    def wrapper(title=None, anchor="split-right", *args, **kwargs):
        if title is None:
            title = f"{func.__name__[:-6]} Output"  # Assuming function names end with '_panel'

        widget_ = func(*args, **kwargs)
        widget_.sc = Sidecar(title=title, anchor=anchor)

        with widget_.sc:
            display(widget_)

        # Add a close method to the widget
        def close():
            widget_.sc.close()

        widget_.close = close

        return widget_

    return wrapper


@create_panel
def pglite_panel(idb="", data=None, **kwargs):
    data = data if data else {}
    return postgresWidget(idb=idb, data=data, **kwargs)
