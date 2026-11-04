// The services the first run connects, as a first-timer knows them. The big three by the product
// people use, with its maker under it; the key comes from the maker's console, and a consumer plan
// is not API access. The rest by their own names, in the More services menu.
export const PRODUCTS = [
	{
		id: "anthropic",
		name: "Claude",
		maker: "Anthropic",
		console: "Anthropic Console",
		plan: true,
		keys: "https://console.anthropic.com/settings/keys",
		billing: "https://console.anthropic.com/settings/billing",
	},
	{
		id: "openai",
		name: "ChatGPT",
		maker: "OpenAI",
		console: "OpenAI Platform",
		plan: true,
		keys: "https://platform.openai.com/api-keys",
		billing: "https://platform.openai.com/settings/organization/billing",
	},
	{
		id: "gemini",
		name: "Gemini",
		maker: "Google",
		console: "Google AI Studio",
		plan: true,
		keys: "https://aistudio.google.com/apikey",
		billing: "https://aistudio.google.com/usage",
	},
];

export const OTHERS = [
	{ id: "openrouter", name: "OpenRouter", keys: "https://openrouter.ai/keys", billing: "https://openrouter.ai/settings/credits" },
	{ id: "xai", name: "Grok", maker: "xAI", keys: "https://console.x.ai" },
	{ id: "groq", name: "Groq", keys: "https://console.groq.com/keys" },
	{ id: "deepseek", name: "DeepSeek", keys: "https://platform.deepseek.com/api_keys" },
	{ id: "mistral", name: "Mistral", keys: "https://console.mistral.ai/api-keys" },
	{ id: "cerebras", name: "Cerebras", keys: "https://cloud.cerebras.ai" },
].map((service) => ({
	maker: service.name,
	...service,
	console: `${service.maker ?? service.name} console`,
	plan: false,
}));

export const SERVICES = [...PRODUCTS, ...OTHERS];

// who bills for it, and that a consumer plan doesn't cover it
export const billedBy = (service) =>
	`Billed per use by ${service.maker}${service.plan ? `, apart from any ${service.name} plan` : ""}.`;
export const serviceFor = (id) => SERVICES.find((service) => service.id === id) ?? null;

// Key prefixes that name their service, the specific before the general (sk-ant- before sk-).
// Mistral and DeepSeek keys carry no prefix of their own, so they ask which service they are for
const PREFIXES = [
	["sk-ant-", "anthropic"],
	["sk-or-", "openrouter"],
	["AIza", "gemini"],
	["gsk_", "groq"],
	["xai-", "xai"],
	["csk-", "cerebras"],
	["sk-", "openai"],
];

export function detectService(key) {
	const hit = PREFIXES.find(([prefix]) => key.startsWith(prefix));
	return hit ? serviceFor(hit[1]) : null;
}

// a key, not an address or a sentence
export const looksLikeKey = (text) => text.length >= 20 && !/\s/.test(text);

// sk-ant-a…4f2a: enough to recognise, nothing to copy
export const mask = (key) => `${key.slice(0, 8)}…${key.slice(-4)}`;
