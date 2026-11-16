// The services Flow connects, as a first-timer knows them. The big three by the product people
// use, with its maker beside it; the key comes from the maker's console. The rest by their own
// names.
export const PRODUCTS = [
	{
		id: "anthropic",
		name: "Claude",
		maker: "Anthropic",
		console: "Anthropic Console",
		keys: "https://console.anthropic.com/settings/keys",
	},
	{
		id: "openai",
		name: "ChatGPT",
		maker: "OpenAI",
		console: "OpenAI Platform",
		keys: "https://platform.openai.com/api-keys",
	},
	{
		id: "gemini",
		name: "Gemini",
		maker: "Google",
		console: "Google AI Studio",
		keys: "https://aistudio.google.com/apikey",
	},
];

export const OTHERS = [
	{ id: "openrouter", name: "OpenRouter", keys: "https://openrouter.ai/keys" },
	{ id: "xai", name: "Grok", maker: "xAI", keys: "https://console.x.ai" },
	{ id: "groq", name: "Groq", keys: "https://console.groq.com/keys" },
	{ id: "deepseek", name: "DeepSeek", keys: "https://platform.deepseek.com/api_keys" },
	{ id: "mistral", name: "Mistral", keys: "https://console.mistral.ai/api-keys" },
	{ id: "cerebras", name: "Cerebras", keys: "https://cloud.cerebras.ai" },
].map((service) => ({
	maker: service.name,
	...service,
	console: `${service.maker ?? service.name} console`,
}));

export const SERVICES = [...PRODUCTS, ...OTHERS];

export const serviceFor = (id) => SERVICES.find((service) => service.id === id) ?? null;

// Key prefixes that name their service. A bare sk- names none (DeepSeek's keys have it too), and
// Mistral keys carry no prefix, so those go to the service picked
const PREFIXES = [
	["sk-ant-", "anthropic"],
	["sk-or-", "openrouter"],
	["AIza", "gemini"],
	["gsk_", "groq"],
	["xai-", "xai"],
	["csk-", "cerebras"],
	["sk-proj-", "openai"],
	["sk-svcacct-", "openai"],
];

export function detectService(key) {
	const hit = PREFIXES.find(([prefix]) => key.trim().startsWith(prefix));
	return hit ? serviceFor(hit[1]) : null;
}

// A provider's models to add, as Combobox options: its list without those it has, then what's
// typed when the list leaves it out (a new one, a preview), in a row of its own that `pick`s it.
// The row's label is the `#item-typed` slot, given the query.
export function addableModels(provider, listed, saved, pick) {
	const prefix = `${provider}/`;
	const typedId = (query) => {
		const typed = query.trim();
		const id = typed.startsWith(prefix) ? typed : `${prefix}${typed}`;
		return id === prefix || /\s/.test(typed) || listed.includes(id) || saved.has(id) ? null : id;
	};
	return [
		...listed.filter((id) => !saved.has(id)).map((id) => ({ label: id.slice(prefix.length), value: id })),
		{
			type: "custom",
			key: "typed",
			label: "Use the typed id",
			slot: "typed",
			condition: ({ query }) => Boolean(typedId(query)),
			onClick: ({ query }) => pick(typedId(query)),
		},
	];
}
