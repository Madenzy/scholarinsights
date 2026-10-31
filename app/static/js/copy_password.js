'use strict';

(function () {
  var btn = document.getElementById('copyPasswordBtn');
  var input = document.getElementById('generatedPassword');
  if (!btn || !input) return;
  btn.addEventListener('click', function () {
    navigator.clipboard.writeText(input.value).then(function () {
      var original = btn.textContent;
      btn.textContent = 'Copied';
      setTimeout(function () { btn.textContent = original; }, 1500);
    }).catch(function () {
      input.select();
    });
  });
})();
