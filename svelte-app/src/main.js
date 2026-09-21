// URL Sanitizer: Ensure any hardcoded backend localhost:5000 calls are rewritten to relative paths
const _nativeFetch = window.fetch;
window.fetch = function (input, init) {
  if (typeof input === 'string') {
    input = input.replace(/^http:\/\/(localhost|127\.0\.0\.1):5000/i, '');
  } else if (input instanceof Request) {
    const cleanUrl = input.url.replace(/^http:\/\/(localhost|127\.0\.0\.1):5000/i, '');
    input = new Request(cleanUrl, input);
  }
  return _nativeFetch(input, init);
};

import { mount } from 'svelte'
import './app.css'
import App from './App.svelte'

const app = mount(App, {
  target: document.getElementById('app'),
})

export default app
