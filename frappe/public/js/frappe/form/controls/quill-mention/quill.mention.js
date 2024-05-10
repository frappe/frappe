import Quill from "quill";
import Keys from "./constants/keys";
import "./blots/mention";

class Mention {
	constructor(quill, options) {
		this.isOpen = false;
		this.itemIndex = 0;
		this.mentionCharPos = null;
		this.cursorPos = null;
		this.values = [];
		this.suspendMouseEnter = false;

		this.quill = quill;

		this.options = {
			source: null,
			renderItem(item, searchTerm) {
				return `${item.value}`;
			},
			mentionDenotationChars: ["@"],
			allowedChars: /^[a-zA-Z0-9_]*$/,
			minChars: 0,
			maxChars: 31,
			offsetTop: 2,
			offsetLeft: 0,
			isolateCharacter: false,
			fixMentionsToQuill: false,
			defaultMenuOrientation: "bottom",
		};

		Object.assign(this.options, options);

		this.mentionContainer = document.createElement("div");
		this.mentionContainer.className = "ql-mention-list-container";
		this.mentionContainer.style.cssText = "display: none; position: absolute;";
		this.mentionContainer.onmousemove = this.onContainerMouseMove.bind(this);

		if (this.options.fixMentionsToQuill) {
			this.mentionContainer.style.width = "auto";
		}

		this.mentionList = document.createElement("ul");
		this.mentionList.className = "ql-mention-list";
		this.mentionContainer.appendChild(this.mentionList);

		this.quill.container.appendChild(this.mentionContainer);

		quill.on("text-change", this.onTextChange.bind(this));
		quill.on("selection-change", this.onSelectionChange.bind(this));

		quill.keyboard.addBinding(
			{
				key: Keys.TAB,
			},
			this.selectHandler.bind(this)
		);
		quill.keyboard.bindings[Keys.TAB].unshift(quill.keyboard.bindings[Keys.TAB].pop());

		quill.keyboard.addBinding(
			{
				key: Keys.ENTER,
			},
			this.selectHandler.bind(this)
		);
		quill.keyboard.bindings[Keys.ENTER].unshift(quill.keyboard.bindings[Keys.ENTER].pop());

		quill.keyboard.addBinding(
			{
				key: Keys.ESCAPE,
			},
			this.escapeHandler.bind(this)
		);

		quill.keyboard.addBinding(
			{
				key: Keys.UP,
			},
			this.upHandler.bind(this)
		);

		quill.keyboard.addBinding(
			{
				key: Keys.DOWN,
			},
			this.downHandler.bind(this)
		);
	}

	selectHandler() {
		if (this.isOpen) {
			this.selectItem();
			return false;
		}
		return true;
	}

	escapeHandler() {
		if (this.isOpen) {
			this.hideMentionList();
			return false;
		}
		return true;
	}

	upHandler() {
		if (this.isOpen) {
			this.prevItem();
			return false;
		}
		return true;
	}

	downHandler() {
		if (this.isOpen) {
			this.nextItem();
			return false;
		}
		return true;
	}

	showMentionList() {
		this.mentionContainer.style.visibility = "hidden";
		this.mentionContainer.style.display = "";
		this.setMentionContainerPosition();
		this.isOpen = true;
	}

	hideMentionList() {
		this.mentionContainer.style.display = "none";
		this.isOpen = false;
	}

	highlightItem(scrollItemInView = true) {
		for (let i = 0; i < this.mentionList.childNodes.length; i += 1) {
			this.mentionList.childNodes[i].classList.remove("selected");
		}
		this.mentionList.childNodes[this.itemIndex].classList.add("selected");

		if (scrollItemInView) {
			const itemHeight = this.mentionList.childNodes[this.itemIndex].offsetHeight;
			const itemPos = this.itemIndex * itemHeight;
			const containerTop = this.mentionContainer.scrollTop;
			const containerBottom = containerTop + this.mentionContainer.offsetHeight;

			if (itemPos < containerTop) {
				// Scroll up if the item is above the top of the container
				this.mentionContainer.scrollTop = itemPos;
			} else if (itemPos > containerBottom - itemHeight) {
				// scroll down if any part of the element is below the bottom of the container
				this.mentionContainer.scrollTop += itemPos - containerBottom + itemHeight;
			}
		}
	}

