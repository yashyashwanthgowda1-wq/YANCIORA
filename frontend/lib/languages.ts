import type { CountStatus, LanguageCode, Script, VariantType } from "./api/types";

export interface LanguageMeta {
  code: LanguageCode;
  name: string;
  native: string;
  nativeScript: Script;
}

export const LANGUAGES: Record<LanguageCode, LanguageMeta> = {
  kn: { code: "kn", name: "Kannada", native: "ಕನ್ನಡ", nativeScript: "Knda" },
  hi: { code: "hi", name: "Hindi", native: "हिन्दी", nativeScript: "Deva" },
  ta: { code: "ta", name: "Tamil", native: "தமிழ்", nativeScript: "Taml" },
  te: { code: "te", name: "Telugu", native: "తెలుగు", nativeScript: "Telu" },
  en: { code: "en", name: "English", native: "English", nativeScript: "Latn" },
};

export const SCRIPT_LABELS: Record<Script, string> = {
  Knda: "Kannada script",
  Deva: "Devanagari",
  Taml: "Tamil script",
  Telu: "Telugu script",
  Latn: "Latin (Roman)",
  mixed: "Mixed scripts",
};

export const VARIANT_LABELS: Record<VariantType, string> = {
  original: "Original",
  translation: "Translation",
  transliteration: "Transliteration",
  code_mixed: "Code-mixed",
  paraphrase: "Paraphrase",
};

export const STATUS_LABELS: Record<CountStatus, { label: string; description: string }> = {
  exact: { label: "Exact", description: "The named tokenizer ran on this text. This is a tokenizer count, not provider-billed usage." },
  estimate: { label: "Estimate", description: "An approximation. The target model's exact tokenizer was not used." },
  provider_reported: { label: "Provider reported", description: "Usage as reported by the model provider's API." },
  research: { label: "Research", description: "Experimental REDUTAX tokenizer. A research result only; it cannot change hosted-model billing." },
  mock: { label: "Mock", description: "Placeholder data for layout only. Not a real measurement." },
  unsupported: { label: "Unsupported", description: "No count is available for this tokenizer or model." },
};

export function languageLabel(code: LanguageCode | null | undefined): string {
  return code ? LANGUAGES[code].name : "Unknown";
}

/** BCP-47 tag for rendering a text sample; Romanized Indic text gets e.g. "kn-Latn". */
export function langTag(language: LanguageCode | null | undefined, script?: Script | null): string | undefined {
  if (!language) return undefined;
  if (script && script !== "mixed" && script !== LANGUAGES[language].nativeScript) return `${language}-${script}`;
  return language;
}
