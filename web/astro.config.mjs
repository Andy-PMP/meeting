import { defineConfig } from "astro/config";

// Served from the custom subdomain root, so no `base` is needed.
//
// The CSP is the enforcement half of the privacy promise: connect-src 'self' means nothing on
// the page can send data to another origin. Astro emits it as a <meta> tag and hashes every
// inline script/style it renders. 'wasm-unsafe-eval' is for onnxruntime-web (P4); blob: workers
// are what Transformers.js spawns. See TECH_REQUIREMENTS.md §6.
export default defineConfig({
  site: "https://meeting.amandapatricks.com",
  security: {
    csp: {
      directives: [
        "default-src 'self'",
        "connect-src 'self'",
        "img-src 'self' data:",
        "worker-src 'self' blob:",
        "object-src 'none'",
        "base-uri 'self'",
        "form-action 'none'",
      ],
      scriptDirective: { resources: ["'self'", "'wasm-unsafe-eval'"] },
      styleDirective: { resources: ["'self'"] },
    },
  },
});
