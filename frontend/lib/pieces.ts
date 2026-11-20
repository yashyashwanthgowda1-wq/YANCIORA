/**
 * Display helpers for token pieces from POST /api/tokenize (include_pieces).
 * The backend decodes each byte-level token on its own, so a token holding part of a multi-byte
 * character shows U+FFFD. Those are byte fragments of Indic characters, not errors.
 */

export type PieceKind = "text" | "space" | "fragment";

export interface DisplayPiece {
  index: number;
  raw: string;
  display: string;
  kind: PieceKind;
}

const REPLACEMENT = "�";

export function classifyPiece(raw: string): PieceKind {
  if (raw.includes(REPLACEMENT)) return "fragment";
  if (raw.trim() === "") return "space";
  return "text";
}

/** Makes whitespace visible: space → "·", newline → "↵", tab → "→". */
export function visiblePiece(raw: string): string {
  return raw.replace(/ /g, "·").replace(/\n/g, "↵").replace(/\t/g, "→").replace(/\r/g, "");
}

export function toDisplayPieces(pieces: string[]): DisplayPiece[] {
  return pieces.map((raw, index) => ({ index, raw, display: visiblePiece(raw) || "∅", kind: classifyPiece(raw) }));
}

export interface PieceStats {
  total: number;
  fragments: number;
  whitespace: number;
  /** share of tokens that are byte fragments, 0..1 */
  fragmentShare: number;
}

export function pieceStats(pieces: string[]): PieceStats {
  let fragments = 0;
  let whitespace = 0;
  for (const p of pieces) {
    const k = classifyPiece(p);
    if (k === "fragment") fragments++;
    else if (k === "space") whitespace++;
  }
  return { total: pieces.length, fragments, whitespace, fragmentShare: pieces.length ? fragments / pieces.length : 0 };
}
