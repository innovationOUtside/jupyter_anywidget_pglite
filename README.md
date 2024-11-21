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
# Close the panel either manually or via:
# pg.close()

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

Use `pg.ready()` / `pg.ready(timeout=TIME_IN_S)` function that will block until the `pglite` widget is loaded and ready to accept requests *(not JupyterLite)*.

## Persisting data in browser storage

To persist the database in browser storage, set the `idb='DBNAME`` parameter when creating a widget. For example:

`pg_headless_persist = pglite_headless(idb="pglitetest1")`

## Running queries

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

To run multiple SQL statements in the same cell:

- use the `-m / --multiple-statements` flag (default: `False`) when calling the cell block magic [NOT RECOMMENDED]. This will naively split the query on each `;` character, and then run each split item as a separate command. The response will be set to the response from the final query;
- use the `-M / --multiple-statement-block` flag to run all the tems using the `pglite` `.exec()` command.

We can also run queries (with the same arguments) using the `%pglite_query` line magic, with the query set via the `-q / --query` parameter:

`%pglite_query -r -q 'SELECT * FROM test LIMIT 1;'`

Having made a query onto the database via a magic cell, we can retrieve the response:

```python
pg.response
```

If `pandas` is installed, we can get rows returned from a query response as a dataframe:

`pg.df()`

Note that the `pglite` query runs asynchronously, so how do we know on the Python side when the repsonse is ready?

Using the [`jupyter_ui_poll`](https://github.com/kirill888/jupyter-ui-poll) package (*not* JupyterLite), we can run a blocking wait on a response from `pglite` *(not JupyterLite)*:

`response = pg.blocking_reply()`

Optionally provide a timeout period (seconds):

`response = pg.blocking_reply(timeout=5)`

We can also use a blocking trick to return a response from the magic cell *(not JupyterLite)*. Set `-r / --response` flag when calling the magic. Optionally set the `-t / --timeout` to the timeout period in seconds (default 5s; if the timeout is explicitly set, `-r` is assumed): `%%pglite -r`, `%pglite -t 10`

![Example showing use of pg.ready() and magic -r response flag ](images/blocking_functions.png)

*Note: I think that IPython notebook cells should have cell run IDs cleared prior to running. I have seen errors if there are non-unique cell run IDs for the blocking cell.*

## Exporting data to file / reloading from file

Save and load data to / from a file.

![example of creating a datadump , saving it to a file, and seeding a widget from it](images/datadump-handling.png)

We can get an export of the data using the `pglite` data exporter ([`.dumpdatadir()`](https://github.com/electric-sql/pglite/blob/main/docs/docs/api.md#dumpdatadir)) in the database by calling:

`pg.create_data_dump()`

For a blocking wait until the datadump is read, use `pg.create_data_dump(True)` or `pg.create_data_dump(wait=True)` (not JupyterLite). You can also pass a `timeout` parameter in seconds (`wait=True` is assumed if the timeout parameter is explicitly set).

After a moment or two, the data will appear in a dictionary on: `pg.file_package`

If we make a copy of that data, we can then create a new `pglite` widget with a new `pglite` instance that can load in the data using the `pglite` data load option ([`loadDataDir`](https://github.com/electric-sql/pglite/blob/main/docs/docs/api.md#options)).

Use the `data=` argument when creating the widget to pass in the data:

```python
datadump = pg.file_package.copy()
# View info
#datadump["file_info"]
# Actual data is in: datadump["file_content"]
pg1 = pglite_inline(data=datadump)
```

We can export the datadump to a file using:

`pg.save_datadump_to_file()`

Or pass a filename: `pg.save_datadump_to_file('myfile.tar.gz')`

Load data into a datadump object:

```python
from jupyter_anywidget_pglite import load_datadump_from_file

dd = load_datadump_from_file("pgdata.tar.gz")
dd["file_info"]
```

Or create a new widget with the `pglite` database seeded from the file:

`pg2 = pglite_panel(data="pgdata.tar.gz")`

## Audible alerts

To provide an audible alert when a query or a data dump generation operation has completed, set: `pg.audio = True`,

## TO DO

- options to display outputs in the panel;
- button to clear input history;
- button to reset database;
- explore possibility of a JuptyerLab extension to load `pglite` "centrally" and then connect to the same instance from any notebook.
