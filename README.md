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

This should open a panel in the right-hand sidebar (`split-right`) by default:

Running queries on the database using IPython cell block magic `%%pglite WIDGET_VARIABLE`:

```python
%%pglite_magic pg
CREATE TABLE IF NOT EXISTS test  (
        id serial primary key,
        title varchar not null
      );

#----
%%pglite_magic pg
INSERT INTO test (title) VALUES ('dummy');

#----
%%pglite_magic pg
SELECT * FROM test;

```

*Currently, it seems as if you can only run one instrcution at a time / per magic cell.*

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
