import { build } from "vite"
import { readFileSync, readdirSync } from "node:fs"
const out = process.argv[2]
await build({ root: process.cwd(), logLevel: "error", build: { outDir: out, emptyOutDir: true, sourcemap: true } })
const r = {}
for (const f of readdirSync(out + "/assets").filter(f => /^(shell|Record)-.*\.js\.map$/.test(f))) {
  const m = JSON.parse(readFileSync(out + "/assets/" + f, "utf8"))
  r[f.split("-")[0]] = Object.fromEntries(m.sources.map((s, i) => [s.replace(/^.*?(frontend\/src|node_modules)/, "$1"), (m.sourcesContent?.[i] ?? "").length]))
}
console.log(JSON.stringify(r))
