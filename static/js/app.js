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
