from typing import Any, Optional, Dict
from pypika.terms import ValueWrapper
from pypika.utils import format_alias_sql


class NamedParameterWrapper():
	def __init__(self, parameters: Dict[str, Any]):
		self.parameters = parameters

	def update_parameters(self, param_key: Any, param_value: Any, **kwargs):
		self.parameters[param_key[1:]] = param_value

	def get_sql(self, **kwargs):
		return f'@param{len(self.parameters) + 1}'


class ParameterizedValueWrapper(ValueWrapper):
	def get_sql(self, quote_char: Optional[str] = None, secondary_quote_char: str = "'", param_wrapper= None, **kwargs: Any) -> str:
		if param_wrapper is None:
			sql = self.get_value_sql(quote_char=quote_char, secondary_quote_char=secondary_quote_char, **kwargs)
			return format_alias_sql(sql, self.alias, quote_char=quote_char, **kwargs)
		else:
			value_sql = self.get_value_sql(quote_char=quote_char, **kwargs)
			param_sql = param_wrapper.get_sql(**kwargs)
			param_wrapper.update_parameters(param_key=param_sql, param_value=value_sql, **kwargs)

			return format_alias_sql(param_sql, self.alias, quote_char=quote_char, **kwargs)