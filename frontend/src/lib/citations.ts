/**
 * Link every "Source N" inside a citation bracket in model markdown.
 *
 * The model writes "[Source 2]" and, more often, grouped forms —
 * "[Source 1, Source 2, Source 7]", "[Sources 3 and 5]" — and every number in
 * the group must resolve, not only a lone one. The brackets stay as literal
 * text around the links so the output reads exactly as written; the renderer
 * turns each "#citation-N" anchor into the citation chip.
 */
const CITATION_GROUP_RE =
  /\[(Sources?\s+\d+(?:\s*(?:,|;|&|and|[-–])\s*(?:Sources?\s+)?\d+)*)\]/g;
const CITATION_ITEM_RE = /(?:Source\s+)?(\d+)/g;

export function preprocessCitations(content: string): string {
  return content.replace(CITATION_GROUP_RE, (_group, inner: string) => {
    const linked = inner.replace(
      CITATION_ITEM_RE,
      (item, n: string) => `[${item}](#citation-${n})`,
    );
    return `\\[${linked}\\]`;
  });
}
