import frappe
from frappe.query_builder import DocType

# copy communication_date from Communication to Communication Link
def execute():
	batch_size = 10_000
	
	CommunicationLink = DocType("Communication Link")
	Communication = DocType("Communication")
	while True:
		# Fetch records that need updating with their communication_date
		records = (
			frappe.qb.from_(CommunicationLink)
			.join(Communication)
			.on(CommunicationLink.parent == Communication.name)
			.select(CommunicationLink.name, Communication.communication_date)
			.where(CommunicationLink.communication_date.isnull())
			.where(Communication.communication_date.isnotnull())
			.limit(batch_size)
		).run(as_dict=True)
		
		if not records:
			break
			
		# Update records in batch
		for record in records:
			(
				frappe.qb.update(CommunicationLink)
				.set(CommunicationLink.communication_date, record.communication_date)
				.where(CommunicationLink.name == record.name)
			).run()
		
		frappe.db.commit()
