# This file provided by the anywidgets generator

import importlib.metadata
import pathlib

import anywidget
import traitlets
import sys

from IPython.display import display


try:
    import pandas as pd
except:
    pass

try:
    __version__ = importlib.metadata.version("jupyter_anywidget_pglite")
except importlib.metadata.PackageNotFoundError:
    __version__ = "unknown"


class postgresWidget(anywidget.AnyWidget):
    _css = pathlib.Path(__file__).parent / "static" / "postgres.css"
    _esm = pathlib.Path(__file__).parent / "static" / "postgres.js"
    # Create a traitlet for the code content
    code_content = traitlets.Unicode("").tag(sync=True)
    response = traitlets.Dict().tag(sync=True)
    headless = traitlets.Bool(False).tag(sync=True)
    multiline = traitlets.Unicode("").tag(sync=True)
    idb = traitlets.Unicode("").tag(sync=True)

    def __init__(self, headless=False, idb="", **kwargs):
        super().__init__(**kwargs)
        self.headless = headless
        self.idb = ""
        if idb:
            self.idb = idb if idb.startswith("idb://") else f"idb://{idb}"

    def set_code_content(self, value, split=""):
        self.multiline = split
        self.code_content = value

    def df(self):
        response = self.response["rows"]
        if "pandas" in sys.modules:
            _df = pd.DataFrame.from_records(response, index="id")
            return _df
        display("pandas not available...")
        return response

from .magics import PGliteMagic

def load_ipython_extension(ipython):
    ipython.register_magics(PGliteMagic)


def pglite_headless(idb=""):
    widget_ = postgresWidget(headless=True, idb=idb)
    display(widget_)
    return widget_

def pglite_inline(idb=""):
    widget_ = postgresWidget(idb=idb)
    display(widget_)
    return widget_

from functools import wraps


# Create a decorator to simplify panel autolaunch
# First parameter on decorated function is optional title
# Second parameter on decorated function is optional anchor location
# Via Claude.ai
def create_panel(widget_class):
    from sidecar import Sidecar

    @wraps(widget_class)
    def wrapper(title=None, anchor="split-right", idb=""):
        if title is None:
            title = f"{widget_class.__name__[:-6]} Output"  # Assuming widget classes end with 'Widget'

        widget_ = widget_class()
        widget_.sc = Sidecar(title=title, anchor=anchor)

        with widget_.sc:
            display(widget_)

        # Add a close method to the widget
        def close():
            widget_.sc.close()

        widget_.close = close

        return widget_
        # We can then close the panel as sc.

    return wrapper


# Launch with custom title as: pglite_panel("PGlite")
# Use second parameter for anchor
@create_panel
def pglite_panel(title=None, anchor=None, idb=""):
    return postgresWidget(idb=idb)
