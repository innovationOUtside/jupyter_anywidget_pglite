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

Close the panel (i.e. "disconnect" the database):

```python
# Either close the panel directly or run:
w.close()
```

## TO DO

- currently the database is ephemeral / not persistent; add option to use browser storage;
- functions to nicely process the response from the database;
- options to display outputs in the panel;
- how to handle lots on inputs?
- button to clear input history;
- button to reset database;
- explore possibility of a JuptyerLab extension to load `pglite` "centrally" and then connect to the same instance from any notebook.
