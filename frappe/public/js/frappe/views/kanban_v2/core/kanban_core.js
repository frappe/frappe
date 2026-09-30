// Kanban board engine: columns, virtualized cards, drag/drop, pagination.
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
		// Per-board id so a card can't be dropped into another swimlane's columns (drag monitors are document-global).
		this.instanceId = `kn-${++_kanban_instance_seq}`;

		this.state = { columns: [], cards: {}, selection: [], loading: false };

		this.rendererCleanups = [];
		this.dragCleanups = [];
		this.monitorCleanup = null;
		this.columnViews = new Map();
		this.providerUnsub = null;
		this.resizeObserver = null;
		this.dropSlotEl = null;
		this.dropCommitPending = false;
		this.dragSourceColumn = null;
		this.dragPreview = null;
		this.dragGrabOffset = null;
		this.lastSelected = null;
		this.pointer = { x: 0, y: 0 };
		this.autoScrollRAF = null;
		// cards this board just moved, so their realtime echo is skipped
		this.ownMoves = new Map();
		this.movesInFlight = 0;
		this.moveSeq = 0;
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
			this.providerUnsub = this.options.provider.onRemoteUpdate((name) =>
				this.queueRemoteUpdate(name)
			);
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
		this._reloadInFlight = true;
		this.setLoading(true);
		// Show placeholder columns on first load while data fetches.
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
			if (reloadSeq === this.reloadSeq) {
				this._reloadInFlight = false;
				this.setLoading(false);
			}
		}
	}

	queueRemoteUpdate(name) {
		const expires = name && this.ownMoves.get(name);
		if (expires) {
			this.ownMoves.delete(name);
			if (expires > Date.now()) return;
		}
		this.bus.emit("remote:update");
		clearTimeout(this.remoteTimer);
		this.remoteTimer = setTimeout(() => this.refreshFromServer(), 500);
	}

	/** Pick up changes made elsewhere: fresh counts and first pages, same column shells. */
	async refreshFromServer() {
		// a refresh mid-drag or before a save lands would put cards back where they were
		const busy = () => this.dragSourceColumn || this.dropCommitPending || this.movesInFlight;
		const retry = () => (this.remoteTimer = setTimeout(() => this.refreshFromServer(), 500));
		if (busy()) return retry();
		const reloadSeq = ++this.reloadSeq;
		const moveSeq = this.moveSeq;
		try {
			const { columns, cards } = await this.options.provider.loadBoard();
			if (reloadSeq !== this.reloadSeq) return;
			// fetched before a move made meanwhile, so it would undo it on screen
			if (moveSeq !== this.moveSeq || busy()) return retry();
			const ids = (list) => list.map((c) => c.id).join("\n");
			const sameColumns = ids(columns) === ids(this.state.columns);
			this.state = { ...this.state, columns, cards };
			if (sameColumns) this.renderColumns(columns.map((c) => c.id));
			else this.render();
			this.bus.emit("state:change", this.getState());
		} catch (error) {
			if (reloadSeq === this.reloadSeq) this.bus.emit("error", error);
		}
	}

	/** Skip the realtime echo of these cards' saves. */
	expectOwnUpdates(cardIds) {
		const expires = Date.now() + 10000;
		for (const id of cardIds) this.ownMoves.set(id, expires);
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
		clearTimeout(this.remoteTimer);
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
						c.id === columnId ? { ...c, total: c.total + 1 } : c
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
			this.trackCleanup(this.options.renderColumnHeader(column, el));
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
		if (this.options.columnReorder === false) return;
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
					// If nothing claims the slot (cancel/invalid drop), animate it closed.
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
		this.loadMore(column.id);
	}

	/** Load the next page for a column (queued via loadColumnPageOnce). */
	async loadMore(columnId) {
		const view = this.columnViews.get(columnId);
		if (!view || view.loading) return;
		try {
			await this.loadColumnPageOnce(columnId);
		} catch (error) {
			this.bus.emit("error", error);
		}
	}

	// Skip if this column is already loading; the per-column queue serializes fetches so an offset is never fetched twice. Returns { fetched, appended }.
	loadColumnPageOnce(columnId, reloadSeq = this.reloadSeq) {
		if (!this._pageLoadQueues) this._pageLoadQueues = {};
		const prev = this._pageLoadQueues[columnId] || Promise.resolve();
		// Chain onto any in-flight load for this column (continue even if it threw).
		const next = prev
			.catch(() => {})
			.then(() => this._appendNextColumnPage(columnId, reloadSeq))
			.finally(() => {
				if (this._pageLoadQueues[columnId] === next) delete this._pageLoadQueues[columnId];
			});
		this._pageLoadQueues[columnId] = next;
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
		const MAX_SPEED = 16;
		const { x, y } = this.pointer;
		const speed = (d) => MAX_SPEED * Math.min(1, d / EDGE);

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

		// Same-column drops do nothing: the board only moves cards between columns.
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

	/** Optimistic single-card move + persist; moves the card back on error. */
	async applyMove(cardId, fromColumn, toColumn, toIndex) {
		const card = this.findCard(cardId);
		if (fromColumn === toColumn || !card) {
			this.clearDropIndicator({ animate: true });
			return;
		}
		const oldIndex = this.orderedNames(fromColumn).indexOf(cardId);
		const move = {
			cardId,
			fromColumn,
			toColumn,
			oldIndex,
			newIndex: toIndex,
			cardIds: [cardId],
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

		const affected = [fromColumn, toColumn];
		// Measure with the slot open, then collapse it and move the card in one FLIP; the moved card is anchored to its release point.
		const releaseAnchor = this.dragReleaseRect ? { cardId, rect: this.dragReleaseRect } : null;
		this.dragReleaseRect = null;
		this.animateMove(
			affected,
			() => {
				this.clearDropIndicator();
				this.moveCardBetweenColumns(cardId, fromColumn, toColumn, toIndex);
				this.renderColumns(affected);
			},
			releaseAnchor
		);
		this.bus.emit("card:move", move);
		cb.onCardMove && cb.onCardMove(move);

		this.expectOwnUpdates([cardId]);
		this.moveSeq++;
		this.movesInFlight++;
		try {
			const saved = await this.options.provider.moveCard(move);
			if (this.settleCards({ [cardId]: saved }, toColumn).length) {
				cb.onMoveError &&
					cb.onMoveError(move, new Error(__("The card was saved in another column")));
			} else {
				cb.onAfterCardMove && cb.onAfterCardMove(move);
			}
		} catch (error) {
			this.moveCardsBack([{ cardId, fromColumn, oldIndex }], toColumn);
			cb.onMoveError && cb.onMoveError(move, error);
			this.bus.emit("error", error);
		} finally {
			this.movesInFlight--;
		}
	}

	/** Optimistic multi-select move in one request; failed cards move back. */
	async applyMoveMultiple(cardIds, toColumn, anchorName, edge) {
		const selected = new Set(cardIds);
		const moves = [];
		for (const col of this.state.columns) {
			if (col.id === toColumn) continue;
			this.orderedNames(col.id).forEach((name, oldIndex) => {
				if (selected.has(name)) moves.push({ cardId: name, fromColumn: col.id, oldIndex });
			});
		}
		if (!moves.length) {
			this.clearDropIndicator({ animate: true });
			return;
		}

		const cb = this.options.callbacks || {};
		for (const { cardId, fromColumn } of moves) {
			const guard =
				cb.canMoveCard && cb.canMoveCard(this.findCard(cardId), fromColumn, toColumn);
			if (guard === false || typeof guard === "string") {
				this.clearDropIndicator({ animate: true });
				return;
			}
		}

		const affected = [...new Set([...moves.map((m) => m.fromColumn), toColumn])];
		const target = this.orderedNames(toColumn);
		let insertAt = target.length;
		if (anchorName) {
			const idx = target.indexOf(anchorName);
			if (idx >= 0) insertAt = edge === "bottom" ? idx + 1 : idx;
		}

		// each card gets the move a single drag would, plus every card in this drag
		const movedIds = moves.map((m) => m.cardId);
		moves.forEach((m, i) =>
			Object.assign(m, { toColumn, newIndex: insertAt + i, cardIds: movedIds })
		);
		// one drag is one decision: a veto on any card cancels the whole drag
		for (const m of moves) {
			if (cb.onBeforeCardMove && (await cb.onBeforeCardMove(m)) === false) {
				this.clearDropIndicator({ animate: true });
				return;
			}
		}

		this.animateMove(affected, () => {
			// Same as single-card: keep hover gap until this FLIP mutate.
			this.clearDropIndicator();
			moves.forEach((m, i) =>
				this.moveCardBetweenColumns(m.cardId, m.fromColumn, toColumn, insertAt + i)
			);
			this.renderColumns(affected);
		});

		for (const m of moves) {
			this.bus.emit("card:move", m);
			cb.onCardMove && cb.onCardMove(m);
		}
		this.setSelection([]);

		const moveErrorArgs = {
			cardId: movedIds[0],
			cardIds: movedIds,
			toColumn,
		};

		this.expectOwnUpdates(movedIds);
		this.moveSeq++;
		this.movesInFlight++;
		let failed, saved;
		try {
			const result = await this.options.provider.moveCards(movedIds, toColumn);
			failed = new Set(result.failed);
			saved = result.saved || {};
		} catch (error) {
			this.moveCardsBack(moves, toColumn);
			cb.onMoveError && cb.onMoveError(moveErrorArgs, error);
			this.bus.emit("error", error);
			return;
		} finally {
			this.movesInFlight--;
		}

		if (failed.size) {
			this.moveCardsBack(
				moves.filter((m) => failed.has(m.cardId)),
				toColumn
			);
			const error = new Error(
				__("{0} of {1} cards could not be moved", [failed.size, moves.length])
			);
			const failedIds = [...failed];
			cb.onMoveError &&
				cb.onMoveError(
					{ ...moveErrorArgs, cardId: failedIds[0], cardIds: failedIds },
					error
				);
			this.bus.emit("error", error);
		}
		const settled = new Set(
			this.settleCards(
				Object.fromEntries(Object.entries(saved).filter(([id]) => !failed.has(id))),
				toColumn
			)
		);
		if (settled.size) {
			const settledIds = [...settled];
			cb.onMoveError &&
				cb.onMoveError(
					{ ...moveErrorArgs, cardId: settledIds[0], cardIds: settledIds },
					new Error(__("Some cards were saved in another column"))
				);
		}
		for (const m of moves) {
			if (!failed.has(m.cardId) && !settled.has(m.cardId)) {
				cb.onAfterCardMove && cb.onAfterCardMove(m);
			}
		}
	}

	/**
	 * Move cards to the column the server saved them in, when it isn't the one they
	 * were dropped in (a doctype can set the value itself, e.g. a computed status).
	 * Returns the names of the cards that moved.
	 */
	settleCards(saved, toColumn) {
		const onBoard = new Set(this.state.columns.map((c) => c.id));
		const dropped = new Set(this.orderedNames(toColumn));
		const misplaced = Object.entries(saved).filter(
			([id, column]) => column != null && column !== toColumn && dropped.has(id)
		);
		if (!misplaced.length) return [];

		const affected = [...new Set([toColumn, ...misplaced.map(([, c]) => c)])].filter((c) =>
			onBoard.has(c)
		);
		this.animateMove(affected, () => {
			for (const [id, column] of misplaced) {
				if (onBoard.has(column)) this.moveCardBetweenColumns(id, toColumn, column, 0);
				else this.removeCard(id, toColumn);
			}
			this.renderColumns(affected);
		});
		return misplaced.map(([id]) => id);
	}

	/** Drop a card whose column isn't on this board. */
	removeCard(cardId, columnId) {
		this.state = {
			...this.state,
			columns: this.state.columns.map((c) =>
				c.id === columnId ? { ...c, total: Math.max(0, c.total - 1) } : c
			),
			cards: {
				...this.state.cards,
				[columnId]: (this.state.cards[columnId] || []).filter((c) => c.name !== cardId),
			},
		};
	}

	/** Undo optimistic moves that the server rejected. */
	moveCardsBack(moves, toColumn) {
		// A reload since the move already shows server state.
		const pending = moves.filter((m) => this.orderedNames(toColumn).includes(m.cardId));
		if (!pending.length) return;
		const affected = [...new Set([...pending.map((m) => m.fromColumn), toColumn])];
		this.animateMove(affected, () => {
			for (const m of pending) {
				this.moveCardBetweenColumns(m.cardId, toColumn, m.fromColumn, m.oldIndex);
			}
			this.renderColumns(affected);
		});
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

	// FLIP-animate cards in the given columns across a DOM change so they ease into place instead of jumping.
	flipCards(bodies, mutate, anchor) {
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

		// Start the dragged card's FLIP from where it was released, not its
		// pre-drag slot, so it settles into place instead of snapping to origin.
		if (anchor && anchor.rect) first.set(anchor.cardId, anchor.rect);

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
	animateMove(ids, mutate, anchor) {
		const bodies = [...new Set(ids)]
			.map((id) => {
				const view = this.columnViews.get(id);
				return view && view.body;
			})
			.filter(Boolean);
		this.flipCards(bodies, mutate, anchor);
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

	// Tilted card that follows the pointer; a multi-select drag shows a stacked deck with a count badge.
	startCardPreview(el, cardId, input) {
		this.endCardPreview(); // never leave a previous preview orphaned
		const rect = el.getBoundingClientRect();
		const sel = this.state.selection;
		const count = sel.length > 1 && sel.includes(cardId) ? sel.length : 1;
		this.dragGrabOffset = {
			dx: input ? input.clientX - rect.left : rect.width / 2,
			dy: input ? input.clientY - rect.top : 24,
			h: rect.height,
			w: rect.width,
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
		if (!this.dragPreview || !this.dragGrabOffset) return;
		const left = x - this.dragGrabOffset.dx;
		const top = y - this.dragGrabOffset.dy;
		this.dragPreview.style.transform = `translate(${left}px, ${top}px) rotate(3deg)`;
		// Remember where the card was released so the post-drop FLIP settles from
		// here into its slot, instead of snapping back to the original position.
		this.dragReleaseRect = {
			left,
			top,
			width: this.dragGrabOffset.w,
			height: this.dragGrabOffset.h,
		};
	}

	/** Remove the custom drag preview from the document. */
	endCardPreview() {
		if (this.dragPreview) {
			this.dragPreview.remove();
			this.dragPreview = null;
		}
		this.dragGrabOffset = null;
	}

	// Show a placeholder slot where the card will land; sibling cards animate around it.
	showDropIndicator(el, edge, data) {
		// Don't tease a drop that won't happen: same-column drops are a no-op
		// (see handleDrop), so hide the placeholder while over the source column
		// instead of showing a slot the release will ignore.
		if (data && data.columnId === this.dragSourceColumn) {
			this.clearDropIndicator({ animate: true });
			return;
		}
		const slot = this.dropSlotEl || (this.dropSlotEl = this.buildDropSlot());
		if (this.dragGrabOffset && this.dragGrabOffset.h) {
			const n = this.dragGrabOffset.count || 1;
			// Slot height = N cards + the mb-2 gaps between them.
			slot.style.height = `${this.dragGrabOffset.h * n + CARD_GAP * (n - 1)}px`;
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
	 * order, which moveCardBetweenColumns consumes.
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

	/** Move a card between loaded column arrays and totals in local state. */
	moveCardBetweenColumns(cardId, fromColumn, toColumn, atIndex = null) {
		const card = this.findCard(cardId);
		if (!card) return;
		const fromArr = (this.state.cards[fromColumn] || []).filter((c) => c.name !== cardId);
		const toArr = [...(this.state.cards[toColumn] || [])];
		const idx = atIndex == null ? toArr.length : clamp(atIndex, 0, toArr.length);
		toArr.splice(idx, 0, { ...card, [this.options.groupBy]: toColumn });
		const delta = { [fromColumn]: -1, [toColumn]: 1 };
		this.state = {
			...this.state,
			columns: this.state.columns.map((c) =>
				c.id in delta ? { ...c, total: Math.max(0, c.total + delta[c.id]) } : c
			),
			cards: { ...this.state.cards, [fromColumn]: fromArr, [toColumn]: toArr },
		};
	}

	/** Visible card names for a column (what the UI currently shows). */
	orderedNames(columnId) {
		const column = this.getColumn(columnId);
		return column ? this.orderedCards(column).map((c) => c.name) : [];
	}

	findCard(cardId) {
		for (const list of Object.values(this.state.cards)) {
			const found = list.find((c) => c.name === cardId);
			if (found) return found;
		}
		return undefined;
	}

	/** Loaded cards in display order. */
	orderedCards(column) {
		return this.state.cards[column.id] || [];
	}

	trackCleanup(cleanup) {
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

	// Placeholder columns shown on first load; count from options.skeletonColumns (default 3).
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
