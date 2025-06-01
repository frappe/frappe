import nts


def execute():
	"""Remove stale docfields from legacy version"""
	nts.db.delete("DocField", {"options": "Data Import", "parent": "Data Import Legacy"})
