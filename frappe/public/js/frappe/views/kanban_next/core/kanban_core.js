/**
 * KanbanCore — the configurable Kanban engine (vanilla JS).
 *
 * Owns the skeleton DOM (board → columns → card lists), paints each card's
 * interior through the host `renderCard`, virtualizes long columns, wires drag &
 * drop (Pragmatic DnD), selection, inline create, and pagination. All business
 * logic lives in the consumer via `provider`, `callbacks` and `renderers`.
 *
 * Layout uses the tailwind-style utility classes from utilities.scss; only
 * behavioural bits are in core/styles.js.
 */
import {
	bindCardDrag,
	bindCardDropTarget,
	bindColumnDropTarget,
	clamp,
	closestEdge,
	startDragMonitor,
} from "./drag";
import { EventBus } from "./events";
import { injectBaseStyles } from "./styles";
import { ColumnVirtualizer } from "./virtualization";

const DEFAULT_PAGE_LENGTH = 50;
/** Extra px added per card to account for inter-card margin in the height model. */
const CARD_GAP = 8;
/** Prefetch the next page when the rendered window is within N rows of loaded end. */
const PREFETCH_ROWS = 8;

// Utility-class strings for the skeleton (utilities.scss).
const CLS = {
	board: "kn-board flex gap-3 overflow-x-auto overflow-y-hidden items-stretch py-2",
	// The column is a flat gray panel: no border in light mode, the fill alone
	// separates it from the board (dark mode flips this — see styles.js). The
	// bottom padding is the column's own, so the scrolling list ends above the
	// panel edge and cards read as sliding inside it.
	column: "kn-column flex flex-col overflow-hidden rounded-lg bg-surface-gray-1 pb-2",
	// Dot + title + count on the left; Add sits hard right.
	header: "kn-column-header flex items-center justify-between gap-2 ps-4 pe-1 pt-1 shrink-0",
	headerMeta: "kn-column-meta flex items-center gap-1.5 min-w-0",
	// Colour lives on the indicator dot (not the count). Margin on ::before is
	// zeroed in styles.js so flex gap alone spaces the dot from the title.
	dot: "kn-column-dot indicator shrink-0",
	title: "kn-column-title text-sm-medium text-ink-gray-8 truncate min-w-0",
	count: "kn-column-count text-sm text-ink-gray-5 shrink-0",
	// The rest of the padding lives on the body, not the column, so card shadows
	// aren't clipped. It is 16px on both sides because the scroll thumb is
	// painted inside that padding (see the scrollbar rules in styles.js) and at
	// 8px it would touch the cards.
	body: "kn-column-body flex-1 overflow-y-auto overflow-x-hidden px-3 pt-2",
	footer: "kn-column-footer shrink-0 px-4 pt-1",
	card: "kn-card bg-surface-elevation-1 border rounded-lg text-ink-gray-8 text-sm p-3 mb-2",
};

export class KanbanCore {
	constructor(options) {
		this.options = Object.assign(
			{ pageLength: DEFAULT_PAGE_LENGTH, selection: "single", virtualization: true },
			options
		);
		this.bus = new EventBus();
		this.container = null;
		this.root = null;

		this.state = { columns: [], cards: {}, selection: [], loading: false };

		this.rendererCleanups = [];
		this.dragCleanups = [];
		this.monitorCleanup = null;
		this.columnViews = new Map();
		this.providerUnsub = null;
		this.resizeObserver = null;
		this.dropIndicatorEl = null;
		this.lastSelected = null;
		this.pointer = { x: 0, y: 0 };
		this.autoScrollRAF = null;
		this.localMoveGraceUntil = 0;
		this.columnSortable = null;
	}

	// --- lifecycle -------------------------------------------------------

	mount(container) {
		this.container = container;
		injectBaseStyles();

		this.root = document.createElement("div");
		this.root.className = CLS.board;
		container.replaceChildren(this.root);
		this.setupColumnSortable();

		if (this.options.provider.onRemoteUpdate) {
			this.providerUnsub = this.options.provider.onRemoteUpdate(() => {
				// Ignore the realtime echo of our own move (already applied optimistically).
				if (Date.now() < this.localMoveGraceUntil) return;
				this.bus.emit("remote:update");
				this.reload();
			});
		}

		this.monitorCleanup = startDragMonitor((args) => this.handleDrop(args));

		// Auto-scroll while dragging near a column/board edge (native DnD events).
		this.root.addEventListener("dragover", this.onDragOver);
		this.root.addEventListener("drop", this.onDragEnd);
		document.addEventListener("dragend", this.onDragEnd);

		if (typeof ResizeObserver !== "undefined") {
			this.resizeObserver = new ResizeObserver(() => this.refreshWindows());
		}

		this.reload();
	}

