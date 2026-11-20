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
    { href: "/counter", label: "Token Counter", availability: "live", note: "POST /api/tokenize" },
    { href: "/compare", label: "Language Comparison", availability: "live", note: "POST /api/compare-languages · /api/script-variants" },
  ] },
  { label: "Reduce", items: [
    { href: "/optimize", label: "Prompt Optimizer", availability: "live", note: "POST /api/optimize · /api/meaning-check · /api/critical-details (rules-based)" },
    { href: "/cost", label: "Cost Calculator", availability: "partial", note: "Formula with prices you enter; no price registry yet" },
    { href: "/models", label: "Model Recommendation", availability: "planned", note: "Model registry arrives in Phase 4" },
  ] },
  { label: "Assist", items: [
    { href: "/chat", label: "AI Chat", availability: "planned", note: "POST /api/chat arrives in Phase 4" },
    { href: "/voice", label: "Voice & Calls", availability: "partial", note: "Browser voice input; Vapi arrives in Phase 5" },
  ] },
  { label: "Research", items: [
    { href: "/research", label: "Research Dashboard", availability: "live", note: "GET /api/benchmarks" },
  ] },
  { label: "System", items: [
    { href: "/settings", label: "Settings & Privacy", availability: "live", note: "Preferences stored in this browser" },
  ] },
];
