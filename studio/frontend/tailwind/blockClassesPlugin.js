import plugin from "tailwindcss/plugin"
import blockClasses from "./blockClasses.js"

// The island build writes its own Tailwind config and takes plugins only. A user makes desk
// components on a site with no build, so the island's stylesheet holds these classes.
export default plugin(() => {}, { safelist: blockClasses })