	async reload() {
		this.setLoading(true);
		try {
			const { columns, cards } = await this.options.provider.loadBoard();
			this.state = { ...this.state, columns, cards };
			this.render();
			this.bus.emit("state:change", this.getState());
		} catch (error) {
			this.bus.emit("error", error);
		} finally {
			this.setLoading(false);
		}
	}

	getState() {
		return this.state;
	}

	/** Programmatically set the selection. */
	select(cardIds) {
		this.setSelection(cardIds);
	}

	on(event, cb) {
		return this.bus.on(event, cb);
	}

	destroy() {
		this.teardownViews();
		this.onDragEnd();
		this.resizeObserver = null;
		this.monitorCleanup && this.monitorCleanup();
		this.monitorCleanup = null;
		this.providerUnsub && this.providerUnsub();
		this.providerUnsub = null;
		if (this.root) {
			this.root.removeEventListener("dragover", this.onDragOver);
			this.root.removeEventListener("drop", this.onDragEnd);
		}
		if (this.columnSortable) {
			this.columnSortable.destroy();
			this.columnSortable = null;
		}
		document.removeEventListener("dragend", this.onDragEnd);
		if (this.container) this.container.replaceChildren();
		this.root = null;
		this.container = null;
		this.bus.clear();
	}

	// --- selection -------------------------------------------------------

	applySelection(cardId, columnId, index, ev) {
		if (this.options.selection === "none") return;
		const multi = this.options.selection === "multi";
		const sel = new Set(this.state.selection);

		if (multi && (ev.metaKey || ev.ctrlKey)) {
			if (sel.has(cardId)) sel.delete(cardId);
			else sel.add(cardId);
			this.lastSelected = { columnId, index };
		} else if (
			multi &&
			ev.shiftKey &&
			this.lastSelected &&
			this.lastSelected.columnId === columnId
		) {
			const ordered = this.orderedNames(columnId);
			const [lo, hi] =
				this.lastSelected.index <= index
					? [this.lastSelected.index, index]
					: [index, this.lastSelected.index];
			for (let i = lo; i <= hi; i++) if (ordered[i]) sel.add(ordered[i]);
		} else {
			sel.clear();
			sel.add(cardId);
			this.lastSelected = { columnId, index };
		}
		this.setSelection([...sel]);
	}

	setSelection(ids) {
		this.state = { ...this.state, selection: ids };
		const set = new Set(ids);
		this.root &&
			this.root
				.querySelectorAll(".kn-card")
				.forEach((el) =>
					el.classList.toggle(
						"kn-selected",
						!!el.dataset.name && set.has(el.dataset.name)
					)
				);
		this.options.callbacks &&
			this.options.callbacks.onSelectionChange &&
			this.options.callbacks.onSelectionChange(ids);
		this.bus.emit("selection:change", ids);
	}

	// --- rendering -------------------------------------------------------

	render() {
		if (!this.root) return;
		this.teardownViews();

		const frag = document.createDocumentFragment();
		for (const column of this.state.columns) {
			frag.appendChild(this.buildColumnShell(column));
		}
		this.root.replaceChildren(frag);

		for (const view of this.columnViews.values()) {
			if (view.virtualizer.count > 0) this.renderWindow(view);
		}
		setTimeout(() => this.refreshWindows(), 0);
	}

	// --- inline create ---------------------------------------------------

	canAddCard() {
		const cb = this.options.callbacks;
		return this.options.addCard != null
			? this.options.addCard
			: !!(cb && (cb.onAddCard || cb.onCardCreate));
	}

	/** Header "+" or legacy path: open new doc, or inline title input at column top. */
	addCard(columnId) {
		const cb = this.options.callbacks;
		if (cb && cb.onAddCard) {
			cb.onAddCard(columnId);
			return;
		}
		const view = this.columnViews.get(columnId);
		if (view) this.openAddCard(view);
	}

	openAddCard(view) {
		if (!view.footer) {
			view.footer = document.createElement("div");
			view.footer.className = CLS.footer;
			view.body.parentElement.appendChild(view.footer);
		}
		const input = document.createElement("textarea");
		input.className =
			"kn-add-card-input w-full border rounded-md p-2 bg-surface-base text-ink-gray-8 text-sm";
		input.rows = 2;
		input.placeholder = __("Card title…");
		const close = () => {
			if (!view.footer) return;
			view.footer.remove();
			view.footer = null;
		};
		input.addEventListener("keydown", (ev) => {
			if (ev.key === "Enter" && !ev.shiftKey) {
				ev.preventDefault();
				this.submitAddCard(view, input.value.trim());
			} else if (ev.key === "Escape") {
				close();
			}
		});
		input.addEventListener("blur", () => close());
		view.footer.replaceChildren(input);
		input.focus();
	}

