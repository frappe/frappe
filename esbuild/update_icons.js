// Rebuilds frappe/public/icons/lucide/icons.svg from the pinned lucide-static package.
// Run with `yarn update-icons`, then check the printed list of removed icons against the apps.
const fs = require("fs");
const path = require("path");

const root = path.resolve(__dirname, "..");
const out_dir = path.join(root, "frappe/public/icons/lucide");
const pkg = path.join(root, "node_modules/lucide-static");
const version = require(path.join(pkg, "package.json")).version;

const symbol = (id, body) =>
	`    <symbol viewBox="0 0 24 24" id="icon-${id}">\n${body}\n    </symbol>`;
const inner = (svg) =>
	svg
		.replace(/^[\s\S]*?<svg[^>]*>/, "")
		.replace(/<\/svg>[\s\S]*$/, "")
		.trim()
		.split("\n")
		.map((line) => "      " + line.trim())
		.join("\n");

// lucide's own sprite: <symbol id="name" viewBox="0 0 24 24">...</symbol>
const sprite = fs.readFileSync(path.join(pkg, "sprite.svg"), "utf8");
const icons = {};
for (const m of sprite.matchAll(/<symbol id="([^"]+)"[^>]*>([\s\S]*?)<\/symbol>/g)) {
	icons[m[1]] = inner(`<svg>${m[2]}</svg>`);
}

// icons Lucide no longer ships (brands) that frappe still needs
for (const file of fs.readdirSync(path.join(out_dir, "extra"))) {
	if (!file.endsWith(".svg")) continue;
	icons[file.slice(0, -4)] = inner(fs.readFileSync(path.join(out_dir, "extra", file), "utf8"));
}

// renamed icons stay reachable by their old name
const aliases = JSON.parse(fs.readFileSync(path.join(out_dir, "aliases.json"), "utf8"));
for (const [old_name, new_name] of Object.entries(aliases)) {
	if (!icons[new_name]) throw new Error(`alias ${old_name}: no icon named ${new_name}`);
	icons[old_name] = icons[new_name];
}

const previous = fs.readFileSync(path.join(out_dir, "icons.svg"), "utf8");
const before = new Set([...previous.matchAll(/id="icon-([^"]+)"/g)].map((m) => m[1]));
const names = Object.keys(icons).sort();

fs.writeFileSync(
	path.join(out_dir, "icons.svg"),
	[
		`<!-- @license lucide-static v${version} - ISC -->`,
		`<svg id="frappe-symbols" aria-hidden="true" style="display: none;" class="icon" xmlns="http://www.w3.org/2000/svg" >`,
		...names.map((id) => symbol(id, icons[id])),
		"</svg>",
		"",
	].join("\n")
);

const removed = [...before].filter((id) => !icons[id]).sort();
const added = names.filter((id) => !before.has(id));
console.log(
	`lucide-static v${version}: ${names.length} icons (${added.length} added, ${removed.length} removed)`
);
if (removed.length) console.log("removed, check the apps for references:", removed.join(" "));
