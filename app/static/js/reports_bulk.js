'use strict';

(function () {
  var container = document.getElementById('bulk-actions');
  if (!container) return;

  var selectAll = document.getElementById('select-all-reports');
  var checkboxes = Array.prototype.slice.call(document.querySelectorAll('.report-checkbox'));
  var printBtn = document.getElementById('bulk-print-btn');
  var downloadBtn = document.getElementById('bulk-download-btn');
  var countLabel = document.getElementById('bulk-count');
  var printUrl = container.dataset.bulkPrintUrl;
  var downloadUrl = container.dataset.bulkDownloadUrl;

  function selectedIds() {
    return checkboxes.filter(function (c) { return c.checked; }).map(function (c) { return c.value; });
  }

  function refresh() {
    var ids = selectedIds();
    countLabel.textContent = ids.length + ' selected';
    printBtn.disabled = ids.length === 0;
    downloadBtn.disabled = ids.length === 0;
    if (selectAll) {
      selectAll.checked = ids.length > 0 && ids.length === checkboxes.length;
    }
  }

  if (selectAll) {
    selectAll.addEventListener('change', function () {
      checkboxes.forEach(function (c) { c.checked = selectAll.checked; });
      refresh();
    });
  }
  checkboxes.forEach(function (c) { c.addEventListener('change', refresh); });

  printBtn.addEventListener('click', function () {
    var ids = selectedIds();
    if (!ids.length) return;
    window.open(printUrl + '?ids=' + ids.join(','), '_blank');
  });
  downloadBtn.addEventListener('click', function () {
    var ids = selectedIds();
    if (!ids.length) return;
    window.location.href = downloadUrl + '?ids=' + ids.join(',');
  });

  refresh();
})();