	async submitAddCard(view, title) {
		const columnId = view.column.id;
		if (view.footer) {
			view.footer.remove();
			view.footer = null;
		}
		if (!title) return;
		try {
			const cb = this.options.callbacks;
			const created = cb && cb.onCardCreate ? await cb.onCardCreate(columnId, title) : null;
			if (created && typeof created === "object") {
				const existing = this.state.cards[columnId] || [];
				this.state = {
					...this.state,
					cards: { ...this.state.cards, [columnId]: [created, ...existing] },
					columns: this.state.columns.map((c) =>
						c.id === columnId
							? { ...c, order: [created.name, ...c.order], total: c.total + 1 }
							: c
					),
				};
				this.renderColumns([columnId]);
				view.body.scrollTop = 0;
			}
		} catch (error) {
			this.bus.emit("error", error);
		}
	}

	refreshWindows() {
		if (!this.options.virtualization) return;
		for (const view of this.columnViews.values()) {
			if (view.virtualizer.count === 0) continue;
			const vr = view.virtualizer.range(view.body.scrollTop, view.body.clientHeight || 600);
			if (vr.start !== view.renderedRange.start || vr.end !== view.renderedRange.end) {
				this.renderWindow(view);
			}
		}
	}

	buildColumnShell(column) {
		const el = document.createElement("div");
		el.className = CLS.column;
		el.dataset.col = column.id;
		el.appendChild(this.renderColumnHeader(column));

		const body = document.createElement("div");
		body.className = CLS.body;
		body.dataset.col = column.id;
		el.appendChild(body);

		this.dragCleanups.push(
			bindColumnDropTarget(body, { kind: "column", columnId: column.id })
		);
		this.resizeObserver && this.resizeObserver.observe(body);

		const topSpacer = document.createElement("div");
		topSpacer.className = "kn-spacer";
		const bottomSpacer = document.createElement("div");
		bottomSpacer.className = "kn-spacer";

		const ordered = this.orderedCards(column);
		const view = {
			column,
			body,
			topSpacer,
			bottomSpacer,
			virtualizer: new ColumnVirtualizer(ordered.length),
			cardCleanups: [],
			renderedRange: { start: 0, end: 0 },
			loading: false,
			footer: null,
		};
		this.columnViews.set(column.id, view);

		if (ordered.length === 0) {
			body.replaceChildren(this.renderEmptyState(column));
		} else {
			body.replaceChildren(topSpacer, bottomSpacer);
		}

		body.addEventListener("scroll", () => this.onColumnScroll(view));
		return el;
	}

	renderWindow(view) {
		const ordered = this.orderedCards(view.column);
		if (view.virtualizer.count !== ordered.length) {
			view.virtualizer.setCount(ordered.length);
		}
		if (ordered.length === 0) {
			this.flushList(view.cardCleanups);
			view.body.replaceChildren(this.renderEmptyState(view.column));
			view.renderedRange = { start: 0, end: 0 };
			return;
		}

		const viewport = this.options.virtualization
			? view.body.clientHeight || 600
			: view.virtualizer.totalHeight;
		const vr = this.options.virtualization
			? view.virtualizer.range(view.body.scrollTop, viewport)
			: { start: 0, end: ordered.length, padTop: 0, padBottom: 0 };

		this.flushList(view.cardCleanups);
		const nodes = [];
		for (let i = vr.start; i < vr.end; i++) {
			nodes.push(this.createCardEl(view.column, ordered[i], i, view.cardCleanups));
		}
		view.topSpacer.style.height = `${vr.padTop}px`;
		view.bottomSpacer.style.height = `${vr.padBottom}px`;
		view.body.replaceChildren(view.topSpacer, ...nodes, view.bottomSpacer);
		view.renderedRange = { start: vr.start, end: vr.end };

		if (this.options.virtualization) {
			let changed = false;
			nodes.forEach((node, k) => {
				const h = node.getBoundingClientRect().height + CARD_GAP;
				if (view.virtualizer.measure(vr.start + k, h)) changed = true;
			});
			if (changed) {
				view.virtualizer.rebuild();
				view.topSpacer.style.height = `${view.virtualizer.offsetOf(vr.start)}px`;
				view.bottomSpacer.style.height = `${
					view.virtualizer.totalHeight - view.virtualizer.offsetOf(vr.end)
				}px`;
			}
		}
	}

