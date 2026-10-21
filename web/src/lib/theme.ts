// Theme preference: "auto" follows the device; "light"/"dark" override it. Stored per browser.
// This is the only thing the site ever writes to storage (pasted text never is).

export type ThemePref = "auto" | "light" | "dark";

export const THEME_KEY = "meeting:theme";
const ORDER: ThemePref[] = ["auto", "light", "dark"];

export function parseTheme(raw: string | null | undefined): ThemePref {
  return raw === "light" || raw === "dark" ? raw : "auto";
}

/** The toggle cycles Auto → Light → Dark → Auto. */
export function nextTheme(t: ThemePref): ThemePref {
  return ORDER[(ORDER.indexOf(t) + 1) % ORDER.length]!;
}

export function themeLabel(t: ThemePref): string {
  return t === "auto" ? "Auto" : t === "light" ? "Light" : "Dark";
}
