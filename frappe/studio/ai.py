import json

import frappe
import litellm

COMPONENT_CATALOG = """
LAYOUT:
- container: layout wrapper (renders as a div). No componentProps. Use baseStyles: display, flexDirection, gap, padding, width, height, flexWrap, alignItems, justifyContent, flexShrink, flex, etc.

TEXT & DISPLAY:
- TextBlock: {text: "string", tag: "p|h1|h2|h3|h4|h5|h6|span"}
- Badge: {variant: "subtle|solid|outline", theme: "green|red|orange|blue|gray", size: "sm|md|lg", label: "string"}
- Avatar: {shape: "circle|square", size: "xs|sm|md|lg|xl|2xl|3xl", label: "initials", image: "url"}
- Progress: {value: 0-100, size: "sm|md|lg", label: "string"}
- Alert: {title: "string", description: "string", theme: "yellow|red|green|blue"}
- ErrorMessage: {message: "string"}
- FeatherIcon: {name: "feather-icon-name", class: "h-5 w-5"}
- ImageView: {image: "url", size: "xs|sm|md|lg|xl"}
- Card: {title: "string", subtitle: "string"}
- Divider: (no props)
- Tooltip: {text: "string"}
- HTML: {html: "<p>raw html</p>"}

INPUTS:
- TextInput: {placeholder: "string"}
- Textarea: {placeholder: "string"}
- FormControl: {type: "text|email|number|select|date|autocomplete|password", label: "string", placeholder: "string"}
- Select: {placeholder: "string", options: [{label: "string", value: "string"}]}
- Checkbox: {label: "string", checked: true|false}
- Switch: {label: "string", description: "string", modelValue: true|false}
- DatePicker: {placeholder: "string"}
- TimePicker: {placeholder: "string"}
- DateTimePicker: {placeholder: "string"}
- MultiSelect: {placeholder: "string", options: [{label: "string", value: "string"}]}
- Rating: {label: "string"}
- FileUploader: {label: "string", fileTypes: "['image/*']"}
- TextEditor: {modelValue: "string", editable: true, fixedMenu: true}

ACTIONS:
- Button: {label: "string", variant: "solid|subtle|outline|ghost", theme: "blue|red|green|gray"}
- Dropdown: {options: [{label: "string", icon: "feather-icon"}], button: {label: "string"}}

NAVIGATION:
- Breadcrumbs: {items: [{label: "string", route: "string"}]}
- Tabs: {tabs: [{label: "string"}]}
- TabButtons: {buttons: [{label: "string", value: "string"}]}
- Sidebar: {header: {title: "string", subtitle: "string"}, sections: [{label: "string", items: [{label: "string", icon: "string", to: "string"}]}]}

DATA DISPLAY:
- ListView: {columns: [{label: "string", key: "string", width: number}], rows: [{key: value}], rowKey: "string"}
- NumberChart: {config: {title: "string", value: number, prefix: "string", delta: number}}
- AxisChart: {config: {data: [{xKey: val, yKey: val}], xAxis: {key: "string", type: "time|category"}, yAxis: {title: "string"}, series: [{name: "string", type: "bar|line"}]}}
- DonutChart: {config: {data: [{cat: val, val: number}], categoryColumn: "string", valueColumn: "string"}}
- Filter: {doctype: "string", filters: {}}
- Link: {doctype: "string"}
- Tree: {nodeKey: "string", node: {name: "string", label: "string", children: []}}
- Repeater: (no props — repeats child template over data)
- Calendar: {config: {defaultMode: "Month"}, events: []}

AUTOCOMPLETE:
- Autocomplete: {placeholder: "string", options: [{label: "string", value: "string"}]}
- Combobox: {placeholder: "string", options: [{group: "string", options: [{label, value}]}]}
"""