	renderColumnHeader(column) {
		const el = document.createElement("div");
		el.className = CLS.header;
		if (this.options.renderColumnHeader) {
			this.track(this.options.renderColumnHeader(column, el));
		} else {
			// Indicator names ("Light Blue") scrub to class names ("light-blue"),
			// matching the classic board's colour palette. Default is gray.
			const color = frappe.scrub(column.color || "gray", "-");
			const dot = document.createElement("span");
			dot.className = `${CLS.dot} ${color}`;
			dot.setAttribute("aria-hidden", "true");

			const title = document.createElement("span");
			title.className = CLS.title;
			title.textContent = column.title;

			// Plain muted number — not a badge.
			const count = document.createElement("span");
			count.className = CLS.count;
			count.textContent = String(column.total);

			const meta = document.createElement("div");
			meta.className = CLS.headerMeta;
			meta.append(dot, title, count);
			el.appendChild(meta);

			if (this.canAddCard()) {
				const addLabel = this.options.addCardLabel || __("Add card");
				const $add = frappe.ui.button({
					icon: "plus",
					variant: "ghost",
					size: "sm",
					tooltip: addLabel,
					css_class: "kn-add-card shrink-0",
					onclick: () => this.addCard(column.id),
				});
				// Keep column Sortable from treating the click as a drag start.
				$add.on("mousedown", (e) => e.stopPropagation());
				el.appendChild($add[0]);
			}
		}
		return el;
	}

	/**
	 * Column reorder uses Sortable on the board root (same approach as old Kanban).
	 * Only headers are handles, so card drag/drop stays independent.
	 */
	setupColumnSortable() {
		if (!this.root || this.columnSortable || typeof Sortable === "undefined") return;
		this.columnSortable = new Sortable(this.root, {
			animation: 150,
			draggable: ".kn-column",
			handle: ".kn-column-header",
			direction: "horizontal",
			bubbleScroll: true,
			// Don't preventDefault on body scroll / card / header-add interactions.
			filter: ".kn-column-body, .kn-column-footer, .kn-card, .kn-add-card",
			preventOnFilter: false,
			onEnd: (evt) => this.onColumnSortEnd(evt),
		});
	}

	/** Persist column order after a Sortable drag operation. */
	async onColumnSortEnd(evt) {
		const from = evt && evt.oldIndex;
		const to = evt && evt.newIndex;
		if (from == null || to == null || from === to) return;

		const previous = [...this.state.columns];
		const next = [...previous];
		const [moved] = next.splice(from, 1);
		next.splice(clamp(to, 0, next.length), 0, moved);

		this.state = { ...this.state, columns: next };
		this.bus.emit("state:change", this.getState());

		try {
			if (this.options.provider.moveColumnOrder) {
				await this.options.provider.moveColumnOrder(next.map((c) => c.id));
			}
			const cb = this.options.callbacks || {};
			cb.onColumnMove &&
				cb.onColumnMove({ fromIndex: from, toIndex: to, order: next.map((c) => c.id) });
		} catch (error) {
			this.state = { ...this.state, columns: previous };
			// Re-render to put DOM back in the saved order if persistence fails.
			this.render();
			this.bus.emit("error", error);
		}
	}

	createCardEl(column, card, index, sink) {
		const el = document.createElement("div");
		el.className = CLS.card;
		el.dataset.name = card.name;
		el.tabIndex = 0;
		const selected = this.state.selection.includes(card.name);
		if (selected) el.classList.add("kn-selected");

		const cleanup = this.options.renderCard(card, el, { column, index, selected });
		if (typeof cleanup === "function") sink.push(cleanup);

		const dragData = { kind: "card", cardId: card.name, columnId: column.id, index };
		sink.push(
			bindCardDrag(el, dragData, {
				onStart: () => el.classList.add("kn-dragging"),
				onEnd: () => el.classList.remove("kn-dragging"),
			}),
			bindCardDropTarget(el, () => dragData, {
				onEdge: (edge) => this.showDropIndicator(el, edge),
				onLeave: () => this.clearDropIndicator(el),
			})
		);

		el.addEventListener("click", (ev) => {
			this.applySelection(card.name, column.id, index, ev);
			const cb = this.options.callbacks;
			cb && cb.onCardClick && cb.onCardClick(card);
			this.bus.emit("card:click", card);
		});
		el.addEventListener("dblclick", () => {
			const cb = this.options.callbacks;
			cb && cb.onCardOpen && cb.onCardOpen(card);
		});
		el.addEventListener("contextmenu", (ev) => {
			const cb = this.options.callbacks;
			cb && cb.onCardContextMenu && cb.onCardContextMenu(card, ev);
		});
		return el;
	}

	renderEmptyState(column) {
		const el = document.createElement("div");
		el.className = "kn-empty";
		if (this.options.renderEmptyState) this.options.renderEmptyState(column, el);
		return el;
	}

	// --- scroll: virtualization window + pagination ----------------------

