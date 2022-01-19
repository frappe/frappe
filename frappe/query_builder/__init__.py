from frappe.query_builder.terms import ParameterizedValueWrapper, ParameterizedFunction
import pypika

pypika.terms.ValueWrapper = ParameterizedValueWrapper
pypika.terms.Function = ParameterizedFunction

from pypika import *
from frappe.query_builder.utils import DocType, get_query_builder, patch_query_execute
