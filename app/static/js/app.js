'use strict';

// Auto-dismiss alerts after 5 s
document.querySelectorAll('.alert').forEach(function (el) {
  setTimeout(function () {
    el.style.transition = 'opacity .4s';
    el.style.opacity = '0';
    setTimeout(function () { el.remove(); }, 400);
  }, 5000);
});

// Confirm delete forms
document.querySelectorAll('form[data-confirm]').forEach(function (form) {
  form.addEventListener('submit', function (e) {
    var msg = form.getAttribute('data-confirm') || 'Are you sure?';
    if (!window.confirm(msg)) e.preventDefault();
  });
});

// Mobile sidebar toggle
var toggle = document.getElementById('sidebarToggle');
var sidebar = document.querySelector('.sidebar');
if (toggle && sidebar) {
  toggle.addEventListener('click', function () {
    sidebar.classList.toggle('open');
  });
  document.addEventListener('click', function (e) {
    if (!sidebar.contains(e.target) && e.target !== toggle) {
      sidebar.classList.remove('open');
    }
  });
}

// Show/hide password toggles
(function () {
  var EYE = '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>';
  var EYE_OFF = '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17.94 17.94A10.94 10.94 0 0 1 12 20c-7 0-11-8-11-8a21.8 21.8 0 0 1 5.06-6.06M9.9 4.24A10.94 10.94 0 0 1 12 4c7 0 11 8 11 8a21.8 21.8 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/></svg>';

  document.querySelectorAll('.password-toggle').forEach(function (btn) {
    var input = document.getElementById(btn.getAttribute('data-target'));
    if (!input) return;
    btn.innerHTML = EYE;
    btn.setAttribute('aria-label', 'Show password');
    btn.addEventListener('click', function () {
      var show = input.type === 'password';
      input.type = show ? 'text' : 'password';
      btn.innerHTML = show ? EYE_OFF : EYE;
      btn.setAttribute('aria-label', show ? 'Hide password' : 'Show password');
    });
  });
})();

// Mark active sidebar link
var path = window.location.pathname;
document.querySelectorAll('.sidebar__link').forEach(function (link) {
  var href = link.getAttribute('href');
  if (href && href !== '/' && path.startsWith(href)) {
    link.classList.add('active');
  } else if (href === '/' && path === '/') {
    link.classList.add('active');
  }
});