	onColumnScroll(view) {
		if (!this.columnViews.has(view.column.id)) return;

		if (this.options.virtualization) {
			const vr = view.virtualizer.range(view.body.scrollTop, view.body.clientHeight || 600);
			if (vr.start !== view.renderedRange.start || vr.end !== view.renderedRange.end) {
				this.renderWindow(view);
			}
		}
		this.maybeLoadMore(view);
	}

	maybeLoadMore(view) {
		if (view.loading) return;
		const column = this.getColumn(view.column.id);
		if (!column) return;
		const loaded = (this.state.cards[column.id] || []).length;
		if (loaded >= column.total) return;
		if (view.renderedRange.end < loaded - PREFETCH_ROWS) return;

		this.bus.emit("column:scroll-end", column.id);
		const cb = this.options.callbacks;
		cb && cb.onColumnScrollEnd && cb.onColumnScrollEnd(column.id);
		this.loadMore(column.id, loaded);
	}

	async loadMore(columnId, start) {
		const view = this.columnViews.get(columnId);
		if (!view || view.loading) return;
		view.loading = true;
		try {
			const { total, cards } = await this.options.provider.loadColumnPage(
				columnId,
				start,
				this.options.pageLength
			);
			const existing = this.state.cards[columnId] || [];
			this.state = {
				...this.state,
				cards: { ...this.state.cards, [columnId]: [...existing, ...cards] },
				columns: this.state.columns.map((c) => (c.id === columnId ? { ...c, total } : c)),
			};
			const column = this.getColumn(columnId);
			if (column) {
				view.column = column;
				view.virtualizer.setCount(this.orderedCards(column).length);
				this.renderWindow(view);
			}
			this.bus.emit("state:change", this.getState());
		} catch (error) {
			this.bus.emit("error", error);
		} finally {
			view.loading = false;
		}
	}

	// --- auto-scroll while dragging --------------------------------------

	onDragOver = (e) => {
		this.pointer.x = e.clientX;
		this.pointer.y = e.clientY;
		if (this.autoScrollRAF === null) {
			this.autoScrollRAF = requestAnimationFrame(this.autoScrollTick);
		}
	};

	onDragEnd = () => {
		if (this.autoScrollRAF !== null) {
			cancelAnimationFrame(this.autoScrollRAF);
			this.autoScrollRAF = null;
		}
	};

	autoScrollTick = () => {
		if (!this.root) {
			this.autoScrollRAF = null;
			return;
		}
		const EDGE = 64;
		const MAX = 16;
		const { x, y } = this.pointer;
		const speed = (d) => MAX * Math.min(1, d / EDGE);

		for (const view of this.columnViews.values()) {
			const r = view.body.getBoundingClientRect();
			if (x < r.left || x > r.right) continue;
			if (y < r.top + EDGE) view.body.scrollTop -= speed(r.top + EDGE - y);
			else if (y > r.bottom - EDGE) view.body.scrollTop += speed(y - (r.bottom - EDGE));
			break;
		}

		const br = this.root.getBoundingClientRect();
		if (x < br.left + EDGE) this.root.scrollLeft -= speed(br.left + EDGE - x);
		else if (x > br.right - EDGE) this.root.scrollLeft += speed(x - (br.right - EDGE));

		this.autoScrollRAF = requestAnimationFrame(this.autoScrollTick);
	};

	// --- drag & drop -----------------------------------------------------

	async handleDrop(args) {
		this.clearDropIndicator();
		this.onDragEnd();
		const src = args && args.source && args.source.data;
		if (!src || src.kind !== "card") return;

		const current = args && args.location && args.location.current;
		const targets = (current && current.dropTargets) || [];
		if (!targets.length) return;

		const innermost = targets[0];
		if (
			innermost &&
			innermost.data &&
			innermost.data.kind === "card" &&
			innermost.data.cardId === src.cardId
		) {
			return;
		}

		const clientY = (current && current.input && current.input.clientY) || 0;
		const cardTarget = targets.find(
			(t) => t.data && t.data.kind === "card" && t.data.cardId !== src.cardId
		);
		const colTarget = targets.find((t) => t.data && t.data.kind === "column");

		let toColumn;
		let toIndex;
		let edge = "bottom";
		if (cardTarget) {
			edge = closestEdge(cardTarget.element.getBoundingClientRect(), clientY);
			toColumn = cardTarget.data.columnId;
			toIndex = cardTarget.data.index + (edge === "bottom" ? 1 : 0);
		} else if (colTarget) {
			toColumn = colTarget.data.columnId;
			toIndex = this.orderedNames(toColumn).length;
		} else {
			return;
		}

		if (this.state.selection.length > 1 && this.state.selection.includes(src.cardId)) {
			const anchor =
				cardTarget && !this.state.selection.includes(cardTarget.data.cardId)
					? cardTarget.data.cardId
					: null;
			await this.applyMoveMultiple([...this.state.selection], toColumn, anchor, edge);
			return;
		}

		await this.applyMove(src.cardId, src.columnId, toColumn, toIndex);
	}

