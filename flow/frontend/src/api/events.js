// The daemon's user_message keeps the whole text a turn sent it: the typed message plus
// the attachment, excerpt and memory blocks Flow appended. The bubble shows the message,
// with the files as chips.
const MEMORY = /\n<memory>\n[\s\S]*?\n<\/memory>$/;
const EXCERPTS = /\n[^\n]*\n<excerpts>\n[\s\S]*?\n<\/excerpts>/;
const FILE_BLOCK = /\n<file name="([^"]*)">\n[\s\S]*?\n<\/file>/g;
const FILE_NOTE = /\n\[Attached file: ([^\n]+?) \(large; relevant excerpts follow\)\]/g;
const XML_ENTITIES = { "&quot;": '"', "&lt;": "<", "&gt;": ">", "&amp;": "&" };

export function cleanUserText(text) {
	const files = [];
	const value = String(text ?? "")
		.replace(MEMORY, "")
		.replace(EXCERPTS, "")
		.replace(FILE_BLOCK, (_, name) => {
			files.push(name.replace(/&quot;|&lt;|&gt;|&amp;/g, (entity) => XML_ENTITIES[entity]));
			return "";
		})
		.replace(FILE_NOTE, (_, name) => {
			files.push(name);
			return "";
		});
	return { text: value, files };
}

// `fileId` names the staged File behind a chip, so a steered message the composer is
// still showing as queued matches its durable row; `modelName` maps a provider model id
// to the Flow Model the page speaks in.
export function presentEvent(
	event,
	{ fileId = (name, fallback) => fallback ?? `file:${name}`, modelName = (id) => id } = {}
) {
	if (event.type === "model_changed") return { ...event, model: modelName(event.model) };
	if (event.type === "user_message")
		return { ...event, content: presentUserContent(event.content, fileId) };
	return event;
}

function presentUserContent(content, fileId) {
	const files = [];
	const chip = (name) => ({ type: "attachment", id: fileId(name), name, kind: "file" });
	if (typeof content === "string") {
		const cleaned = cleanUserText(content);
		if (!cleaned.files.length) return cleaned.text;
		return [{ type: "text", text: cleaned.text }, ...cleaned.files.map(chip)];
	}
	if (!Array.isArray(content)) return content;
	const blocks = content.map((block) => {
		if (block.type === "attachment") return { ...block, id: fileId(block.name, block.id) };
		if (block.type !== "text") return block;
		const cleaned = cleanUserText(block.text);
		files.push(...cleaned.files);
		return { ...block, text: cleaned.text };
	});
	return [...blocks, ...files.map(chip)];
}
