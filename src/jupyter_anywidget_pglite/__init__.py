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

try:
    from jupyter_ui_poll import ui_events
except:
    warnings.warn(
        "You must install jupyter_ui_poll if you want to return cell responses / blocking waits (not JupyerLite); install necessary packages then restart the notebook kernel:%pip install jupyter_ui_poll",
        UserWarning,
    )

try:
    import pandas as pd
except:
    pass

try:
    __version__ = importlib.metadata.version("jupyter_anywidget_pglite")
except importlib.metadata.PackageNotFoundError:
    __version__ = "unknown"


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
    _css = pathlib.Path(__file__).parent / "static" / "postgres.css"
    _esm = pathlib.Path(__file__).parent / "static" / "postgres.js"
    # Create a traitlet for the code content
    code_content = traitlets.Unicode("").tag(sync=True)
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
    def __init__(self, headless=False, idb="", data=None, **kwargs):
        super().__init__(**kwargs)
        self.response = {"status": "initialising"}
        self.headless = headless
        self.idb = ""
        if idb:
            self.idb = idb if idb.startswith("idb://") else f"idb://{idb}"
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
        start_time = time.time()
        with ui_events() as ui_poll:
            while self.response[conditions[0]] != conditions[1]:
                ui_poll(10)
                if timeout and time.time() - start_time > timeout:
                    raise TimeoutError(
                        "Action not completed within the specified timeout."
                    )
                time.sleep(0.1)
        return

    def ready(self, timeout=5):
        self._wait(timeout, ("status", "ready"))

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

    def df(self):
        response = self.response["response"]["rows"]
        if "pandas" in sys.modules:
            _df = pd.DataFrame.from_records(response, index="id")
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


from .magics import PGliteMagic


def load_ipython_extension(ipython):
    ipython.register_magics(PGliteMagic)


def pglite_headless(idb="", data=None):
    data = data if data else {}
    widget_ = postgresWidget(headless=True, idb=idb, data=data)
    display(widget_)
    return widget_


def pglite_inline(idb="", data=None):
    data = data if data else {}
    widget_ = postgresWidget(idb=idb, data=data)
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
            "Missing package (sidecar): run `pip install sidecar` before trying to access the panel.",
            UserWarning,
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
