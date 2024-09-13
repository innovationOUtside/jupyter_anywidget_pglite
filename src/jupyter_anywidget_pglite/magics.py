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

    def _run_query(self, args, q):
        if args.widget_name:
            self._set_widget(args.widget_name)
        splitter = ";" if args.multiple_statements else ""
        if self.widget is None:
            print(
                "Error: No widget / widget name set. Use %set_myAnywidget_object first to set the name."
            )
            return
        elif q:
            # Get the actual widget
            w = self.widget
            w.multiexec = args.multiple_statement_block
            w.set_code_content(q, split=splitter)
            autorespond = bool(args.timeout or args.response)
            if autorespond:
                timeout = args.timeout if args.timeout > 0 else 5
                return w.blocking_reply(timeout)
        return

    @line_magic
    def setwidget(self, line):
        """Set the object name to be used in subsequent myAnywidget_magic calls."""
        self._set_widget(line)

    @line_magic
    @magic_arguments()
    @argument("-w", "--widget-name", type=str, help="widget variable name")
    @argument(
        "-r",
        "--response",
        action="store_true",
        help="Provide response from cell (not JupyterLite)",
    )
    @argument(
        "-t",
        "--timeout",
        type=float,
        default=0,
        help="timeout period on blocking response (default: 5)",
    )
    @argument(
        "-m",
        "--multiple-statements",
        action="store_true",
        help="Allow naive `;` separated multiple statements",
    )
    @argument(
        "-M",
        "--multiple-statement-block",
        action="store_true",
        help="Use exec to execute multiple statements",
    )
    @argument("-q", "--query", type=str, help="SQL query")
    def pglite_query(self, line):
        args = parse_argstring(self.pglite_query, line)
        # The query is returned as wrapped string
        return self._run_query(args, args.query.strip("'\""))

    @cell_magic
    @magic_arguments()
    @argument("-w", "--widget-name", type=str, help="widget variable name")
    @argument(
        "-m",
        "--multiple-statements",
        action="store_true",
        help="Allow naive `;` separated multiple statements",
    )
    @argument(
        "-M",
        "--multiple-statement-block",
        action="store_true",
        help="Use exec to execute multiple statements",
    )
    @argument("-r", "--response", action="store_true", help="Provide response from cell (not JupyterLite)")
    @argument("-t", "--timeout", type=float, default=0, help="timeout period on blocking response (default: 5)")
    def pglite_magic(self, line, cell):
        args = parse_argstring(self.pglite_magic, line)
        return self._run_query(args, cell)

## %load_ext jupyter_anywidget_pglite
## Usage: %%pglite_magic x [where x is the widget object ]


# TO DO - can we generalise how we set names?

"""
  def set_attribute(self, name, value):
    setattr(self, name, value)
"""
