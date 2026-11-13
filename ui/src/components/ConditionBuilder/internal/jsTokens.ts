// The tokens of the small JavaScript subset a `depends_on` condition is read in.
// Anything outside it throws, and the condition stays code.

export interface Token {
  kind: "name" | "number" | "string" | "punct";
  text: string;
}

// Longest first, so `===` is not read as `==` and `=`.
const PUNCTUATION = [
  "===",
  "!==",
  "==",
  "!=",
  "<=",
  ">=",
  "&&",
  "||",
  "??",
].concat(["<", ">", "!", "(", ")", "[", "]", ",", ".", "-", ";"]);

const ESCAPES: Record<string, string> = {
  n: "\n",
  t: "\t",
  r: "\r",
  b: "\b",
  f: "\f",
  "\\": "\\",
  '"': '"',
  "'": "'",
  "/": "/",
};

export function tokenize(source: string): Token[] {
  const tokens: Token[] = [];
  let at = 0;
  while (at < source.length) {
    const rest = source.slice(at);
    const space = /^\s+/.exec(rest);
    if (space) {
      at += space[0].length;
      continue;
    }
    const token = readToken(rest);
    tokens.push(token.token);
    at += token.length;
  }
  return tokens;
}

function readToken(rest: string): { token: Token; length: number } {
  const name = /^[A-Za-z_$][\w$]*/.exec(rest);
  if (name)
    return { token: { kind: "name", text: name[0] }, length: name[0].length };

  // A number runs into a name (`1e3`, `0x1f`) only in forms this subset refuses;
  // a leading zero (`010`) is octal in sloppy code, so it is refused too.
  const number = /^(0|[1-9]\d*)(\.\d+)?(?![\w$.])/.exec(rest);
  if (number)
    return {
      token: { kind: "number", text: number[0] },
      length: number[0].length,
    };

  if (rest[0] === '"' || rest[0] === "'") return readString(rest);

  const punct = PUNCTUATION.find((one) => rest.startsWith(one));
  if (!punct) throw new SyntaxError(`Unexpected ${rest[0]}`);
  return { token: { kind: "punct", text: punct }, length: punct.length };
}

function readString(rest: string): { token: Token; length: number } {
  const quote = rest[0];
  let text = "";
  let at = 1;
  while (at < rest.length && rest[at] !== quote) {
    // A line break ends a string literal: JavaScript refuses the code.
    if (rest[at] === "\n" || rest[at] === "\r")
      throw new SyntaxError("Unterminated string");
    if (rest[at] !== "\\") {
      text += rest[at++];
      continue;
    }
    const escaped = readEscape(rest, at + 1);
    text += escaped.text;
    at = escaped.end;
  }
  if (at >= rest.length) throw new SyntaxError("Unterminated string");
  return { token: { kind: "string", text }, length: at + 1 };
}

function readEscape(rest: string, at: number): { text: string; end: number } {
  const unicode = /^u([0-9a-fA-F]{4})/.exec(rest.slice(at));
  if (unicode) {
    return { text: String.fromCharCode(parseInt(unicode[1], 16)), end: at + 5 };
  }
  if (!Object.hasOwn(ESCAPES, rest[at]))
    throw new SyntaxError("Unknown escape");
  return { text: ESCAPES[rest[at]], end: at + 1 };
}
