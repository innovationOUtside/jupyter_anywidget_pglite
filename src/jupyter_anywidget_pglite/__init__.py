# This file provided by the anywidgets generator

import importlib.metadata
import pathlib

import anywidget
import traitlets

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

    def __init__(self, headless=False, **kwargs):
        super().__init__(**kwargs)
        self.headless = headless

    def set_code_content(self, value):
        self.code_content = value


from .magics import PGliteMagic


def load_ipython_extension(ipython):
    ipython.register_magics(PGliteMagic)


def pglite_headless():
    widget_ = postgresWidget(headless=True)
    display(widget_)
    return widget_

def pglite_inline():
    widget_ = postgresWidget()
    display(widget_)
    return widget_

from functools import wraps
from sidecar import Sidecar
from IPython.display import display


# Create a decorator to simplify panel autolaunch
# First parameter on decorated function is optional title
# Second parameter on decorated function is optional anchor location
# Via Claude.ai
def create_panel(widget_class):
    @wraps(widget_class)
    def wrapper(title=None, anchor="split-right"):
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
def pglite_panel(title=None, anchor=None):
    return postgresWidget()
