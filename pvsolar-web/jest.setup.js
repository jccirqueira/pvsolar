/**
 * Setup global do Jest (jsdom).
 * Polyfills de APIs de navegador ausentes no jsdom.
 */

// window.matchMedia nao existe no jsdom — usado pelo ThemeContext.
if (typeof window !== 'undefined' && !window.matchMedia) {
  window.matchMedia = function (query) {
    return {
      matches: false,
      media: query,
      onchange: null,
      addListener: function () {},
      removeListener: function () {},
      addEventListener: function () {},
      removeEventListener: function () {},
      dispatchEvent: function () {
        return false;
      },
    };
  };
}
