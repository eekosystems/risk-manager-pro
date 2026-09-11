/**
 * Fold model text onto the character set of jsPDF's built-in fonts.
 *
 * The PDF export uses the standard Helvetica, which is WinAnsi-encoded. Any
 * character outside that set makes jsPDF switch the run to a two-byte
 * encoding the font cannot draw, and the words around it collapse into
 * overlapping glyphs — "wrong‑turn taxiing" (non-breaking hyphen) printed as
 * "ttaxiin g" and was reported as a typo. The model writes those characters
 * routinely: non-breaking hyphens, thin spaces, arrows, check marks.
 *
 * Characters WinAnsi does have (en/em dashes, curly quotes, bullets, ×, °,
 * ellipsis) pass through unchanged.
 */

const REPLACEMENTS: ReadonlyMap<string, string> = new Map([
  // Hyphens and minus signs that are not the ASCII hyphen.
  ["\u2010", "-"], // hyphen
  ["\u2011", "-"], // non-breaking hyphen
  ["\u2012", "-"], // figure dash
  ["\u2043", "-"], // hyphen bullet
  ["\u2212", "-"], // minus sign
  // Typographic spaces.
  ["\u00A0", " "],
  ["\u2002", " "],
  ["\u2003", " "],
  ["\u2004", " "],
  ["\u2005", " "],
  ["\u2006", " "],
  ["\u2007", " "],
  ["\u2008", " "],
  ["\u2009", " "],
  ["\u200A", " "],
  ["\u202F", " "],
  ["\u205F", " "],
  ["\u3000", " "],
  // Invisible formatting characters.
  ["\u200B", ""],
  ["\u200C", ""],
  ["\u200D", ""],
  ["\u2060", ""],
  ["\uFEFF", ""],
  // Arrows and comparison symbols.
  ["\u2192", "->"], // →
  ["\u2190", "<-"], // ←
  ["\u2194", "<->"], // ↔
  ["\u21D2", "=>"], // ⇒
  ["\u2264", "<="], // ≤
  ["\u2265", ">="], // ≥
  ["\u2260", "!="], // ≠
  ["\u2248", "~"], // ≈
  // Check marks and crosses.
  ["\u2713", "[x]"], // ✓
  ["\u2714", "[x]"], // ✔
  ["\u2717", "x"], // ✗
  ["\u2718", "x"], // ✘
  // Bullet variants, folded onto the bullet WinAnsi has.
  ["\u25E6", "•"], // ◦
  ["\u25AA", "•"], // ▪
  ["\u25A0", "•"], // ■
  ["\u25CF", "•"], // ●
  ["\u2023", "•"], // ‣
  // Primes.
  ["\u2032", "'"], // ′
  ["\u2033", '"'], // ″
]);

// The characters WinAnsi places at 0x80-0x9F, beyond Latin-1.
const WINANSI_EXTRA = new Set([
  "\u20AC", // €
  "\u201A", // ‚
  "\u0192", // ƒ
  "\u201E", // „
  "\u2026", // …
  "\u2020", // †
  "\u2021", // ‡
  "\u02C6", // ˆ
  "\u2030", // ‰
  "\u0160", // Š
  "\u2039", // ‹
  "\u0152", // Œ
  "\u017D", // Ž
  "\u2018", // ‘
  "\u2019", // ’
  "\u201C", // “
  "\u201D", // ”
  "\u2022", // •
  "\u2013", // –
  "\u2014", // —
  "\u02DC", // ˜
  "\u2122", // ™
  "\u0161", // š
  "\u203A", // ›
  "\u0153", // œ
  "\u017E", // ž
  "\u0178", // Ÿ
]);

const COMBINING_MARKS_RE = /[\u0300-\u036F]/g;

function isEncodable(ch: string): boolean {
  const code = ch.codePointAt(0) ?? 0;
  return (
    (code >= 0x20 && code <= 0x7e) ||
    (code >= 0xa0 && code <= 0xff) ||
    ch === "\n" ||
    ch === "\r" ||
    ch === "\t" ||
    WINANSI_EXTRA.has(ch)
  );
}

function isPictograph(code: number): boolean {
  return code >= 0x1f000 || (code >= 0x2600 && code <= 0x27bf);
}

export function toStandardFontText(text: string): string {
  let out = "";
  for (const ch of text) {
    const mapped = REPLACEMENTS.get(ch);
    if (mapped !== undefined) {
      out += mapped;
      continue;
    }
    if (isEncodable(ch)) {
      out += ch;
      continue;
    }
    // Accented letters outside Latin-1 keep their base letter.
    const folded = ch.normalize("NFKD").replace(COMBINING_MARKS_RE, "");
    if (folded !== ch && [...folded].every(isEncodable)) {
      out += folded;
      continue;
    }
    // Emoji and pictographs carry no meaning the PDF needs; anything else
    // unknown is shown as "?" rather than silently dropped.
    out += isPictograph(ch.codePointAt(0) ?? 0) ? "" : "?";
  }
  return out;
}
