import pypika.terms
from pypika import *
from pypika import Field
from pypika.utils import ignore_copy

from frappe.query_builder.terms import ParameterizedFunction, ParameterizedValueWrapper
from frappe.query_builder.utils import (
	Column,
	DocType,
	get_qb_engine,
	get_query_builder,
	patch_query_aggregation,
	patch_query_execute,
)

pypika.terms.ValueWrapper = ParameterizedValueWrapper
pypika.terms.Function = ParameterizedFunction

# * Overrides the field() method and replaces it with the a `PseudoColumn` 'field' for consistency
pypika.queries.Selectable.__getattr__ = ignore_copy(lambda table, x: Field(x, table=table))
pypika.queries.Selectable.__getitem__ = ignore_copy(lambda table, x: Field(x, table=table))
pypika.queries.Selectable.field = pypika.terms.PseudoColumn("field")
