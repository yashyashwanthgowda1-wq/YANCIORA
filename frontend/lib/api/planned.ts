/**
 * Feature availability, derived from the backend source on 2026-11-20 (see docs/FRONTEND_INSPECTION.md).
 * Planned endpoints are listed by NAME ONLY — no request/response types are invented for them.
 * When the backend implements one, add its types to types.ts (mirroring schemas.py) and flip `availability`.
 */

export type Availability = "live" | "partial" | "planned";

export interface PlannedEndpoint {
  method: "GET" | "POST";
  path: string;
  purpose: string;
  phase: string;
}

export const PLANNED_ENDPOINTS = {
  optimize: { method: "POST", path: "/api/optimize", purpose: "Generate, score and select an optimized candidate", phase: "Phase 3" },
  evaluateMeaning: { method: "POST", path: "/api/evaluate-meaning", purpose: "Semantic and critical-detail preservation", phase: "Phase 3" },
  costEstimate: { method: "POST", path: "/api/cost/estimate", purpose: "Cost from a versioned price record", phase: "Phase 4" },
  modelsRecommend: { method: "POST", path: "/api/models/recommend", purpose: "Eligible models and selection explanation", phase: "Phase 4" },
  chat: { method: "POST", path: "/api/chat", purpose: "Chat turn with Auto or Manual model selection", phase: "Phase 4" },
  vapiWebhook: { method: "POST", path: "/api/vapi/webhook", purpose: "Authenticated Vapi events and tool calls", phase: "Phase 5" },
  vapiAnswer: { method: "POST", path: "/api/vapi/optimize-and-answer", purpose: "Transcript → optimize → route → spoken reply", phase: "Phase 5" },
  benchmarksRun: { method: "POST", path: "/api/benchmarks/run", purpose: "Start an authorized benchmark job", phase: "Phase 2+" },
} as const satisfies Record<string, PlannedEndpoint>;

export interface NavItem {
  href: string;
  label: string;
  availability: Availability;
  note: string;
}

export interface NavGroup {
  label: string;
  items: NavItem[];
}

export const NAV: NavGroup[] = [
  { label: "Overview", items: [
    { href: "/", label: "Home", availability: "live", note: "System status and project overview" },
  ] },
  { label: "Measure", items: [
    { href: "/counter", label: "Token Counter", availability: "live", note: "Count tokens and words with a named tokenizer" },
    { href: "/compare", label: "Language Comparison", availability: "live", note: "Compare the same meaning across languages and scripts" },
  ] },
  { label: "Reduce", items: [
    { href: "/optimize", label: "Prompt Optimizer", availability: "live", note: "Shorten a prompt while keeping its important details" },
    { href: "/cost", label: "Cost Calculator", availability: "live", note: "Estimate cost from registry or user-entered prices" },
    { href: "/models", label: "Model Recommendation", availability: "live", note: "Rule-based model suggestions from configured model data" },
  ] },
  { label: "Assist", items: [
    { href: "/chat", label: "AI Chat", availability: "live", note: "Analyse a prompt; sending needs a configured LLM" },
    { href: "/voice", label: "Voice & Calls", availability: "live", note: "Turn speech into an optimized prompt; connect telephone calls in Vapi" },
  ] },
  { label: "Research", items: [
    { href: "/research", label: "Research Dashboard", availability: "live", note: "Stored tokenizer benchmark runs and results" },
    // The Linguistic Review page was removed from the frontend. The backend
    // /api/linguistics/* endpoints and the review datasets are unchanged.
  ] },
  { label: "System", items: [
    { href: "/settings", label: "Settings & Privacy", availability: "live", note: "Preferences stored in this browser" },
  ] },
];
