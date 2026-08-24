/**
 * Strip common markdown syntax so text-to-speech doesn't read punctuation
 * literally (e.g. "**bold**" -> "asterisk asterisk bold asterisk asterisk").
 * Not a full markdown parser — just enough to make spoken output natural.
 */
export function stripMarkdown(text: string): string {
  return text
    // fenced code blocks — drop the fence markers, keep the content
    .replace(/```[\w-]*\n?([\s\S]*?)```/g, "$1")
    // inline code
    .replace(/`([^`]+)`/g, "$1")
    // images ![alt](url) -> alt
    .replace(/!\[([^\]]*)\]\([^)]+\)/g, "$1")
    // links [text](url) -> text
    .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1")
    // bold + italic: ***x***, ___x___, **x**, __x__, *x*, _x_
    .replace(/\*\*\*([^*]+)\*\*\*/g, "$1")
    .replace(/___([^_]+)___/g, "$1")
    .replace(/\*\*([^*]+)\*\*/g, "$1")
    .replace(/__([^_]+)__/g, "$1")
    .replace(/\*([^*]+)\*/g, "$1")
    .replace(/_([^_]+)_/g, "$1")
    // strikethrough
    .replace(/~~([^~]+)~~/g, "$1")
    // headings
    .replace(/^#{1,6}\s+/gm, "")
    // blockquotes
    .replace(/^>\s?/gm, "")
    // list markers (-, *, +, 1.)
    .replace(/^\s*[-*+]\s+/gm, "")
    .replace(/^\s*\d+\.\s+/gm, "")
    // horizontal rules
    .replace(/^\s*[-*_]{3,}\s*$/gm, "")
    // leftover stray markdown characters
    .replace(/[*_`#]/g, "")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}
