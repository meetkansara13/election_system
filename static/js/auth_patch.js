/**
 * Add this <script> block to the TOP of templates/dashboard/index.html
 * inside the <head> tag — before any other scripts.
 *
 * It:
 *   1. Redirects to /login/ if no token found
 *   2. Patches window.fetch to auto-attach Authorization header
 *   3. Shows logged-in user's name in the navbar
 *   4. Handles 401 → auto logout + redirect
 */

(function () {
  const token = localStorage.getItem('auth_token');
  const user = JSON.parse(localStorage.getItem('auth_user') || 'null');

  // Not logged in → go to login page
  if (!token) {
    window.location.href = '/login/';
    return;
  }

  // Patch fetch to always send token
  const _fetch = window.fetch;
  window.fetch = function (url, opts = {}) {
    opts.headers = Object.assign({
      'Authorization': 'Token ' + token,
      'Content-Type': 'application/json',
    }, opts.headers || {});
    return _fetch(url, opts).then(res => {
      if (res.status === 401) {
        localStorage.removeItem('auth_token');
        localStorage.removeItem('auth_user');
        window.location.href = '/login/';
      }
      return res;
    });
  };

  // Show user info once DOM is ready
  document.addEventListener('DOMContentLoaded', function () {
    const el = document.getElementById('nav-user');
    if (el && user) el.textContent = user.full_name || user.email;
  });
})();