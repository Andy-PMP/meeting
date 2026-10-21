import { describe, expect, it } from "vitest";
import { nextTheme, parseTheme, themeLabel } from "./theme";

describe("theme preference", () => {
  it("cycles auto → light → dark → auto", () => {
    expect(nextTheme("auto")).toBe("light");
    expect(nextTheme("light")).toBe("dark");
    expect(nextTheme("dark")).toBe("auto");
  });

  it("treats missing or unknown stored values as auto", () => {
    expect(parseTheme(null)).toBe("auto");
    expect(parseTheme(undefined)).toBe("auto");
    expect(parseTheme("purple")).toBe("auto");
    expect(parseTheme("dark")).toBe("dark");
  });

  it("labels each state", () => {
    expect(["auto", "light", "dark"].map((t) => themeLabel(parseTheme(t)))).toEqual([
      "Auto",
      "Light",
      "Dark",
    ]);
  });
});
