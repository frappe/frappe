// The records with a page of their own, beside the chats: their list, and each one's form.
// `key` names the page's path and its spec. The list shows each record's title, its `columns`
// and its status, one line a row; `filters` narrow it, each a field and its choices (from the
// boot data where those are records), beside the status filter every page has.
export const PAGES = [
	{
		key: "agents",
		icon: "lucide-bot",
		description: "Who answers, and what each agent can do.",
		columns: [
			{ label: "Description", width: "2fr", value: (row) => row.description },
			{ label: "Model", width: "1fr", value: (row) => row.model },
		],
		filters: (boot) => [
			{
				field: "model",
				label: "Model",
				options: boot.models.map((model) => ({
					label: model.title || model.name,
					value: model.name,
				})),
			},
		],
	},
	{
		key: "skills",
		icon: "lucide-book-open",
		description: "Know-how agents can pick up for particular tasks.",
		columns: [
			{ label: "Description", width: "2fr", value: (row) => row.description },
			{
				label: "Available to",
				width: "1fr",
				value: (row) => (row.is_global ? "All agents" : "Selected agents"),
			},
		],
		filters: () => [
			{
				field: "is_global",
				label: "Available to",
				options: [
					{ label: "All agents", value: "1" },
					{ label: "Selected agents", value: "0" },
				],
			},
		],
	},
	{
		key: "triggers",
		icon: "lucide-workflow",
		description: "Run an agent when a document changes or on a schedule.",
		columns: [
			{ label: "Agent", width: "1fr", value: (row) => row.agent },
			{
				label: "When",
				width: "1.5fr",
				value: (row) =>
					row.event === "Scheduled"
						? `Schedule · ${row.cron_expression ?? ""}`
						: `${row.target_doctype ?? ""} · ${row.doc_event ?? ""}`,
			},
		],
		filters: (boot) => [
			{
				field: "event",
				label: "Event",
				options: [
					{ label: "Document event", value: "DocType Event" },
					{ label: "Schedule", value: "Scheduled" },
				],
			},
			{
				field: "agent",
				label: "Agent",
				options: boot.agents.map((agent) => ({ label: agent.title, value: agent.name })),
			},
		],
	},
];

export const STATUS_FILTER = {
	field: "enabled",
	label: "Status",
	options: [
		{ label: "Enabled", value: "1" },
		{ label: "Disabled", value: "0" },
	],
};
