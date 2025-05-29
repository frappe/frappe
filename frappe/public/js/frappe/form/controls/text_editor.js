import Quill from "quill";
import ImageResize from "frappe-quill-image-resize";
import MagicUrl from "quill-magic-url";

Quill.register("modules/imageResize", ImageResize);
Quill.register("modules/magicUrl", MagicUrl);
const CodeBlockContainer = Quill.import("formats/code-block-container");
CodeBlockContainer.tagName = "PRE";
Quill.register(CodeBlockContainer, true);
const Embed = Quill.import("blots/embed");
const Delta = Quill.import("delta");

class BreakBlot extends Embed {}
BreakBlot.blotName = "Break";
BreakBlot.tagName = "br";

Quill.register(BreakBlot);

// font size
let font_sizes = [
	false,
	"8px",
	"9px",
	"10px",
	"11px",
	"12px",
	"13px",
	"14px",
	"15px",
	"16px",
	"18px",
	"20px",
	"22px",
	"24px",
	"32px",
	"36px",
	"40px",
	"48px",
	"54px",
	"64px",
	"96px",
	"128px",
];
const Size = Quill.import("attributors/style/size");
Size.whitelist = font_sizes;
Quill.register(Size, true);

// table
const Table = Quill.import("formats/table-container");
const superCreate = Table.create.bind(Table);
Table.create = (value) => {
	const node = superCreate(value);
	node.classList.add("table");
	node.classList.add("table-bordered");
	return node;
};

Quill.register(Table, true);

// link without href
var Link = Quill.import("formats/link");
var Image = Quill.import("formats/image");

class MyImage extends Image {
	static create(value) {
		let node = super.create(value);
		let attrs = ["style", "align", "src"];
		attrs.forEach((a) => {
			if (value[a]) node.setAttribute(a, value[a]);
		});
		return node;
	}
	static value(node) {
		return {
			align: node.align,
			style: node.style.cssText,
			src: node.src,
		};
	}
}

Quill.register(MyImage, true);
class MyLink extends Link {
	static create(value) {
		let node = super.create(value);
		value = this.sanitize(value);
		node.setAttribute("href", value);
		if (value.startsWith("/") || value.indexOf(window.location.host)) {
			// no href if internal link
			node.removeAttribute("target");
		}
		return node;
	}
}

Quill.register(MyLink, true);

// image uploader
const Uploader = Quill.import("modules/uploader");
Uploader.DEFAULTS.mimetypes.push("image/gif", "image/webp");

// inline style
const BackgroundStyle = Quill.import("attributors/style/background");
const ColorStyle = Quill.import("attributors/style/color");
const FontStyle = Quill.import("attributors/style/font");
const AlignStyle = Quill.import("attributors/style/align");
const DirectionStyle = Quill.import("attributors/style/direction");
Quill.register(BackgroundStyle, true);
Quill.register(ColorStyle, true);
Quill.register(FontStyle, true);
Quill.register(AlignStyle, true);
Quill.register(DirectionStyle, true);

// direction class
const DirectionClass = Quill.import("attributors/class/direction");
Quill.register(DirectionClass, true);

// replace font tag with span
const Inline = Quill.import("blots/inline");

class CustomColor extends Inline {
	constructor(domNode, value) {
		super(domNode, value);
		this.domNode.style.color = this.domNode.color;
		domNode.outerHTML = this.domNode.outerHTML
			.replace(/<font/g, "<span")
			.replace(/<\/font>/g, "</span>");
	}
}

CustomColor.blotName = "customColor";
CustomColor.tagName = "font";

Quill.register(CustomColor, true);

