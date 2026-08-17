import Quill from "quill";

const Embed = Quill.import("blots/embed");

class MentionBlot extends Embed {
	static create(data) {
		const node = super.create();
		const denotationChar = document.createElement("span");
		denotationChar.className = "ql-mention-denotation-char";
		denotationChar.innerHTML = data.denotationChar;
		node.appendChild(denotationChar);
		const valueSpan = document.createElement("span");
		valueSpan.innerHTML = data.value;
		node.appendChild(valueSpan);
		if (data.isGroup === "true") {
			node.innerHTML += frappe.utils.icon("users");
		}
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
		// mentions written by other editors (e.g. tiptap editor)
		// stores in label with format
		// '<p><span data-id="abc@g.com" data-label="RKL" class="mention" data-type="mention">@RKL</span> sdf</p>'
		const denotationChar = domNode.dataset.denotationChar || "@";
		const value =
			domNode.dataset.value ||
			domNode.dataset.label ||
			domNode.textContent.replace(denotationChar, "").trim();
		return {
			id: domNode.dataset.id,
			value: value,
			link: domNode.dataset.link || null,
			denotationChar: denotationChar,
			isGroup: domNode.dataset.isGroup,
		};
	}
}

MentionBlot.blotName = "mention";
MentionBlot.tagName = "span";
MentionBlot.className = "mention";

Quill.register(MentionBlot, true);
