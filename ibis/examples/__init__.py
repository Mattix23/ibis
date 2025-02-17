from __future__ import annotations

import json
import os
from typing import TYPE_CHECKING, Optional

import ibis
from ibis.common.grounds import Concrete

try:
    import importlib_resources as resources
except ImportError:
    from importlib import resources

if TYPE_CHECKING:
    import ibis.expr.types as ir
    from ibis.backends.base import BaseBackend

_EXAMPLES = None

_METADATA = json.loads(resources.files(__name__).joinpath("metadata.json").read_text())

# These backends load the data directly using `read_csv`/`read_parquet`. All
# other backends load the data using pyarrow, then passing it off to
# `create_table`.
_DIRECT_BACKENDS = frozenset({"duckdb", "polars"})


class Example(Concrete):
    descr: Optional[str]
    key: str

    def fetch(
        self,
        *,
        table_name: str | None = None,
        backend: BaseBackend | None = None,
    ) -> ir.Table:
        path = _EXAMPLES.fetch(self.key, progressbar=True)

        if backend is None:
            backend = ibis.get_backend()

        if table_name is None:
            table_name = ibis.util.gen_name(f"examples_{type(self).__name__}")

        if backend.name in _DIRECT_BACKENDS:
            # Read directly into these backends. This helps reduce memory
            # usage, making the larger example datasets easier to work with.
            if path.endswith(".parquet"):
                return backend.read_parquet(path, table_name=table_name)
            else:
                return backend.read_csv(path, table_name=table_name)
        else:
            if path.endswith(".parquet"):
                import pyarrow.parquet

                table = pyarrow.parquet.read_table(path)
            else:
                import pyarrow.csv

                # The convert options lets pyarrow treat empty strings as null for
                # string columns, but not quoted empty strings.
                table = pyarrow.csv.read_csv(
                    path,
                    convert_options=pyarrow.csv.ConvertOptions(
                        strings_can_be_null=True,
                        quoted_strings_can_be_null=False,
                    ),
                )

                # All null columns are inferred as null-type, but not all
                # backends support null-type columns. Cast to an all-null
                # string column instead.
                for i, field in enumerate(table.schema):
                    if pyarrow.types.is_null(field.type):
                        table = table.set_column(i, field.name, table[i].cast("string"))

            # TODO: It should be possible to avoid this memtable call, once all
            # backends support passing a `pyarrow.Table` to `create_table`
            # directly.
            obj = ibis.memtable(table)
            return backend.create_table(table_name, obj, temp=True, overwrite=True)


_FETCH_DOCSTRING_TEMPLATE = """\
Fetch the {name} example.

Parameters
----------
table_name
    The table name to use, defaults to a generated table name.
backend
    The backend to load the example into. Defaults to the default backend.

Returns
-------
ir.Table
    Table expression

Examples
--------
>>> import ibis
>>> t = ibis.examples.{name}.fetch()
"""


def __dir__() -> list[str]:
    return sorted(_METADATA.keys())


def __getattr__(name: str) -> Example:
    global _EXAMPLES  # noqa: PLW0603

    if _EXAMPLES is None:
        import pooch

        _EXAMPLES = pooch.create(
            path=pooch.os_cache("ibis-framework"),
            # the trailing slash matters here
            base_url="https://storage.googleapis.com/ibis-examples/data/",
            version=ibis.__version__,
            env="IBIS_EXAMPLES_DATA",
        )
        with resources.files(__name__).joinpath("registry.txt").open(mode="r") as _f:
            _EXAMPLES.load_registry(_f)

    spec = _METADATA.get(name, {})

    if (key := spec.get("key")) is None:
        raise AttributeError(name)

    description = spec.get("description")

    _, ext = key.split(os.extsep, maxsplit=1)

    fields = {"__doc__": description} if description is not None else {}

    example_class = type(name, (Example,), fields)
    example_class.fetch.__doc__ = _FETCH_DOCSTRING_TEMPLATE.format(name=name)
    example = example_class(descr=description, key=key)
    setattr(ibis.examples, name, example)
    return example
