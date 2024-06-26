"""Basic DB optimizer for Frappe Framework based app.

This is largely based on heuristics and known good practices for indexing.
"""

from collections import defaultdict
from dataclasses import dataclass
from typing import TypeVar

from sql_metadata import Parser

import frappe
from frappe.utils import flt

# Any index that reads more than 30% table on average is not "useful"
INDEX_SCORE_THRESHOLD = 0.3
# Anything reading less than this percent of table is considered optimal
OPTIMIZATION_THRESHOLD = 0.1

T = TypeVar("T")


@dataclass
class DBColumn:
	name: str
	cardinality: int | None
	is_nullable: bool
	default: str
	data_type: str

	@classmethod
	def from_frappe_ouput(cls, data) -> "DBColumn":
		"Parse DBColumn from output of describe-database-table command in Frappe"
		return cls(
			name=data["column"],
			cardinality=data.get("cardinality"),
			is_nullable=data["is_nullable"],
			default=data["default"],
			data_type=data["type"],
		)


@dataclass
class DBIndex:
	name: str
	column: str
	table: str
	unique: bool | None = None
	cardinality: int | None = None
	sequence: int = 1
	nullable: bool = True
	_score: float = 0.0

	def __eq__(self, other: "DBIndex") -> bool:
		return self.column == other.column and self.sequence == other.sequence and self.table == other.table

	def __repr__(self):
		return f"DBIndex(`{self.table}`.`{self.column}`)"

	@classmethod
	def from_frappe_ouput(cls, data, table) -> "DBIndex":
		"Parse DBIndex from output of describe-database-table command in Frappe"
		return cls(
			name=data["name"],
			table=table,
			unique=data["unique"],
			cardinality=data["cardinality"],
			sequence=data["sequence"],
			nullable=data["nullable"],
			column=data["column"],
		)


@dataclass
class ColumnStat:
	column_name: str
	avg_frequency: float
	avg_length: float
	nulls_ratio: float | None = None
	histogram: list[float] = None

	def __post_init__(self):
		if not self.histogram:
			self.histogram = []

	@classmethod
	def from_frappe_ouput(cls, data) -> "ColumnStat":
		return cls(
			column_name=data["column_name"],
			avg_frequency=data["avg_frequency"],
			avg_length=data["avg_length"],
			nulls_ratio=data["nulls_ratio"],
			histogram=[flt(bin) for bin in data["histogram"].split(",")] if data["histogram"] else [],
		)


@dataclass
class DBTable:
	name: str
	total_rows: int
	schema: list[DBColumn] | None = None
	indexes: list[DBIndex] | None = None

	def __post_init__(self):
		if not self.schema:
			self.schema = []
		if not self.indexes:
			self.indexes = []

	def update_cardinality(self, column_stats: list[ColumnStat]) -> None:
		"""Estimate cardinality using mysql.column_stat"""
		for column_stat in column_stats:
			for col in self.schema:
				if col.name == column_stat.column_name and not col.cardinality and column_stat.avg_frequency:
					# "hack" or "math" - average frequency is on average how frequently a row value appears.
					# Avg = total_rows / cardinality, so...
					col.cardinality = self.total_rows / column_stat.avg_frequency

	@classmethod
	def from_frappe_ouput(cls, data) -> "DBTable":
		"Parse DBTable from output of describe-database-table command in Frappe"
		table_name = data["table_name"]
		return cls(
			name=table_name,
			total_rows=data["total_rows"],
			schema=[DBColumn.from_frappe_ouput(c) for c in data["schema"]],
			indexes=[DBIndex.from_frappe_ouput(i, table_name) for i in data["indexes"]],
		)

	def has_column(self, column: str) -> bool:
		for col in self.schema:
			if col.name == column:
				return True
		return False


