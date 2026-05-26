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
- Button: {label: "string", variant: "solid|subtle|outline|ghost", size: "sm|md|lg|xl|2xl", theme: "gray (DEFAULT — omit unless red/green/blue is semantically required)"}
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

SYSTEM_PROMPT = f"""You are an expert UI builder for Frappe Studio, a Vue.js-based low-code app builder. Your task is to generate a JSON block tree that Studio will render as a live Vue application. Each block in the tree maps to a Vue component or native html element (div) or a Studio Vue component or a Frappe UI Vue component.

OUTPUT FORMAT:
Return ONLY a JSON object with a single key "blocks" containing an array with one root block.

BLOCK STRUCTURE:
{{
  "componentName": "string (required)",
  "componentProps": {{}},      // component-specific props
  "baseStyles": {{}},          // CSS-in-JS camelCase properties
  "children": [],              // nested blocks (for container blocks)
  "componentSlots": {{}}       // for frappe-ui components that hold child content
}}

ROOT BLOCK:
Always start with: {{"componentName": "div", "originalElement": "body", "blockName": "body", "baseStyles": {{"display": "flex", "flexDirection": "column", "flexShrink": 0, "width": "inherit", "overflowX": "hidden", "height": "100%"}}}}

LAYOUT CONTAINERS (CRITICAL — originalElement is required or children won't render):
{{"componentName": "container", "originalElement": "div", "blockName": "container", "baseStyles": {{}}, "children": [...]}}
- Use container for all inner layout wrappers — never use "div" as componentName for inner blocks
- flexDirection: "row" for horizontal layouts, "column" for vertical
- Use gap, padding for spacing. width: "100%" for full-width sections. flex: 1 to fill space.

COMPONENT STYLING RULES:
- Always use CSS variables. Avoid raw hex colors/values.
	- backgroundColor:  var(--surface-white) | var(--surface-gray-1..7) | var(--surface-cards) | var(--surface-red-1) | var(--surface-green-1) | var(--surface-amber-1) | var(--surface-blue-1)
	- color (text): var(--ink-white) | var(--ink-gray-1..9)
	- borderColor: var(--outline-white) | var(--outline-gray-1..5) | var(--outline-red-1..3) | var(--outline-green-1..2) | var(--outline-amber-1..2) | var(--outline-blue-1) | var(--outline-orange-1)
	- boxShadow: "sm" | "DEFAULT" | "md" | "lg" | "xl" | "2xl" | "none" (keywords only, not raw values)
	- borderRadius: "none" (0px) | "sm" (0.25rem) | "DEFAULT" (0.5rem) | "md" (0.625rem) | "lg" (0.75rem) | "xl" (1rem) | "2xl" (1.25rem) | "full" (9999px)
- Button: use size prop ("sm"|"md"|"lg"|"xl"|"2xl") for sizing — DO NOT set height in baseStyles. Keep `theme` gray or default unless prompted. Only use colored themes (blue, red, green) when semantically meaningful: destructive actions → red, success/confirmed → green.
- Avoid applying visual baseStyles (color, backgroundColor, border, fontSize) to frappe-ui components (eg: height on Button component) — their props handle this. Only use baseStyles on components for layout (width, flex, margin, etc.).
- TextBlock: use tag prop for semantics (h1/h2/h3 for headings, p for body). Set fontSize/fontWeight/color on TextBlock baseStyles.

AVAILABLE COMPONENTS:
{COMPONENT_CATALOG}

RULES:
- componentName must exactly match a name from the catalog above
- baseStyles keys must be camelCase CSS (backgroundColor, borderRadius, fontSize, etc.)
- Do NOT include componentId (auto-generated)
- Do NOT include parentBlock
- Keep componentProps to only what's relevant to the description

EXAMPLE — "A login form with email, password and a submit button":
{{
  "blocks": [{{
    "componentName": "div", "originalElement": "body", "blockName": "body",
    "baseStyles": {{"display": "flex", "flexDirection": "column", "flexShrink": 0, "width": "inherit", "overflowX": "hidden", "height": "100%"}},
    "children": [{{
      "componentName": "container", "originalElement": "div", "blockName": "container",
      "baseStyles": {{"display": "flex", "flexDirection": "column", "alignItems": "center", "justifyContent": "center", "flex": 1, "padding": "24px"}},
      "children": [{{
        "componentName": "container", "originalElement": "div", "blockName": "container",
        "baseStyles": {{"display": "flex", "flexDirection": "column", "gap": "16px", "width": "100%", "maxWidth": "400px", "padding": "32px", "backgroundColor": "var(--surface-white)", "borderRadius": "0.75rem", "boxShadow": "md"}},
        "children": [
          {{"componentName": "TextBlock", "componentProps": {{"text": "Sign In", "tag": "h2"}}, "baseStyles": {{"fontSize": "20px", "fontWeight": "600", "color": "var(--ink-gray-9)"}}, "children": []}},
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
	api_key = settings.get_password("ai_api_key", raise_exception=False)
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

	content = strip_fences(content)
	try:
		parsed = json.loads(content)
	except json.JSONDecodeError as e:
		frappe.log_error(title="Studio AI: JSON parse error", message=f"{e}\ncontent:\n{content}")
		frappe.throw(f"The AI model returned invalid JSON ({e}). Raw response has been logged.")

	blocks = parsed.get("blocks", parsed) if isinstance(parsed, dict) else parsed
	if not isinstance(blocks, list):
		frappe.throw("AI returned an unexpected response format. Please try again.")

	return json.dumps(blocks)


def strip_fences(text: str) -> str:
	text = text.strip()
	if text.startswith("```"):
		lines = text.splitlines()
		# drop first line (```json or ```) and last line (```)
		inner_lines = lines[1:-1] if lines[-1].strip() == "```" else lines[1:]
		return "\n".join(inner_lines).strip()
	return text
