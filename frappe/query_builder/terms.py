from typing import Any, Dict, Optional

from pypika.terms import Function, ValueWrapper
from pypika.utils import format_alias_sql


class NamedParameterWrapper():
	def __init__(self, parameters: Dict[str, Any]):
		self.parameters = parameters

	def update_parameters(self, param_key: Any, param_value: Any, **kwargs):
		self.parameters[param_key[2:-2]] = param_value

	def get_sql(self, **kwargs):
		return f'%(param{len(self.parameters) + 1})s'


class ParameterizedValueWrapper(ValueWrapper):
	def get_sql(self, quote_char: Optional[str] = None, secondary_quote_char: str = "'", param_wrapper= None, **kwargs: Any) -> str:
		if param_wrapper is None:
			sql = self.get_value_sql(quote_char=quote_char, secondary_quote_char=secondary_quote_char, **kwargs)
			return format_alias_sql(sql, self.alias, quote_char=quote_char, **kwargs)
		else:
			value_sql = self.get_value_sql(quote_char=quote_char, **kwargs) if not isinstance(self.value,int) else self.value
			param_sql = param_wrapper.get_sql(**kwargs)
			param_wrapper.update_parameters(param_key=param_sql, param_value=value_sql, **kwargs)
		return format_alias_sql(param_sql, self.alias, quote_char=quote_char, **kwargs)


class ParameterizedFunction(Function):
	def get_sql(self, **kwargs: Any) -> str:
		with_alias = kwargs.pop("with_alias", False)
		with_namespace = kwargs.pop("with_namespace", False)
		quote_char = kwargs.pop("quote_char", None)
		dialect = kwargs.pop("dialect", None)
		param_wrapper = kwargs.pop("param_wrapper", None)

		function_sql = self.get_function_sql(with_namespace=with_namespace, quote_char=quote_char, param_wrapper=param_wrapper, dialect=dialect)

		if self.schema is not None:
			function_sql = "{schema}.{function}".format(
				schema=self.schema.get_sql(quote_char=quote_char, dialect=dialect, **kwargs),
				function=function_sql,
			)

		if with_alias:
			return format_alias_sql(function_sql, self.alias, quote_char=quote_char, **kwargs)

		return function_sql
