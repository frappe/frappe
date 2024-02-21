import frappe


def execute():
	# if current = 0, simply delete the key as it'll be recreated on first entry
	frappe.db.delete("Series", {"current": 0})

	duplicate_keys = frappe.db.sql(
		"""
		SELECT name, max(current) as current
		from
			`tabSeries`
		group by
			name
		having count(name) > 1
	""",
		as_dict=True,
	)

	for row in duplicate_keys:
		frappe.db.delete("Series", {"name": row.name})
		if row.current:
			frappe.db.sql("insert into `tabSeries`(`name`, `current`) values (%(name)s, %(current)s)", row)
	frappe.db.commit()

	frappe.db.sql("ALTER table `tabSeries` ADD PRIMARY KEY IF NOT EXISTS (name)")
