import hljs from "highlight.js/lib/core";
import javascript from "highlight.js/lib/languages/javascript";
import python from "highlight.js/lib/languages/python";
import xml from "highlight.js/lib/languages/xml";
import sql from "highlight.js/lib/languages/sql";

hljs.registerLanguage("javascript", javascript);
hljs.registerLanguage("python", python);
hljs.registerLanguage("xml", xml);
hljs.registerLanguage("sql", sql);

window.hljs = hljs;
