// Sample rows the stories share. Shaped like the rows a list page hands `List`: a
// `name` that identifies the row, and one property per column.
import type { ListColumn, ListRowData } from "../types";

export const leadColumns: ListColumn[] = [
	{ fieldname: "lead_name", label: "Name" },
	{ fieldname: "status", label: "Status" },
	{ fieldname: "organization", label: "Organization" },
	{ fieldname: "annual_revenue", label: "Annual revenue", align: "right" },
];

export const leads: ListRowData[] = [
	{
		name: "CRM-LEAD-0001",
		lead_name: "Rosa Diaz",
		status: "Open",
		organization: "Nine-Nine",
		annual_revenue: 120000,
	},
	{
		name: "CRM-LEAD-0002",
		lead_name: "Jake Peralta",
		status: "Contacted",
		organization: "Nine-Nine",
		annual_revenue: 80000,
	},
	{
		name: "CRM-LEAD-0003",
		lead_name: "Amy Santiago",
		status: "Qualified",
		organization: "Binders Inc",
		annual_revenue: 250000,
	},
	{
		name: "CRM-LEAD-0004",
		lead_name: "Terry Jeffords",
		status: "Open",
		organization: "Yogurt Co",
		annual_revenue: 45000,
	},
	{
		name: "CRM-LEAD-0005",
		lead_name: "Raymond Holt",
		status: "Converted",
		organization: "Kevin & Co",
		annual_revenue: 900000,
	},
];

/** `count` rows in the same shape, for the virtual window. */
export function manyLeads(count: number): ListRowData[] {
	return Array.from({ length: count }, (_, index) => {
		const base = leads[index % leads.length];
		return {
			...base,
			name: `CRM-LEAD-${String(index + 1).padStart(4, "0")}`,
			annual_revenue: (index + 1) * 1000,
		};
	});
}
