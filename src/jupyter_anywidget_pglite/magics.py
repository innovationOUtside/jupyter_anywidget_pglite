from IPython.core.magic import Magics, magics_class, cell_magic, line_magic
from IPython.core.magic_arguments import argument, magic_arguments, parse_argstring

@magics_class
class PGliteMagic(Magics):
    def __init__(self, shell):
        super(PGliteMagic, self).__init__(shell)
        self.widget_name = (
            None  # Store the widget variable name as an instance attribute
        )
        self.widget = None

    def _set_widget(self, w_name=""):
        w_name = w_name.strip()
        if w_name:
            self.widget_name = w_name
        self.widget = self.shell.user_ns[self.widget_name]
        # Perhaps add a test that it is a widget type, else None?
        # print(f"pglite_magic object set to: {self.widget_name}")

    @line_magic
    def setwidget(self, line):
        """Set the object name to be used in subsequent myAnywidget_magic calls."""
        self._set_widget(line)

    @cell_magic
    @magic_arguments()
    @argument("-w", "--widget-name", type=str, help="widget variable name")
    def pglite_magic(self, line, cell):
        args = parse_argstring(self.pglite_magic, line)
        if args.widget_name:
            self._set_widget(args.widget_name)
        if self.widget is None:
            print(
                "Error: No widget / widget name set. Use %set_myAnywidget_object first to set the name."
            )
            return
        elif cell:
            # Get the actual widget
            w = self.widget
            w.set_code_content(cell)
            # The w.response is the previous state so we can't return it

## %load_ext jupyter_anywidget_pglite
## Usage: %%pglite_magic x [where x is the widget object ]


# TO DO - can we generalise how we set names?

"""
  def set_attribute(self, name, value):
    setattr(self, name, value)
"""
