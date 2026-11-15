/** The legal pages and their URL segment (same in both languages, like /search). */
export type LegalPageKey = "terms" | "privacy" | "rega";

export const LEGAL_SLUGS: Record<LegalPageKey, string> = {
  terms: "terms",
  privacy: "privacy",
  rega: "rega-licence",
};
