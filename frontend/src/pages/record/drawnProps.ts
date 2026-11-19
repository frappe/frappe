// What draws a header item declares, read off frappe-ui here so the engine imports no component list.
import { Button } from "frappe-ui";
import type { DrawnProps } from "@/recordPage";

// `MenuActionOption`'s declared keys, less the engine's own words and the slot keys; the type
// carries an index signature, so there is no runtime list to read and this one is kept by hand.
const MENU_OPTION_PROPS = ["description", "selected", "disabled", "theme", "condition", "route"];

/** The declared-prop lists the record page hands the engine, as `setIconSource` hands it the sprite. */
export function recordDrawnProps(): DrawnProps {
	return { button: Object.keys(Button.props ?? {}), menuOption: MENU_OPTION_PROPS };
}