frappe.ui.form.ControlTextEditor = class ControlTextEditor extends frappe.ui.form.ControlCode {
	make_wrapper() {
		super.make_wrapper();
	}

	make_input() {
		this.has_input = true;
		this.make_quill_editor();
	}

	make_quill_editor() {
		if (this.quill) return;
		this.quill_container = $("<div>").appendTo(this.input_area);
		if (this.df.max_height) {
			$(this.quill_container).css({ "max-height": this.df.max_height, overflow: "auto" });
		}
		this.quill = new Quill(this.quill_container[0], this.get_quill_options());
		this.bind_events();
		const toolbar = this.quill.getModule("toolbar");
		toolbar.addHandler("table", this.handle_table_actions);
	}

	handle_table_actions(value) {
		const table = this.quill.getModule("table");

		if (value === "insert-table") {
			table.insertTable(2, 2);
		} else if (value === "insert-row-above") {
			table.insertRowAbove();
		} else if (value === "insert-row-below") {
			table.insertRowBelow();
		} else if (value === "insert-column-left") {
			table.insertColumnLeft();
		} else if (value === "insert-column-right") {
			table.insertColumnRight();
		} else if (value === "delete-row") {
			table.deleteRow();
		} else if (value === "delete-column") {
			table.deleteColumn();
		} else if (value === "delete-table") {
			table.deleteTable();
		}

		if (value !== "delete-row") {
			table.balanceTables();
		}
	}
	bind_events() {
		this.quill.on(
			"text-change",
			frappe.utils.debounce((delta, oldDelta, source) => {
				if (!this.is_quill_dirty(source)) return;

				const input_value = this.get_input_value();
				this.parse_validate_and_set_in_model(input_value);
			}, 300)
		);

		$(this.quill.root).on("keydown", (e) => {
			const key = frappe.ui.keys && frappe.ui.keys.get_key(e);
			if (["ctrl+b", "meta+b"].includes(key)) {
				e.stopPropagation();
			}
		});

		$(this.quill.root).on("drop", (e) => {
			e.stopPropagation();
		});

		// font size dropdown
		let $font_size_label = this.$wrapper.find(".ql-size .ql-picker-label:first");
		let $default_font_size = this.$wrapper.find(".ql-size .ql-picker-item:first");

		if ($font_size_label.length) {
			$font_size_label.attr("data-value", "---");
			$default_font_size.attr("data-value", "---");
		}
	}

	is_quill_dirty(source) {
		if (source === "api") return false;
		let input_value = this.get_input_value();
		return this.value !== input_value;
	}

	get_quill_options() {
		const options = {
			modules: {
				toolbar: Object.keys(this.df).includes("get_toolbar_options")
					? this.df.get_toolbar_options()
					: this.get_toolbar_options(),
				table: true,
				imageResize: {},
				magicUrl: true,
				mention: this.get_mention_options(),
				keyboard: {
					bindings: this.get_keyboard_bindings(),
				},
			},
			theme: this.df.theme || "snow",
			readOnly: this.disabled,
			bounds: this.quill_container[0],
			placeholder: this.df.placeholder || "",
		};

		// In a grid row where space is constrained, hide the toolbar.
		if (this.grid_row) {
			options.theme = null;
			options.modules.toolbar = [];
		}

		return options;
	}

	get_mention_options() {
		if (!this.enable_mentions && !this.df.enable_mentions) {
			return null;
		}
		let me = this;
		return {
			allowedChars: /^[A-Za-z0-9_]*$/,
			mentionDenotationChars: ["@"],
			isolateCharacter: true,
			source: frappe.utils.debounce(async function (search_term, renderList) {
				let method =
					me.mention_search_method || "frappe.desk.search.get_names_for_mentions";
				let values = await frappe.xcall(method, {
					search_term,
				});

				let sorted_values = me.prioritize_involved_users_in_mention(values);
				renderList(sorted_values, search_term);
			}, 300),
			renderItem(item) {
				let value = item.value;
				return `${value} ${item.is_group ? frappe.utils.icon("users") : ""}`;
			},
		};
	}

	prioritize_involved_users_in_mention(values) {
		const involved_users =
			this.frm?.get_involved_users() || // input on form
			cur_frm?.get_involved_users() || // comment box / dialog on active form
			[];

		return values
			.filter((val) => involved_users.includes(val.id))
			.concat(values.filter((val) => !involved_users.includes(val.id)));
	}

	get_toolbar_options() {
		return [
			[{ header: [1, 2, 3, false] }],
			[{ size: font_sizes }],
			["bold", "italic", "underline", "strike", "clean"],
			[{ color: [] }, { background: [] }],
			["blockquote", "code-block"],
			// Adding Direction tool to give the user the ability to change text direction.
			[{ direction: "rtl" }],
			["link", "image"],
			[{ list: "ordered" }, { list: "bullet" }, { list: "check" }],
			[{ align: [] }],
			[{ indent: "-1" }, { indent: "+1" }],
			[
				{
					table: [
						"insert-table",
						"insert-row-above",
						"insert-row-below",
						"insert-column-right",
						"insert-column-left",
						"delete-row",
						"delete-column",
						"delete-table",
					],
				},
			],
		];
	}

	parse(value) {
		if (value == null) {
			value = "";
		}
		return frappe.dom.remove_script_and_style(value);
	}

	set_formatted_input(value) {
		if (!this.quill) return;
		if (value === this.get_input_value()) return;
		if (!value) {
			// clear contents for falsy values like '', undefined or null
			this.quill.setText("");
			return;
		}

		// set html without triggering a focus
		const delta = this.quill.clipboard.convert(
			{ html: value, text: "" },
			{
				image: MyImage,
			}
		);
		this.quill.setContents(delta);
	}

	get_input_value() {
		let value = this.quill ? this.quill.root.innerHTML : "";
		// hack to retain space sequence.
		value = value.replace(/(\s)(\s)/g, " &nbsp;");
		value = this.patch_unordered_list(value);

		try {
			if (!$(value).find(".ql-editor").length) {
				value = `<div class="ql-editor read-mode">${value}</div>`;
			}
		} catch (e) {
			value = `<div class="ql-editor read-mode">${value}</div>`;
		}

		return value;
	}

	patch_unordered_list(value) {
		/*
		Quill uses the <ol> element for ordered AND unordered lists. Unordered
		lists are identified by the data-list attribute. This creates problems
		when cleaning up the html and the style of the list is lost.

		To fix this, we convert the unordered lists to <ul> elements.
		*/
		const valueElement = document.createElement("div");
		valueElement.innerHTML = value;

		const firstBulletLiElements = valueElement.querySelectorAll(
			"ol li[data-list=bullet]:first-child"
		);
		firstBulletLiElements.forEach((li) => {
			const parent = li.parentNode;
			const children = Array.from(parent.children);
			const ul = document.createElement("ul");
			children.forEach((child) => {
				ul.appendChild(child);
			});
			parent.parentNode.replaceChild(ul, parent);
		});

		return valueElement.innerHTML;
	}

	set_focus() {
		this.quill.focus();
	}

	get_keyboard_bindings() {
		let bindings = {
			"table enter": {
				key: "Enter",
				formats: ["table"],
				handler: function (range) {
					this.quill.updateContents(
						new Delta()
							.retain(range.index)
							.delete(range.length)
							.insert({ Break: true })
					);

					if (!this.quill.getLeaf(range.index + 1)[0].next) {
						this.quill.updateContents(
							new Delta()
								.retain(range.index + 1)
								.delete(0)
								.insert({ Break: true }),
							"user"
						);
					}

					this.quill.setSelection(range.index + 1, Quill.sources.SILENT);
					return false; // dont call other handlers
				},
			},
		};
		return bindings;
	}
};
