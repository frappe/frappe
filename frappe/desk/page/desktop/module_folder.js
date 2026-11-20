const FOLDER_SPRING =
	"linear(0, 0.0238, 0.0842, 0.1675, 0.2628, 0.3623, 0.4603, 0.5528, 0.6372, 0.7124, 0.7776, 0.8331, 0.8792, 0.9167, 0.9466, 0.9698, 0.9873, 1.0001, 1.009, 1.0148, 1.0181, 1.0197, 1.0199, 1.0191, 1.0177, 1.0159, 1.014, 1.012, 1.0101, 1.0083, 1.0067, 1.0053, 1.004, 1.003, 1.0021, 1.0014, 1.0009, 1.0005, 1.0002, 0.9999, 1)";

frappe.ui.ModuleFolder = class ModuleFolder {
	constructor(tile) {
		this.tile = tile;
		this.face = tile.querySelector(".module-folder-face");
		this.card = tile.querySelector(".module-folder-card");
		this.toggle = tile.querySelector(".icon-title");
		this.is_open = false;

		this.toggle.setAttribute("aria-haspopup", "dialog");
		this.toggle.setAttribute("aria-expanded", "false");
		tile.querySelectorAll(".icon-link, .icon-title").forEach((link) =>
			link.addEventListener("click", (e) => {
				const quick = e.detail === 0;
				this.is_open ? this.close(true, quick) : this.open(quick);
			})
		);
		this.card
			.querySelectorAll(".module-folder-app")
			.forEach((app) => app.addEventListener("click", () => this.reset()));
		this.card.querySelectorAll("img").forEach((img) => img.decode?.().catch(() => {}));

		this.card.addEventListener("pointermove", (e) => {
			if (e.movementX || e.movementY) tile.classList.add("is-hover-ready");
		});

		this.on_keydown = (e) => e.key === "Escape" && this.close(true, true);
		const toggles = [...tile.querySelectorAll(".icon-link, .icon-title")];
		this.on_pointerdown = (e) => {
			if (this.card.contains(e.target) || toggles.some((t) => t.contains(e.target))) return;
			this.close(false);
		};
	}

	open(quick = false) {
		this.is_open = true;
		this.tile.classList.remove("is-hover-ready");
		this.keep_on_screen();
		this.set_state();
		document.addEventListener("keydown", this.on_keydown);
		document.addEventListener("pointerdown", this.on_pointerdown);
		this.card.querySelector(".module-folder-app")?.focus({ preventScroll: true });
		this.fly(false, quick);
	}

	keep_on_screen() {
		const gutter = 16;
		const style = this.card.style;
		style.removeProperty("--folder-shift-x");
		style.removeProperty("--folder-shift-y");
		const r = this.card.getBoundingClientRect();
		const right = document.documentElement.clientWidth - gutter;
		const x = Math.max(gutter - r.left, 0) - Math.max(r.right - right, 0);
		const y = Math.max(this.tile.parentElement.getBoundingClientRect().top - r.top, 0);
		if (x) style.setProperty("--folder-shift-x", `${x}px`);
		if (y) style.setProperty("--folder-shift-y", `${y}px`);
	}

	close(refocus = true, quick = false) {
		if (!this.is_open) return;
		this.is_open = false;
		this.set_state();
		this.remove_listeners();
		if (refocus) this.toggle.focus({ preventScroll: true });
		this.fly(true, quick);
	}

	reset() {
		this.is_open = false;
		this.remove_listeners();
		this.card.getAnimations({ subtree: true }).forEach((a) => a.cancel());
		this.tile.classList.remove("is-open", "is-flying");
		this.set_state();
	}

	remove_listeners() {
		document.removeEventListener("keydown", this.on_keydown);
		document.removeEventListener("pointerdown", this.on_pointerdown);
	}

	set_state() {
		this.tile.classList.toggle("is-open", this.is_open);
		this.toggle.setAttribute("aria-expanded", String(this.is_open));
		this.card.toggleAttribute("inert", !this.is_open);
		this.card.setAttribute("aria-hidden", String(!this.is_open));
	}

	fly(closing, quick = false) {
		const card = this.card;
		const tile = this.tile;
		const current = new Map();
		card.getAnimations({ subtree: true }).forEach((a) => {
			const el = a.effect.target;
			const style = getComputedStyle(el);
			const values = current.get(el) || {};
			for (const frame of a.effect.getKeyframes()) {
				for (const prop of Object.keys(frame)) {
					if (!["offset", "computedOffset", "easing", "composite"].includes(prop)) {
						values[prop] = style[prop];
					}
				}
			}
			current.set(el, values);
			a.cancel();
		});
		const animations = [];
		const animate = (el, frames, options) => {
			frames = (closing ? [...frames].reverse() : frames).map((f) => ({ ...f }));
			Object.assign(frames[0], current.get(el));
			animations.push(el.animate(frames, options));
		};
		const finish = () => {
			tile.classList.remove("is-flying");
			if (closing) card.getAnimations({ subtree: true }).forEach((a) => a.cancel());
		};
		tile.classList.add("is-flying");
		const fill = closing ? "forwards" : "backwards";

		if (quick || window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
			animate(card, [{ opacity: 0 }, { opacity: 1 }], {
				duration: 150,
				easing: "ease-out",
				fill,
			});
		} else {
			const has_spring = CSS.supports("animation-timing-function", "linear(0, 1)");
			const duration = closing ? 260 : has_spring ? 620 : 420;
			const easing = closing
				? "cubic-bezier(.77, 0, .175, 1)"
				: has_spring
				? FOLDER_SPRING
				: "cubic-bezier(.32, .72, 0, 1)";

			const c = card.getBoundingClientRect();
			const f = this.face.getBoundingClientRect();
			const bg = card.querySelector(".module-folder-bg");
			animate(
				bg,
				[
					{
						clipPath: `inset(${f.top - c.top}px ${c.right - f.right}px ${
							c.bottom - f.bottom
						}px ${f.left - c.left}px round 16px)`,
						backgroundColor: getComputedStyle(this.face).backgroundColor,
					},
					{
						clipPath: `inset(0px round ${getComputedStyle(bg).borderTopLeftRadius})`,
						backgroundColor: getComputedStyle(bg).backgroundColor,
					},
				],
				{ duration, easing, fill }
			);
			animate(
				card.querySelector(".module-folder-shadow"),
				[
					{
						transform: `translate(${f.left - c.left}px, ${f.top - c.top}px) scale(${
							f.width / c.width
						}, ${f.height / c.height})`,
						opacity: 0,
					},
					{ transform: "none", opacity: 1 },
				],
				{ duration, easing, fill }
			);

			card.querySelectorAll(".module-folder-logo").forEach((logo, i) => {
				const r = logo.getBoundingClientRect();
				const mini = this.face.querySelector(
					`[data-folder-item="${logo.dataset.folderItem}"]`
				);
				const m = mini
					? mini.getBoundingClientRect()
					: { left: f.left + f.width / 2, top: f.top + f.height / 2, width: 0 };
				const from = {
					transform: `translate(${m.left - r.left}px, ${m.top - r.top}px) scale(${
						m.width / r.width
					})`,
					opacity: mini ? 1 : 0,
				};
				animate(logo, [from, { transform: "none", opacity: 1 }], {
					duration,
					easing,
					delay: closing ? 0 : i * 40,
					fill,
				});
			});

			card.querySelectorAll("[data-folder-fade]").forEach((text) =>
				animate(text, [{ opacity: 0 }, { opacity: 1 }], {
					duration: closing ? 120 : 220,
					delay: closing ? 0 : 180,
					easing: "ease-out",
					fill: "both",
				})
			);
		}

		Promise.all(animations.map((a) => a.finished)).then(finish, () => {});
	}
};
