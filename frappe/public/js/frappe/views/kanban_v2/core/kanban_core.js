/**
 * KanbanCore — board engine: columns, virtualized cards, drag/drop, selection,
 * inline create, pagination. Host supplies `provider`, `callbacks`, `renderers`.
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
import { ColumnVirtualizer } from "./virtualization";

const DEFAULT_PAGE_LENGTH = 50;
/** Extra px added per card to account for inter-card margin in the height model. */
const CARD_GAP = 8;
/** Prefetch the next page when the rendered window is within N rows of loaded end. */
const PREFETCH_ROWS = 8;

// Counter for building each board's unique instanceId (see constructor).
let _kanban_instance_seq = 0;

const CLS = {
	board: "kn-board flex gap-3 overflow-x-auto pb-2",
	column: "kn-column flex flex-col overflow-hidden rounded-lg bg-surface-gray-1 pb-2",
	header: "kn-column-header flex items-center justify-between gap-2 ps-4 pe-1 pt-1 shrink-0",
	headerMeta: "kn-column-meta flex items-center gap-1.5 min-w-0",
	dot: "kn-column-dot indicator shrink-0",
	title: "kn-column-title text-sm-medium text-ink-gray-8 truncate min-w-0",
	count: "kn-column-count text-sm text-ink-gray-5 shrink-0",
	body: "kn-column-body flex-1 px-3 pt-2",
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
		// Shared across every drop target / drag source on this board. Grouped
		// swimlanes each get their own id so a card cannot be dropped into
		// another group's columns (monitors are document-global).
		this.instanceId = `kn-${++_kanban_instance_seq}`;

		this.state = { columns: [], cards: {}, selection: [], loading: false };

		this.rendererCleanups = [];
		this.dragCleanups = [];
		this.monitorCleanup = null;
		this.columnViews = new Map();
		this.providerUnsub = null;
		this.resizeObserver = null;
		this.dropSlotEl = null;
		this.dropAnchor = null;
		this.dropCommitPending = false;
		this.dragSourceColumn = null;
		this.dragPreview = null;
		this.dragGrab = null;
		this.lastSelected = null;
		this.pointer = { x: 0, y: 0 };
		this.autoScrollRAF = null;
		this.ignoreRemoteUpdatesUntil = 0;
		this.columnSortable = null;
		// Incremented on every reload so a late response from an earlier reload
		// can be discarded instead of overwriting fresher data.
		this.reloadSeq = 0;
	}

	/** Mount into `container`, wire DnD/scroll, and load the board. */
	mount(container) {
		this.container = container;
		this.root = document.createElement("div");
		this.root.className = CLS.board;
		container.replaceChildren(this.root);
		this.setupColumnSortable();

		if (this.options.provider.onRemoteUpdate) {
			this.providerUnsub = this.options.provider.onRemoteUpdate(() => {
				// Ignore the realtime echo of our own move (already applied optimistically).
				if (Date.now() < this.ignoreRemoteUpdatesUntil) return;
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

	/** Fetch board data and re-render; responses from an earlier reload are ignored. */
	async reload() {
		const reloadSeq = ++this.reloadSeq;
		this.setLoading(true);
		// First load has no columns yet — show placeholder columns instead of a
		// blank panel while loadBoard() runs. render() replaces them with real data.
		if (!this.state.columns.length) this.renderSkeleton();
		try {
			const { columns, cards } = await this.options.provider.loadBoard();
			if (reloadSeq !== this.reloadSeq) return;
			this.state = { ...this.state, columns, cards };
			this.render();
			this.bus.emit("state:change", this.getState());
		} catch (error) {
			if (reloadSeq === this.reloadSeq) this.bus.emit("error", error);
		} finally {
			if (reloadSeq === this.reloadSeq) this.setLoading(false);
		}
	}

	getState() {
		return this.state;
	}

	select(cardIds) {
		this.setSelection(cardIds);
	}

	on(event, cb) {
		return this.bus.on(event, cb);
	}

	/** Tear down listeners, drag UI, and DOM. Safe to call mid-drag. */
	destroy() {
		this.teardownViews();
		this.onDragEnd();
		// Teardown can happen while a drag is still active (route change/unmount).
		// Ensure transient drag visuals are always removed.
		this.dragSourceColumn = null;
		this.clearCardsDragging();
		this.endCardPreview();
		this.clearDropIndicator();
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

	/** Click / ctrl / shift selection against the loaded column order. */
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

	/** Replace selection and update selected card chrome + callbacks. */
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

	/** Rebuild all column shells and visible card windows from state. */
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

	/** Show the inline title input under a column. */
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

	/** Create a card via callback and prepend it into the column. */
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

	/** Recompute visible windows after resize / layout change. */
	refreshWindows() {
		if (!this.options.virtualization) return;
		for (const view of this.columnViews.values()) {
			if (view.virtualizer.count === 0) continue;
			const visibleRange = view.virtualizer.range(
				view.body.scrollTop,
				view.body.clientHeight || 600
			);
			if (
				visibleRange.start !== view.renderedRange.start ||
				visibleRange.end !== view.renderedRange.end
			) {
				this.renderWindow(view);
			}
		}
	}

	/** Build one column (header + scroll body + virtualizer view). */
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
			bindColumnDropTarget(
				body,
				{ kind: "column", columnId: column.id, boardId: this.instanceId },
				({ source }) => source.data && source.data.boardId === this.instanceId
			)
		);
		this.resizeObserver && this.resizeObserver.observe(body);

		const topSpacer = document.createElement("div");
		topSpacer.className = "kn-spacer w-full";
		const bottomSpacer = document.createElement("div");
		bottomSpacer.className = "kn-spacer w-full";

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

	/** Paint the virtualized (or full) card window for a column. */
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
		const visibleRange = this.options.virtualization
			? view.virtualizer.range(view.body.scrollTop, viewport)
			: { start: 0, end: ordered.length, padTop: 0, padBottom: 0 };

		this.flushList(view.cardCleanups);
		const nodes = [];
		for (let i = visibleRange.start; i < visibleRange.end; i++) {
			nodes.push(this.createCardEl(view.column, ordered[i], i, view.cardCleanups));
		}
		view.topSpacer.style.height = `${visibleRange.padTop}px`;
		view.bottomSpacer.style.height = `${visibleRange.padBottom}px`;
		view.body.replaceChildren(view.topSpacer, ...nodes, view.bottomSpacer);
		view.renderedRange = { start: visibleRange.start, end: visibleRange.end };

		if (this.options.virtualization) {
			let changed = false;
			nodes.forEach((node, k) => {
				const h = node.getBoundingClientRect().height + CARD_GAP;
				if (view.virtualizer.measure(visibleRange.start + k, h)) changed = true;
			});
			if (changed) {
				view.virtualizer.rebuild();
				view.topSpacer.style.height = `${view.virtualizer.offsetOf(visibleRange.start)}px`;
				view.bottomSpacer.style.height = `${
					view.virtualizer.totalHeight - view.virtualizer.offsetOf(visibleRange.end)
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
			ghostClass: "kn-col-dragging",
			direction: "horizontal",
			bubbleScroll: true,
			// Don't preventDefault on body scroll / card / header-add interactions.
			filter: ".kn-column-body, .kn-column-footer, .kn-card, .kn-add-card",
			preventOnFilter: false,
			onEnd: (evt) => this.onColumnSortEnd(evt),
		});
	}

	/** Persist column order after a header drag; roll back on failure. */
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

	/** Create one card element and bind drag / drop / click handlers. */
	createCardEl(column, card, index, cleanups) {
		const el = document.createElement("div");
		el.className = CLS.card;
		el.dataset.name = card.name;
		el.tabIndex = 0;
		const selected = this.state.selection.includes(card.name);
		if (selected) el.classList.add("kn-selected");

		const cleanup = this.options.renderCard(card, el, { column, index, selected });
		if (typeof cleanup === "function") cleanups.push(cleanup);

		const dragData = {
			kind: "card",
			cardId: card.name,
			columnId: column.id,
			index,
			boardId: this.instanceId,
		};
		cleanups.push(
			bindCardDrag(el, dragData, {
				onStart: (input) => {
					this.dragSourceColumn = column.id;
					this.markCardsDragging(card.name);
					this.startCardPreview(el, card.name, input);
				},
				onEnd: () => {
					this.dragSourceColumn = null;
					this.clearCardsDragging();
					this.endCardPreview();
					// Defer: handleDrop may still be in its sync setup and about to
					// claim the slot for the post-drop FLIP. If nothing claims it,
					// ease the gap closed (cancel / invalid drop).
					queueMicrotask(() => {
						if (!this.dropCommitPending) {
							this.clearDropIndicator({ animate: true });
						}
					});
				},
			}),
			bindCardDropTarget(el, () => dragData, {
				canDrop: ({ source }) => source.data && source.data.boardId === this.instanceId,
				// Only ever MOVE the slot to the hovered card. Removing it on leave
				// (then re-inserting on the next card) flashed the dimmed source card
				// between states — the slot now lives until drop/drag-end.
				onEdge: (edge) => this.showDropIndicator(el, edge, dragData),
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

	/** On scroll: refresh the virtual window and prefetch the next page. */
	onColumnScroll(view) {
		if (!this.columnViews.has(view.column.id)) return;

		if (this.options.virtualization) {
			const visibleRange = view.virtualizer.range(
				view.body.scrollTop,
				view.body.clientHeight || 600
			);
			if (
				visibleRange.start !== view.renderedRange.start ||
				visibleRange.end !== view.renderedRange.end
			) {
				this.renderWindow(view);
			}
		}
		this.maybeLoadMore(view);
	}

	/** Prefetch when the rendered window nears the end of loaded cards. */
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

	/** Load the next page for a column (queued via loadColumnPageOnce). */
	async loadMore(columnId, start) {
		const view = this.columnViews.get(columnId);
		// A load already running for this column? The shared per-column queue would
		// serialize us anyway; returning early just keeps scroll from stacking calls.
		if (!view || view.loading) return;
		try {
			await this.loadColumnPageOnce(columnId);
		} catch (error) {
			this.bus.emit("error", error);
		}
	}

	/**
	 * The single choke point every page fetch goes through — scroll prefetch
	 * (`loadMore`) AND a drag's `ensureOrderKnown`. Calls are serialized per column
	 * via `_pageLoads`, so a column never has two overlapping fetches for the same
	 * offset: each load computes its offset from the freshly-appended state, and
	 * appends are de-duped by card name as a backstop. Resolves to
	 * `{ fetched, appended }`.
	 */
	loadColumnPageOnce(columnId, reloadSeq = this.reloadSeq) {
		if (!this._pageLoads) this._pageLoads = {};
		const prev = this._pageLoads[columnId] || Promise.resolve();
		// Chain onto any in-flight load for this column (continue even if it threw).
		const next = prev
			.catch(() => {})
			.then(() => this._appendNextColumnPage(columnId, reloadSeq))
			.finally(() => {
				if (this._pageLoads[columnId] === next) delete this._pageLoads[columnId];
			});
		this._pageLoads[columnId] = next;
		return next;
	}

	/** Fetch and append one page of cards for a column. */
	async _appendNextColumnPage(columnId, reloadSeq) {
		// If the board already reloaded, skip the fetch entirely.
		// This prevents a stale request from setting loading=true on the new view.
		if (reloadSeq !== this.reloadSeq) return { fetched: 0, appended: 0 };
		const view = this.columnViews.get(columnId);
		const column = this.getColumn(columnId);
		if (!column) return { fetched: 0, appended: 0 };
		const loaded = (this.state.cards[columnId] || []).length;
		if (column.total != null && loaded >= column.total) return { fetched: 0, appended: 0 };
		if (view) view.loading = true;
		try {
			const { total, cards } = await this.options.provider.loadColumnPage(
				columnId,
				loaded,
				this.options.pageLength
			);
			// Reload replaced board state while this request was in-flight.
			if (reloadSeq !== this.reloadSeq)
				return { fetched: (cards || []).length, appended: 0 };
			const existing = this.state.cards[columnId] || [];
			// De-dupe by name: a racing fetch (or a re-fetched offset) can't append a
			// card the column already holds.
			const have = new Set(existing.map((c) => c.name));
			const fresh = (cards || []).filter((c) => c && !have.has(c.name));
			this.state = {
				...this.state,
				cards: { ...this.state.cards, [columnId]: [...existing, ...fresh] },
				columns: this.state.columns.map((c) => (c.id === columnId ? { ...c, total } : c)),
			};
			const col = this.getColumn(columnId);
			if (view && col) {
				view.column = col;
				view.virtualizer.setCount(this.orderedCards(col).length);
				this.renderWindow(view);
			}
			this.bus.emit("state:change", this.getState());
			return { fetched: (cards || []).length, appended: fresh.length };
		} finally {
			if (view) view.loading = false;
		}
	}

	/**
	 * Guarantee a column's full card order is known before a move.
	 *
	 * `persistedOrder()` returns null for a column that has no saved order and is
	 * only partially loaded — we can't build a truncation-safe list without the
	 * unloaded names. Rather than abort the drag (which looks broken to the user),
	 * load the remaining pages: once `loaded === total` the natural order is fully
	 * known and the move proceeds normally. Resolves to true when the order is
	 * usable, false only if the column vanished or the backend stops returning rows.
	 */
	async ensureOrderKnown(columnId) {
		const reloadSeq = this.reloadSeq;
		if (this.persistedOrder(columnId)) return true;
		while (!this.persistedOrder(columnId)) {
			if (reloadSeq !== this.reloadSeq) return false;
			const column = this.getColumn(columnId);
			if (!column) return false;
			const loaded = (this.state.cards[columnId] || []).length;
			if (loaded >= (column.total || 0)) break;
			// Same serialized loader as the scroll prefetch, so a drag and a scroll
			// can't fetch the same offset and double-append the remaining pages.
			const { fetched } = await this.loadColumnPageOnce(columnId, reloadSeq);
			if (reloadSeq !== this.reloadSeq) return false;
			if (!fetched) break; // no progress — avoid an infinite loop
		}
		return !!this.persistedOrder(columnId);
	}

	/**
	 * Surface a move that couldn't be applied because the column order couldn't be
	 * resolved — so a rejected drag shows feedback (and rolls the card back)
	 * instead of silently vanishing. Returns undefined so callers can `return this…`.
	 */
	reportMoveBlocked(cardId, fromColumn, toColumn) {
		const cb = this.options.callbacks || {};
		const error = new Error("kanban: could not resolve column order for the move");
		cb.onMoveError && cb.onMoveError({ cardId, fromColumn, toColumn }, error);
		this.bus.emit("error", error);
	}

	/** Track pointer + kick auto-scroll while a native drag is active. */
	onDragOver = (e) => {
		this.pointer.x = e.clientX;
		this.pointer.y = e.clientY;
		this.positionCardPreview(e.clientX, e.clientY);
		if (this.autoScrollRAF === null) {
			this.autoScrollRAF = requestAnimationFrame(this.autoScrollTick);
		}
	};

	/** Stop auto-scroll and clear drag chrome when the drag ends. */
	onDragEnd = () => {
		if (this.autoScrollRAF !== null) {
			cancelAnimationFrame(this.autoScrollRAF);
			this.autoScrollRAF = null;
		}
	};

	/** Scroll column/board when the pointer is near an edge during drag. */
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

	/** Resolve a Pragmatic drop into a single- or multi-card move. */
	async handleDrop(args) {
		this.onDragEnd();
		const src = args && args.source && args.source.data;
		// Cancelled / invalid drops: ease the hover gap closed. Successful moves
		// keep the slot until animateMove so target cards don't bounce.
		const abort = () => this.clearDropIndicator({ animate: true });

		if (!src || src.kind !== "card") return abort();
		// Each swimlane board registers a global monitor — ignore drags that
		// started on another instance, and never apply a drop onto foreign targets.
		if (src.boardId !== this.instanceId) return abort();
		if (!this.findCard(src.cardId)) return abort();

		const current = args && args.location && args.location.current;
		const targets = (current && current.dropTargets) || [];
		if (!targets.length) return abort();

		const innermost = targets[0];
		if (
			innermost &&
			innermost.data &&
			innermost.data.kind === "card" &&
			innermost.data.cardId === src.cardId
		) {
			return abort();
		}

		const clientY = (current && current.input && current.input.clientY) || 0;
		const cardTarget = targets.find(
			(t) =>
				t.data &&
				t.data.kind === "card" &&
				t.data.cardId !== src.cardId &&
				t.data.boardId === this.instanceId
		);
		const colTarget = targets.find(
			(t) => t.data && t.data.kind === "column" && t.data.boardId === this.instanceId
		);

		let toColumn;
		let toIndex;
		let edge = "bottom";
		if (cardTarget) {
			edge = closestEdge(cardTarget.element.getBoundingClientRect(), clientY);
			toColumn = cardTarget.data.columnId;
			toIndex = cardTarget.data.index + (edge === "bottom" ? 1 : 0);
		} else if (colTarget) {
			// Released over the column — or over the placeholder slot, which is
			// pointer-events:none so the hit test falls through to the column. Derive
			// the insert index from where the pointer actually is among the rendered
			// cards, so the card lands where the user dropped it (and stays visible).
			toColumn = colTarget.data.columnId;
			toIndex = this.dropIndexFromPointer(toColumn, clientY);
		} else {
			return abort();
		}

		// Same-column drops are a no-op: this board is about moving cards BETWEEN
		// columns (which changes the group-by field). We don't support manual
		// within-column reordering — the board fetches/paginates by `modified desc`,
		// so a reorder can't be reflected on large columns anyway, and persisting one
		// calls update_order_for_single_card (which set_value's the card, bumping
		// `modified`) for no visible gain. Cross-column moves always go through.
		if (toColumn === src.columnId) {
			return abort();
		}

		// Claim the hover slot so onEnd's microtask does not close it before
		// animateMove can measure with the gap still open.
		this.dropCommitPending = true;
		try {
			if (this.state.selection.length > 1 && this.state.selection.includes(src.cardId)) {
				const anchor =
					cardTarget && !this.state.selection.includes(cardTarget.data.cardId)
						? cardTarget.data.cardId
						: null;
				await this.applyMoveMultiple([...this.state.selection], toColumn, anchor, edge);
				return;
			}

			await this.applyMove(src.cardId, src.columnId, toColumn, toIndex);
		} finally {
			this.dropCommitPending = false;
			// Aborted moves clear themselves; this is a safety net if they don't.
			if (this.dropSlotEl && this.dropSlotEl.parentNode) {
				this.clearDropIndicator({ animate: true });
			}
		}
	}

	/** Optimistic single-card move + persist; animates rollback on error. */
	async applyMove(cardId, fromColumn, toColumn, toIndex) {
		const sameColumn = fromColumn === toColumn;
		// A partially-loaded column with no saved order has an unknown full order;
		// load the rest first so the move works instead of silently aborting. If it
		// can't be resolved (backend stopped returning rows), tell the user rather
		// than snapping the card back with no explanation.
		if (!(await this.ensureOrderKnown(fromColumn))) {
			this.clearDropIndicator({ animate: true });
			return this.reportMoveBlocked(cardId, fromColumn, toColumn);
		}
		if (!sameColumn && !(await this.ensureOrderKnown(toColumn))) {
			this.clearDropIndicator({ animate: true });
			return this.reportMoveBlocked(cardId, fromColumn, toColumn);
		}
		// Use full persisted order (includes not-yet-loaded names), not only
		// the loaded window — otherwise the server would drop unloaded cards.
		const loadedFrom = this.orderedNames(fromColumn);
		const fromNames = this.persistedOrder(fromColumn);
		// null means partial load with no saved order — sending it would truncate unloaded names.
		if (!fromNames) {
			this.clearDropIndicator({ animate: true });
			return this.reportMoveBlocked(cardId, fromColumn, toColumn);
		}
		const oldIndex = fromNames.indexOf(cardId);
		if (oldIndex < 0) {
			this.clearDropIndicator({ animate: true });
			return;
		}

		const loadedTo = sameColumn ? loadedFrom : this.orderedNames(toColumn);
		const toNames = sameColumn ? fromNames : this.persistedOrder(toColumn);
		if (!toNames) {
			this.clearDropIndicator({ animate: true });
			return this.reportMoveBlocked(cardId, fromColumn, toColumn);
		}
		let insertIndex = this.persistedInsertIndex(toNames, loadedTo, toIndex);
		fromNames.splice(oldIndex, 1);
		if (sameColumn && oldIndex < insertIndex) insertIndex -= 1;
		insertIndex = clamp(insertIndex, 0, toNames.length);
		if (sameColumn && insertIndex === oldIndex) {
			this.clearDropIndicator({ animate: true });
			return;
		}
		toNames.splice(insertIndex, 0, cardId);

		const card = this.findCard(cardId);
		if (!card) {
			this.clearDropIndicator({ animate: true });
			return;
		}

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
		if (guard === false || typeof guard === "string") {
			this.clearDropIndicator({ animate: true });
			return;
		}
		const beforeOk = cb.onBeforeCardMove ? await cb.onBeforeCardMove(move) : undefined;
		if (beforeOk === false) {
			this.clearDropIndicator({ animate: true });
			return;
		}

		const affected = sameColumn ? [fromColumn] : [fromColumn, toColumn];
		const snapshot = this.state;
		const reloadSeqAtSnapshot = this.reloadSeq;
		// Measure with the hover slot still open, then collapse slot + apply the
		// new layout in one FLIP so (1) source cards ease up once, (2) target cards
		// stay put (gap already reserved), (3) the moved card flies source→target.
		this.animateMove(affected, () => {
			this.clearDropIndicator();
			this.setColumnOrder(fromColumn, fromNames, sameColumn ? 0 : -1);
			if (sameColumn) {
				// Keep the loaded list in visual order (display uses it while paginated).
				this.reorderLoaded(fromColumn, cardId, toIndex);
			} else {
				this.setColumnOrder(toColumn, toNames, 1);
				this.moveCardBucket(cardId, fromColumn, toColumn, toIndex);
			}
			this.renderColumns(affected);
		});
		this.bus.emit("card:move", move);
		cb.onCardMove && cb.onCardMove(move);

		this.ignoreRemoteUpdatesUntil = Date.now() + 3000;
		try {
			await this.options.provider.moveCard(move);
			this.ignoreRemoteUpdatesUntil = Date.now() + 3000;
			cb.onAfterCardMove && cb.onAfterCardMove(move);
		} catch (error) {
			// Skip rollback if a reload has since replaced this state.
			if (this.reloadSeq === reloadSeqAtSnapshot) {
				this.animateMove(affected, () => {
					this.state = snapshot;
					this.renderColumns(affected);
				});
			}
			cb.onMoveError && cb.onMoveError(move, error);
			this.bus.emit("error", error);
		}
	}

	/** Optimistic multi-select move in one request; reloads on failure. */
	async applyMoveMultiple(cardIds, toColumn, anchorName, edge) {
		const selected = new Set(cardIds);
		// Load the target and any column holding a selected card that has no saved
		// order yet, so no selected card is silently dropped from the move below.
		const involved = new Set([toColumn]);
		for (const col of this.state.columns) {
			const names = (this.state.cards[col.id] || []).map((c) => c.name);
			if (names.some((n) => selected.has(n))) involved.add(col.id);
		}
		for (const colId of involved) {
			if (!(await this.ensureOrderKnown(colId))) {
				this.clearDropIndicator({ animate: true });
				return this.reportMoveBlocked(cardIds[0], colId, toColumn);
			}
		}

		const selectedOrdered = [];
		const sourceOf = new Map();
		// Walk full persisted order so multi-select keeps unloaded cards intact.
		for (const col of this.state.columns) {
			const colOrder = this.persistedOrder(col.id);
			if (!colOrder) continue; // partial load, no saved order — skip column
			for (const name of colOrder) {
				if (selected.has(name)) {
					selectedOrdered.push(name);
					sourceOf.set(name, col.id);
				}
			}
		}
		if (!selectedOrdered.length) {
			this.clearDropIndicator({ animate: true });
			return;
		}

		const cb = this.options.callbacks || {};
		for (const name of selectedOrdered) {
			const from = sourceOf.get(name);
			const card = this.findCard(name);
			if (!from || !card) continue;
			const guard = cb.canMoveCard && cb.canMoveCard(card, from, toColumn);
			if (guard === false || typeof guard === "string") {
				this.clearDropIndicator({ animate: true });
				return;
			}
		}

		const affected = [...new Set([...sourceOf.values(), toColumn])];
		const snapshot = this.state;
		const reloadSeqAtSnapshot = this.reloadSeq;

		const toPersistedOrder = this.persistedOrder(toColumn);
		// null means partial load with no saved order — abort to avoid truncating unloaded names.
		if (!toPersistedOrder) {
			this.clearDropIndicator({ animate: true });
			return this.reportMoveBlocked(cardIds[0], sourceOf.get(cardIds[0]), toColumn);
		}
		const targetClean = toPersistedOrder.filter((n) => !selected.has(n));
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
			const srcOrder = this.persistedOrder(colId);
			if (!srcOrder) continue; // shouldn't happen: sourceOf was built from non-null orders
			finalSourceOrders.set(
				colId,
				srcOrder.filter((n) => !selected.has(n))
			);
		}

		const addedToTarget = selectedOrdered.filter((n) => sourceOf.get(n) !== toColumn).length;

		this.animateMove(affected, () => {
			// Same as single-card: keep hover gap until this FLIP mutate.
			this.clearDropIndicator();
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

		// Multi-move must be one request. A sequential moveCard loop can commit
		// early cards, then fail later — restoring `snapshot` would lie about
		// server state. Providers without updateOrder cannot multi-move safely.
		const orderPayload = { [toColumn]: finalTargetOrder };
		for (const [colId, order] of finalSourceOrders) {
			orderPayload[colId] = order;
		}

		const moveErrorArgs = {
			cardId:
				selectedOrdered.length === 1
					? selectedOrdered[0]
					: __("{0} cards", [selectedOrdered.length]),
			cardIds: [...selectedOrdered],
			toColumn,
		};

		if (!this.options.provider.updateOrder) {
			// Skip rollback if a reload has since replaced this state.
			if (this.reloadSeq === reloadSeqAtSnapshot) {
				this.state = snapshot;
				this.renderColumns(affected);
			}
			const error = new Error(__("Bulk move is not supported"));
			cb.onMoveError && cb.onMoveError(moveErrorArgs, error);
			this.bus.emit("error", error);
			return;
		}

		this.ignoreRemoteUpdatesUntil = Date.now() + 3000;
		try {
			await this.options.provider.updateOrder(orderPayload);
			this.ignoreRemoteUpdatesUntil = Date.now() + 3000;
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
			// Skip rollback if a reload (e.g. from another session) has since replaced this state.
			if (this.reloadSeq === reloadSeqAtSnapshot) {
				this.state = snapshot;
				this.renderColumns(affected);
			}
			// Refetch the actual server state.
			this.reload();
			cb.onMoveError && cb.onMoveError(moveErrorArgs, error);
			this.bus.emit("error", error);
		}
	}

	/** Re-render only the given columns (counts + card windows). */
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

	/**
	 * FLIP-animate `.kn-card` nodes inside the given column bodies across a DOM
	 * mutation. Used after a real drop and while the hover drop-slot moves so
	 * sibling cards ease into place instead of jumping.
	 */
	flipCards(bodies, mutate) {
		const parents = [...new Set((bodies || []).filter(Boolean))];
		const first = new Map();
		for (const parent of parents) {
			parent.querySelectorAll(".kn-card").forEach((el) => {
				if (!el.dataset.name) return;
				// Finish any in-flight FLIP so the next read is layout position,
				// not a mid-tween transform (which would skew the next delta).
				el.getAnimations().forEach((a) => a.cancel());
				first.set(el.dataset.name, el.getBoundingClientRect());
			});
		}

		mutate();

		for (const parent of parents) {
			parent.querySelectorAll(".kn-card").forEach((el) => {
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

	/** FLIP across columns, then drop the hover slot after mutate. */
	animateMove(ids, mutate) {
		const bodies = [...new Set(ids)]
			.map((id) => {
				const view = this.columnViews.get(id);
				return view && view.body;
			})
			.filter(Boolean);
		this.flipCards(bodies, mutate);
	}

	/**
	 * Lift the dragged card — and every other selected card in a multi-selection —
	 * so a bulk drag shows all the cards being moved, not just the one grabbed.
	 */
	markCardsDragging(cardId) {
		const sel = this.state.selection;
		const names = sel.length > 1 && sel.includes(cardId) ? sel : [cardId];
		const set = new Set(names);
		this.root &&
			this.root.querySelectorAll(".kn-card").forEach((el) => {
				if (el.dataset.name && set.has(el.dataset.name)) el.classList.add("kn-dragging");
			});
	}

	clearCardsDragging() {
		this.root &&
			this.root
				.querySelectorAll(".kn-card.kn-dragging")
				.forEach((el) => el.classList.remove("kn-dragging"));
	}

	/**
	 * Build the tilted card that follows the pointer (the native ghost is
	 * disabled in drag.js). A multi-selection gets a fanned "deck" behind the top
	 * card plus a count badge, so a bulk drag clearly carries the whole set.
	 */
	startCardPreview(el, cardId, input) {
		this.endCardPreview(); // never leave a previous preview orphaned
		const rect = el.getBoundingClientRect();
		const sel = this.state.selection;
		const count = sel.length > 1 && sel.includes(cardId) ? sel.length : 1;
		this.dragGrab = {
			dx: input ? input.clientX - rect.left : rect.width / 2,
			dy: input ? input.clientY - rect.top : 24,
			h: rect.height,
			// Multi-drag reserves N card heights so the post-drop FLIP doesn't
			// have to shove target cards further after release.
			count,
		};

		const layer = document.createElement("div");
		layer.className = "kn-drag-preview";
		layer.style.width = `${rect.width}px`;

		for (let i = Math.min(count - 1, 2); i >= 1; i--) {
			const ghost = document.createElement("div");
			ghost.className = "kn-drag-stack";
			ghost.style.transform = `translate(${i * 7}px, ${i * 7}px) rotate(${i * 3}deg)`;
			layer.appendChild(ghost);
		}

		const top = el.cloneNode(true);
		top.classList.remove("kn-dragging", "kn-selected");
		top.classList.add("kn-drag-preview-card");
		top.style.width = `${rect.width}px`;
		layer.appendChild(top);

		document.body.appendChild(layer);
		this.dragPreview = layer;
		const px = input ? input.clientX : this.pointer.x;
		const py = input ? input.clientY : this.pointer.y;
		this.positionCardPreview(px, py);
	}

	/** Follow the pointer with the custom drag preview. */
	positionCardPreview(x, y) {
		if (!this.dragPreview || !this.dragGrab) return;
		const left = x - this.dragGrab.dx;
		const top = y - this.dragGrab.dy;
		this.dragPreview.style.transform = `translate(${left}px, ${top}px) rotate(3deg)`;
	}

	/** Remove the custom drag preview from the document. */
	endCardPreview() {
		if (this.dragPreview) {
			this.dragPreview.remove();
			this.dragPreview = null;
		}
		this.dragGrab = null;
	}

	/**
	 * Open a dashed placeholder slot at the drop position — cards flow around it,
	 * like the Frappe UI board, so you see exactly where the card(s) will land.
	 * `edge` is which half of `el` the pointer is over (top → slot before it).
	 * Sibling cards FLIP-animate into place (same motion as post-drop).
	 */
	showDropIndicator(el, edge, data) {
		// Don't tease a drop that won't happen: same-column drops are a no-op
		// (see handleDrop), so hide the placeholder while over the source column
		// instead of showing a slot the release will ignore.
		if (data && data.columnId === this.dragSourceColumn) {
			this.clearDropIndicator({ animate: true });
			return;
		}
		this.dropAnchor = el;
		const slot = this.dropSlotEl || (this.dropSlotEl = this.buildDropSlot());
		if (this.dragGrab && this.dragGrab.h) {
			const n = this.dragGrab.count || 1;
			// Slot height = N cards + the mb-2 gaps between them.
			slot.style.height = `${this.dragGrab.h * n + CARD_GAP * (n - 1)}px`;
		}
		const parent = el.parentNode;
		if (!parent) return;
		const ref = edge === "top" ? el : el.nextSibling;
		if (slot.parentNode === parent && slot.nextSibling === ref) return; // already placed

		const prevParent = slot.parentNode;
		this.flipCards([parent, prevParent], () => {
			parent.insertBefore(slot, ref);
		});
	}

	/** Create the dashed hover placeholder element (reused). */
	buildDropSlot() {
		const slot = document.createElement("div");
		slot.className = "kn-drop-slot shrink-0 mb-2";
		return slot;
	}

	/**
	 * Remove the hover drop slot.
	 * @param {{ animate?: boolean }} [opts] - When true (hover leave / same-column),
	 *        sibling cards ease closed; on actual drop/end, leave false so the
	 *        post-drop animateMove owns the motion.
	 */
	clearDropIndicator(opts = {}) {
		this.dropAnchor = null;
		if (!(this.dropSlotEl && this.dropSlotEl.parentNode)) return;
		const parent = this.dropSlotEl.parentNode;
		const remove = () => parent.removeChild(this.dropSlotEl);
		if (opts.animate) this.flipCards([parent], remove);
		else remove();
	}

	/**
	 * Insert index for a drop over a column, from the pointer Y against the
	 * column's rendered cards. Deterministic at drop time — no reliance on hover
	 * state surviving until release. Returned index is in the loaded (visible)
	 * order, which moveCardBucket/reorderLoaded consume.
	 */
	dropIndexFromPointer(columnId, clientY) {
		const view = this.columnViews.get(columnId);
		if (!view) return this.orderedNames(columnId).length;
		const start = (view.renderedRange && view.renderedRange.start) || 0;
		const cards = view.body.querySelectorAll(".kn-card");
		for (let i = 0; i < cards.length; i++) {
			const r = cards[i].getBoundingClientRect();
			if (clientY < r.top + r.height / 2) return start + i;
		}
		return start + cards.length;
	}

	/** Write a column's persisted name order (and optional total delta). */
	setColumnOrder(columnId, order, totalDelta) {
		this.state = {
			...this.state,
			columns: this.state.columns.map((c) =>
				c.id === columnId ? { ...c, order: [...order], total: c.total + totalDelta } : c
			),
		};
	}

	/** Move a card between loaded column arrays in local state. */
	moveCardBucket(cardId, fromColumn, toColumn, atIndex = null) {
		const card = this.findCard(cardId);
		if (!card) return;
		const fromArr = (this.state.cards[fromColumn] || []).filter((c) => c.name !== cardId);
		const toArr = [...(this.state.cards[toColumn] || [])];
		const idx = atIndex == null ? toArr.length : clamp(atIndex, 0, toArr.length);
		toArr.splice(idx, 0, { ...card, [this.options.groupBy]: toColumn });
		this.state = {
			...this.state,
			cards: { ...this.state.cards, [fromColumn]: fromArr, [toColumn]: toArr },
		};
	}

	/** Reorder a card within a column's loaded (visible) list — keeps the display
	 * correct while a column shows its fetch order (partial/paginated). */
	reorderLoaded(columnId, cardId, toIndex) {
		const arr = [...(this.state.cards[columnId] || [])];
		const from = arr.findIndex((c) => c.name === cardId);
		if (from < 0) return;
		const [card] = arr.splice(from, 1);
		let idx = toIndex;
		if (from < idx) idx -= 1;
		idx = clamp(idx, 0, arr.length);
		arr.splice(idx, 0, card);
		this.state = { ...this.state, cards: { ...this.state.cards, [columnId]: arr } };
	}

	/** Visible card names for a column (what the UI currently shows). */
	orderedNames(columnId) {
		const column = this.getColumn(columnId);
		return column ? this.orderedCards(column).map((c) => c.name) : [];
	}

	/**
	 * Full column order for persistence (loaded + not-yet-loaded names).
	 * Drag UI uses orderedNames(); saves must use this so unloaded cards stay put.
	 * Returns null when the order is unknown (no saved order + column partially loaded)
	 * — callers must treat null as "abort; would truncate unloaded names".
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
		// No saved order: safe only when all cards are loaded. With a partial load
		// we don't know the unloaded names, so returning only loaded names would
		// silently truncate the server's order on the first move.
		const loaded = this.state.cards[columnId] || [];
		if (loaded.length < (column.total || 0)) return null;
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

	/** Loaded cards in display order (fetch order while paginated). */
	orderedCards(column) {
		const loaded = this.state.cards[column.id] || [];
		// While a column is only partially loaded (paginated), keep the server's
		// fetch order. Re-sorting a partial set against the full saved order makes
		// the top reshuffle as later pages arrive (early-in-order cards load late).
		// Moves keep `loaded` in visual order, so this stays correct through drags.
		// Once everything is loaded (small columns) the saved order is applied — it
		// is stable then and preserves manual ordering across reloads.
		if (!column.order.length || loaded.length < (column.total || 0)) return loaded;

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

	/** Drop column virtualizers and card/drag cleanups before a re-render. */
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

	/**
	 * Placeholder columns for the first load (before board data arrives), so the
	 * board area shows structure instead of blank white. Uses the real column
	 * shell classes for an accurate silhouette; blocks are frappe.ui.skeleton
	 * (pulsing, theme- and reduced-motion-aware). Column count comes from
	 * options.skeletonColumns (the caller knows the board's columns); default 3.
	 */
	renderSkeleton() {
		if (!this.root) return;
		const count = Math.max(1, this.options.skeletonColumns || 3);
		const frag = document.createDocumentFragment();
		for (let c = 0; c < count; c++) {
			const col = document.createElement("div");
			col.className = CLS.column;
			const header = document.createElement("div");
			header.className = CLS.header + " pb-2";
			header.innerHTML = frappe.ui.skeleton.html({
				width: "40%",
				height: "12px",
				css_class: "my-2 ms-1",
			});
			const body = document.createElement("div");
			body.className = CLS.body;
			for (let i = 0; i < 3 - (c % 2); i++) {
				body.insertAdjacentHTML(
					"beforeend",
					frappe.ui.skeleton.html({
						width: "100%",
						height: "68px",
						css_class: "mb-2",
					})
				);
			}
			col.append(header, body);
			frag.appendChild(col);
		}
		this.root.replaceChildren(frag);
	}

	getColumn(id) {
		return this.state.columns.find((c) => c.id === id);
	}
}
