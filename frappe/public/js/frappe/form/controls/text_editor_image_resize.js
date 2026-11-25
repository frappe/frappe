import Quill from "quill";

const ALIGNMENTS = [
	{ icon: "text-align-start", margin_left: "", margin_right: "auto" },
	{ icon: "text-align-center", margin_left: "auto", margin_right: "auto" },
	{ icon: "text-align-end", margin_left: "auto", margin_right: "" },
];

const HANDLES = [
	{ corner: "nw", from_left: true },
	{ corner: "ne", from_left: false },
	{ corner: "se", from_left: false },
	{ corner: "sw", from_left: true },
];

export default class ImageResize {
	constructor(quill) {
		this.quill = quill;
		this.container = quill.root.parentNode;
		quill.root.addEventListener("click", this.on_click);
		quill.root.addEventListener("scroll", this.hide);
	}

	on_click = (e) => {
		if (e.target.tagName === "IMG" && this.quill.isEnabled()) {
			if (e.target !== this.img) this.show(e.target);
		} else {
			this.hide();
		}
	};

	show(img) {
		this.hide();
		this.img = img;
		this.quill.setSelection(null);

		this.overlay = document.createElement("div");
		this.overlay.className = "ql-image-overlay";
		this.overlay.addEventListener("mousedown", (e) => e.preventDefault());
		for (const handle of HANDLES) {
			this.overlay.append(this.make_handle(handle));
		}
		this.size_label = document.createElement("div");
		this.size_label.className = "ql-image-size";
		this.overlay.append(this.size_label, this.make_toolbar());
		this.container.append(this.overlay);

		document.addEventListener("mousedown", this.on_outside_event, true);
		document.addEventListener("focusin", this.on_outside_event, true);
		document.addEventListener("keyup", this.on_keyup, true);
		this.quill.root.addEventListener("input", this.hide, true);
		this.update();
	}

	hide = () => {
		if (!this.overlay) return;
		document.removeEventListener("mousedown", this.on_outside_event, true);
		document.removeEventListener("focusin", this.on_outside_event, true);
		document.removeEventListener("keyup", this.on_keyup, true);
		this.quill.root.removeEventListener("input", this.hide, true);
		this.overlay.remove();
		this.overlay = this.img = this.size_label = this.buttons = null;
	};

	on_outside_event = (e) => {
		if (e.target !== this.img && !this.overlay.contains(e.target)) this.hide();
	};

	on_keyup = (e) => {
		const blot = ["Backspace", "Delete"].includes(e.key) && Quill.find(this.img);
		this.hide();
		if (blot) {
			this.quill.deleteText(this.quill.getIndex(blot), 1, Quill.sources.USER);
		}
	};

	make_handle({ corner, from_left }) {
		const handle = document.createElement("div");
		handle.className = `ql-image-handle ql-image-handle-${corner}`;
		handle.addEventListener("mousedown", (e) => this.start_resize(e, corner, from_left));
		return handle;
	}

	start_resize(e, corner, from_left) {
		const img = this.img;
		const start_x = e.clientX;
		const start_width = img.width || img.naturalWidth;
		const cursor_class = ["nw", "se"].includes(corner)
			? "ql-image-resizing-nwse"
			: "ql-image-resizing-nesw";
		document.body.classList.add(cursor_class);

		const on_move = (e) => {
			const delta = from_left ? start_x - e.clientX : e.clientX - start_x;
			img.width = Math.max(1, Math.round(start_width + delta));
			if (this.img === img) this.update();
		};
		const on_up = () => {
			document.body.classList.remove(cursor_class);
			document.removeEventListener("mousemove", on_move);
			document.removeEventListener("mouseup", on_up);
		};
		document.addEventListener("mousemove", on_move);
		document.addEventListener("mouseup", on_up);
	}

	make_toolbar() {
		const toolbar = document.createElement("div");
		toolbar.className = "ql-image-toolbar";
		toolbar.setAttribute("role", "toolbar");
		const labels = [__("Align left"), __("Align center"), __("Align right")];
		this.buttons = ALIGNMENTS.map((alignment, i) => {
			const button = document.createElement("button");
			button.type = "button";
			button.tabIndex = -1;
			button.className = "es-button";
			button.dataset.size = "sm";
			button.dataset.iconButton = "true";
			button.setAttribute("aria-label", labels[i]);
			button.innerHTML = frappe.utils.icon(alignment.icon, "sm");
			button.addEventListener("click", () => this.align(alignment));
			toolbar.append(button);
			return button;
		});
		return toolbar;
	}

	get_alignment() {
		const { display, marginLeft, marginRight } = this.img.style;
		if (display !== "block") return;
		return ALIGNMENTS.find(
			(alignment) =>
				(marginLeft === "auto") === (alignment.margin_left === "auto") &&
				(marginRight === "auto") === (alignment.margin_right === "auto")
		);
	}

	align(alignment) {
		const is_applied = this.get_alignment() === alignment;
		const style = this.img.style;
		for (const property of ["float", "display", "margin-left", "margin-right"]) {
			style.removeProperty(property);
		}
		if (!is_applied) {
			style.display = "block";
			style.marginLeft = alignment.margin_left;
			style.marginRight = alignment.margin_right;
		}
		if (!style.cssText) this.img.removeAttribute("style");
		this.update();
	}

	update() {
		const img_rect = this.img.getBoundingClientRect();
		const container_rect = this.container.getBoundingClientRect();
		const position = {
			left: img_rect.left - container_rect.left + this.container.scrollLeft,
			top: img_rect.top - container_rect.top + this.container.scrollTop,
			width: img_rect.width,
			height: img_rect.height,
		};
		for (const [name, value] of Object.entries(position)) {
			this.overlay.style.setProperty(`--ql-image-${name}`, `${value}px`);
		}

		const alignment = this.get_alignment();
		this.buttons.forEach((button, i) => {
			const active = ALIGNMENTS[i] === alignment;
			button.dataset.variant = active ? "subtle" : "ghost";
			button.setAttribute("aria-pressed", String(active));
		});

		const width = Math.round(img_rect.width);
		const height = Math.round(img_rect.height);
		this.size_label.textContent = `${width} × ${height}`;
		const outside = width <= 120 || height <= 30;
		this.size_label.classList.toggle("outside", outside);
		this.size_label.classList.toggle("outside-left", outside && alignment === ALIGNMENTS[2]);
	}
}
