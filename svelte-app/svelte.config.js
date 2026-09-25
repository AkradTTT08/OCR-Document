/** @type {import("@sveltejs/vite-plugin-svelte").SvelteConfig} */
export default {
  onwarn: (warning, handler) => {
    // Suppress accessibility (a11y) and unused CSS selector warnings in IDE and build
    if (warning.code.startsWith('a11y_') || warning.code.startsWith('a11y-') || warning.code.startsWith('css_unused_')) return;
    handler(warning);
  }
};