	getItemData() {
		const itemLink = this.mentionList.childNodes[this.itemIndex].dataset.link;
		return {
			id: this.mentionList.childNodes[this.itemIndex].dataset.id,
			value: itemLink
				? `<a href="${itemLink}" target="_blank">${
						this.mentionList.childNodes[this.itemIndex].dataset.value
				  }`
				: this.mentionList.childNodes[this.itemIndex].dataset.value,
			link: itemLink || null,
			denotationChar: this.mentionList.childNodes[this.itemIndex].dataset.denotationChar,
			isGroup: this.mentionList.childNodes[this.itemIndex].dataset.isGroup,
		};
	}

	onContainerMouseMove() {
		this.suspendMouseEnter = false;
	}

	selectItem() {
		const data = this.getItemData();
		this.quill.deleteText(
			this.mentionCharPos,
			this.cursorPos - this.mentionCharPos,
			Quill.sources.API
		);
		this.quill.insertEmbed(this.mentionCharPos, "mention", data, Quill.sources.API);
		this.quill.insertText(this.mentionCharPos + 1, " ", Quill.sources.API);
		this.quill.setSelection(this.mentionCharPos + 2, Quill.sources.API);
		this.hideMentionList();
	}

	onItemMouseEnter(e) {
		if (this.suspendMouseEnter) {
			return;
		}

		const index = Number(e.target.dataset.index);

		if (!Number.isNaN(index) && index !== this.itemIndex) {
			this.itemIndex = index;
			this.highlightItem(false);
		}
	}

	onItemClick(e) {
		e.stopImmediatePropagation();
		e.preventDefault();
		this.itemIndex = e.currentTarget.dataset.index;
		this.highlightItem();
		this.selectItem();
	}

	renderList(mentionChar, data, searchTerm) {
		if (data && data.length > 0) {
			this.values = data;
			this.mentionList.innerHTML = "";
			for (let i = 0; i < data.length; i += 1) {
				const li = document.createElement("li");
				li.className = "ql-mention-list-item";
				li.dataset.index = i;
				li.dataset.id = data[i].id;
				li.dataset.value = data[i].value;
				li.dataset.isGroup = Boolean(data[i].is_group);
				li.dataset.denotationChar = mentionChar;
				if (data[i].link) {
					li.dataset.link = data[i].link;
				}
				li.innerHTML = this.options.renderItem(data[i], searchTerm);
				li.onmouseenter = this.onItemMouseEnter.bind(this);
				li.onclick = this.onItemClick.bind(this);
				this.mentionList.appendChild(li);
			}
			this.itemIndex = 0;
			this.highlightItem();
			this.showMentionList();
		} else {
			this.hideMentionList();
		}
	}

	nextItem() {
		this.itemIndex = (this.itemIndex + 1) % this.values.length;
		this.suspendMouseEnter = true;
		this.highlightItem();
	}

	prevItem() {
		this.itemIndex = (this.itemIndex + this.values.length - 1) % this.values.length;
		this.suspendMouseEnter = true;
		this.highlightItem();
	}

	hasValidChars(s) {
		return this.options.allowedChars.test(s);
	}

	containerBottomIsNotVisible(topPos, containerPos) {
		const mentionContainerBottom =
			topPos + this.mentionContainer.offsetHeight + containerPos.top;
		return mentionContainerBottom > window.pageYOffset + window.innerHeight;
	}

	containerRightIsNotVisible(leftPos, containerPos) {
		if (this.options.fixMentionsToQuill) {
			return false;
		}

		const rightPos = leftPos + this.mentionContainer.offsetWidth + containerPos.left;
		const browserWidth = window.pageXOffset + document.documentElement.clientWidth;
		return rightPos > browserWidth;
	}

