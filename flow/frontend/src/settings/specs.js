import { formatTokens } from "@flow/ui-core/transcript.js";
import { __ } from "@flow/ui-core/translate.js";

// What each settings screen and record page edits. A field's `when` hides it, `locked` disables
// it; both mirror the doctype's own depends_on rules. `child` maps a multi-link to its child
// table. `rename` marks the field a record is named after: changing it renames the record. A
// settings row shows `subtitle` under its title; a search looks in `searchFields` (else
// `listFields`).
const enabled = { name: "enabled", label: __("Enabled"), type: "check" };
const system = (doc) => !!doc.is_system_generated;
// the site may add skills and knowledge to the built-in assistant
const systemButAssistant = (doc) => system(doc) && doc.name !== "frappe/Flow";
const saved = (doc) => !!doc.name;
// the tools among `names` that can't run while server scripts are off, as boot lists them
const scriptsOff = (names, boot) =>
	names.filter((name) => boot.unavailable_tools?.includes(name));
// the harness's /providers list, then two ways to reach any other endpoint
const PROVIDERS = [
	{ label: "OpenAI", value: "openai" },
	{ label: "Anthropic", value: "anthropic" },
	{ label: "Google Gemini", value: "gemini" },
	{ label: "OpenRouter", value: "openrouter" },
	{ label: "xAI", value: "xai" },
	{ label: "Groq", value: "groq" },
	{ label: "DeepSeek", value: "deepseek" },
	{ label: "Mistral", value: "mistral" },
	{ label: "Cerebras", value: "cerebras" },
	{ label: __("OpenAI-compatible endpoint"), value: "custom_openai" },
	{ label: __("LiteLLM proxy"), value: "litellm_proxy" },
];