	async applyMove(cardId, fromColumn, toColumn, toIndex) {
		const sameColumn = fromColumn === toColumn;
		// Use full persisted order (includes not-yet-loaded names), not only
		// the loaded window — otherwise the server would drop unloaded cards.
		const loadedFrom = this.orderedNames(fromColumn);
		const fromNames = this.persistedOrder(fromColumn);
		const oldIndex = fromNames.indexOf(cardId);
		if (oldIndex < 0) return;

		const loadedTo = sameColumn ? loadedFrom : this.orderedNames(toColumn);
		const toNames = sameColumn ? fromNames : this.persistedOrder(toColumn);
		let insertIndex = this.persistedInsertIndex(toNames, loadedTo, toIndex);
		fromNames.splice(oldIndex, 1);
		if (sameColumn && oldIndex < insertIndex) insertIndex -= 1;
		insertIndex = clamp(insertIndex, 0, toNames.length);
		if (sameColumn && insertIndex === oldIndex) return;
		toNames.splice(insertIndex, 0, cardId);

		const card = this.findCard(cardId);
		if (!card) return;

		const move = {
			cardId,
			fromColumn,
			toColumn,
			oldIndex,
			newIndex: insertIndex,
			fromOrder: [...fromNames],
			toOrder: [...toNames],
		};

		const cb = this.options.callbacks || {};
		const guard = cb.canMoveCard && cb.canMoveCard(card, fromColumn, toColumn);
		if (guard === false || typeof guard === "string") return;
		const beforeOk = cb.onBeforeCardMove ? await cb.onBeforeCardMove(move) : undefined;
		if (beforeOk === false) return;

		const affected = sameColumn ? [fromColumn] : [fromColumn, toColumn];
		const snapshot = this.state;
		this.animateMove(affected, () => {
			this.setColumnOrder(fromColumn, fromNames, sameColumn ? 0 : -1);
			if (!sameColumn) {
				this.setColumnOrder(toColumn, toNames, 1);
				this.moveCardBucket(cardId, fromColumn, toColumn);
			}
			this.renderColumns(affected);
		});
		this.bus.emit("card:move", move);
		cb.onCardMove && cb.onCardMove(move);

		this.localMoveGraceUntil = Date.now() + 3000;
		try {
			await this.options.provider.moveCard(move);
			this.localMoveGraceUntil = Date.now() + 3000;
			cb.onAfterCardMove && cb.onAfterCardMove(move);
		} catch (error) {
			this.animateMove(affected, () => {
				this.state = snapshot;
				this.renderColumns(affected);
			});
			cb.onMoveError && cb.onMoveError(move, error);
			this.bus.emit("error", error);
		}
	}

