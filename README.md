# jupyter_anywidget_pglite

Jupyter [`anywidget`](https://anywidget.dev/) and magic for working with [`pglite`](https://github.com/electric-sql/pglite) (single use postgres wasm build).

Install from PyPi as: `pip install jupyter_anywidget_pglite`

![Example of usage for pglite anywidget and magic](images/pglite_anywidget_magic.png)

Usage:

- import package and magic:

```python
%load_ext jupyter_anywidget_pglite
from jupyter_anywidget_pglite import pglite_panel

pg = pglite_panel()
#This should open a panel in the right-hand sidebar
# (`split-right`) by default.

# w = pglite_panel("example panel title)`
# w = pglite_panel(None, "split-bottom")`

# Headless mode (no HTML UI, works in:
# Jupyter Lab, Jupyter Notebook, VS Code w/ Jupyter notebook support)
#from jupyter_anywidget_pglite import pglite_headless
#pg = pglite_headless()

# Inline display
# Display HTML UI as initialising code cell output
# Display will be updated with consequent queries
#from jupyter_anywidget_pglite import pglite_inline
#pg = pglite_inline()
```

To persist the database in browser storage, set the `idb='DBNAME`` parameter when creating a widget. For example:

`pg_headless_persist = pglite_headless(idb="pglitetest1")`

To run a query, place the query insde a `%%pglite` cell block magic.

- use the `-w / --widget-name` setting to set the widget within the magic and it does not need to be passed again (for example, `%%pglite -w pg`)
- alternatively, prior to calling the block magic, set the widget used in the magic via a line magic: `%setwidget pg`

Running queries on the database using IPython cell block magic `%%pglite WIDGET_VARIABLE`:

```python
%%pglite_magic -w pg
CREATE TABLE IF NOT EXISTS test  (
        id serial primary key,
        title varchar not null
      );

#----
%%pglite_magic
INSERT INTO test (title) VALUES ('dummy');

#----
%%pglite_magic
SELECT * FROM test;

```

To run multiple SQL statements in the same cell, use the `-m / --multiple-statements` flag (default: `False`) when calling the cell block magic. This will naively split the query on each `;` character, and then run each split item as a separate command. The response will be set to the response from the final query.

Having made a query onto the database via a magic cell, we can retrieve the response:

```python
pg.response
```

If `pandas` is installed, we can get rows returned from a query response as a dataframe:

`pg.df()`

Close the panel (i.e. "disconnect" the database):

```python
# Either close the panel directly or run:
w.close()
```

## TO DO

- options to display outputs in the panel;
- how to handle lots on inputs?
- button to clear input history;
- button to reset database;
- explore possibility of a JuptyerLab extension to load `pglite` "centrally" and then connect to the same instance from any notebook.
