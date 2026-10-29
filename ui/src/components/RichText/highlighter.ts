/** The editor's highlighter with its common languages, and the colours it is drawn in. */
import { common, createLowlight } from "lowlight";
import "./highlightTheme.css";

export const highlighter = createLowlight(common);