	setMentionContainerPosition() {
		const containerPos = this.quill.container.getBoundingClientRect();
		const mentionCharPos = this.quill.getBounds(this.mentionCharPos);
		const containerHeight = this.mentionContainer.offsetHeight;

		let topPos = this.options.offsetTop;
		let leftPos = this.options.offsetLeft;

		// handle horizontal positioning
		if (this.options.fixMentionsToQuill) {
			const rightPos = 0;
			this.mentionContainer.style.right = `${rightPos}px`;
		} else {
			leftPos += mentionCharPos.left;
		}

		if (this.containerRightIsNotVisible(leftPos, containerPos)) {
			const containerWidth = this.mentionContainer.offsetWidth + this.options.offsetLeft;
			const quillWidth = containerPos.width;
			leftPos = quillWidth - containerWidth;
		}

		// handle vertical positioning
		if (this.options.defaultMenuOrientation === "top") {
			// Attempt to align the mention container with the top of the quill editor
			if (this.options.fixMentionsToQuill) {
				topPos = -1 * (containerHeight + this.options.offsetTop);
			} else {
				topPos = mentionCharPos.top - (containerHeight + this.options.offsetTop);
			}

			// default to bottom if the top is not visible
			if (topPos + containerPos.top <= 0) {
				let overMentionCharPos = this.options.offsetTop;

				if (this.options.fixMentionsToQuill) {
					overMentionCharPos += containerPos.height;
				} else {
					overMentionCharPos += mentionCharPos.bottom;
				}

				topPos = overMentionCharPos;
			}
		} else {
			// Attempt to align the mention container with the bottom of the quill editor
			if (this.options.fixMentionsToQuill) {
				topPos += containerPos.height;
			} else {
				topPos += mentionCharPos.bottom;
			}

			// default to the top if the bottom is not visible
			if (this.containerBottomIsNotVisible(topPos, containerPos)) {
				let overMentionCharPos = this.options.offsetTop * -1;

				if (!this.options.fixMentionsToQuill) {
					overMentionCharPos += mentionCharPos.top;
				}

				topPos = overMentionCharPos - containerHeight;
			}
		}

		this.mentionContainer.style.top = `${topPos}px`;
		this.mentionContainer.style.left = `${leftPos}px`;

		this.mentionContainer.style.visibility = "visible";
	}

	onSomethingChange() {
		const range = this.quill.getSelection();
		if (range == null) return;
		this.cursorPos = range.index;
		const startPos = Math.max(0, this.cursorPos - this.options.maxChars);
		const beforeCursorPos = this.quill.getText(startPos, this.cursorPos - startPos);
		const mentionCharIndex = this.options.mentionDenotationChars.reduce((prev, cur) => {
			const previousIndex = prev;
			const mentionIndex = beforeCursorPos.lastIndexOf(cur);

			return mentionIndex > previousIndex ? mentionIndex : previousIndex;
		}, -1);
		if (mentionCharIndex > -1) {
			if (
				this.options.isolateCharacter &&
				!(mentionCharIndex == 0 || !!beforeCursorPos[mentionCharIndex - 1].match(/\s/g))
			) {
				this.hideMentionList();
				return;
			}
			const mentionCharPos = this.cursorPos - (beforeCursorPos.length - mentionCharIndex);
			this.mentionCharPos = mentionCharPos;
			const textAfter = beforeCursorPos.substring(mentionCharIndex + 1);
			if (textAfter.length >= this.options.minChars && this.hasValidChars(textAfter)) {
				const mentionChar = beforeCursorPos[mentionCharIndex];
				this.options.source(
					textAfter,
					this.renderList.bind(this, mentionChar),
					mentionChar
				);
			} else {
				this.hideMentionList();
			}
		} else {
			this.hideMentionList();
		}
	}

	onTextChange(delta, oldDelta, source) {
		if (source === "user") {
			this.onSomethingChange();
		}
	}

	onSelectionChange(range) {
		if (range && range.length === 0) {
			this.onSomethingChange();
		} else {
			this.hideMentionList();
		}
	}
}

Quill.register("modules/mention", Mention, true);

export default Mention;
