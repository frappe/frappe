import nts
from nts.query_builder.utils import DocType


def execute():
	# Email Template & Help Article have owner field that doesn't have any additional functionality
	# Only ToDo has to be updated.

	ToDo = DocType("ToDo")
	nts.reload_doctype("ToDo", force=True)

	nts.qb.update(ToDo).set(ToDo.allocated_to, ToDo.owner).run()
