frappe.pages["component-explorer"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Components"),
		single_column: true,
	});

	// sample people for the Avatar Group examples
	const PEOPLE = [
		{ label: "John Doe", image: "https://avatars.githubusercontent.com/u/499550?s=60&v=4" },
		{ label: "Jane Smith" },
		{ label: "Sam Smith" },
		{ label: "Alice Adams" },
		{ label: "Ryan Reed" },
		{ label: "Kim Lee" },
		{ label: "Max Hart" },
	];
	const person_card = (person) =>
		$('<div class="flex gap-3 items-center"></div>').append(
			frappe.ui.avatar({ ...person, size: "xl" }),
			$("<div></div>").append(
				$('<div class="text-base-medium text-ink-gray-8"></div>').text(person.label),
				$('<div class="text-sm text-ink-gray-5"></div>').text(
					`${frappe.scrub(person.label, ".")}@example.com`
				)
			)
		);

	// the quick entry example's fields, read back by its Save action
	let explorer_todo_fields;
	let explorer_contact_fields;
	// the search box and the button of the BottomSheet multi-select example
	const explorer_assign = {};
	// rows of the BottomSheet search example: the caller decides what matches
	const explorer_date_rows = (query = "") =>
		["Date", "Delivery Date", "Created On"]
			.filter((label) => label.toLowerCase().includes(query.trim().toLowerCase()))
			.map((label) => ({
				label,
				onclick: (e, sheet) => {
					sheet.push({
						title: "Condition",
						subtitle: label,
						options: ["Equals", "After", "Before", "Between", "Timespan"].map(
							(condition) => ({
								label: condition,
								onclick: () =>
									frappe.ui.toast({ message: `${label} · ${condition}` }),
							})
						),
					});
					return false;
				},
			}));

	// Examples are grouped (all variants together, all sizes together...).
	// Each item's opts object is both the displayed code and the real input
	// for the live preview — what you see is exactly what runs.
	// a footer row two Combobox demos share
	const CREATE_CUSTOMER_ROW = {
		type: "custom",
		label: __("Create a new Customer"),
		icon: "plus",
		onclick: ({ query }) =>
			frappe.ui.toast({ message: __('Create "{0}"', [query || __("new")]) }),
	};

	const COMPONENTS = {
		Combobox: {
			helper: "frappe.ui.combobox",
			stacked: true,
			groups: [
				{
					title: __("Basic"),
					items: [
						{
							placeholder: __("Select status"),
							options: ["Open", "Working", "Pending Review", "Closed"],
							on_change: (value) =>
								frappe.ui.toast({ message: __("Picked {0}", [value]) }),
						},
						{
							placeholder: __("Select status"),
							value: "Working",
							options: ["Open", "Working", "Closed"],
						},
						{
							placeholder: __("Disabled"),
							value: "Open",
							disabled: true,
							options: ["Open", "Closed"],
						},
					],
				},
				{
					title: __("Rich rows: avatar, description, badge, disabled"),
					items: [
						{
							placeholder: __("Select customer"),
							search_placeholder: __("Search customers..."),
							options: [
								{
									label: "Acme Industries",
									value: "CUST-0001",
									description: "CUST-0001, Mumbai",
									image: "/assets/frappe/images/frappe-framework-logo.svg",
									badge: { label: "Commercial", theme: "green" },
								},
								{
									label: "Ace Hardware Ltd",
									value: "CUST-0042",
									description: "CUST-0042, Pune",
									avatar: true,
									badge: { label: "Individual", theme: "blue" },
								},
								{
									label: "Pacific Traders",
									value: "CUST-0107",
									description: "CUST-0107, Chennai",
									avatar: true,
								},
								{
									label: "Acme Exports",
									value: "CUST-0009",
									description: "CUST-0009",
									avatar: true,
									disabled: true,
								},
							],
							on_change: (value, option) =>
								frappe.ui.toast({ message: `${option.label} (${value})` }),
						},
						{
							placeholder: __("Select priority"),
							options: [
								{ label: "Urgent", value: "Urgent", icon: "flame" },
								{ label: "High", value: "High", icon: "arrow-up" },
								{ label: "Medium", value: "Medium", icon: "minus" },
								{ label: "Low", value: "Low", icon: "arrow-down" },
							],
						},
					],
				},
				{
					title: __("Groups"),
					items: [
						{
							placeholder: __("Select account"),
							search_placeholder: __("Search 412 accounts..."),
							options: [
								{
									group: "Receivable",
									options: [
										{
											label: "Debtors - FT",
											value: "Debtors - FT",
											description: "Accounts Receivable",
										},
										{
											label: "Debtors USD - FT",
											value: "Debtors USD - FT",
											description: "Accounts Receivable",
										},
									],
								},
								{
									group: "Expenses",
									options: [
										{
											label: "Bad Debts - FT",
											value: "Bad Debts - FT",
											description: "Indirect Expenses",
										},
									],
								},
							],
						},
					],
				},
				{
					title: __("Custom rows (footer) and empty state"),
					items: [
						{
							placeholder: __("Select customer"),
							options: ["Acme Industries", "Ace Hardware Ltd"],
							footer: [
								CREATE_CUSTOMER_ROW,
								{
									type: "custom",
									label: __("Browse all Customers"),
									icon: "search",
									condition: ({ query }) => !query,
									onclick: () => frappe.ui.toast({ message: __("Browse all") }),
								},
							],
						},
					],
				},
				{
					title: __("Applied filters — every operator, many at once, long values"),
					items: [
						{
							placeholder: __("One filter"),
							filters: ["Customer Group: Commercial"],
							options: ["Acme Industries", "Pacific Traders"],
						},
						{
							placeholder: __("Every operator"),
							filters: [
								"Customer Group: Commercial",
								"Status ≠ Disabled",
								"Territory in India, Nepal, Bhutan, Sri Lanka, Bangladesh…",
								'Name contains "acme"',
								"Creation between 01-01-2026 and 31-03-2026",
								"Tax ID is set",
								"Enabled",
								"Account Group descendant of Current Assets - FT",
							],
							footer: [CREATE_CUSTOMER_ROW],
							options: ["Acme Industries", "Pacific Traders"],
						},
						{
							placeholder: __("Long values"),
							filters: [
								"Company: Frappe Technologies Private Limited (Mumbai Head Office and Regional Branches)",
								"Cost Center: Main - Frappe Technologies Private Limited - Mumbai - FT",
							],
							options: ["Acme Industries", "Pacific Traders"],
						},
						{
							placeholder: __("Plain text form"),
							filters:
								"Customer Group equals Commercial and Territory is one of India, Nepal, Bhutan and Status is not Disabled",
							options: ["Acme Industries", "Pacific Traders"],
						},
					],
				},
				{
					title: __("No search row (short lists)"),
					items: [
						{
							placeholder: __("Select company"),
							hide_search: true,
							value: "Frappe Technologies",
							options: ["Frappe Technologies", "Frappe Cloud LLC", "Frappe UK Ltd"],
						},
					],
				},
				{
					title: __("Load more on scroll (page_size)"),
					items: [
						{
							placeholder: __("Select item"),
							search_placeholder: __("Search 143 items..."),
							filterable: false,
							page_size: 20,
							options: (query, { start }) =>
								new Promise((resolve) =>
									setTimeout(() => {
										const all = Array.from({ length: 143 }, (_, i) => ({
											label: `Item ${String(i + 1).padStart(3, "0")}`,
											value: `ITEM-${String(i + 1).padStart(3, "0")}`,
											description: i % 3 ? "Accessories" : "Electronics",
										}));
										const hits = all.filter((o) =>
											o.label.toLowerCase().includes(query.toLowerCase())
										);
										resolve(hits.slice(start, start + 20));
									}, 400)
								),
						},
					],
				},
				{
					title: __("Async options (server search)"),
					items: [
						{
							placeholder: __("Select user"),
							search_placeholder: __("Search users..."),
							filterable: false,
							options: (query) =>
								new Promise((resolve) =>
									setTimeout(() => {
										const all = [
											"Jane Doe",
											"John Smith",
											"Priya Shah",
											"Ravi Kumar",
										];
										resolve(
											all
												.filter((n) =>
													n.toLowerCase().includes(query.toLowerCase())
												)
												.map((n) => ({
													label: n,
													value: n,
													avatar: true,
												}))
										);
									}, 600)
								),
						},
					],
				},
			],
		},
		"Multi Combobox": {
			helper: "frappe.ui.multi_combobox",
			stacked: true,
			groups: [
				{
					title: __("Basic"),
					items: [
						{
							placeholder: __("Select roles"),
							options: [
								"Accounts Manager",
								"Accounts User",
								"Sales User",
								"Stock User",
								"System Manager",
							],
							on_change: (values) =>
								frappe.ui.toast({ message: __("{0} selected", [values.length]) }),
						},
						{
							placeholder: __("Select roles"),
							value: ["Sales User", "System Manager"],
							options: [
								"Accounts User",
								"Sales User",
								"Stock User",
								"System Manager",
							],
						},
						{
							placeholder: __("Disabled"),
							value: ["Sales User"],
							disabled: true,
							options: ["Sales User"],
						},
					],
				},
				{
					title: __("One line: extra values show as +N"),
					items: [
						{
							one_line: true,
							value: ["Accounts User", "Sales User", "Stock User", "System Manager"],
							options: [
								"Accounts User",
								"Sales User",
								"Stock User",
								"System Manager",
							],
						},
					],
				},
			],
		},
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
									icon: "trash",
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
										{
											label: "Documentation",
											href: "https://docs.frappe.io/framework",
											target: "_blank",
											icon_right: "external-link",
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
				const avatar = opts.__avatar
					? frappe.ui.avatar.html({ label: opts.__avatar, theme: "blue", size: "sm" })
					: "";
				const $trigger = $(
					`<a href="#" onclick="return false" class="text-base ${
						avatar ? "d-inline-flex align-items-center gap-2" : ""
					}">${avatar}${frappe.utils.escape_html(opts.__trigger || __("@jane"))}</a>`
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
							__avatar: "Jane Smith",
							__trigger: "Jane Smith",
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
							content: "Jane Smith · Product engineer",
							__note: "opens after 200ms instead of the default 700ms",
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
							text: "Opens on top",
							__note: "top is the default side",
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
		"Bottom Sheet": {
			helper: "frappe.ui.bottom_sheet",
			groups: [
				{
					title: __("Action menu (a divider between groups, red for destructive)"),
					items: [
						{
							button: { label: "Record menu", icon: "ellipsis" },
							title: "SAL-ORD-2026-00142",
							subtitle: "Sales Order",
							options: [
								{
									group: "",
									hide_label: true,
									options: [
										{
											label: "Duplicate",
											icon: "copy",
											onclick: () =>
												frappe.ui.toast({ message: "Duplicated" }),
										},
										{
											label: "Print",
											icon: "printer",
											onclick: () => frappe.ui.toast({ message: "Print" }),
										},
										{
											label: "Email",
											icon: "mail",
											onclick: () => frappe.ui.toast({ message: "Email" }),
										},
										{
											label: "Copy link",
											icon: "link",
											onclick: () =>
												frappe.ui.toast({ message: "Link copied" }),
										},
									],
								},
								{
									group: "",
									hide_label: true,
									options: [
										{
											label: "Delete",
											icon: "trash-2",
											theme: "red",
											onclick: () => frappe.ui.toast({ message: "Deleted" }),
										},
									],
								},
							],
						},
					],
				},
				{
					title: __("Picker (the current choice is checked; a tap applies and closes)"),
					items: [
						{
							button: { label: "Sort by", icon: "arrow-down-wide-narrow" },
							title: "Sort by",
							options: [
								{
									label: "Created On",
									selected: true,
									onclick: () =>
										frappe.ui.toast({ message: "Sorted by Created On" }),
								},
								{
									label: "Last Updated On",
									onclick: () =>
										frappe.ui.toast({ message: "Sorted by Last Updated On" }),
								},
								{
									label: "Grand Total",
									onclick: () =>
										frappe.ui.toast({ message: "Sorted by Grand Total" }),
								},
								{
									label: "Customer",
									onclick: () =>
										frappe.ui.toast({ message: "Sorted by Customer" }),
								},
							],
						},
					],
				},
				{
					title: __("Confirmation (your own buttons in the footer, side by side)"),
					items: [
						{
							button: { label: "Delete 3 orders", icon: "trash-2", theme: "red" },
							title: "Delete 3 Sales Orders?",
							content:
								"Draft orders are deleted permanently. Submitted ones have to be cancelled first.",
							footer: (sheet) => [
								frappe.ui.button({
									label: "Cancel",
									size: "md",
									onclick: () => sheet.close(),
								}),
								frappe.ui.button({
									label: "Delete",
									variant: "solid",
									theme: "red",
									size: "md",
									onclick: () => {
										frappe.ui.toast({ message: "3 Sales Orders deleted" });
										sheet.close();
									},
								}),
							],
						},
					],
				},
				{
					title: __("Quick entry form (close button, full height, sticky Save)"),
					items: [
						{
							__code: 'let fields;\nfrappe.ui.bottom_sheet({\n  button: { label: "New ToDo", icon: "plus" },\n  title: "New ToDo",\n  show_close: true,\n  height: "full",\n  content: () => {\n    const body = document.createElement("div");\n    fields = new frappe.ui.FieldGroup({ body, fields: todo_fields });\n    fields.make();\n    return body;\n  },\n  // the footer is yours: the sheet stays open until you close it\n  footer: (sheet) => frappe.ui.button({\n    label: "Save",\n    variant: "solid",\n    size: "md",\n    onclick: () => save(fields.get_values(true)) && sheet.close(),\n  }),\n})',
							button: { label: "New ToDo", icon: "plus" },
							title: "New ToDo",
							show_close: true,
							height: "full",
							content: () => {
								const body = document.createElement("div");
								explorer_todo_fields = new frappe.ui.FieldGroup({
									body,
									fields: [
										{
											fieldtype: "Small Text",
											fieldname: "description",
											label: "Description",
											reqd: 1,
										},
										{
											fieldtype: "Date",
											fieldname: "date",
											label: "Due Date",
										},
										{
											fieldtype: "Select",
											fieldname: "priority",
											label: "Priority",
											options: "Low\nMedium\nHigh",
											default: "Medium",
										},
										{
											fieldtype: "Link",
											fieldname: "allocated_to",
											label: "Allocated To",
											options: "User",
										},
									],
								});
								explorer_todo_fields.make();
								return body;
							},
							footer: (sheet) =>
								frappe.ui.button({
									label: "Save",
									variant: "solid",
									size: "md",
									onclick: () => {
										const values = explorer_todo_fields.get_values(true);
										if (!values.description) {
											frappe.ui.toast({
												message: "Add a description first",
											});
											return;
										}
										frappe.ui.toast({
											message: `ToDo saved: ${values.description}`,
										});
										sheet.close();
									},
								}),
						},
					],
				},
				{
					title: __(
						"Searchable multi-select (search in the header, a count in the footer)"
					),
					items: [
						{
							__code: 'const picked = new Set();\nconst $search = $(\'<input type="search" class="form-control">\');\nconst $assign = frappe.ui.button({ label: "Assign", variant: "solid", size: "md", disabled: true });\nfrappe.ui.bottom_sheet({\n  button: { label: "Assign to", icon: "user-plus" },\n  title: "Assign to",\n  height: "full",\n  header: $search,   // fixed at the top, under the title\n  content: () => build_user_list($search, picked, $assign),\n  footer: $assign,   // fixed at the bottom\n})',
							button: { label: "Assign to", icon: "user-plus" },
							title: "Assign to",
							height: "full",
							header: () =>
								(explorer_assign.$search = $(
									'<input type="search" class="form-control">'
								).attr("placeholder", __("Search users"))),
							footer: (sheet) =>
								(explorer_assign.$button = frappe.ui.button({
									label: "Assign",
									variant: "solid",
									size: "md",
									disabled: true,
									onclick: () => {
										frappe.ui.toast({ message: "Assigned" });
										sheet.close();
									},
								})),
							content: () => {
								const users = [
									["Priya Shah", "priya@example.com"],
									["Ravi Kumar", "ravi@example.com"],
									["Jane Doe", "jane@example.com"],
									["John Smith", "john@example.com"],
									["Aisha Khan", "aisha@example.com"],
								];
								const picked = new Set();
								const $list = $('<div class="flex flex-col"></div>');
								const update_footer = () => {
									const $assign = explorer_assign.$button;
									$assign.prop("disabled", !picked.size);
									$assign
										.find(".es-button__label")
										.text(picked.size ? `Assign · ${picked.size}` : "Assign");
								};
								const render = (query) => {
									$list.empty();
									users
										.filter((user) =>
											user
												.join(" ")
												.toLowerCase()
												.includes(query.toLowerCase())
										)
										.forEach(([name, email]) => {
											const $row = $(`
												<label class="flex items-center gap-3 py-2 cursor-pointer">
													<input type="checkbox">
													${frappe.ui.avatar.html({ label: name })}
													<span class="flex flex-col">
														<span class="name"></span>
														<span class="email text-ink-gray-5"></span>
													</span>
												</label>`);
											$row.find(".name").text(name);
											$row.find(".email").text(email);
											$row.find("input")
												.prop("checked", picked.has(email))
												.on("change", (e) => {
													e.target.checked
														? picked.add(email)
														: picked.delete(email);
													update_footer();
												});
											$list.append($row);
										});
								};
								explorer_assign.$search.on("input", (e) => render(e.target.value));
								render("");
								return $list[0];
							},
						},
					],
				},
				{
					title: __("Peek with snap points (drag the handle between half and full)"),
					items: [
						{
							button: { label: "Preview order", icon: "panel-bottom" },
							title: "SAL-ORD-2026-00142",
							subtitle: "Acme Industries",
							snap_points: ["half", "full"],
							content: () =>
								$(`
									<div class="flex flex-col">
										<div class="flex justify-between py-2 border-b"><span class="text-ink-gray-5">Date</span><span>12-09-2026</span></div>
										<div class="flex justify-between py-2 border-b"><span class="text-ink-gray-5">Delivery Date</span><span>26-09-2026</span></div>
										<div class="flex justify-between py-2 border-b"><span class="text-ink-gray-5">Grand Total</span><span>₹ 1,24,500.00</span></div>
										<div class="flex justify-between py-2"><span class="text-ink-gray-5">Items</span><span>3</span></div>
									</div>`)[0],
							footer: (sheet) => [
								frappe.ui.button({
									label: "Open",
									size: "md",
									onclick: () => sheet.close(),
								}),
								frappe.ui.button({
									label: "Create Invoice",
									variant: "solid",
									size: "md",
									onclick: () => {
										frappe.ui.toast({ message: "Invoice created" });
										sheet.close();
									},
								}),
							],
						},
					],
				},
				{
					title: __("Steps inside one sheet (push shows Back; Escape goes back first)"),
					items: [
						{
							__code: 'const rows = (query = "") =>\n  date_fields\n    .filter((label) => label.toLowerCase().includes(query.trim().toLowerCase()))\n    .map((label) => ({\n      label,\n      // push a step instead of opening a second sheet; false keeps it open\n      onclick: (e, sheet) => {\n        sheet.push({ title: "Condition", subtitle: label, options: conditions });\n        return false;\n      },\n    }));\nfrappe.ui.bottom_sheet({\n  button: { label: "Filter by date", icon: "calendar-range" },\n  title: "Choose field",\n  // the search box is yours: decide what matches, then hand the sheet the rows\n  header: (sheet) =>\n    $(\'<input type="search" class="form-control" placeholder="Search fields">\')\n      .on("input", (e) => sheet.set_options(rows(e.target.value))),\n  options: rows(),\n})',
							button: { label: "Filter by date", icon: "calendar-range" },
							title: "Choose field",
							header: (sheet) =>
								$('<input type="search" class="form-control">')
									.attr("placeholder", "Search fields")
									.on("input", (e) =>
										sheet.set_options(explorer_date_rows(e.target.value))
									),
							options: explorer_date_rows(),
						},
					],
				},
				{
					title: __("Your own header and footer (a title with a button, a tab bar)"),
					items: [
						{
							__code: 'frappe.ui.bottom_sheet({\n  button: { label: "Sort and filter", icon: "arrow-up-down" },\n  // without a title, your header takes its place; several pieces sit side by side\n  header: (sheet) => [\n    $(\'<div class="es-bottom-sheet__title">Sort</div>\'),\n    frappe.ui.button({ label: "Reset", variant: "ghost", onclick: () => sheet.close() }),\n  ],\n  options: sort_options,\n  // anything can go in the footer, not only buttons\n  footer: () => frappe.ui.tab_buttons({ options: tabs, value: "Sort" }),\n})',
							button: { label: "Sort and filter", icon: "arrow-up-down" },
							header: (sheet) => [
								$('<div class="es-bottom-sheet__title"></div>').text("Sort"),
								frappe.ui.button({
									label: "Reset",
									variant: "ghost",
									onclick: () => sheet.close(),
								}),
							],
							options: [
								"What's new",
								"Price - high to low",
								"Popularity",
								"Discount",
								"Price - low to high",
							].map((label, index) => ({
								label,
								selected: index === 0,
								onclick: () => frappe.ui.toast({ message: label }),
							})),
							footer: () =>
								frappe.ui.tab_buttons({
									options: ["Sort", "Brand", "Size", "Color"].map((label) => ({
										label,
									})),
									value: "Sort",
								}),
						},
					],
				},
				{
					title: __("Not dismissible (only its action closes it)"),
					items: [
						{
							button: { label: "Required notice" },
							title: "Session expired",
							content:
								"Sign in again to keep working. Unsaved changes stay in this tab.",
							dismissible: false,
							footer: (sheet) =>
								frappe.ui.button({
									label: "Sign in",
									variant: "solid",
									size: "md",
									onclick: () => {
										frappe.ui.toast({ message: "Signing in…" });
										sheet.close();
									},
								}),
						},
					],
				},
			],
		},
		"Optional Sections": {
			helper: "frappe.ui.optional_sections",
			stacked: true,
			groups: [
				{
					title: __("Basic (add a section, Remove puts its button back)"),
					items: [
						{
							label: "Add more now",
							sections: [
								{ title: "Contact", content: "Contact fields go here." },
								{ title: "Salary and bank", content: "Salary fields go here." },
								{
									title: "Emergency contact",
									content: "Emergency contact fields go here.",
								},
							],
							on_add: (i, section) =>
								frappe.ui.toast({ message: `${section.title} added` }),
						},
					],
				},
				{
					title: __("A section added from the start"),
					items: [
						{
							label: "Add more now",
							sections: [
								{ title: "Notes", content: "Shown until removed.", added: true },
								{ title: "Attachments", content: "Attachment fields go here." },
							],
						},
					],
				},
				{
					title: __("Fields in a section, cleared on Remove"),
					items: [
						{
							__code: 'let fields;\nfrappe.ui.optional_sections({\n  label: "Add more now",\n  sections: [{\n    title: "Contact",\n    content: () => {\n      const body = document.createElement("div");\n      fields = new frappe.ui.FieldGroup({ body, fields: contact_fields });\n      fields.make();\n      return body;\n    },\n  }],\n  on_remove: () => fields.set_values({ email: "", mobile: "" }),\n})',
							label: "Add more now",
							sections: [
								{
									title: "Contact",
									content: () => {
										const body = document.createElement("div");
										explorer_contact_fields = new frappe.ui.FieldGroup({
											body,
											fields: [
												{
													fieldtype: "Data",
													fieldname: "email",
													label: "Email",
												},
												{ fieldtype: "Column Break", fieldname: "column" },
												{
													fieldtype: "Data",
													fieldname: "mobile",
													label: "Mobile",
												},
											],
										});
										explorer_contact_fields.make();
										return body;
									},
								},
							],
							on_remove: () =>
								explorer_contact_fields.set_values({ email: "", mobile: "" }),
						},
					],
				},
			],
		},
		Tabs: {
			helper: "frappe.ui.tabs",
			wide: true,
			stacked: true,
			groups: [
				{
					title: __("Horizontal (arrows move between tabs, Home/End jump)"),
					items: [
						{
							tabs: [
								{
									label: "Details",
									content: "Name, owner and status of this record.",
								},
								{
									label: "Activity",
									content: "Edits and comments appear here, newest first.",
								},
								{ label: "Archived", disabled: true },
								{
									label: "Settings",
									content: "Notification and sharing preferences.",
								},
							],
							__note: "tab content runs once, on first activation; pass an element or a function returning one",
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
					caption: "type",
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
					caption: "size",
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
			preview: { group: 6, item: 0 },
			wide: true,
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
					title: __("Label position"),
					items: [
						{
							__code: 'frappe.ui.stepper({\n  steps: [{ label: "Config" }, { label: "Preview" }, { label: "Fix issues" }, { label: "Import" }],\n  current: 1,\n  label_position: "bottom",  // or "right" (default), "left", "top"\n})',
							steps: [
								{ label: "Config" },
								{ label: "Preview" },
								{ label: "Fix issues" },
								{ label: "Import" },
							],
							current: 1,
							label_position: "bottom",
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
			wide: true,
			stacked: true,
			groups: [
				{
					title: __("Basic (label + hint)"),
					items: [{ value: 30, label: "Importing", hint: true }, { value: 65 }],
				},
				{
					title: __("Sizes"),
					caption: "size",
					items: [
						{
							value: 40,
							size: "sm",
							label: "Uploading files",
							__note: "sm is the default",
						},
						{ value: 40, size: "md", label: "Uploading files" },
						{ value: 40, size: "lg", label: "Uploading files" },
						{ value: 40, size: "xl", label: "Uploading files" },
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
							__label: __("Animate progress"),
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
		"Stat Card": {
			helper: "frappe.ui.stat_card",
			groups: [
				{
					title: __("Value + caption"),
					items: [
						{ label: "Open orders", value: "24", caption: "₹3,40,000 to deliver" },
						{ label: "Customers", value: "1,208", icon: "users" },
					],
				},
				{
					title: __("Trend delta"),
					items: [
						{
							label: "Net sales",
							value: "₹12,40,000",
							delta: { value: 12.4, suffix: "since last year" },
						},
						{
							label: "Overdue",
							value: "₹1,80,000",
							delta: {
								value: 8,
								positive_is_good: false,
								suffix: "since last month",
							},
						},
						{ label: "Returns", value: "3", delta: { value: 0 } },
					],
				},
				{
					title: __("No reading vs zero"),
					items: [
						{ label: "Conversion rate", value: null },
						{ label: "Refunds", value: "0" },
					],
				},
				{
					title: __("Loading"),
					items: [{ label: "Net sales", loading: true }],
				},
				{
					title: __("Series dot + clickable"),
					items: [
						{
							label: "Paid",
							value: "₹8,20,000",
							dot: "var(--blue-600)",
							onclick: () => frappe.ui.toast({ message: "Paid" }),
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
			preview_label: __("Show toast"),
			html: (opts) => "",
			groups: [
				{
					title: __("Types"),
					caption: "type",
					items: [
						{
							__label: __("Show message"),
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
							__label: __("Show progress"),
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
							__label: __("Show message with link"),
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
							__label: __("Show unsafe HTML"),
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
			wide: true,
			preview: { group: 0, item: 1 },
			html: (opts) => frappe.ui.alert.html(opts),
			stacked: true,
			groups: [
				{
					title: __("Themes"),
					caption: "theme",
					items: [
						{ title: "Payroll runs on the 28th this month", __note: "gray, no icon" },
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
					title: __("Actions"),
					caption: "primary_action, secondary_action",
					items: [
						{
							title: "Permissions for this document have been customized.",
							theme: "yellow",
							__note: "one action and no description: the button sits inline",
							primary_action: {
								label: "Reset to default",
								onclick: () => frappe.show_alert(__("Reset")),
							},
						},
						{
							title: "A new version is available",
							description: "Update now to get the latest fixes.",
							theme: "blue",
							__note: "a description or a second action moves the buttons underneath",
							primary_action: {
								label: "Update",
								onclick: () => frappe.show_alert(__("Updating...")),
							},
							secondary_action: {
								label: "Later",
								onclick: () => frappe.show_alert(__("Later")),
							},
						},
					],
				},
				{
					title: __("Variants"),
					caption: "variant",
					items: [
						{
							title: "Leave balances reset on 1 April",
							theme: "blue",
							variant: "subtle",
							__note: "subtle is the default",
						},
						{
							title: "Your timesheet is due on Friday",
							__note: "outline keeps the icon and drops the fill",
							theme: "blue",
							variant: "outline",
						},
						{ title: "Expense claims close at month end", variant: "outline" },
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
					caption: "variant",
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
					caption: "size",
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
		"Segmented Button": {
			helper: "frappe.ui.segmented_button",
			groups: [
				{
					title: __("Main action with more ways to do it"),
					items: [
						{
							label: "Add Invoice",
							icon: "plus",
							variant: "solid",
							onclick: () => frappe.ui.toast({ message: "Add Invoice" }),
							options: [
								{
									group: "Create",
									hide_label: true,
									options: [
										{
											label: "Add manually",
											icon: "plus",
											description: "Fill in a blank form",
											onclick: () =>
												frappe.ui.toast({ message: "Add Invoice" }),
										},
										{
											label: "Upload",
											icon: "upload",
											description: "Create invoices from PDFs or images",
											onclick: () => frappe.ui.toast({ message: "Upload" }),
										},
									],
								},
								{
									group: "Import",
									hide_label: true,
									options: [
										{
											label: "Import",
											icon: "import",
											description: "Add many invoices from a spreadsheet",
											onclick: () => frappe.ui.toast({ message: "Import" }),
										},
									],
								},
							],
						},
					],
				},
				{
					title: __("Variants"),
					caption: "variant",
					items: ["solid", "subtle", "outline", "ghost"].map((variant) => ({
						label: "Save",
						variant,
						options: [{ label: "Save and New" }, { label: "Save as Draft" }],
					})),
				},
				{
					title: __("Sizes"),
					caption: "size",
					items: ["xs", "sm", "md", "lg"].map((size) => ({
						label: "Save",
						size,
						options: [{ label: "Save and New" }, { label: "Save as Draft" }],
					})),
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
						{ label: "Olive Oak", theme: "orange" },
						{ label: "Pia Park", theme: "pink" },
						{ label: "Yara Young", theme: "yellow" },
						{ label: "Theo Tan", theme: "teal" },
						{ label: "Cyra Cole", theme: "cyan" },
						{ label: "Paul Price", theme: "purple" },
					],
				},
				{
					title: __("Auto theme (picked from the name, same name same color)"),
					items: [
						{ label: "John Doe", theme: "auto" },
						{ label: "Jane Smith", theme: "auto" },
						{ label: "Sam Smith", theme: "auto" },
						{ label: "Alice Adams", theme: "auto" },
						{ label: "Ryan Reed", theme: "auto" },
					],
				},
				{
					title: __("Sizes"),
					caption: "size",
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
					caption: "shape",
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
		"Avatar Group": {
			helper: "frappe.ui.avatar_group",
			groups: [
				{
					title: __("Basic"),
					items: [
						{
							__code: "frappe.ui.avatar_group({ avatars: [{ label, image, theme }, ...] })",
							avatars: PEOPLE.slice(0, 3),
						},
					],
				},
				{
					title: __("Overflow (hover +4 to see everyone)"),
					items: [
						{
							__code: "frappe.ui.avatar_group({ avatars: seven_people, max: 3 })",
							avatars: PEOPLE,
							max: 3,
						},
					],
				},
				{
					title: __("With add button"),
					items: [
						{
							__code: 'frappe.ui.avatar_group({\n  avatars,\n  add: { title: "Assign", onclick: () => assign() },\n})',
							avatars: PEOPLE.slice(0, 5),
							add: {
								title: __("Assign"),
								onclick: () => frappe.ui.toast({ message: __("Add clicked") }),
							},
						},
					],
				},
				{
					title: __("Empty (only the add button)"),
					items: [
						{
							__code: 'frappe.ui.avatar_group({ avatars: [], add: { title: "Assign" } })',
							avatars: [],
							add: { title: __("Assign") },
						},
					],
				},
				{
					title: __("Clickable avatars (click +4: the list rows click too)"),
					items: [
						{
							__code: "frappe.ui.avatar_group({\n  avatars,\n  onclick: (avatar, e) => open_profile(avatar),\n})",
							avatars: PEOPLE,
							onclick: (avatar) =>
								frappe.ui.toast({ message: __("Clicked {0}", [avatar.label]) }),
						},
					],
				},
				{
					title: __("Hover card (rest the pointer on an avatar)"),
					items: [
						{
							__code: "frappe.ui.avatar_group({\n  avatars,\n  hover_card: (avatar) => build_user_card(avatar),  // details only; actions go in onclick\n})",
							avatars: PEOPLE.slice(0, 3),
							hover_card: person_card,
						},
					],
				},
				{
					title: __("Sizes"),
					caption: "size",
					items: ["xs", "sm", "md", "lg", "xl"].map((size) => ({
						__code: `frappe.ui.avatar_group({ avatars, size: "${size}", add: {} })`,
						avatars: PEOPLE,
						size,
						add: {},
					})),
				},
				{
					title: __("Colors (auto by default; a group or avatar theme overrides it)"),
					items: [
						{
							__code: 'frappe.ui.avatar_group({ avatars })  // theme: "auto"',
							avatars: PEOPLE.slice(1),
						},
						{
							__code: 'frappe.ui.avatar_group({ avatars, theme: "gray" })',
							avatars: PEOPLE.slice(1),
							theme: "gray",
						},
						{
							__code: 'frappe.ui.avatar_group({ avatars: [{ label: "Everyone", theme: "blue" }, ...] })',
							avatars: [{ label: "Everyone", theme: "blue" }, ...PEOPLE.slice(1, 4)],
						},
					],
				},
				{
					title: __("Square"),
					items: [
						{
							__code: 'frappe.ui.avatar_group({ avatars, size: "lg", shape: "square", add: {} })',
							avatars: PEOPLE,
							size: "lg",
							shape: "square",
							add: {},
						},
					],
				},
			],
		},
		Skeleton: {
			helper: "frappe.ui.skeleton",
			wide: true,
			preview: { group: 1 },
			html: (opts) => frappe.ui.skeleton.html(opts),
			groups: [
				{
					title: __("Sizes"),
					caption: "size",
					items: [
						{ width: "120px", height: "16px" },
						{ width: "240px", height: "16px" },
						{ width: "100%", height: "40px" },
					],
				},
				{
					title: __("Shapes"),
					caption: "shape",
					items: [
						{ width: "32px", height: "32px", css_class: "rounded-full" },
						{ width: "180px", height: "12px", css_class: "rounded-full" },
					],
				},
			],
		},
		Divider: {
			helper: "frappe.ui.divider",
			wide: true,
			// a vertical line needs a row with a height, or it has none to fill
			make: (opts) => {
				const $line = $(frappe.ui.divider(opts));
				if (opts.orientation !== "vertical") return $line;
				const label = (text) => `<span class="text-p-base text-ink-gray-5">${text}</span>`;
				return $('<div class="explorer-divider-row"></div>').append(
					label(__("Left")),
					$line,
					label(__("Right"))
				);
			},
			preview: { group: 1, item: 0 },
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
							__fill: true,
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
					caption: "theme",
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
					caption: "variant",
					items: [
						{ label: "Subtle" },
						{ label: "Solid", theme: "red", variant: "solid" },
						{ label: "Outline", variant: "outline" },
						{ label: "Ghost", variant: "ghost" },
					],
				},
				{
					title: __("Sizes"),
					caption: "size",
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

	const ROUTE = "component-explorer";
	const NAMES = Object.keys(COMPONENTS).sort((a, b) => a.localeCompare(b));
	const NAME_BY_SLUG = Object.fromEntries(NAMES.map((name) => [frappe.scrub(name, "-"), name]));
	const LAZY_BUNDLES = {
		"Stat Card": ["desk_charts.bundle.js", "desk_charts.bundle.css"],
		"Bottom Sheet": ["bottom_sheet.bundle.js", "bottom_sheet.bundle.css"],
		"Optional Sections": ["optional_sections.bundle.js", "optional_sections.bundle.css"],
	};
	// a group with `caption: "size"` labels each example with its `size`, and so on
	const CAPTION_KEYS = ["variant", "size", "theme", "shape", "type"];

	const href_of = (name) => `/desk/${ROUTE}/${frappe.scrub(name, "-")}`;
	const load_bundles = (names) =>
		Promise.all(
			names
				.filter((name) => LAZY_BUNDLES[name])
				.map((name) => frappe.require(LAZY_BUNDLES[name]))
		);

	function item_code(component, opts) {
		const code = opts.__code || to_code(component, opts);
		return opts.__note ? `// ${opts.__note}\n${code}` : code;
	}

	function count_examples(component) {
		return component.groups.reduce((total, group) => total + group.items.length, 0);
	}

	function make_example(component, opts, run_label) {
		// toasts and the like show themselves elsewhere: the example is their trigger
		if (opts.__run) {
			return frappe.ui.button({
				label: run_label || opts.__label || __("Run"),
				size: "sm",
				variant: "outline",
				onclick: opts.__run,
			});
		}
		return (component.make || helper_fn(component.helper))(opts);
	}

	// "solid" twice in one group becomes "solid" and "solid · red"
	function get_captions(group) {
		const key = group.caption;
		const runs = group.items.some((opts) => opts.__run);
		if (!key || runs || !group.items.some((opts) => opts[key]))
			return group.items.map(() => "");
		const captions = group.items.map((opts) => opts[key] || __("default"));
		const others = CAPTION_KEYS.filter((other) => other !== key);
		return group.items.map((opts, i) => {
			if (captions.indexOf(captions[i]) === captions.lastIndexOf(captions[i]))
				return captions[i];
			const extra = others.map((other) => opts[other]).filter(Boolean);
			return [captions[i], ...extra.slice(0, 1)].join(" · ");
		});
	}

	// "Picker (a tap applies and closes)" -> title "Picker", note "a tap applies and closes"
	function split_title(title) {
		const at = title.indexOf(" (");
		if (at < 0) return { title, note: "" };
		return { title: title.slice(0, at), note: title.slice(at + 2).replace(/\)$/, "") };
	}

	const $root = $('<div class="explorer"></div>').appendTo(page.main);
	let search_term = "";
	let $grid_view;
	let render_token = 0;

	// ---- grid ----

	// shrinking below 0.85 makes text unreadable, so a taller preview fades out instead
	function fit_stage(clip) {
		const stage = clip.firstElementChild;
		if (!clip.clientWidth || !stage) return;
		const natural = Math.max(stage.offsetWidth, stage.scrollWidth);
		const scale = Math.max(0.85, Math.min(1, clip.clientWidth / natural));
		stage.style.setProperty("--explorer-scale", scale);
		clip.classList.toggle("is-tall", stage.offsetHeight * scale > clip.clientHeight);
	}

	function build_card(name) {
		const component = COMPONENTS[name];
		const count = count_examples(component);
		const $card = $(`
			<a class="explorer-card" href="${href_of(name)}">
				<div class="explorer-card__preview">
					<div class="explorer-card__clip">
						<div inert class="explorer-card__stage ${component.stacked ? "is-stacked" : ""} ${
			component.wide ? "is-fill" : ""
		}"></div>
					</div>
				</div>
				<div class="explorer-card__body">
					<div class="explorer-card__name text-base-medium text-ink-gray-8"></div>
					<div class="text-base text-ink-gray-5">${
						count === 1 ? __("1 variant") : __("{0} variants", [count])
					}</div>
				</div>
			</a>
		`);
		const $name = $card.find(".explorer-card__name").text(name);
		frappe.ui.tooltip($name, { text: name, only_on_overflow: true });

		const pick = component.preview || { group: 0, item: 0 };
		const group = component.groups[pick.group];
		const items = pick.item === undefined ? group.items : [group.items[pick.item]];
		const $stage = $card.find(".explorer-card__stage");
		const $examples = items.map((opts) =>
			make_example(component, opts, component.preview_label)
		);
		if (items.length === 1) $stage.append($examples[0]);
		else $stage.append($('<div class="explorer-card__stack"></div>').append($examples));
		const clip = $card.find(".explorer-card__clip")[0];
		new ResizeObserver(() => fit_stage(clip)).observe(clip);
		return $card;
	}

	function update_grid() {
		const query = search_term.trim().toLowerCase();
		let shown = 0;
		$grid_view.find(".explorer-card").each((_, card) => {
			const match = card.dataset.name.toLowerCase().includes(query);
			card.hidden = !match;
			if (match) shown++;
		});
		const total = NAMES.length;
		const noun = (n) => (n === 1 ? __("1 component") : __("{0} components", [n]));
		$grid_view
			.find(".explorer-count")
			.text(!query ? noun(total) : __("{0} of {1} components", [shown, total]))
			.toggle(!query || !!shown);
		$grid_view.find(".explorer-grid").toggle(!!shown);
		const $empty = $grid_view.find(".explorer-empty").empty().toggle(!shown);
		if (shown) return;
		$empty.append(
			frappe.ui.empty_state({
				icon: "search",
				title: __('No components match "{0}"', [search_term.trim()]),
				actions: [
					{
						label: __("Clear search"),
						onclick: () =>
							$grid_view.find(".explorer-search").val("").trigger("input").focus(),
					},
				],
			})
		);
	}

	async function build_grid() {
		await load_bundles(NAMES);
		const $view = $(`
			<div>
				<div class="explorer-toolbar">
					<input type="search" class="form-control explorer-search" placeholder="${__(
						"Search"
					)}" aria-label="${__("Search")}">
					<div class="explorer-count text-base text-ink-gray-5"></div>
				</div>
				<div class="explorer-grid"></div>
				<div class="explorer-empty"></div>
			</div>
		`);
		const $grid = $view.find(".explorer-grid");
		NAMES.forEach((name) => {
			const $card = build_card(name);
			$card[0].dataset.name = name;
			$grid.append($card);
		});
		$view
			.find(".explorer-search")
			.val(search_term)
			.on("keydown", (e) => {
				// Escape clears the field; keep the desk from taking focus away
				if (e.key === "Escape") {
					e.stopPropagation();
					e.target.value = "";
					$(e.target).trigger("input");
				}
			})
			.on("input", (e) => {
				search_term = e.target.value;
				update_grid();
			});
		return $view;
	}

	async function show_grid() {
		const token = ++render_token;
		page.$title_area.find(".explorer-back").remove();
		page.set_breadcrumbs([{ label: __("Components") }]);
		frappe.utils.set_title(__("Components"));
		if (!$grid_view) {
			const $built = await build_grid();
			if (token !== render_token) return;
			$grid_view = $built;
		}
		$root.children().detach();
		$root.append($grid_view);
		update_grid();
	}

	// ---- one component ----

	function build_example(component, opts, caption) {
		const code = item_code(component, opts);
		const $example = $(`
			<div class="explorer-example ${opts.__fill ? "is-fill" : ""}">
				<div class="explorer-example__item"></div>
				${caption ? '<div class="explorer-example__caption text-p-sm text-ink-gray-5"></div>' : ""}
				<div class="explorer-example__copy"></div>
			</div>
		`);
		$example.find(".explorer-example__item").append(make_example(component, opts));
		$example.find(".explorer-example__caption").text(caption);
		// on touch there is no hover: a tap on an example shows its copy button
		$example.on("click", () => {
			$example.closest(".explorer-canvas").find(".is-active").removeClass("is-active");
			$example.addClass("is-active");
		});
		$example.find(".explorer-example__copy").append(
			frappe.ui.button({
				icon: "copy",
				size: "xs",
				variant: "ghost",
				tooltip: __("Copy code"),
				onclick: () => frappe.utils.copy_to_clipboard(code, __("Copied")),
			})
		);
		return $example;
	}

	function build_group(component, group) {
		const captions = get_captions(group);
		const $group = $(`
			<section class="explorer-group" data-testid="${frappe.scrub(split_title(group.title).title, "-")}">
				<div class="explorer-group__head">
					<h3 class="explorer-group__title text-base-medium text-ink-gray-8"></h3>
					<div class="explorer-group__toggle"></div>
				</div>
				<div class="explorer-preview explorer-canvas ${component.stacked ? "is-stacked" : ""} ${
			component.wide ? "is-wide" : ""
		} ${captions.some(Boolean) ? "has-captions" : ""}"></div>
				<pre dir="ltr" class="explorer-code text-ink-gray-8 text-p-sm" hidden><code></code></pre>
			</section>
		`);
		const { title, note } = split_title(group.title);
		$group.find(".explorer-group__title").text(title);
		const code = group.items.map((opts) => item_code(component, opts)).join("\n");
		$group.find("code").text(note ? `// ${note}\n${code}` : code);

		const $code = $group.find(".explorer-code");
		const $toggle = frappe.ui.button({
			label: __("Code"),
			icon: "code",
			size: "sm",
			variant: "ghost",
			attrs: { "aria-expanded": "false" },
			onclick: () => {
				const open = $code[0].hidden;
				$code[0].hidden = !open;
				$toggle.attr("aria-expanded", String(open));
			},
		});
		$group.find(".explorer-group__toggle").append($toggle);

		const $canvas = $group.find(".explorer-canvas");
		group.items.forEach((opts, i) => {
			$canvas.append(build_example(component, opts, captions[i]));
		});
		// on a phone, labels sit above their examples when a beside-layout would overflow
		const canvas = $canvas[0];
		new ResizeObserver(() => {
			canvas.classList.remove("labels-above");
			if (canvas.scrollWidth > canvas.clientWidth + 1) canvas.classList.add("labels-above");
		}).observe(canvas);
		return $group;
	}

	function build_pager(name) {
		const index = NAMES.indexOf(name);
		const link = (target, side) => {
			if (!target) return '<span class="explorer-pager__slot"></span>';
			const arrow = frappe.utils.icon(side === "prev" ? "arrow-left" : "arrow-right", "sm");
			const label = `<span class="explorer-pager__label">${frappe.utils.escape_html(
				target
			)}</span>`;
			return `<a class="explorer-pager__link explorer-pager__link--${side} text-base text-ink-gray-6" href="${href_of(
				target
			)}">${side === "prev" ? arrow + label : label + arrow}</a>`;
		};
		return $(
			`<nav class="explorer-pager" aria-label="${__("Components")}">${link(
				NAMES[index - 1],
				"prev"
			)}${link(NAMES[index + 1], "next")}</nav>`
		);
	}

	async function render_component(name) {
		const token = ++render_token;
		const component = COMPONENTS[name];
		if (!component) return show_grid();
		await load_bundles([name]);
		if (token !== render_token) return;

		page.set_breadcrumbs([
			{ label: __("Components"), href: `/desk/${ROUTE}` },
			{ label: name },
		]);
		// breadcrumbs collapse on phones, so a back button takes their place there
		page.$title_area.find(".explorer-back").remove();
		page.$title_area.prepend(
			$('<span class="explorer-back"></span>').append(
				frappe.ui.button({
					icon: "chevron-left",
					variant: "ghost",
					tooltip: __("Components"),
					onclick: () => frappe.set_route(ROUTE),
				})
			)
		);
		frappe.utils.set_title(name);

		const $view = $(`
			<div class="explorer-view">
				<div><code class="explorer-helper text-p-sm text-ink-gray-6"></code></div>
				<div class="explorer-groups" data-component="${frappe.utils.escape_html(name)}"></div>
			</div>
		`);
		$view.find(".explorer-helper").text(component.helper);
		const $groups = $view.find(".explorer-groups");
		component.groups.forEach((group) => $groups.append(build_group(component, group)));
		$view.append(build_pager(name));

		$root.children().detach();
		$root.append($view);
		frappe.utils.scroll_to(0);
	}

	// ---- routing ----

	function show_route() {
		const slug = frappe.get_route()[1];
		if (!slug) return show_grid();
		const name = NAME_BY_SLUG[slug];
		if (!name) return frappe.set_route(ROUTE);
		return render_component(name);
	}

	$(wrapper).on("show", show_route);
	// a render still loading when the page is left must not retitle the next page
	$(wrapper).on("hide", () => render_token++);

	// Deterministic entry point for UI tests: show one component's variants
	// without going through the grid. See playwright/tests/es_components.spec.js.
	frappe.pages["component-explorer"].render_component = render_component;
};