SYSTEM_PROMPT = f"""You are a UI builder for a no-code app platform. Generate a JSON block tree for a Studio page based on the user's description.

OUTPUT FORMAT:
Return ONLY a JSON object with a single key "blocks" containing an array with one root block.

BLOCK STRUCTURE:
{{
  "componentName": "string (required)",
  "componentProps": {{}},      // component-specific props
  "baseStyles": {{}},          // CSS properties in camelCase (e.g. display, flexDirection, gap, padding, backgroundColor)
  "children": [],              // nested blocks
  "componentSlots": {{}}       // rarely needed; use children instead
}}

ROOT BLOCK RULES:
- Always start with the page root: {{"componentName": "div", "originalElement": "body", "blockName": "body", "baseStyles": {{"display": "flex", "flexDirection": "column", "flexShrink": 0, "width": "inherit", "overflowX": "hidden", "height": "100%"}}}}
- Nest all content inside this root block's children
- For ALL inner layout wrappers use "container" (not "div"): {{"componentName": "container", "originalElement": "div", "blockName": "container", ...}}

LAYOUT TIPS:
- Use container blocks with display:flex for rows and columns
- flexDirection: "row" for horizontal, "column" for vertical
- gap: "16px" between items, padding: "16px" or "24px" for spacing
- Use flexWrap: "wrap" for responsive grids
- width: "100%" on containers; use flex: 1 to fill remaining space

AVAILABLE COMPONENTS:
{COMPONENT_CATALOG}

RULES:
- componentName must exactly match a name from the catalog above
- baseStyles keys must be camelCase CSS (e.g. backgroundColor, borderRadius, fontSize)
- Do NOT include componentId (auto-generated)
- Do NOT include parentBlock
- Keep componentProps minimal — only include props relevant to the user's description

EXAMPLE — "A login form with email, password and a submit button":
{{
  "blocks": [{{
    "componentName": "div",
    "originalElement": "body",
    "blockName": "body",
    "baseStyles": {{"display": "flex", "flexDirection": "column", "flexShrink": 0, "width": "inherit", "overflowX": "hidden", "height": "100%"}},
    "children": [{{
      "componentName": "container",
      "originalElement": "div",
      "blockName": "container",
      "baseStyles": {{"display": "flex", "flexDirection": "column", "alignItems": "center", "justifyContent": "center", "flex": 1, "padding": "24px"}},
      "children": [{{
        "componentName": "container",
        "originalElement": "div",
        "blockName": "container",
        "baseStyles": {{"display": "flex", "flexDirection": "column", "gap": "16px", "width": "100%", "maxWidth": "400px"}},
        "children": [
          {{"componentName": "TextBlock", "componentProps": {{"text": "Sign In", "tag": "h2"}}, "baseStyles": {{"fontSize": "24px", "fontWeight": "600"}}, "children": []}},
          {{"componentName": "TextInput", "componentProps": {{"placeholder": "Email address"}}, "children": []}},
          {{"componentName": "FormControl", "componentProps": {{"type": "password", "label": "Password", "placeholder": "Enter password"}}, "children": []}},
          {{"componentName": "Button", "componentProps": {{"label": "Sign In", "variant": "solid"}}, "children": []}}
        ]
      }}]
    }}]
  }}]
}}
"""


@frappe.whitelist()
def generate_page_from_prompt(prompt: str) -> str:
	settings = frappe.get_single("Studio Settings")
	api_key = settings.get_password("openrouter_api_key") if settings.openrouter_api_key else None
	model = settings.ai_model or "openrouter/google/gemini-3.1-pro-preview"

	if not api_key:
		frappe.throw("OpenRouter API key is not configured. Please set it in Studio Settings.")

	response = litellm.completion(
		model=model,
		messages=[
			{"role": "system", "content": SYSTEM_PROMPT},
			{"role": "user", "content": prompt},
		],
		api_key=api_key,
	)

	content = response.choices[0].message.content
	if not content:
		frappe.throw("The AI model returned an empty response. Try a different model or prompt.")

	# strip markdown code fences if the model wrapped the JSON
	content = content.strip()
	if content.startswith("```"):
		content = content.split("\n", 1)[-1]
		content = content.rsplit("```", 1)[0].strip()

	parsed = json.loads(content)

	blocks = parsed.get("blocks", parsed) if isinstance(parsed, dict) else parsed
	if not isinstance(blocks, list):
		frappe.throw("AI returned an unexpected response format. Please try again.")

	return json.dumps(blocks)
