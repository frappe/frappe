// The server's entry: reads [{ name, script }] as JSON on stdin and writes [{ name, code, errors }].
// With --key-parts, it writes the parts of the server's cache key instead.
import { text } from "node:stream/consumers";
import { cacheKeyParts, compileScript } from "./compileScript.mjs";

if (process.argv.includes("--key-parts")) {
  process.stdout.write(JSON.stringify(cacheKeyParts()));
} else {
  const scripts = JSON.parse(await text(process.stdin));
  const results = scripts.map(({ name, script }) => ({
    name,
    ...compileScript(script),
  }));
  process.stdout.write(JSON.stringify(results));
}