	async applyMoveMultiple(cardIds, toColumn, anchorName, edge) {
		const selected = new Set(cardIds);
		const selectedOrdered = [];
		const sourceOf = new Map();
		// Walk full persisted order so multi-select keeps unloaded cards intact.
		for (const col of this.state.columns) {
			for (const name of this.persistedOrder(col.id)) {
				if (selected.has(name)) {
					selectedOrdered.push(name);
					sourceOf.set(name, col.id);
				}
			}
		}
		if (!selectedOrdered.length) return;

		const cb = this.options.callbacks || {};
		for (const name of selectedOrdered) {
			const from = sourceOf.get(name);
			const card = this.findCard(name);
			if (!from || !card) continue;
			const guard = cb.canMoveCard && cb.canMoveCard(card, from, toColumn);
			if (guard === false || typeof guard === "string") return;
		}

		const affected = [...new Set([...sourceOf.values(), toColumn])];
		const snapshot = this.state;

		const targetClean = this.persistedOrder(toColumn).filter((n) => !selected.has(n));
		let insertAt = targetClean.length;
		if (anchorName) {
			const idx = targetClean.indexOf(anchorName);
			if (idx >= 0) insertAt = edge === "bottom" ? idx + 1 : idx;
		}
		const finalTargetOrder = [
			...targetClean.slice(0, insertAt),
			...selectedOrdered,
			...targetClean.slice(insertAt),
		];
		const finalSourceOrders = new Map();
		for (const colId of new Set(sourceOf.values())) {
			if (colId === toColumn) continue;
			finalSourceOrders.set(
				colId,
				this.persistedOrder(colId).filter((n) => !selected.has(n))
			);
		}

		const addedToTarget = selectedOrdered.filter((n) => sourceOf.get(n) !== toColumn).length;

		this.animateMove(affected, () => {
			const columns = this.state.columns.map((col) => {
				if (col.id === toColumn) {
					return { ...col, order: finalTargetOrder, total: col.total + addedToTarget };
				}
				if (finalSourceOrders.has(col.id)) {
					const removed = selectedOrdered.filter(
						(n) => sourceOf.get(n) === col.id
					).length;
					return {
						...col,
						order: finalSourceOrders.get(col.id),
						total: Math.max(0, col.total - removed),
					};
				}
				return col;
			});

			const moved = [];
			for (const name of selectedOrdered) {
				const obj = this.findCard(name);
				if (obj) moved.push({ ...obj, [this.options.groupBy]: toColumn });
			}
			const cards = {};
			for (const [colId, list] of Object.entries(this.state.cards)) {
				cards[colId] = list.filter((cd) => !selected.has(cd.name));
			}
			cards[toColumn] = [...moved, ...(cards[toColumn] || [])];

			this.state = { ...this.state, columns, cards };
			this.renderColumns(affected);
		});

		this.setSelection([]);

		// One server write for the whole selection so a mid-loop failure cannot
		// leave partial moves persisted while the UI rolls back.
		const orderPayload = { [toColumn]: finalTargetOrder };
		for (const [colId, order] of finalSourceOrders) {
			orderPayload[colId] = order;
		}

		this.localMoveGraceUntil = Date.now() + 3000;
		try {
			if (this.options.provider.updateOrder) {
				await this.options.provider.updateOrder(orderPayload);
			} else {
				for (const name of selectedOrdered) {
					const from = sourceOf.get(name);
					await this.options.provider.moveCard({
						cardId: name,
						fromColumn: from,
						toColumn,
						oldIndex: 0,
						newIndex: finalTargetOrder.indexOf(name),
						fromOrder:
							from === toColumn
								? finalTargetOrder
								: finalSourceOrders.get(from) || [],
						toOrder: finalTargetOrder,
					});
				}
			}
			this.localMoveGraceUntil = Date.now() + 3000;
			for (const name of selectedOrdered) {
				const from = sourceOf.get(name);
				cb.onAfterCardMove &&
					cb.onAfterCardMove({
						cardId: name,
						fromColumn: from,
						toColumn,
						oldIndex: 0,
						newIndex: finalTargetOrder.indexOf(name),
						fromOrder:
							from === toColumn
								? finalTargetOrder
								: finalSourceOrders.get(from) || [],
						toOrder: finalTargetOrder,
					});
			}
		} catch (error) {
			this.state = snapshot;
			this.renderColumns(affected);
			// Surface the failure the same way a single-card move does — otherwise a
			// multi-move that fails just silently snaps back with no explanation.
			cb.onMoveError &&
				cb.onMoveError(
					{
						cardId:
							selectedOrdered.length === 1
								? selectedOrdered[0]
								: __("{0} cards", [selectedOrdered.length]),
						cardIds: [...selectedOrdered],
						toColumn,
					},
					error
				);
			this.bus.emit("error", error);
		}
	}

	renderColumns(ids) {
		for (const id of new Set(ids)) {
			const view = this.columnViews.get(id);
			const column = this.getColumn(id);
			if (!view || !column) continue;
			view.column = column;
			view.virtualizer.setCount(this.orderedCards(column).length);
			const colEl = view.body.parentElement;
			const countEl = colEl && colEl.querySelector(".kn-column-count");
			if (countEl) countEl.textContent = String(column.total);
			this.renderWindow(view);
		}
	}

	animateMove(ids, mutate) {
		const uniq = [...new Set(ids)];
		const first = new Map();
		for (const id of uniq) {
			const view = this.columnViews.get(id);
			if (!view) continue;
			view.body.querySelectorAll(".kn-card").forEach((el) => {
				if (el.dataset.name) first.set(el.dataset.name, el.getBoundingClientRect());
			});
		}

		mutate();

		for (const id of uniq) {
			const view = this.columnViews.get(id);
			if (!view) continue;
			view.body.querySelectorAll(".kn-card").forEach((el) => {
				const prev = el.dataset.name ? first.get(el.dataset.name) : undefined;
				const last = el.getBoundingClientRect();
				if (prev) {
					const dx = prev.left - last.left;
					const dy = prev.top - last.top;
					if (dx || dy) {
						el.animate(
							[
								{ transform: `translate(${dx}px, ${dy}px)` },
								{ transform: "translate(0, 0)" },
							],
							{ duration: 180, easing: "cubic-bezier(0.2, 0, 0, 1)" }
						);
					}
				} else {
					el.animate(
						[
							{ opacity: 0, transform: "scale(0.96)" },
							{ opacity: 1, transform: "scale(1)" },
						],
						{ duration: 200, easing: "cubic-bezier(0.2, 0, 0, 1)" }
					);
				}
			});
		}
	}

