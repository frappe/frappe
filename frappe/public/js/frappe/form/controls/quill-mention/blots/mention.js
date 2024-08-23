import Quill from "quill";

const Embed = Quill.import("blots/embed");

class MentionBlot extends Embed {
	static create(data) {
		const node = super.create();
		const denotationChar = document.createElement("span");
		denotationChar.className = "ql-mention-denotation-char";
		denotationChar.innerHTML = data.denotationChar;
		node.appendChild(denotationChar);
		node.innerHTML += data.value;
		node.innerHTML += `${data.isGroup === "true" ? frappe.utils.icon("users") : ""}`;
		node.dataset.id = data.id;
		node.dataset.value = data.value;
		node.dataset.denotationChar = data.denotationChar;
		node.dataset.isGroup = data.isGroup;
		if (data.link) {
			node.dataset.link = data.link;
		}
		return node;
	}

	static value(domNode) {
		return {
			id: domNode.dataset.id,
			value: domNode.dataset.value,
			link: domNode.dataset.link || null,
			denotationChar: domNode.dataset.denotationChar,
			isGroup: domNode.dataset.isGroup,
		};
	}
}

MentionBlot.blotName = "mention";
MentionBlot.tagName = "span";
MentionBlot.className = "mention";

Quill.register(MentionBlot, true);
