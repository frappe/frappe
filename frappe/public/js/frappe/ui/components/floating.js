import { place } from "./position.js";

let id_counter = 0;

/**
 * Internal: a panel in <body> hung off an anchor, for pickers whose focus stays
 * on their own field while the panel is open (Combobox, DatePicker). Unlike
 * frappe.ui.Popover it never takes focus; it closes on a press outside the
 * anchor and panel, or when focus leaves both. Keys stay with the owner.
 */
export class FloatingPanel {
	/**
	 * @param {Object} opts
	 * @param {HTMLElement} opts.anchor What the panel hangs off.
	 * @param {string} [opts.class_name] Classes on the panel.
	 * @param {string} [opts.role] Role of the panel.
	 * @param {"top"|"right"|"bottom"|"left"} [opts.side="bottom"]
	 * @param {"start"|"center"|"end"} [opts.align="start"]
	 * @param {number} [opts.offset=4]
	 * @param {boolean} [opts.match_width] At least as wide as the anchor.
	 * @param {(reason:string)=>void} [opts.on_close] "outside" | "blur" | "owner" or the owner's reason.
	 */
	constructor(opts) {
		this.opts = opts;
		this.panel = null;
		this.id = `es-floating-${++id_counter}`;
	}

	get is_open() {
		return Boolean(this.panel);
	}

	/** @param {HTMLElement} content */
	open(content) {
		if (this.panel) return this.panel;
		const { anchor, class_name, role, match_width } = this.opts;
		const panel = document.createElement("div");
		panel.className = class_name || "";
		panel.id = this.id;
		if (role) panel.setAttribute("role", role);
		panel.append(content);
		if (match_width) panel.style.minWidth = `${anchor.getBoundingClientRect().width}px`;

		document.body.append(panel);
		this.panel = panel;
		this.reposition();
		panel.setAttribute("data-state", "open");

		this.onpointerdown = (e) => {
			if (panel.contains(e.target) || anchor.contains(e.target)) return;
			if (anchor.closest("label")?.contains(e.target)) return;
			this.close("outside");
		};
		this.onfocusin = (e) => {
			if (panel.contains(e.target) || anchor.contains(e.target)) return;
			this.close("blur");
		};
		this.onreposition = (e) => {
			if (e?.target instanceof Node && panel.contains(e.target)) return;
			this.reposition();
		};
		document.addEventListener("pointerdown", this.onpointerdown, { capture: true });
		document.addEventListener("focusin", this.onfocusin);
		window.addEventListener("resize", this.onreposition);
		document.addEventListener("scroll", this.onreposition, { capture: true, passive: true });
		return panel;
	}

	reposition() {
		if (!this.panel) return;
		const { anchor, side = "bottom", align = "start", offset = 4 } = this.opts;
		this.panel.style.maxHeight = "";
		place(this.panel, anchor.getBoundingClientRect(), side, align, offset);
	}

	close(reason = "owner") {
		if (!this.panel) return;
		const panel = this.panel;
		this.panel = null;
		document.removeEventListener("pointerdown", this.onpointerdown, { capture: true });
		document.removeEventListener("focusin", this.onfocusin);
		window.removeEventListener("resize", this.onreposition);
		document.removeEventListener("scroll", this.onreposition, { capture: true });
		panel.remove();
		this.opts.on_close?.(reason);
	}
}