	showDropIndicator(el, edge) {
		if (this.dropIndicatorEl && this.dropIndicatorEl !== el) {
			this.dropIndicatorEl.classList.remove("kn-drop-before", "kn-drop-after");
		}
		this.dropIndicatorEl = el;
		el.classList.toggle("kn-drop-before", edge === "top");
		el.classList.toggle("kn-drop-after", edge === "bottom");
	}

	clearDropIndicator(el) {
		const target = el || this.dropIndicatorEl;
		if (target) target.classList.remove("kn-drop-before", "kn-drop-after");
		if (!el || el === this.dropIndicatorEl) this.dropIndicatorEl = null;
	}

	setColumnOrder(columnId, order, totalDelta) {
		this.state = {
			...this.state,
			columns: this.state.columns.map((c) =>
				c.id === columnId ? { ...c, order: [...order], total: c.total + totalDelta } : c
			),
		};
	}

	moveCardBucket(cardId, fromColumn, toColumn) {
		const card = this.findCard(cardId);
		if (!card) return;
		const fromArr = (this.state.cards[fromColumn] || []).filter((c) => c.name !== cardId);
		const toArr = [
			...(this.state.cards[toColumn] || []),
			{ ...card, [this.options.groupBy]: toColumn },
		];
		this.state = {
			...this.state,
			cards: { ...this.state.cards, [fromColumn]: fromArr, [toColumn]: toArr },
		};
	}

	orderedNames(columnId) {
		const column = this.getColumn(columnId);
		return column ? this.orderedCards(column).map((c) => c.name) : [];
	}

	/**
	 * Full column order for persistence (loaded + not-yet-loaded names).
	 * Drag UI uses orderedNames(); saves must use this so unloaded cards stay put.
	 */
	persistedOrder(columnId) {
		const column = this.getColumn(columnId);
		if (!column) return [];
		if (column.order && column.order.length) {
			const seen = new Set(column.order);
			const extras = (this.state.cards[columnId] || [])
				.map((c) => c.name)
				.filter((name) => !seen.has(name));
			return [...column.order, ...extras];
		}
		return this.orderedNames(columnId);
	}

	/**
	 * Map a drop index from the loaded (visible) list into the full persisted order.
	 * Unloaded cards usually sit after the loaded prefix, so visual indices align
	 * with that prefix; append-after-last-loaded inserts after the last visible card.
	 */
	persistedInsertIndex(persisted, loaded, toIndex) {
		if (!loaded.length) return clamp(toIndex, 0, persisted.length);
		if (toIndex <= 0) {
			const first = persisted.indexOf(loaded[0]);
			return first >= 0 ? first : 0;
		}
		if (toIndex >= loaded.length) {
			const last = persisted.indexOf(loaded[loaded.length - 1]);
			return last >= 0 ? last + 1 : persisted.length;
		}
		const at = persisted.indexOf(loaded[toIndex]);
		return at >= 0 ? at : clamp(toIndex, 0, persisted.length);
	}

	findCard(cardId) {
		for (const list of Object.values(this.state.cards)) {
			const found = list.find((c) => c.name === cardId);
			if (found) return found;
		}
		return undefined;
	}

	// --- internals -------------------------------------------------------

	orderedCards(column) {
		const loaded = this.state.cards[column.id] || [];
		if (!column.order.length) return loaded;

		const byName = new Map(loaded.map((c) => [c.name, c]));
		const ordered = [];
		for (const name of column.order) {
			const card = byName.get(name);
			if (card) {
				ordered.push(card);
				byName.delete(name);
			}
		}
		for (const card of byName.values()) ordered.push(card);
		return ordered;
	}

	track(cleanup) {
		if (typeof cleanup === "function") this.rendererCleanups.push(cleanup);
	}

	flushList(list) {
		for (const fn of list) {
			try {
				fn();
			} catch (e) {
				// cleanup must not break teardown
			}
		}
		list.length = 0;
	}

	flushRendererCleanups() {
		this.flushList(this.rendererCleanups);
	}

	teardownViews() {
		this.resizeObserver && this.resizeObserver.disconnect();
		this.flushRendererCleanups();
		this.flushList(this.dragCleanups);
		for (const view of this.columnViews.values()) {
			this.flushList(view.cardCleanups);
		}
		this.columnViews.clear();
	}

	setLoading(loading) {
		this.state = { ...this.state, loading };
		this.root && this.root.classList.toggle("kn-loading", loading);
	}

	getColumn(id) {
		return this.state.columns.find((c) => c.id === id);
	}
}
