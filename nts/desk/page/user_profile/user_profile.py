from datetime import datetime

import nts
from nts.query_builder import Interval, Order
from nts.query_builder.functions import Date, Sum, UnixTimestamp
from nts.utils import getdate


@nts.whitelist()
def get_energy_points_heatmap_data(user, date):
	try:
		date = getdate(date)
	except Exception:
		date = getdate()

	eps_log = nts.qb.DocType("Energy Point Log")

	return dict(
		nts.qb.from_(eps_log)
		.select(UnixTimestamp(Date(eps_log.creation)), Sum(eps_log.points))
		.where(eps_log.user == user)
		.where(eps_log["type"] != "Review")
		.where(Date(eps_log.creation) > Date(date) - Interval(years=1))
		.where(Date(eps_log.creation) < Date(date) + Interval(years=1))
		.groupby(Date(eps_log.creation))
		.orderby(Date(eps_log.creation), order=Order.asc)
		.run()
	)


@nts.whitelist()
def get_energy_points_percentage_chart_data(user, field):
	result = nts.get_all(
		"Energy Point Log",
		filters={"user": user, "type": ["!=", "Review"]},
		group_by=field,
		order_by=field,
		fields=[field, "ABS(sum(points)) as points"],
		as_list=True,
	)

	return {
		"labels": [r[0] for r in result if r[0] is not None],
		"datasets": [{"values": [r[1] for r in result]}],
	}


@nts.whitelist()
def get_user_rank(user):
	month_start = datetime.today().replace(day=1)
	monthly_rank = nts.get_all(
		"Energy Point Log",
		group_by="`tabEnergy Point Log`.`user`",
		filters={"creation": [">", month_start], "type": ["!=", "Review"]},
		fields=["user", "sum(points)"],
		order_by="sum(points) desc",
		as_list=True,
	)

	all_time_rank = nts.get_all(
		"Energy Point Log",
		group_by="`tabEnergy Point Log`.`user`",
		filters={"type": ["!=", "Review"]},
		fields=["user", "sum(points)"],
		order_by="sum(points) desc",
		as_list=True,
	)

	return {
		"monthly_rank": [i + 1 for i, r in enumerate(monthly_rank) if r[0] == user],
		"all_time_rank": [i + 1 for i, r in enumerate(all_time_rank) if r[0] == user],
	}


@nts.whitelist()
def update_profile_info(profile_info):
	profile_info = nts.parse_json(profile_info)
	keys = ["location", "interest", "user_image", "bio"]

	for key in keys:
		if key not in profile_info:
			profile_info[key] = None

	user = nts.get_doc("User", nts.session.user)
	user.update(profile_info)
	user.save()
	return user


@nts.whitelist()
def get_energy_points_list(start, limit, user):
	return nts.db.get_list(
		"Energy Point Log",
		filters={"user": user, "type": ["!=", "Review"]},
		fields=[
			"name",
			"user",
			"points",
			"reference_doctype",
			"reference_name",
			"reason",
			"type",
			"seen",
			"rule",
			"owner",
			"creation",
			"revert_of",
		],
		start=start,
		limit=limit,
		order_by="creation desc",
	)
