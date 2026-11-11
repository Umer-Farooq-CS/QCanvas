import { Fragment } from "react";

type Lang = "python" | "qasm";

const KEYWORDS: Record<Lang, Set<string>> = {
  python: new Set([
    "import", "from", "as", "def", "return", "for", "in", "if", "else",
    "elif", "while", "with", "class", "None", "True", "False", "and", "or", "not",
  ]),
  qasm: new Set(["OPENQASM", "include", "qubit", "bit", "measure", "reset", "gate", "if", "for"]),
};

// comment | string | decorator | number | identifier | anything else
const TOKEN = /(#[^\n]*|\/\/[^\n]*)|("[^"\n]*"|'[^'\n]*')|(@[\w.]+)|(\b\d+(?:\.\d+)?\b)|([A-Za-z_]\w*)|([\s\S])/g;

/** Tiny build-time highlighter for static samples (no client JS). */
function highlight(code: string, lang: Lang) {
  const out: React.ReactNode[] = [];
  let plain = "";
  const flush = () => {
    if (plain) out.push(plain);
    plain = "";
  };
  for (const m of Array.from(code.matchAll(TOKEN))) {
    const [text, comment, str, deco, num, ident] = m;
    let cls: string | null = null;
    if (comment) cls = "qc-tok-c";
    else if (str) cls = "qc-tok-s";
    else if (deco) cls = "qc-tok-k";
    else if (num) cls = "qc-tok-n";
    else if (ident && KEYWORDS[lang].has(ident)) cls = "qc-tok-k";
    if (cls) {
      flush();
      out.push(
        <span key={out.length} className={cls}>
          {text}
        </span>,
      );
    } else {
      plain += text;
    }
  }
  flush();
  return out;
}

export default function CodeSample({
  code,
  lang = "python",
  className = "",
  plain = false,
}: {
  code: string;
  lang?: Lang;
  className?: string;
  /** Transparent background, for samples that sit inside a card. */
  plain?: boolean;
}) {
  return (
    <pre
      className={`qc-code ${plain ? "qc-code--plain" : ""} overflow-x-auto text-[12.5px] leading-[1.7] ${className}`}
      tabIndex={0}
    >
      <code>
        {highlight(code, lang).map((node, i) => (
          <Fragment key={i}>{node}</Fragment>
        ))}
      </code>
    </pre>
  );
}