@dataclass
class DBOptimizer:
	query: str  # raw query in string format
	tables: dict[str, DBTable] = None
	parsed_query: Parser = None

	def __post_init__(self):
		if not self.tables:
			self.tables = {}
		self.parsed_query = Parser(self.query)

	def tables_examined(self) -> list[str]:
		return self.parsed_query.tables

	def update_table_data(self, table: DBTable):
		self.tables[table.name] = table

	def _convert_to_db_index(self, column: str) -> DBIndex:
		column_name, table = None, None

		if "." in column:
			table, column_name = column.split(".")
		else:
			column_name = column
			for table_name, db_table in self.tables.items():
				if db_table.has_column(column):
					table = table_name
					break
		return DBIndex(column=column_name, name=column_name, table=table)

	def _remove_existing_indexes(self, potential_indexes: list[DBIndex]) -> list[DBIndex]:
		"""Given list of potential index candidates remove the ones that already exist.

		This also removes multi-column indexes for parts that are applicable to query.
		Example: If multi-col index A+B+C exists and query utilizes A+B then
		A+B are removed from potential indexes.
		"""

		def remove_maximum_indexes(idx: list[DBIndex]):
			"""Try to remove entire index from potential indexes, if not possible, reduce one part and try again until no parts are left."""
			if not idx:
				return
			matched_sub_index = []
			for idx_part in list(idx):
				matching_part = [
					i for i in potential_indexes if i.column == idx_part.column and i.table == idx_part.table
				]
				if not matching_part:
					# pop and recurse
					idx.pop()
					return remove_maximum_indexes(idx)
				else:
					matched_sub_index.extend(matching_part)

			# Every part matched now, lets remove those parts
			for i in matched_sub_index:
				potential_indexes.remove(i)

		# Reconstruct multi-col index
		for table in self.tables.values():
			merged_indexes = defaultdict(list)
			for index in table.indexes:
				merged_indexes[index.name].append(index)

			for idx in merged_indexes.values():
				idx.sort(key=lambda x: x.sequence)

			for idx in merged_indexes.values():
				remove_maximum_indexes(idx)
		return potential_indexes

	def potential_indexes(self) -> list[DBIndex]:
		"""Get all columns that can potentially be indexed to speed up this query."""

		possible_indexes = []

		# Where claus columns using these operators benefit from index
		#  1. = (equality)
		#  2. >, <, >=, <=
		#  3. LIKE 'xyz%' (Prefix search)
		#  4. BETWEEN (for date[time] fields)
		#  5. IN (similar to equality)

		if not self.parsed_query.columns_dict:
			return []

		if where_columns := self.parsed_query.columns_dict.get("where"):
			# TODO: Apply some heuristics here, not all columns in where clause are actually useful
			possible_indexes.extend(where_columns)

		# Join clauses - Both sides of join should ideally be indexed. One will *usually* be primary key.
		if join_columns := self.parsed_query.columns_dict.get("join"):
			possible_indexes.extend(join_columns)

		# Top N query variant - Order by column can possibly speed up the query
		if order_by_columns := self.parsed_query.columns_dict.get("order_by"):
			if self.parsed_query.limit_and_offset:
				possible_indexes.extend(order_by_columns)

		possible_db_indexes = [self._convert_to_db_index(i) for i in possible_indexes]
		possible_db_indexes = [i for i in possible_db_indexes if i.column not in ("*", "name")]
		possible_db_indexes.sort(key=lambda i: (i.table, i.column))

		return self._remove_existing_indexes(possible_db_indexes)

	def suggest_index(self) -> DBIndex | None:
		"""Suggest best possible column to index given query and table stats."""
		if missing_tables := (set(self.tables_examined()) - set(self.tables.keys())):
			frappe.throw("DBTable infomation missing for: " + ", ".join(missing_tables))

		potential_indexes = self.potential_indexes()

		for index in list(potential_indexes):
			table = self.tables[index.table]

			# Data type is not easily indexable - skip
			column = next(c for c in table.schema if c.name == index.column)
			if "text" in column.data_type.lower() or "json" in column.data_type.lower():
				potential_indexes.remove(index)
			# Update cardinality from column so scoring can be done
			index.cardinality = column.cardinality

		for index in potential_indexes:
			index._score = self.index_score(index)

		potential_indexes.sort(key=lambda i: i._score)
		if (
			potential_indexes
			and (best_index := potential_indexes[0])
			and best_index._score < INDEX_SCORE_THRESHOLD
		):
			return best_index

	def index_score(self, index: DBIndex) -> float:
		"""Score an index from 0 to 1 based on usefulness.

		A score of 0.5 indicates on average this index will read 50% of the table. (e.g. checkboxes)"""
		table = self.tables[index.table]

		cardinality = index.cardinality or 2
		total_rows = table.total_rows or cardinality or 1

		# We assume most unique values are evenly distributed, this is
		# definitely not the case IRL but it should be good enough assumptions
		# Score is rouhgly what percentage of table we will end up reading on typical query
		rows_fetched_on_average = (table.total_rows or cardinality) / cardinality
		return rows_fetched_on_average / total_rows