export const SPECS = {
	providers: {
		key: "providers",
		doctype: "Flow Provider",
		label: __("Providers"),
		singular: __("provider"),
		titleField: "provider",
		listFields: ["name", "provider", "base_url"],
		subtitle: (doc) => doc.base_url || "",
		fields: [
			{
				name: "provider",
				label: __("Provider"),
				type: "provider",
				options: PROVIDERS,
				required: true,
				description:
					__("For anything else, like Ollama, LM Studio or a gateway, pick OpenAI-compatible endpoint or LiteLLM proxy and set its Base URL."),
				locked: saved,
			},
			enabled,
			{
				name: "api_key",
				label: __("API key"),
				type: "password",
				description: __("Not needed for local servers such as Ollama."),
			},
			{
				name: "base_url",
				label: __("Base URL"),
				type: "url",
				placeholder: "https://…",
				description: __("Only for a proxy or a self-hosted server."),
			},
		],
	},
	models: {
		key: "models",
		doctype: "Flow Model",
		label: __("Models"),
		singular: __("model"),
		titleField: "title",
		listFields: ["name", "title", "model_id", "context_window"],
		subtitle: (doc) =>
			[doc.model_id, doc.context_window && __("{0} context", [formatTokens(doc.context_window)])]
				.filter(Boolean)
				.join(" · "),
		fields: [
			{ name: "title", label: __("Title"), type: "text", required: true, rename: true },
			enabled,
			{
				name: "embedding",
				label: __("Embedding model"),
				type: "check",
				description: __("Turns text into vectors for Knowledge's search. Not offered in chats."),
			},
			{
				name: "provider",
				label: __("Provider"),
				type: "link",
				link: "Flow Provider",
				description: __("The key and endpoint come from the provider."),
			},
			{
				name: "model_id",
				label: __("Model ID"),
				type: "model_id",
				required: true,
				placeholder: "claude-sonnet-4-6",
				description:
					__("Pick one of the provider's models, or type any other id. Without a provider, add its prefix: anthropic/claude-sonnet-4-6."),
			},
			{ name: "api_key", label: __("API key"), type: "password", when: (doc) => !doc.provider },
			{
				name: "base_url",
				label: __("Base URL"),
				type: "url",
				when: (doc) => !doc.provider,
				placeholder: "http://localhost:11434",
			},
			{
				name: "extra_params",
				label: __("Extra params"),
				type: "code",
				language: "json",
				placeholder: '{"provider": {"zdr": true}}',
				description:
					__("Extra LiteLLM params sent with every call to this model. Anyone who can use Flow can read them, so keep keys out."),
			},
			{
				name: "roles",
				label: __("Roles"),
				type: "multilink",
				link: "Role",
				child: "role",
				description:
					__("Who can use this model; empty means every Flow user. A sub-agent on it still works for anyone using its agent."),
			},
		],
		actions: [
			{
				label: __("Test connection"),
				method: "test_connection",
				when: saved,
				success: __("Connection OK"),
			},
		],
	},
	agents: {
		key: "agents",
		doctype: "Flow Agent",
		label: __("Agents"),
		singular: __("agent"),
		titleField: "title",
		listFields: ["name", "title", "model"],
		searchFields: ["title", "description", "model"],
		subtitle: (doc) => doc.model,
		fields: [
			{
				name: "title",
				label: __("Title"),
				type: "text",
				required: true,
				rename: true,
				locked: system,
			},
			enabled,
			{
				name: "description",
				label: __("Description"),
				type: "textarea",
				rows: 2,
				description:
					__("What this agent is for, read by an agent that has it as a sub-agent."),
				locked: system,
			},
			{
				name: "model",
				label: __("Model"),
				type: "link",
				link: "Flow Model",
				required: true,
			},
			{
				name: "max_iterations",
				label: __("Max iterations"),
				type: "int",
				description: __("How many steps the agent may take before giving up."),
				locked: system,
			},
			{
				name: "token_budget",
				label: __("Token budget"),
				type: "int",
				placeholder: __("No limit"),
				description:
					__("Tokens a single run may spend, shared with its sub-agents. Cached reads are not counted."),
			},
			{
				name: "instructions",
				label: __("Instructions"),
				type: "textarea",
				rows: 10,
				required: true,
				description:
					__("What the agent does, and the rules it follows. {{ user }}, {{ full_name }} and {{ today }} are filled in when a chat starts."),
				locked: system,
			},
			{
				name: "tools",
				label: __("Tools"),
				type: "multilink",
				link: "Flow Tool",
				child: "tool",
				locked: system,
				note: (doc, boot) => {
					const off = scriptsOff(doc.tools ?? [], boot);
					const names = off.map((name) => name.replace("frappe/", "")).join(", ");
					return off.length
						? __("Server scripts are off on this bench, so these can't run: {0}.", [names])
						: "";
				},
			},
			{
				name: "sub_agents",
				label: __("Sub-agents"),
				type: "multilink",
				link: "Flow Agent",
				child: "agent",
				description: __("Agents this one can hand a task to."),
				locked: system,
			},
			{
				name: "skills",
				label: __("Skills"),
				type: "multilink",
				link: "Flow Skill",
				child: "skill",
				description: __("Know-how the agent can use when a task calls for it."),
				locked: systemButAssistant,
			},
			{
				name: "knowledge_bases",
				label: __("Knowledge bases"),
				type: "multilink",
				link: "Flow Knowledge Base",
				child: "knowledge_base",
				description:
					__("What the agent can search. Anyone who can use the agent can read them, whatever their own access."),
				locked: systemButAssistant,
			},
			{
				name: "roles",
				label: __("Roles"),
				type: "multilink",
				link: "Role",
				child: "role",
				description:
					__("Who can use this agent directly; empty means every Flow user. As a sub-agent it works for anyone using an agent that has it. Disabling a role also drops it here, which can leave the agent open to every Flow user."),
			},
		],
	},
	skills: {
		key: "skills",
		doctype: "Flow Skill",
		label: __("Skills"),
		singular: __("skill"),
		titleField: "title",
		listFields: ["name", "title", "description"],
		searchFields: ["title", "description"],
		subtitle: (doc) => doc.description,
		fields: [
			{
				name: "title",
				label: __("Title"),
				type: "text",
				required: true,
				rename: true,
				locked: system,
			},
			enabled,
			{
				name: "is_global",
				label: __("Available to all agents"),
				type: "check",
				description: __("Every agent can use it, not only the ones it is added to."),
			},
			{
				name: "user_invocable",
				label: __("User invocable"),
				type: "check",
				description:
					__("Anyone chatting with the agent can start it by typing /skill: and its name."),
			},
			{
				name: "description",
				label: __("Description"),
				type: "textarea",
				rows: 2,
				required: true,
				description: __("One line on what this covers and when to use it."),
				locked: system,
			},
			{
				name: "instructions",
				label: __("Instructions"),
				type: "textarea",
				rows: 14,
				required: true,
				description: __("The steps to follow."),
				locked: system,
			},
		],
	},
	tools: {
		key: "tools",
		doctype: "Flow Tool",
		label: __("Tools"),
		singular: __("tool"),
		titleField: "title",
		listFields: ["name", "title", "type"],
		subtitle: (doc) => `${doc.name} · ${doc.type}`,
		notice: (doc, boot) =>
			scriptsOff([doc.name], boot).length
				? __("Server scripts are off on this bench, so this tool can't run.")
				: "",
		fields: [
			{ name: "title", label: __("Title"), type: "text", required: true },
			{
				name: "slug",
				label: __("Function name"),
				type: "text",
				required: true,
				placeholder: "close_overdue_orders",
				description: __("A short name with underscores, like close_overdue_orders."),
				locked: saved,
			},
			{
				name: "type",
				label: __("Type"),
				type: "select",
				options: ["Script", "Imported", "Server"],
				locked: (doc) => system(doc) || saved(doc),
			},
			enabled,
			{
				name: "requires_confirmation",
				label: __("Requires confirmation"),
				type: "check",
				description: __("Ask the user before it runs."),
				locked: system,
			},
			{
				name: "background",
				label: __("Run in background"),
				type: "check",
				description: __("Run it in a background job, for slow tools."),
				when: (doc) => doc.type !== "Server",
				locked: system,
			},
			{
				name: "description",
				label: __("Description (for the model)"),
				type: "textarea",
				rows: 4,
				required: true,
				locked: system,
			},
			{
				name: "summary",
				label: __("Summary (for people)"),
				type: "textarea",
				rows: 2,
				when: (doc) => doc.type === "Script",
			},
			{
				name: "import_path",
				label: __("Import path"),
				type: "text",
				placeholder: "myapp.ai.tools.close_orders",
				when: (doc) => doc.type === "Imported",
				locked: system,
			},
			{
				name: "code",
				label: __("Code"),
				type: "code",
				language: "python",
				when: (doc) => doc.type === "Script",
				description: __("Python, with the logic in a main() function."),
			},
		],
	},
	triggers: {
		key: "triggers",
		doctype: "Flow Trigger",
		label: __("Triggers"),
		singular: __("trigger"),
		titleField: "title",
		listFields: [
			"name",
			"title",
			"agent",
			"event",
			"target_doctype",
			"doc_event",
			"cron_expression",
		],
		searchFields: ["title", "agent", "target_doctype"],
		subtitle: (doc) =>
			doc.event === "Scheduled"
				? `${doc.agent} · ${doc.cron_expression}`
				: `${doc.agent} · ${doc.target_doctype} ${doc.doc_event}`,
		fields: [
			{
				name: "title",
				label: __("Title"),
				type: "text",
				required: true,
				rename: true,
				locked: system,
			},
			enabled,
			{
				name: "agent",
				label: __("Agent"),
				type: "link",
				link: "Flow Agent",
				required: true,
				locked: system,
			},
			{
				name: "event",
				label: __("Event"),
				type: "select",
				options: ["DocType Event", "Scheduled"],
				locked: system,
			},
			{
				name: "run_as",
				label: __("Run as"),
				type: "link",
				link: "User",
				description:
					__("The agent acts as this user. Empty means whoever created the trigger."),
				locked: system,
			},
			{
				name: "target_doctype",
				label: __("Target DocType"),
				type: "link",
				link: "DocType",
				when: (doc) => doc.event === "DocType Event",
				locked: system,
			},
			{
				name: "doc_event",
				label: __("Doc event"),
				type: "select",
				options: ["after_insert", "on_update", "on_submit", "on_cancel", "on_trash"],
				when: (doc) => doc.event === "DocType Event",
				locked: system,
			},
			{
				name: "cron_expression",
				label: __("Cron expression"),
				type: "text",
				placeholder: "0 9 * * 5",
				when: (doc) => doc.event === "Scheduled",
				locked: system,
			},
			{
				name: "last_fired_at",
				label: __("Last fired"),
				type: "readonly",
				when: (doc) => doc.event === "Scheduled" && doc.last_fired_at,
			},
			{
				name: "condition",
				label: __("Condition"),
				type: "code",
				language: "python",
				description:
					__('Only run when this is true, for example doc.status == "Open". A multi-line condition must set result to True or False.'),
				locked: system,
			},
			{
				name: "prompt_template",
				label: __("Prompt template"),
				type: "code",
				language: "jinja",
				required: true,
				description: __("What to ask the agent. {{ doc.name }} inserts the record's name."),
				locked: system,
			},
		],
	},
	knowledge_bases: {
		key: "knowledge_bases",
		doctype: "Flow Knowledge Base",
		label: __("Knowledge bases"),
		singular: __("knowledge base"),
		titleField: "title",
		listFields: ["name", "title", "description"],
		subtitle: (doc) => doc.description,
		fields: [
			{
				name: "title",
				label: __("Title"),
				type: "text",
				required: true,
				rename: true,
				locked: system,
			},
			enabled,
			{
				name: "description",
				label: __("Description"),
				type: "textarea",
				rows: 3,
				description: __("What is in here, in one line."),
			},
		],
	},
	knowledge_sources: {
		key: "knowledge_sources",
		doctype: "Flow Knowledge Source",
		label: __("Sources"),
		singular: __("source"),
		titleField: "title",
		listFields: ["name", "title", "knowledge_base", "source_type"],
		subtitle: (doc) => `${doc.knowledge_base} · ${doc.source_type}`,
		fields: [
			{ name: "title", label: __("Title"), type: "text", required: true },
			{
				name: "knowledge_base",
				label: __("Knowledge base"),
				type: "link",
				link: "Flow Knowledge Base",
				required: true,
				locked: saved,
			},
			{
				name: "source_type",
				label: __("Source type"),
				type: "select",
				options: ["Text", "File", "URL", "DocType"],
				locked: saved,
			},
			{
				name: "content",
				label: __("Content"),
				type: "textarea",
				rows: 10,
				when: (doc) => doc.source_type === "Text",
			},
			{
				name: "file",
				label: __("File"),
				type: "attach",
				when: (doc) => doc.source_type === "File",
			},
			{ name: "url", label: __("URL"), type: "url", when: (doc) => doc.source_type === "URL" },
			{
				name: "reference_doctype",
				label: __("DocType"),
				type: "link",
				link: "DocType",
				when: (doc) => doc.source_type === "DocType",
			},
			{
				name: "filters",
				label: __("Filters"),
				type: "code",
				language: "json",
				placeholder: '{"status": "Resolved"}',
				when: (doc) => doc.source_type === "DocType",
			},
			{
				name: "content_fields",
				label: __("Content fields"),
				type: "text",
				placeholder: "subject, description, resolution",
				when: (doc) => doc.source_type === "DocType",
			},
			{
				name: "auto_sync",
				label: __("Auto sync"),
				type: "check",
				description: __("Updated once a day."),
				when: (doc) => doc.source_type === "DocType",
			},
			{
				name: "chunk_size",
				label: __("Chunk size"),
				type: "int",
				placeholder: __("Default"),
				description: __("Leave empty to use the default."),
				zeroMessage: __("Cannot be 0. Using the default."),
			},
			{
				name: "chunk_overlap",
				label: __("Chunk overlap"),
				type: "int",
				placeholder: __("Default"),
				description: __("Leave empty to use the default."),
				zeroMessage: __("Cannot be 0. Using the default."),
			},
			{ name: "status", label: __("Status"), type: "readonly", when: saved },
			{ name: "chunk_count", label: __("Chunks"), type: "readonly", when: saved },
			{
				name: "last_synced_at",
				label: __("Last synced"),
				type: "readonly",
				when: (doc) => doc.last_synced_at,
			},
			{ name: "error_log", label: __("Error"), type: "readonly", when: (doc) => doc.error_log },
		],
		actions: [
			{
				label: __("Resync"),
				method: "resync",
				args: { rebuild: 0 },
				when: saved,
				success: __("Resync started"),
			},
			{
				label: __("Rebuild"),
				method: "resync",
				args: { rebuild: 1 },
				when: (doc) => saved(doc) && doc.chunk_count,
				success: __("Rebuild started"),
			},
			{
				label: __("Reconcile"),
				method: "reconcile",
				when: (doc) => saved(doc) && doc.source_type === "DocType",
				success: __("Reconcile started"),
			},
		],
	},
	knowledge_settings: {
		key: "knowledge_settings",
		doctype: "Flow Knowledge Settings",
		label: __("Knowledge settings"),
		single: true,
		fields: [
			{
				name: "embedding_model",
				label: __("Embedding model"),
				type: "link",
				link: "Flow Model",
				description: __("Add one in Models first, such as OpenAI's text-embedding-3-small."),
			},
			{
				name: "embedding_dimension",
				label: __("Embedding dimension"),
				type: "readonly",
				when: (doc) => doc.embedding_dimension,
			},
			{
				name: "search_type",
				label: __("Search"),
				type: "select",
				options: ["Hybrid", "Vector"],
			},
			{ name: "chunk_size", label: __("Chunk size"), type: "int" },
			{ name: "chunk_overlap", label: __("Chunk overlap"), type: "int" },
		],
	},
	flow_settings: {
		key: "flow_settings",
		doctype: "Flow Settings",
		label: __("Flow settings"),
		single: true,
		fields: [
			{
				name: "small_model",
				label: __("Helper model"),
				type: "link",
				link: "Flow Model",
				description: __("Does quick side jobs, like chat titles. A cheaper model saves credits."),
			},
			{
				name: "search_provider",
				label: __("Web search"),
				type: "select",
				options: ["DuckDuckGo", "Brave", "Tavily", "Exa"],
				description: __("The service agents use to search the web."),
			},
			{
				name: "search_api_key",
				label: __("Search API key"),
				type: "password",
				beside: "search_provider", // a key button beside it, in a form of rows
				links: {
					Brave: "https://brave.com/search/api/",
					Tavily: "https://app.tavily.com",
					Exa: "https://dashboard.exa.ai/api-keys",
				},
				when: (doc) => doc.search_provider && doc.search_provider !== "DuckDuckGo",
			},
			{
				name: "guest_messages_per_hour",
				label: __("Guest messages per hour"),
				type: "int",
				placeholder: __("Default"),
				description:
					__("Messages one address may send to public agents in an hour. Leave empty to use the default of 30."),
				zeroMessage: __("Cannot be 0. Using the default."),
			},
		],
	},
	memories: {
		key: "memories",
		doctype: "Flow Agent Memory",
		label: __("Memories"),
		singular: __("memory"),
		titleField: "content",
		listFields: [
			"name",
			"content",
			"agent",
			"scope",
			"user",
			"user.email as user_email",
			"status",
			"source",
		],
		searchFields: ["name", "content", "agent", "scope", "user", "user.email", "status", "source"],
		subtitle: (doc) =>
			[doc.agent, doc.scope === "User" ? doc.user_email || doc.user : __("shared"), doc.status]
				.filter(Boolean)
				.join(" · "),
		orderBy: "modified desc",
		fields: [
			{ name: "agent", label: __("Agent"), type: "link", link: "Flow Agent", required: true },
			{
				name: "scope",
				label: __("Scope"),
				type: "select",
				options: ["Agent", "User"],
				description: __("Agent: shared by everyone. User: one person only."),
				locked: saved,
			},
			{
				name: "user",
				label: __("User"),
				type: "link",
				link: "User",
				when: (doc) => doc.scope === "User",
				locked: saved,
			},
			{ name: "status", label: __("Status"), type: "select", options: ["Active", "Archived"] },
			{ name: "source", label: __("Source"), type: "readonly", when: saved },
			{
				name: "content",
				label: __("Content"),
				type: "textarea",
				rows: 3,
				required: true,
				description: __("One short fact."),
			},
		],
	},
};

export function newDoc(spec) {
	const doc = { doctype: spec.doctype };
	for (const field of spec.fields) {
		if (field.type === "check") doc[field.name] = field.name === "enabled" ? 1 : 0;
		else if (field.type === "multilink") doc[field.name] = [];
		else if (field.type === "select") doc[field.name] = field.options[0];
		else if (field.type === "int") doc[field.name] = 0;
		// a read-only field is left out: Frappe fills its default only for a missing value
		else if (field.type !== "readonly") doc[field.name] = "";
	}
	if (spec.doctype === "Flow Agent") {
		doc.max_iterations = 100;
	}
	return doc;
}
