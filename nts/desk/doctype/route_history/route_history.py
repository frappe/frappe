# Copyright (c) 2022, nts Technologies and contributors
# License: MIT. See LICENSE

import nts
from nts.deferred_insert import deferred_insert as _deferred_insert
from nts.model.document import Document


class RouteHistory(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from nts.types import DF

		route: DF.Data | None
		user: DF.Link | None
	# end: auto-generated types

	@staticmethod
	def clear_old_logs(days=30):
		from nts.query_builder import Interval
		from nts.query_builder.functions import Now

		table = nts.qb.DocType("Route History")
		nts.db.delete(table, filters=(table.modified < (Now() - Interval(days=days))))


@nts.whitelist()
def deferred_insert(routes):
	routes = [
		{
			"user": nts.session.user,
			"route": route.get("route"),
			"creation": route.get("creation"),
		}
		for route in nts.parse_json(routes)
	]

	_deferred_insert("Route History", routes)


@nts.whitelist()
def frequently_visited_links():
	return nts.get_all(
		"Route History",
		fields=["route", "count(name) as count"],
		filters={"user": nts.session.user},
		group_by="route",
		order_by="count desc",
		limit=5,
	)
