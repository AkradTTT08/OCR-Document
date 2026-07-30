import { mount } from 'svelte'
import './app.css'
import App from './App.svelte'

// --- Auth Interceptor ---
window.originalFetch = window.fetch;
window.fetch = async (resource, config) => {
  const token = localStorage.getItem('auth_token');
  
  // If this is an API call (and not login), inject token
  if (typeof resource === 'string' && resource.includes('/api/') && !resource.includes('/api/login')) {
    config = config || {};
    config.headers = config.headers || {};
    
    if (config.headers instanceof Headers) {
      config.headers.set('Authorization', `Bearer ${token}`);
    } else {
      config.headers['Authorization'] = `Bearer ${token}`;
    }
  }
  
  try {
    const response = await window.originalFetch(resource, config);
    // If successfully interacted with API, this implies activity
    if (response.ok && resource.includes('/api/')) {
        // Trigger activity update (sliding session)
        localStorage.setItem('last_activity', Date.now().toString());
    }
    
    if (response.status === 401 && resource.includes('/api/')) {
        window.dispatchEvent(new Event('auth_expired'));
    }
    return response;
  } catch (err) {
    throw err;
  }
};
// -----------------------

const app = mount(App, {
  target: document.getElementById('app'),
})

export default app
