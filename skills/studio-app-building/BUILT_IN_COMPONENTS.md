# Built-in components

The components that Studio ships with, by purpose. A block uses one by its
name in `componentName`. For the parts that you make, a Studio Component or a
Vue component, see "Choose a component" in SKILL.md.

## Get the full props of a built-in component

Do not guess a prop, and do not read the Studio source for it. Call the
whitelisted method `frappe.studio.api.get_component_definition` with
`component` set to the name, such as `Badge`. It only reads.

The result is the JSON schema of the props: each prop with its type, its
allowed values, and the required props. On a bench, the same file is
`studio/frontend/src/json_types/<library>/<Component>.json`.

The method has no definition for some components that work only inside
another one, such as `SidebarItem` in a `Sidebar` and `ListCell` in a `List`.
It returns an error for these. Use the props that this file gives for them.

## Before you use this file

- The block structure, the slot structure, bindings, icons, and handler
  strings are in SKILL.md and RULES.md. They apply to all components.
- The slots named here are the common ones, not all of them. Content in a
  slot that the component does not have is not rendered, and there is no
  error.

## Layout

- `div`: the layout block. Set `originalElement` to `"div"`. It has no props.
  Use `baseStyles` for flex, gap, padding, and size.
- `Repeater`: repeats its children one time for each row of `data`.
  - Props: `data` (bind it to `{{ source.data }}`), `dataKey` (required: the
    field with a stable, unique value for each row, usually `"name"`),
    `emptyStateMessage`.
  - Make one row template as its child. Do not make one child for each
    record. In the template, `dataItem` is the row and `dataIndex` is its
    zero-based index. Read a field with `{{ dataItem.item_name }}`.
  - Descendant blocks inherit `dataItem` and `dataIndex` through nested
    containers. Use them directly in props, styles, `visibilityCondition`,
    and event scripts.
  - For a reusable Studio Component in the template, pass row values as
    props, such as `{"title": "{{ dataItem.item_name }}"}`. Its internal
    blocks should read its props.
  - In a nested `Repeater`, `dataItem` and `dataIndex` refer to the inner row.
  - It shows its empty message when `data` is missing or empty, including
    before a source loads. Handle loading separately, and avoid a duplicate
    empty state.
  - Its own layout is a wrapping row with a gap. For a vertical list, set
    `flexDirection: "column"` and the gap in its `baseStyles`.
- `Divider`: no props.

There is no `Card`. Make a surface from a `div`: a background, a border, a
radius, and padding from DESIGN.md.

## Text and display

- `TextBlock`: `text`, `tag` (`p`, `h1` to `h6`, `span`), `fontSize` (a
  `text-*` class name). Use it for standalone text. A component draws its
  own label and description.
- `Icon`: `icon`. Use it for an icon that stands alone.
- `Badge`: `label`, `variant`, `theme`, `size`. Slots: `prefix`, `suffix`.
- `Avatar`: `label` (makes initials), `image`, `size`, `shape`.
- `Alert`: `title`, `description`, `theme`, `dismissible`. Slots: `prefix`,
  `title`, `description`, `actions`.
- `Progress`: `value` (0 to 100, required), `label`, `size`.
- `NumberCard`: `title` and `value` (required), `prefix`, `suffix`, `delta`,
  `deltaSuffix`, `deltaCaption`, `negativeIsBetter`. It draws its own card.
- `ImageView`: `image`, `alt`, `size`, `shape`.
- `Tooltip`: `text`. The block that it explains is its child.
- `Spinner`, `ErrorMessage` (`message`), `HTML` (`html`: raw markup, also
  for an SVG logo).

## Inputs

- `FormControl` is the default input: `type` (`text`, `number`, `email`,
  `textarea`, `select`, `checkbox`, `date`, and more), `label`,
  `placeholder`, `modelValue`, and `options` for `select`.
- Single inputs with `label`, `placeholder`, and `modelValue`: `TextInput`,
  `Textarea`, `Select` (`options`), `MultiSelect` (`modelValue` is an
  array), `Combobox`, `Duration`, `DatePicker`, `TimePicker`,
  `DateTimePicker`, `DateRangePicker` (`modelValue` is an array of two
  dates).
- `Checkbox`, `Switch`, `Rating`, and `Slider` take `label` and `modelValue`.
  They have no `placeholder`.
- `Password`: `label`, `placeholder`.
- `TextEditor` keeps its value in `content`, not `modelValue`. It has no
  `label`: put a `FormLabel` above it.
- `FileUploader`: `fileTypes`. It has no `label` and no value prop.
- `RadioGroup`: `label`, `modelValue`. Its children are `Radio` blocks
  (`value`, `label`). A `Radio` outside a `RadioGroup` throws.
- `FormLabel`: `label`. Use it only for an input that has no `label` prop.
- Inputs that read a DocType: `Link` (`doctype`, required), `Phone`,
  `TableMultiSelect`, `Grid` (a child table; `columns` required),
  `FormLayout` (a full form; `layout` required).

## Actions and overlays

- `Button`: `label`, `variant` (`solid`, `subtle`, `outline`, `ghost`),
  `theme`, `size`, `icon`, `iconLeft`, `iconRight`, `loading`, `disabled`,
  `route`. A primary action is `variant: "solid"`. Use `theme: "red"` only
  for a destructive action. Slots: `prefix`, `suffix`.
- `Dropdown`: `options` (`[{label, icon, onClick}]`, or groups of them) and
  `button` (`{label}`).
