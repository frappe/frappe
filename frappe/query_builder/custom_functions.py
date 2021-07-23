from pypika import functions as fn
from pypika.utils import builder



class GROUP_CONCAT(fn.DistinctOptionFunction):
	def __init__(self, col, alias=None):
		super(GROUP_CONCAT, self).__init__("GROUP_CONCAT", col, alias=alias)


class STRING_AGG(fn.DistinctOptionFunction):
	def __init__(self, col, val=",", alias=None):
		super(STRING_AGG, self).__init__("STRING_AGG", col, val, alias=alias)

class Match(fn.DistinctOptionFunction):
	def __init__(self, col, *args, **kwargs):
		alias = kwargs.get("alias")
		super(Match, self).__init__(" MATCH", col, *args, alias=alias)
		self._Against = False

	def get_function_sql(self, **kwargs):
		s = super(fn.DistinctOptionFunction, self).get_function_sql(**kwargs)

		# n = len(self.name) + 1
		if self._Against:
			return s + f" AGAINST ('+{self._Against}*' IN BOOLEAN MODE)"
		return s

	@builder
	def Against(self, b):
		self._Against = b


class TO_TSVECTOR(fn.DistinctOptionFunction):
	def __init__(self, col, *args, **kwargs):
		alias = kwargs.get("alias")
		super(TO_TSVECTOR, self).__init__("TO_TSVECTOR", col, *args, alias=alias)
		self._PLAINTO_TSQUERY = False

	def get_function_sql(self, **kwargs):
		s = super(fn.DistinctOptionFunction, self).get_function_sql(**kwargs)

		# n = len(self.name) + 1
		if self._PLAINTO_TSQUERY:
			return s + f" @@ PLAINTO_TSQUERY('{self._PLAINTO_TSQUERY}')"
		return s

	@builder
	def Against(self, b):
		self._PLAINTO_TSQUERY = b
