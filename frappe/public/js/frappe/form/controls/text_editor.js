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

// toolbar icons: swap Quill's stock SVGs for the app's lucide set (the same
// glyphs frappe-ui's TextEditor uses). Display-only — Quill still binds every
// handler through the ql-* classes, and app-supplied toolbars get them too.
const quill_icons = Quill.import("ui/icons");
const toolbar_icon = (name) => frappe.utils.icon(name, "sm", "", "", "", true);
Object.assign(quill_icons, {
	bold: toolbar_icon("bold"),
	italic: toolbar_icon("italic"),
	underline: toolbar_icon("underline"),
	strike: toolbar_icon("strikethrough"),
	blockquote: toolbar_icon("quote"),
	"code-block": toolbar_icon("code"),
	code: toolbar_icon("code"),
	link: toolbar_icon("link-2"),
	image: toolbar_icon("image-plus"),
	video: toolbar_icon("video"),
	clean: toolbar_icon("eraser"),
	color: toolbar_icon("paint-bucket"),
	background: toolbar_icon("highlighter"),
	formula: toolbar_icon("sigma"),
	table: toolbar_icon("table-properties"),
});
Object.assign(quill_icons.list, {
	ordered: toolbar_icon("list-ordered"),
	bullet: toolbar_icon("list"),
	check: toolbar_icon("list-check"),
});
Object.assign(quill_icons.indent, {
	"+1": toolbar_icon("list-indent-increase"),
	"-1": toolbar_icon("list-indent-decrease"),
});
Object.assign(quill_icons.direction, {
	"": toolbar_icon("pilcrow-right"),
	rtl: toolbar_icon("pilcrow-left"),
});
Object.assign(quill_icons.align, {
	"": toolbar_icon("text-align-start"),
	center: toolbar_icon("text-align-center"),
	right: toolbar_icon("text-align-end"),
	justify: toolbar_icon("text-align-justify"),
});
Object.assign(quill_icons.script, {
	sub: toolbar_icon("subscript"),
	super: toolbar_icon("superscript"),
});
for (let level = 1; level <= 6; level++) {
	quill_icons.header[String(level)] = toolbar_icon(`heading-${level}`);
}

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
		this.add_toolbar_tooltips(toolbar);
		this.dress_toolbar_pickers(toolbar);
	}

	dress_toolbar_pickers(toolbar) {
		if (!toolbar?.container) return;
		// swap quill's stock up/down caret for the app chevron. Text pickers
		// only: icon and color pickers show the current selection as their
		// label, so they have no caret. Quill never rewrites these labels
		// after construction, so the swap sticks. A bare sprite reference,
		// NOT frappe.utils.icon — the global .icon class carries
		// margin: 0 auto, which floats the caret to the middle of the
		// space-between label
		toolbar.container
			.querySelectorAll(
				".ql-picker:not(.ql-icon-picker):not(.ql-color-picker) .ql-picker-label > svg"
			)
			.forEach((svg) => {
				svg.outerHTML = `<svg class="ql-picker-caret" aria-hidden="true" stroke="currentColor" fill="none">
					<use href="#icon-chevron-down"></use>
				</svg>`;
			});

		// header picker → frappe-ui's "Text style" rows: an icon per level and
		// "Paragraph" instead of "Normal". Labels ride quill's own data-label
		// channel (its CSS renders attr(data-label) above the hardcoded
		// 'Heading N' strings, and selectItem copies it to the label on every
		// selection) — which also makes them translatable, unlike the stock
		// ::before content
		const sprite_icon = (name, attrs = "") =>
			`<svg aria-hidden="true" stroke="currentColor" fill="none" ${attrs}>
				<use href="#icon-${name}"></use>
			</svg>`;
		toolbar.container.querySelectorAll(".ql-picker.ql-header").forEach((picker) => {
			picker.querySelectorAll(".ql-picker-item").forEach((item) => {
				const level = item.getAttribute("data-value");
				const is_heading = /^[1-6]$/.test(level || "");
				item.setAttribute(
					"data-label",
					is_heading ? __("Heading {0}", [level]) : __("Paragraph")
				);
				item.insertAdjacentHTML(
					"afterbegin",
					sprite_icon(is_heading ? `heading-${level}` : "type")
				);
			});
			// the label shows the selected level's ICON, not text: all seven
			// ride in the label and CSS reveals the one matching the label's
			// data-value, which quill keeps in sync on every selection
			const label = picker.querySelector(".ql-picker-label");
			if (label) {
				const level_icons = ["p", "1", "2", "3", "4", "5", "6"]
					.map((level) =>
						sprite_icon(
							level === "p" ? "type" : `heading-${level}`,
							`class="ql-label-icon" data-level="${level}"`
						)
					)
					.join("");
				label.insertAdjacentHTML("afterbegin", level_icons);
			}
		});

		// font size: a static icon label too — the ql-active chip signals a
		// non-default size, the dropdown shows the value
		toolbar.container
			.querySelectorAll(".ql-picker.ql-size .ql-picker-label")
			.forEach((label) => {
				label.insertAdjacentHTML(
					"afterbegin",
					sprite_icon("a-large-small", 'class="ql-label-icon"')
				);
			});

		// table picker: menu items ride the same data-label channel; the
		// visible label rides data-title instead, since selectItem copies the
		// clicked item's data-label onto the label
		const table_labels = {
			"insert-table": __("Insert Table"),
			"insert-row-above": __("Insert Row Above"),
			"insert-row-below": __("Insert Row Below"),
			"insert-column-right": __("Insert Column Right"),
			"insert-column-left": __("Insert Column Left"),
			"delete-row": __("Delete Row"),
			"delete-column": __("Delete Column"),
			"delete-table": __("Delete Table"),
		};
		toolbar.container.querySelectorAll(".ql-table .ql-picker-item").forEach((item) => {
			item.setAttribute("data-label", table_labels[item.dataset.value]);
		});
		toolbar.container
			.querySelector(".ql-table .ql-picker-label")
			?.setAttribute("data-title", __("Table"));
	}

	add_toolbar_tooltips(toolbar) {
		if (!toolbar?.container) return;

		// title-attr fallback path only; the es tooltip renders combos itself
		const shortcut_hint = (combo) =>
			frappe.ui.keys?.get_shortcut_label
				? ` (${frappe.ui.keys.get_shortcut_label(combo)})`
				: "";

		const tooltips = {
			"button.ql-bold": { text: __("Bold"), shortcut: "ctrl+b" },
			"button.ql-italic": { text: __("Italic"), shortcut: "ctrl+i" },
			"button.ql-underline": { text: __("Underline"), shortcut: "ctrl+u" },
			"button.ql-strike": __("Strikethrough"),
			"button.ql-clean": __("Remove formatting"),
			"button.ql-blockquote": __("Blockquote"),
			"button.ql-code-block": __("Code block"),
			"button.ql-link": __("Insert link"),
			"button.ql-image": __("Insert image"),
			"button.ql-video": __("Insert video"),
			'button.ql-list[value="ordered"]': __("Numbered list"),
			'button.ql-list[value="bullet"]': __("Bullet list"),
			'button.ql-list[value="check"]': __("Task list"),
			'button.ql-indent[value="+1"]': __("Increase indent"),
			'button.ql-indent[value="-1"]': __("Decrease indent"),
			'button.ql-script[value="sub"]': __("Subscript"),
			'button.ql-script[value="super"]': __("Superscript"),
			"button.ql-direction": __("Text direction"),
			".ql-header .ql-picker-label": __("Text style"),
			".ql-size .ql-picker-label": __("Font size"),
			".ql-color .ql-picker-label": __("Text color"),
			".ql-background .ql-picker-label": __("Background color"),
			".ql-align .ql-picker-label": __("Alignment"),
			".ql-table .ql-picker-label": __("Table"),
		};

		for (const [selector, tip] of Object.entries(tooltips)) {
			const opts = typeof tip === "string" ? { text: tip } : tip;
			toolbar.container.querySelectorAll(selector).forEach((el) => {
				if (frappe.ui.tooltip) {
					frappe.ui.tooltip(el, opts);
				} else {
					el.title = opts.text + (opts.shortcut ? shortcut_hint(opts.shortcut) : "");
				}
				// the buttons are icon-only — give them a name too
				if (!el.getAttribute("aria-label")) {
					el.setAttribute("aria-label", opts.text);
				}
			});
		}
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

		const imageResizeModule = this.quill.getModule("imageResize");
		if (imageResizeModule) {
			imageResizeModule.checkImage = (evt) => {
				if (imageResizeModule.img) {
					// Delete / Backspace key pressed
					if (evt.keyCode == 46 || evt.keyCode == 8) {
						const blot = Quill.find(imageResizeModule.img);
						if (blot) blot.deleteAt(0);
					}
					imageResizeModule.hide();
				}
			};
		}

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
			readOnly: this.disabled || this.df.read_only,
			bounds: this.quill_container[0],
			placeholder: __(this.df.placeholder || "Type something..."),
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
			allowedChars: /^[\p{L}0-9_]*$/u,
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
				let email = item?.email ? `(${item?.email})` : "";
				return `${value} ${email} ${item.is_group ? frappe.utils.icon("users") : ""}`;
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
			[{ header: [1, 2, 3, 4, 5, 6, false] }],
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
		const bindings = {
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

		if (this.grid_row) {
			bindings["tab"] = {
				key: "Tab",
				handler: () => true, // call default handler
			};
		}

		return bindings;
	}
};