- `ContextMenu`: `options`. Its child is the area that opens the menu.
- `Dialog`: `modelValue` (open state), `title`, `message`, `size`, `actions`
  (`[{label, variant, theme, onClick}]`).
  - Keep `modelValue` bound to a variable that starts `false`. Open the
    dialog by setting the variable in an event. Close it the same way.
  - The body of the dialog is its children, not a prop.
  - `bare: true` removes the header, the padding, and the actions.
- `Popover`: `trigger` (`click` or `manual`), `side`, `align`. Slots:
  `trigger`, `default`.

## Navigation

- `Sidebar`: `collapsible`. It is a frame. Its children are:
  - `SidebarHeader`: `title`, `subtitle`, `menuItems` (`[{label, icon,
    onClick}]`).
  - `SidebarLabel`: its text is a `TextBlock` child, not a prop.
  - `SidebarItem`: `label`, `icon`, `route`, `active`.
  - `SidebarCard`: `title`, `description`, `theme`, `action`.
  - `SidebarCollapseToggle`: no props.
- `SidebarRail`: a narrow column of icons beside a `Sidebar`, not in it. Its
  children are `SidebarRailItem` blocks (`label`, `icon`, `route`, `active`,
  `badge`).
- `Breadcrumbs`: `items` (`[{label, route}]`, required).
- `Tabs`: `tabs` (`[{label, value}]`), `modelValue`. Slots: `tab-prefix`,
  `tab-label`, `tab-suffix`, `tab-panel`.
- `TabButtons`: `options` (`[{label, value}]`), `modelValue`, `variant`.
- `Header`: a page header.

## Lists and data

- The `List` family is the default for a list or a table. The parts are
  `List` (`columns`, `rowHeight`), `ListHeader`, `ListHeaderCell`,
  `ListHeaderCellSort`, `ListRows` (`items`, `rowKey`), `ListRow` (`value`,
  `route`), `ListCell`, and `ListGroup`.
  - A `List` does not accept table-style `rows` and `columns` objects. Set
    `columns` to CSS grid track sizes, one for each cell.
  - Put `ListHeader` and `ListRows` directly in `List`.
  - Bind the records to `ListRows.items`. Put one `ListRow` template in the
    `default` slot of `ListRows`.
  - The slot gives `item`, `index`, and `value`. Bind a cell with
    `{{ item.<field> }}`. Bind the `value` prop of the row with `{{ value }}`.

  ```json
  {
  	"componentName": "List",
  	"componentProps": {"columns": ["minmax(0, 1fr)", "8rem"], "rowHeight": 56},
  	"baseStyles": {"width": "100%"},
  	"children": [
  		{
  			"componentName": "ListHeader",
  			"children": [
  				{"componentName": "ListHeaderCell", "children": [{"componentName": "TextBlock", "componentProps": {"text": "Item"}}]},
  				{"componentName": "ListHeaderCell", "children": [{"componentName": "TextBlock", "componentProps": {"text": "Group"}}]}
  			]
  		},
  		{
  			"componentName": "ListRows",
  			"componentProps": {"items": "{{ items.data || [] }}"},
  			"componentSlots": {
  				"default": {
  					"slotName": "default",
  					"slotContent": [
  						{
  							"componentName": "ListRow",
  							"componentProps": {"value": "{{ value }}"},
  							"children": [
  								{"componentName": "ListCell", "children": [{"componentName": "TextBlock", "componentProps": {"text": "{{ item.item_name }}"}}]},
  								{"componentName": "ListCell", "children": [{"componentName": "TextBlock", "componentProps": {"text": "{{ item.item_group }}"}}]}
  							]
  						}
  					]
  				}
  			}
  		}
  	]
  }
  ```

  Add a `componentId` to each block. Bind `items` with `|| []`: the source
  has no data until it loads.
- `Tree`: `nodes` (`[{name, label, children}]`, required), `nodeKey`,
  `guides`. Slots: `item`, `item-label`.
- `Calendar`: `events` (required), `config`.
- Blocks for a DocType list: `ListView`, `ListViewShell`, `Filter`,
  `QuickFilter`, `SortBy`, `ColumnSettings`. Each takes `doctype`.
- Activity and files: `ActivityTimeline`, `CommentItem`, `CommentComposer`,
  `EmailItem`, `EmailComposer`, `NotificationPanel`, `NotificationItem`,
  `AttachmentsList`, `FileUploadDialog`, `UploadTray`.

## Charts

`BarChart`, `LineChart`, `AreaChart`, `DonutChart`, `FunnelChart`,
`HeatmapChart`, `ScatterChart`, `SankeyChart`.

- The props name the columns of your rows:
  `{"title": "Sales", "data": "{{ sales.data }}", "x": "month", "y": "amount"}`.
  `y` takes an array for more than one series. `DonutChart` and
  `FunnelChart` use `category` and `value`.
- A chart fills its parent. Give the chart block a height in `baseStyles`,
  such as `{"width": "100%", "height": "300px"}`. Without a height it is 0px
  tall.

## Settings dialog

`SettingsDialog` is a family: `SettingsSidebar`, `SettingsNavGroup`,
`SettingsNavItem`, `SettingsContent`, `SettingsPanel`, `SettingsHeader`,
`SettingsBody`, `SettingsRow`. A `SettingsNavItem` and its `SettingsPanel`
share the same `value`. Copy the tree from the `settings-dialog` template
when you can read the Studio source.

## Design review

`Variants` shows one of its children at a time, to compare design options.
See RULES.md.
