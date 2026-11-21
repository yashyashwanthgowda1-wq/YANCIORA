import { existsSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { NAV } from "@/lib/api/planned";

const appDir = join(__dirname, "..", "app");
const items = NAV.flatMap((g) => g.items);

describe("navigation", () => {
  it("does not show Linguistic Review in any menu", () => {
    expect(items.some((i) => i.href === "/review" || /linguistic review/i.test(i.label))).toBe(false);
  });

  it("keeps the Research Dashboard in the Research menu", () => {
    const research = NAV.find((g) => g.label === "Research");
    expect(research?.items.map((i) => i.href)).toEqual(["/research"]);
  });

  it("has no Linguistic Review page that could be opened directly", () => {
    expect(existsSync(join(appDir, "review"))).toBe(false);
  });

  it("shows no API endpoint text in menu or home-card descriptions", () => {
    for (const i of items) expect(i.note, i.href).not.toMatch(/\/api\/|\b(GET|POST) \//);
  });

  it("points every link at an existing page", () => {
    for (const i of items) {
      const page = i.href === "/" ? join(appDir, "page.tsx") : join(appDir, i.href.slice(1), "page.tsx");
      expect(existsSync(page), `${i.href} has no page`).toBe(true);
    }
  });
});
