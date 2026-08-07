frappe.pages["component-explorer"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Component Explorer"),
		single_column: true,
	});

	// Examples are grouped (all variants together, all sizes together...).
	// Each item's opts object is both the displayed code and the real input
	// for the live preview — what you see is exactly what runs.
	const COMPONENTS = {
		Dropdown: {
			helper: "frappe.ui.dropdown",
			groups: [
				{
					title: __("Basic actions"),
					items: [
						{
							button: { label: "Options" },
							options: [
								{
									label: "Edit",
									icon: "pen",
									onclick: () => frappe.ui.toast({ message: "Edit clicked" }),
								},
								{
									label: "Duplicate",
									icon: "copy",
									onclick: () => frappe.ui.toast({ message: "Duplicated" }),
								},
								{
									label: "Delete",
									icon: "trash-2",
									theme: "red",
									onclick: () =>
										frappe.ui.toast({ message: "Deleted", type: "error" }),
								},
							],
						},
					],
				},
				{
					title: __("Groups, shortcuts and disabled rows"),
					items: [
						{
							button: { label: "File" },
							options: [
								{
									group: "Document",
									options: [
										{
											label: "Rename",
											shortcut: "ctrl+r",
											onclick: () =>
												frappe.ui.toast({ message: "Rename clicked" }),
										},
										{
											label: "Print",
											shortcut: "ctrl+p",
											onclick: () =>
												frappe.ui.toast({ message: "Print clicked" }),
										},
									],
								},
								{
									group: "Danger zone",
									options: [
										{ label: "Archive", disabled: true },
										{
											label: "Delete permanently",
											theme: "red",
											onclick: () =>
												frappe.ui.toast({
													message: "Deleted",
													type: "error",
												}),
										},
									],
								},
							],
						},
					],
				},
				{
					title: __("Submenus"),
					items: [
						{
							button: { label: "Actions" },
							options: [
								{
									label: "Open",
									icon: "external-link",
									onclick: () => frappe.ui.toast({ message: "Opened" }),
								},
								{
									label: "Move to",
									icon: "folder",
									submenu: [
										{
											label: "Inbox",
											onclick: () =>
												frappe.ui.toast({ message: "Moved to Inbox" }),
										},
										{
											label: "Archive",
											onclick: () =>
												frappe.ui.toast({ message: "Moved to Archive" }),
										},
										{
											label: "More...",
											submenu: [
												{
													label: "Folder A",
													onclick: () =>
														frappe.ui.toast({
															message: "Moved to Folder A",
														}),
												},
												{
													label: "Folder B",
													onclick: () =>
														frappe.ui.toast({
															message: "Moved to Folder B",
														}),
												},
											],
										},
									],
								},
							],
						},
					],
				},
				{
					title: __("Async items (loading state)"),
					items: [
						{
							button: { label: "Async options" },
							options: () =>
								new Promise((resolve) =>
									setTimeout(
										() =>
											resolve([
												{
													label: "Fetched row 1",
													onclick: () =>
														frappe.ui.toast({ message: "Row 1" }),
												},
												{
													label: "Fetched row 2",
													onclick: () =>
														frappe.ui.toast({ message: "Row 2" }),
												},
											]),
										600
									)
								),
						},
						{
							button: { label: "Async submenu" },
							options: [
								{
									label: "Recent documents",
									icon: "clock",
									submenu: () =>
										new Promise((resolve) =>
											setTimeout(
												() =>
													resolve([
														{
															label: "Doc A",
															onclick: () =>
																frappe.ui.toast({
																	message: "Doc A",
																}),
														},
														{
															label: "Doc B",
															onclick: () =>
																frappe.ui.toast({
																	message: "Doc B",
																}),
														},
													]),
												600
											)
										),
								},
								{
									label: "Fails to load",
									icon: "cloud-off",
									submenu: () =>
										new Promise((resolve, reject) =>
											setTimeout(
												() => reject(new Error("network down")),
												600
											)
										),
								},
							],
						},
					],
				},
				{
					title: __("Selected row, descriptions and links"),
					items: [
						{
							button: { label: "View" },
							options: [
								{
									label: "List",
									selected: true,
									onclick: () => frappe.ui.toast({ message: "List view" }),
								},
								{
									label: "Kanban",
									description: "Drag cards between columns",
									onclick: () => frappe.ui.toast({ message: "Kanban view" }),
								},
								{
									label: "Documentation",
									icon: "book-open",
									href: "https://docs.frappe.io",
								},
							],
						},
					],
				},
				{
					title: __("Placement and empty state"),
					items: [
						{
							button: { label: "Opens top-end" },
							side: "top",
							align: "end",
							options: [
								{
									label: "One",
									onclick: () => frappe.ui.toast({ message: "One" }),
								},
								{
									label: "Two",
									onclick: () => frappe.ui.toast({ message: "Two" }),
								},
							],
						},
						{
							button: { label: "No items" },
							options: [],
							empty_text: "Nothing here yet",
						},
					],
				},
			],
		},
		"Context Menu": {
			helper: "new frappe.ui.ContextMenu",
			code_lead: "target: row_el",
			stacked: true,
			make: (opts) => {
				const $surface = $(
					`<div class="rounded-md border px-4 py-4 text-base text-ink-gray-6" style="border-style: dashed">${frappe.utils.escape_html(
						opts.__surface || __("Right-click here")
					)}</div>`
				);
				new frappe.ui.ContextMenu({ target: $surface, ...opts });
				return $surface;
			},
			groups: [
				{
					title: __("Basic"),
					items: [
						{
							options: [
								{
									label: "Cut",
									shortcut: "ctrl+x",
									onclick: () => frappe.ui.toast({ message: "Cut" }),
								},
								{
									label: "Copy",
									shortcut: "ctrl+c",
									onclick: () => frappe.ui.toast({ message: "Copied" }),
								},
								{
									label: "Paste",
									shortcut: "ctrl+v",
									onclick: () => frappe.ui.toast({ message: "Pasted" }),
								},
								{
									label: "Delete",
									theme: "red",
									onclick: () =>
										frappe.ui.toast({ message: "Deleted", type: "error" }),
								},
							],
						},
					],
				},
				{
					title: __("Groups and submenus"),
					items: [
						{
							__surface: __("Right-click this task card"),
							options: [
								{
									group: "Task",
									options: [
										{
											label: "Open",
											icon: "external-link",
											onclick: () => frappe.ui.toast({ message: "Opened" }),
										},
										{
											label: "Assign to",
											icon: "user-plus",
											submenu: [
												{
													label: "John Doe",
													onclick: () =>
														frappe.ui.toast({
															message: "Assigned to John",
														}),
												},
												{
													label: "Jane Smith",
													onclick: () =>
														frappe.ui.toast({
															message: "Assigned to Jane",
														}),
												},
											],
										},
									],
								},
								{
									group: "Board",
									options: [
										{
											label: "Move to Done",
											icon: "circle-check",
											onclick: () =>
												frappe.ui.toast({
													message: "Moved to Done",
													type: "success",
												}),
										},
									],
								},
							],
						},
					],
				},
			],
		},
		"Hover Card": {
			helper: "frappe.ui.hover_card",
			make: (opts) => {
				const $trigger = $(
					`<a href="#" onclick="return false" class="text-base">${frappe.utils.escape_html(
						opts.__trigger || __("@jane")
					)}</a>`
				);
				frappe.ui.hover_card($trigger, opts);
				return $trigger;
			},
			groups: [
				{
					title: __("A user preview on a link (rest the pointer on it)"),
					items: [
						{
							__code: "frappe.ui.hover_card(user_link_el, {\n  content: () => build_user_card(user),  // any element, built fresh per open\n})",
							content: () => {
								const wrap = $(`
									<div>
										<div class="flex gap-3 align-items-center">
											${frappe.ui.avatar.html({ label: "Jane Smith", theme: "blue", size: "lg" })}
											<div>
												<div class="text-base-medium text-ink-gray-8">Jane Smith</div>
												<div class="text-sm text-ink-gray-5">jane@example.com</div>
											</div>
										</div>
										<p class="text-p-sm text-ink-gray-6 mt-3 mb-0">
											${__("Product engineer. Writes the release notes nobody reads.")}
										</p>
									</div>
								`);
								return wrap;
							},
						},
					],
				},
				{
					title: __("Timing (quick preview: shorter delays)"),
					items: [
						{
							__code: 'frappe.ui.hover_card(link_el, { content: "...", open_delay: 200, close_delay: 150 })',
							__trigger: __("Fast card"),
							content: "Opens after 200ms instead of the default 700ms.",
							open_delay: 200,
							close_delay: 150,
						},
					],
				},
			],
		},
		Tooltip: {
			helper: "frappe.ui.tooltip",
			code_first: "button_el",
			make: (opts) => {
				const $btn = frappe.ui.button({ label: opts.__trigger || __("Hover me") });
				frappe.ui.tooltip($btn, opts);
				return $btn;
			},
			groups: [
				{
					title: __("Basic (hover, or focus with Tab)"),
					items: [
						{
							__trigger: __("Hover me"),
							text: "Adds a row below",
						},
					],
				},
				{
					title: __("Sides"),
					items: [
						{
							__trigger: __("Top"),
							text: "Top is the default",
						},
						{
							__trigger: __("Right"),
							text: "Opens right",
							side: "right",
						},
						{
							__trigger: __("Bottom"),
							text: "Opens bottom",
							side: "bottom",
						},
						{
							__trigger: __("Left"),
							text: "Opens left",
							side: "left",
						},
					],
				},
				{
					title: __("Delay"),
					items: [
						{
							__trigger: __("No delay"),
							text: "Shows immediately",
							delay: 0,
						},
						{
							__trigger: __("Slow"),
							text: "Shows after a second",
							delay: 1000,
						},
					],
				},
				{
					title: __("Long text (wraps)"),
					items: [
						{
							__trigger: __("Long"),
							text: "A longer explanation that wraps across a couple of lines instead of running off the screen",
						},
					],
				},
			],
		},
		Popover: {
			helper: "frappe.ui.popover",
			groups: [
				{
					title: __("Interactive content (a filters panel)"),
					items: [
						{
							__code: 'frappe.ui.popover({\n  button: { label: "Filter", icon: "list-filter" },\n  content: () => build_filter_form(),  // any element, built fresh per open\n  on_close: (reason) => apply_filters(),\n})',
							button: { label: "Filter", icon: "list-filter" },
							content: () => {
								const wrap = $(`
									<div>
										<div class="es-popover__header">
											<div class="es-popover__title">${__("Filters")}</div>
											<p class="es-popover__description">${__("Narrow down the list.")}</p>
										</div>
										<div class="flex flex-col gap-2">
											<input type="text" class="form-control" placeholder="${__("Status")}">
											<input type="text" class="form-control" placeholder="${__("Owner")}">
										</div>
									</div>
								`);
								const apply = frappe.ui.button({
									label: __("Apply"),
									size: "sm",
									variant: "solid",
									css_class: "mt-3",
									onclick: () =>
										frappe.ui.toast({ message: __("Filters applied") }),
								});
								wrap.append(apply);
								return wrap;
							},
						},
					],
				},
				{
					title: __("Plain text (strings render as text, never HTML)"),
					items: [
						{
							__code: 'frappe.ui.popover({ button: { label: "About" }, content: "Version 16.0.0 — <b>tags stay text</b>" })',
							button: { label: "About" },
							content: "Version 16.0.0 — <b>tags stay text</b>",
						},
					],
				},
				{
					title: __("Placement"),
					items: [
						{
							__code: 'frappe.ui.popover({ button: { label: "Opens top-end" }, side: "top", align: "end", content: "..." })',
							button: { label: "Opens top-end" },
							side: "top",
							align: "end",
							content: "Hangs off the top edge, right ends lined up.",
						},
					],
				},
			],
		},
		Tabs: {
			helper: "frappe.ui.tabs",
			stacked: true,
			groups: [
				{
					title: __("Horizontal (arrows move between tabs, Home/End jump)"),
					items: [
						{
							tabs: [
								{
									label: "Details",
									content:
										"The content function of a tab runs once, on first activation.",
								},
								{
									label: "Activity",
									content: "Rendered lazily when this tab was first opened.",
								},
								{ label: "Archived", disabled: true },
								{
									label: "Settings",
									content:
										"Use an element or a function returning one for real content.",
								},
							],
							on_change: (i, tab) =>
								frappe.ui.toast({ message: __("Switched to {0}", [tab.label]) }),
						},
					],
				},
				{
					title: __("Horizontal, with icons"),
					items: [
						{
							tabs: [
								{
									label: "Overview",
									icon: "layout-dashboard",
									content: "Overview panel",
								},
								{ label: "Activity", icon: "activity", content: "Activity panel" },
								{ label: "Settings", icon: "settings", content: "Settings panel" },
							],
						},
					],
				},
				{
					title: __("Vertical"),
					items: [
						{
							vertical: true,
							tabs: [
								{ label: "Profile", content: "Profile panel" },
								{ label: "Sessions", content: "Sessions panel" },
								{ label: "API Access", content: "API access panel" },
							],
						},
					],
				},
				{
					title: __("Vertical, with icons"),
					items: [
						{
							vertical: true,
							tabs: [
								{
									label: "Overview",
									icon: "layout-dashboard",
									content: "Overview panel",
								},
								{ label: "Activity", icon: "activity", content: "Activity panel" },
								{ label: "Settings", icon: "settings", content: "Settings panel" },
							],
						},
					],
				},
			],
		},
		"Tab Buttons": {
			helper: "frappe.ui.tab_buttons",
			// one group per line: the block wrapper keeps the inline-flex rail
			// at its content width while the stacked column separates examples
			stacked: true,
			make: (opts) => $("<div>").append(frappe.ui.tab_buttons(opts)),
			groups: [
				{
					title: __("Types (same options, four looks)"),
					items: [
						{
							options: [
								{ label: "Open" },
								{ label: "In Progress" },
								{ label: "Done" },
							],
						},
						{
							type: "ghost",
							options: [
								{ label: "Open" },
								{ label: "In Progress" },
								{ label: "Done" },
							],
						},
						{
							type: "underline",
							options: [
								{ label: "Open" },
								{ label: "In Progress" },
								{ label: "Done" },
							],
						},
						{
							type: "browser-tab",
							options: [
								{ label: "Open" },
								{ label: "In Progress" },
								{ label: "Done" },
							],
						},
					],
				},
				{
					title: __("Sizes, with icons (sm is the default)"),
					items: [
						{
							options: [
								{ label: "Day", icon_left: "sun" },
								{ label: "Week", icon_left: "calendar-days" },
								{ label: "Month", icon_left: "calendar-range" },
							],
							value: "Week",
						},
						{
							size: "md",
							options: [
								{ label: "Day", icon_left: "sun" },
								{ label: "Week", icon_left: "calendar-days" },
								{ label: "Month", icon_left: "calendar-range" },
							],
							value: "Week",
						},
					],
				},
				{
					title: __("Icon-only pills (label becomes the accessible name)"),
					items: [
						{
							options: [
								{ icon: "list", label: "List view", value: "list" },
								{ icon: "kanban", label: "Kanban view", value: "kanban" },
								{ icon: "calendar", label: "Calendar view", value: "calendar" },
							],
						},
						{
							type: "ghost",
							size: "md",
							options: [
								{ icon: "list", label: "List view", value: "list" },
								{ icon: "layout-grid", label: "Grid view", value: "grid" },
							],
						},
					],
				},
				{
					title: __("Disabled options (a page-size picker)"),
					items: [
						{
							options: [
								{ label: "20" },
								{ label: "100" },
								{ label: "500" },
								{ label: "2500", disabled: true },
							],
							value: "100",
							on_change: (value) =>
								frappe.ui.toast({ message: __("Page size: {0}", [value]) }),
						},
					],
				},
				{
					title: __("Vertical (subtle, underline, and right-attached browser-tab)"),
					items: [
						{
							vertical: true,
							options: [
								{ label: "Inbox", icon_left: "inbox" },
								{ label: "Sent", icon_left: "send" },
								{ label: "Drafts", icon_left: "file" },
							],
						},
						{
							vertical: true,
							type: "underline",
							options: [
								{ label: "General" },
								{ label: "Members" },
								{ label: "Webhooks" },
							],
						},
						{
							vertical: true,
							type: "browser-tab",
							direction: "right",
							options: [
								{ label: "invoice.py" },
								{ label: "invoice.js" },
								{ label: "invoice.json" },
							],
						},
					],
				},
				{
					title: __("Prefix and suffix (rich content per option)"),
					items: [
						{
							__code: 'frappe.ui.tab_buttons({\n  options: [\n    { label: "Open", suffix: () => count_badge(24) },\n    { label: "Closed", suffix: () => count_badge(113) },\n  ],\n})',
							options: [
								{
									label: "Open",
									suffix: () =>
										frappe.ui.badge({
											label: "24",
											size: "sm",
											theme: "blue",
										}),
								},
								{
									label: "Closed",
									suffix: () => frappe.ui.badge({ label: "113", size: "sm" }),
								},
							],
						},
					],
				},
			],
		},
		Stepper: {
			helper: "frappe.ui.stepper",
			stacked: true,
			groups: [
				{
					title: __("Basic (active + completed states)"),
					items: [
						{
							steps: [
								{ label: "Config" },
								{ label: "Preview" },
								{ label: "Fix issues" },
								{ label: "Import" },
							],
							current: 1,
						},
					],
				},
				{
					title: __("Locked steps"),
					items: [
						{
							steps: [
								{ label: "Details" },
								{ label: "Review" },
								{ label: "Submit" },
							],
							current: 0,
							is_locked: (index) => index === 2,
						},
					],
				},
				{
					title: __("Click to navigate"),
					items: [
						{
							steps: [{ label: "One" }, { label: "Two" }, { label: "Three" }],
							current: 0,
							on_step_click: function (index) {
								this.set_current(index);
							},
						},
					],
				},
				{
					title: __("Revisiting a finished flow (factual completion)"),
					items: [
						{
							steps: [
								{ label: "Config" },
								{ label: "Preview" },
								{ label: "Import" },
							],
							current: 1,
							is_completed: () => true,
						},
					],
				},
				{
					title: __("Compact (narrow layouts)"),
					items: [
						{
							steps: [
								{ label: "Config" },
								{ label: "Preview" },
								{ label: "Fix issues" },
								{ label: "Import" },
							],
							current: 1,
							compact: true,
						},
					],
				},
				{
					title: __("Live (next / previous on the first stepper above)"),
					items: [
						{
							__label: __("Next step"),
							__code: '$(".es-stepper").first().data("es-stepper").next_step();',
							__run: () => {
								$(".explorer-preview .es-stepper")
									.first()
									.data("es-stepper")
									?.next_step();
							},
						},
						{
							__label: __("Previous step"),
							__code: '$(".es-stepper").first().data("es-stepper").prev_step();',
							__run: () => {
								$(".explorer-preview .es-stepper")
									.first()
									.data("es-stepper")
									?.prev_step();
							},
						},
					],
				},
			],
		},
		Progress: {
			helper: "frappe.ui.progress",
			stacked: true,
			groups: [
				{
					title: __("Basic (label + hint)"),
					items: [{ value: 30, label: "Importing", hint: true }, { value: 65 }],
				},
				{
					title: __("Sizes"),
					items: [
						{ value: 40, size: "sm", label: "sm (default)" },
						{ value: 40, size: "md", label: "md" },
						{ value: 40, size: "lg", label: "lg" },
						{ value: 40, size: "xl", label: "xl" },
					],
				},
				{
					title: __("Intervals"),
					items: [
						{ value: 50, intervals: true, label: "Setup steps", hint: true },
						{
							value: 75,
							intervals: true,
							interval_count: 4,
							size: "lg",
							label: "Quarter goals",
						},
					],
				},
				{
					title: __("Custom hint text"),
					items: [
						{
							value: 42,
							label: "Backing up",
							hint: (value) => __("{0} of 120 files", [Math.round(value * 1.2)]),
						},
					],
				},
				{
					title: __("Live (updates via set_value)"),
					items: [
						{
							__label: __("Animate the first bar above"),
							__code: 'const progress = $(".es-progress").first().data("es-progress");\ntimer = setInterval(() => progress.set_value(progress.get_value() + 5), 200);',
							__run: () => {
								const progress = $(".explorer-preview .es-progress")
									.first()
									.data("es-progress");
								if (!progress) return;
								progress.set_value(0);
								const timer = setInterval(() => {
									const next = progress.get_value() + 5;
									progress.set_value(next);
									if (next >= 100) clearInterval(timer);
								}, 200);
							},
						},
					],
				},
			],
		},
		"Empty State": {
			helper: "frappe.ui.empty_state",
			stacked: true,
			groups: [
				{
					title: __("Basic (icon + title + description)"),
					items: [
						{
							icon: "inbox",
							title: "No invoices yet",
							description: "Invoices you create will show up here.",
						},
					],
				},
				{
					title: __("With a create action"),
					items: [
						{
							icon: "file-text",
							title: "No sales orders",
							description: "Create your first sales order to get started.",
							actions: [
								{
									label: "New Sales Order",
									variant: "solid",
									icon: "plus",
									onclick: () => frappe.ui.toast({ message: "New Sales Order" }),
								},
							],
						},
					],
				},
				{
					title: __("Multiple actions (create button + docs link)"),
					items: [
						{
							__code: 'frappe.ui.empty_state({\n  icon: "package",\n  title: "No items yet",\n  description: "Add an item, or read how stock works.",\n  actions: [\n    { label: "New Item", variant: "solid", icon: "plus", onclick: () => new_item() },\n    { label: "Documentation", href: "https://docs.erpnext.com/", icon: "external-link" },\n  ],\n})',
							icon: "package",
							title: "No items yet",
							description: "Add an item, or read how stock works.",
							actions: [
								{
									label: "New Item",
									variant: "solid",
									icon: "plus",
									onclick: () => frappe.ui.toast({ message: "New Item" }),
								},
								{
									label: "Documentation",
									href: "https://docs.frappe.io/",
									icon: "external-link",
								},
							],
						},
					],
				},
			],
		},
		Toast: {
			helper: "frappe.ui.toast",
			html: (opts) => "",
			groups: [
				{
					title: __("Types"),
					items: [
						{
							__label: __("Message (default, no icon)"),
							__code: 'frappe.ui.toast({ message: "Draft restored" })',
							__run: () => frappe.ui.toast({ message: "Draft restored" }),
						},
						{
							__label: __("Info"),
							__code: 'frappe.ui.toast({ message: "3 documents queued", type: "info" })',
							__run: () =>
								frappe.ui.toast({ message: "3 documents queued", type: "info" }),
						},
						{
							__label: __("Success"),
							__code: 'frappe.ui.toast({ message: "Saved", type: "success" })',
							__run: () => frappe.ui.toast({ message: "Saved", type: "success" }),
						},
						{
							__label: __("Warning"),
							__code: 'frappe.ui.toast({ message: "Low stock for Item A", type: "warning" })',
							__run: () =>
								frappe.ui.toast({
									message: "Low stock for Item A",
									type: "warning",
								}),
						},
						{
							__label: __("Error"),
							__code: 'frappe.ui.toast({ message: "Could not connect", type: "error" })',
							__run: () =>
								frappe.ui.toast({ message: "Could not connect", type: "error" }),
						},
					],
				},
				{
					title: __("With description"),
					items: [
						{
							__label: __("Show with description"),
							__code: 'frappe.ui.toast({ message: "Import finished", description: "42 rows created, 3 skipped", type: "success" })',
							__run: () =>
								frappe.ui.toast({
									message: "Import finished",
									description: "42 rows created, 3 skipped",
									type: "success",
								}),
						},
					],
				},
				{
					title: __("With action"),
					items: [
						{
							__label: __("Show with Undo"),
							__code: 'frappe.ui.toast({ message: "Email sent", type: "success", action: { label: "Undo", onclick: () => frappe.ui.toast({ message: "Undone" }) } })',
							__run: () =>
								frappe.ui.toast({
									message: "Email sent",
									type: "success",
									action: {
										label: "Undo",
										onclick: () => frappe.ui.toast({ message: "Undone" }),
									},
								}),
						},
					],
				},
				{
					title: __("Same id updates in place"),
					items: [
						{
							__label: __("Run 3-step progress"),
							__code: 'frappe.ui.toast({ id: "sync", message: "Step " + n + " of 3...", type: "info" })',
							__run: () => {
								let n = 0;
								const step = () => {
									n += 1;
									frappe.ui.toast({
										id: "sync",
										message: n < 3 ? `Step ${n} of 3...` : "All steps done",
										type: n < 3 ? "info" : "success",
									});
									if (n < 3) setTimeout(step, 900);
								};
								step();
							},
						},
					],
				},
				{
					title: __("Custom icon"),
					items: [
						{
							__label: __("Show custom icon"),
							__code: 'frappe.ui.toast({ message: "New feature unlocked", icon: "sparkles", icon_class: "text-ink-violet-5" })',
							__run: () =>
								frappe.ui.toast({
									message: "New feature unlocked",
									icon: "sparkles",
									icon_class: "text-ink-violet-5",
								}),
						},
					],
				},
				{
					title: __("Legacy html content (frappe.show_alert)"),
					items: [
						{
							__label: __("HTML message with inline link"),
							__code: 'frappe.show_alert({ message: `Email sent <span data-action="undo" style="text-decoration: underline; cursor: pointer">Undo</span>`, indicator: "green" }, 7, { undo: () => frappe.ui.toast({ message: "Undone" }) })',
							__run: () =>
								frappe.show_alert(
									{
										message:
											'Email sent <span data-action="undo" style="text-decoration: underline; cursor: pointer">Undo</span>',
										indicator: "green",
									},
									7,
									{ undo: () => frappe.ui.toast({ message: "Undone" }) }
								),
						},
						{
							__label: __("Unsafe html gets stripped"),
							__code: 'frappe.show_alert({ message: `<b>Bold is fine</b> <img src=x onerror="alert(1)"> <a href="javascript:alert(1)">bad link</a>`, indicator: "blue" })',
							__run: () =>
								frappe.show_alert({
									message:
										'<b>Bold is fine</b> <img src=x onerror="alert(1)"> <a href="javascript:alert(1)">bad link</a>',
									indicator: "blue",
								}),
						},
					],
				},
				{
					title: __("Follows a promise"),
					items: [
						{
							__label: __("Promise that succeeds"),
							__code: 'frappe.ui.toast.promise(save(), { loading: "Saving...", success: "Saved", error: "Failed to save" })',
							__run: () =>
								frappe.ui.toast.promise(
									new Promise((resolve) => setTimeout(resolve, 1500)),
									{
										loading: "Saving...",
										success: "Saved",
										error: "Failed to save",
									}
								),
						},
						{
							__label: __("Promise that fails"),
							__code: 'frappe.ui.toast.promise(save(), { loading: "Saving...", success: "Saved", error: (e) => e.message })',
							__run: () =>
								frappe.ui.toast
									.promise(
										new Promise((_, reject) =>
											setTimeout(
												() => reject(new Error("Server timed out")),
												1500
											)
										),
										{
											loading: "Saving...",
											success: "Saved",
											error: (e) => e.message,
										}
									)
									.catch(() => {}),
						},
					],
				},
			],
		},
		Alert: {
			helper: "frappe.ui.alert",
			html: (opts) => frappe.ui.alert.html(opts),
			stacked: true,
			groups: [
				{
					title: __("Themes"),
					items: [
						{ title: "Heads up — plain gray, no icon" },
						{ title: "Your draft was restored", theme: "blue" },
						{ title: "This document is locked", theme: "yellow" },
						{ title: "Import failed for 3 rows", theme: "red" },
						{ title: "All checks passed", theme: "green" },
					],
				},
				{
					title: __("With description"),
					items: [
						{
							title: "Scheduled maintenance",
							description:
								"The site will be read-only on Sunday between 02:00 and 04:00 UTC.",
							theme: "blue",
						},
					],
				},
				{
					title: __("Variants"),
					items: [
						{ title: "Subtle is the default", theme: "blue", variant: "subtle" },
						{
							title: "Outline keeps the icon, drops the fill",
							theme: "blue",
							variant: "outline",
						},
						{ title: "Plain outline", variant: "outline" },
					],
				},
				{
					title: __("Dismissible"),
					items: [
						{
							title: "Saved successfully",
							theme: "green",
							dismissible: true,
							on_dismiss: () => frappe.show_alert(__("Alert dismissed")),
						},
					],
				},
				{
					title: __("Custom icon + footer"),
					items: [
						{
							title: "New experimental feature",
							description: "Turn it on from the settings panel.",
							icon: "flask-conical",
							footer: () =>
								frappe.ui.button({
									label: "Open Settings",
									size: "sm",
									variant: "outline",
									onclick: () => frappe.show_alert(__("Opening settings...")),
								}),
						},
					],
				},
			],
		},
		Button: {
			helper: "frappe.ui.button",
			html: (opts) => frappe.ui.button.html(opts),
			groups: [
				{
					title: __("Variants"),
					items: [
						{ label: "Save" },
						{ label: "Submit", variant: "solid" },
						{ label: "Cancel", variant: "outline" },
						{ label: "More", variant: "ghost" },
						{ label: "Delete", variant: "solid", theme: "red" },
					],
				},
				{
					title: __("Icons"),
					items: [
						{ label: "Add", icon: "plus" },
						{ label: "Next", icon_right: "chevron-right" },
						{ icon: "settings", title: "Settings", variant: "ghost" },
						{ icon: "bell", tooltip: "Notifications", variant: "ghost" },
					],
				},
				{
					title: __("Sizes"),
					items: [
						{ label: "Extra small", size: "xs" },
						{ label: "Small" },
						{ label: "Medium", size: "md" },
						{ label: "Large", size: "lg" },
					],
				},
				{
					title: __("States"),
					items: [
						{ label: "Save", loading: true },
						{ label: "Save", disabled: true },
					],
				},
			],
		},
		Avatar: {
			helper: "frappe.ui.avatar",
			html: (opts) => frappe.ui.avatar.html(opts),
			groups: [
				{
					title: __("With image"),
					items: [
						{
							label: "John Doe",
							image: "https://avatars.githubusercontent.com/u/499550?s=60&v=4",
						},
						{
							label: "Jane Smith",
							image: "https://avatars.githubusercontent.com/u/1?s=60&v=4",
							size: "2xl",
						},
						{
							label: "Sam Smith",
							image: "https://avatars.githubusercontent.com/u/2?s=60&v=4",
							shape: "square",
							size: "2xl",
						},
					],
				},
				{
					title: __("Fallback themes"),
					items: [
						{ label: "John Doe" },
						{ label: "Jane Smith", theme: "blue" },
						{ label: "Sam Smith", theme: "green" },
						{ label: "Alice Adams", theme: "amber" },
						{ label: "Ryan Reed", theme: "red" },
						{ label: "Violet Vane", theme: "violet" },
					],
				},
				{
					title: __("Sizes"),
					items: [
						{ label: "John Doe", size: "xs" },
						{ label: "John Doe", size: "sm" },
						{ label: "John Doe" },
						{ label: "John Doe", size: "lg" },
						{ label: "John Doe", size: "xl" },
						{ label: "John Doe", size: "2xl" },
						{ label: "John Doe", size: "3xl" },
					],
				},
				{
					title: __("Shapes"),
					items: [
						{ label: "John Doe", theme: "blue" },
						{ label: "John Doe", theme: "blue", shape: "square" },
						{ label: "John Doe", theme: "blue", shape: "square", size: "2xl" },
					],
				},
				{
					title: __("With indicator"),
					items: [
						{
							label: "John Doe",
							image: "https://avatars.githubusercontent.com/u/499550?s=60&v=4",
							indicator: "green",
							size: "xl",
						},
						{ label: "Jane Smith", theme: "blue", indicator: "gray", size: "xl" },
						{ label: "Sam Smith", theme: "violet", indicator: "red", size: "2xl" },
					],
				},
			],
		},
		Skeleton: {
			helper: "frappe.ui.skeleton",
			html: (opts) => frappe.ui.skeleton.html(opts),
			groups: [
				{
					title: __("Sizes"),
					items: [
						{ width: "120px", height: "16px" },
						{ width: "240px", height: "16px" },
						{ width: "100%", height: "40px" },
					],
				},
				{
					title: __("Shapes"),
					items: [
						{ width: "32px", height: "32px", css_class: "rounded-full" },
						{ width: "180px", height: "12px", css_class: "rounded-full" },
					],
				},
			],
		},
		Divider: {
			helper: "frappe.ui.divider",
			html: (opts) => frappe.ui.divider.html(opts),
			groups: [
				{
					title: __("Plain"),
					items: [{}],
				},
				{
					title: __("With action"),
					items: [
						{ action: { label: "Load More" } },
						{ action: { label: "Show all" }, position: "start" },
					],
				},
				{
					title: __("Vertical (in a flex row)"),
					items: [{ orientation: "vertical", flex_item: true }],
				},
			],
		},
		Breadcrumbs: {
			helper: "frappe.ui.breadcrumbs",
			html: (opts) => frappe.ui.breadcrumbs.html(opts),
			stacked: true,
			groups: [
				{
					title: __("Links"),
					items: [
						{
							items: [
								{ label: "Home", href: "/app" },
								{ label: "Accounting", href: "#" },
								{ label: "Sales Invoice" },
							],
						},
					],
				},
				{
					title: __("With click handlers"),
					items: [
						{
							items: [
								{
									label: "Projects",
									onclick: () => frappe.show_alert(__("Going to Projects")),
								},
								{ label: "Website Redesign" },
							],
						},
					],
				},
				{
					title: __("Prefix, suffix and icon-only crumbs"),
					items: [
						{
							items: [
								{ prefix: "house", title: "Home", href: "#" },
								{ label: "Inbox", prefix: "mail", href: "#" },
								{ label: "Quarterly Report", suffix: "lock" },
							],
						},
					],
				},
				{
					title: __("Long current page (truncates)"),
					items: [
						{
							items: [
								{ label: "Home", href: "#" },
								{
									label: "A very long document title that will not fit and gets cut off with an ellipsis at some point",
								},
							],
						},
					],
				},
			],
		},
		Badge: {
			helper: "frappe.ui.badge",
			html: (opts) => frappe.ui.badge.html(opts),
			groups: [
				{
					title: __("Themes"),
					items: [
						{ label: "Open" },
						{ label: "Info", theme: "blue" },
						{ label: "Success", theme: "green" },
						{ label: "Warning", theme: "amber" },
						{ label: "Overdue", theme: "red" },
						{ label: "Special", theme: "violet" },
					],
				},
				{
					title: __("Variants"),
					items: [
						{ label: "Subtle" },
						{ label: "Solid", theme: "red", variant: "solid" },
						{ label: "Outline", variant: "outline" },
						{ label: "Ghost", variant: "ghost" },
					],
				},
				{
					title: __("Sizes"),
					items: [
						{ label: "Small", theme: "blue", size: "sm" },
						{ label: "Medium", theme: "blue" },
						{ label: "Large", theme: "blue", size: "lg" },
					],
				},
				{
					title: __("With icon"),
					items: [
						{ label: "Small", theme: "green", icon: "check", size: "sm" },
						{ label: "Medium", theme: "blue", icon: "check" },
						{ label: "Large", theme: "red", icon: "check", size: "lg" },
					],
				},
			],
		},
	};

	// ---- code column: turn an opts object into copy-paste-ready code ----
	// Short values stay on one line; anything longer breaks into indented
	// lines, the way a person would write it. Keys starting with "__" are
	// explorer plumbing (labels, trigger text, canned code), not part of
	// the call, so they never print.
	const MAX_INLINE = 68;
	const INDENT = "  ";

	// join the parts on one line if the result is short enough, otherwise
	// put one part per line, indented one level deeper than the parent
	function wrap(parts, open, close, depth, spaced) {
		if (!parts.length) return `${open}${close}`;
		const one_line = spaced
			? `${open} ${parts.join(", ")} ${close}`
			: `${open}${parts.join(", ")}${close}`;
		if (one_line.length <= MAX_INLINE && !one_line.includes("\n")) return one_line;
		const pad = INDENT.repeat(depth + 1);
		return `${open}\n${pad}${parts.join(`,\n${pad}`)}\n${INDENT.repeat(depth)}${close}`;
	}

	function format_value(value, depth) {
		if (typeof value === "function") {
			// print the real handler, collapsing the source file's own
			// wrapping/indentation so it reads as one clean expression
			return value.toString().replace(/\n\s*/g, " ");
		}
		if (Array.isArray(value)) {
			return wrap(
				value.map((entry) => format_value(entry, depth + 1)),
				"[",
				"]",
				depth
			);
		}
		if (value && typeof value === "object") {
			const entries = Object.entries(value).filter(([key]) => !key.startsWith("__"));
			return wrap(
				entries.map(([key, entry]) => `${key}: ${format_value(entry, depth + 1)}`),
				"{",
				"}",
				depth,
				true
			);
		}
		return JSON.stringify(value);
	}

	function to_code(component, opts) {
		const entries = Object.entries(opts).filter(([key]) => !key.startsWith("__"));
		const parts = entries.map(([key, entry]) => `${key}: ${format_value(entry, 1)}`);
		// e.g. ContextMenu takes a target element we can't print for real
		if (component.code_lead) parts.unshift(component.code_lead);
		const object_code = wrap(parts, "{", "}", 0, true);
		// e.g. tooltip's first argument is the trigger element
		const first = component.code_first ? `${component.code_first}, ` : "";
		return `${component.helper}(${first}${object_code})`;
	}

	// "frappe.ui.alert" -> the callable helper (element form, so handlers work)
	function helper_fn(path) {
		return path.split(".").reduce((obj, key) => obj[key], window);
	}

	const $body = $(`
		<div class="explorer flex flex-col gap-4 px-4 py-4">
			<div class="explorer-picker"></div>
			<div class="explorer-groups flex flex-col gap-4"></div>
		</div>
	`).appendTo(page.main);

	function render_component(name) {
		const component = COMPONENTS[name];
		const $groups = $body.find(".explorer-groups").empty();
		if (!component) return;
		// marks which component is on screen — Cypress waits on this
		// attribute after switching components (see cypress spec)
		$groups.attr("data-component", name);

		component.groups.forEach((group) => {
			const $group = $(`
				<div class="explorer-group flex flex-col gap-2" data-testid="${frappe.scrub(group.title, "-")}">
					<div class="text-base-semibold text-ink-gray-8">${frappe.utils.escape_html(group.title)}</div>
					<div class="flex gap-3 items-stretch">
						<pre dir="ltr" class="flex-1 rounded-md border m-0 px-4 py-3 text-ink-gray-8 text-p-sm overflow-x-auto"><code></code></pre>
						<div class="flex-1 min-w-0 flex ${
							component.stacked ? "flex-col items-stretch" : "flex-wrap items-center"
						} gap-2 rounded-md border px-4 py-4 explorer-preview"></div>
					</div>
				</div>
			`);
			const code = group.items
				.map((opts) => opts.__code || to_code(component, opts))
				.join("\n");
			$group.find("code").text(code);
			const $preview = $group.find(".explorer-preview");
			const make = component.make || helper_fn(component.helper);
			group.items.forEach((opts) => {
				// some things (like toasts) show themselves elsewhere — those
				// items carry their own code text and a Run trigger
				if (opts.__run) {
					$preview.append(
						frappe.ui.button({
							label: opts.__label || __("Run"),
							size: "sm",
							variant: "outline",
							onclick: opts.__run,
						})
					);
					return;
				}
				$preview.append(make(opts));
			});
			$groups.append($group);
		});
	}

	const picker = frappe.ui.form.make_control({
		parent: $body.find(".explorer-picker"),
		df: {
			fieldtype: "Autocomplete",
			fieldname: "component",
			label: __("Component"),
			options: Object.keys(COMPONENTS).sort(),
			change: () => render_component(picker.get_value()),
		},
		render_input: true,
	});

	picker.set_value("Button");
	render_component("Button");

	// Deterministic entry point for Cypress: switch the shown component
	// without driving the Autocomplete widget. Safe to expose — the
	// explorer is a dev-only page. See cypress/integration/es_components.js.
	frappe.pages["component-explorer"].render_component = render_component;
};
