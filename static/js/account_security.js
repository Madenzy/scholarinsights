'use strict';

(function () {
  const statusEl = document.getElementById('mfa-status');
  const choiceEl = document.getElementById('mfa-enroll-choice');
  const totpSetupEl = document.getElementById('mfa-totp-setup');
  const backupCodesEl = document.getElementById('mfa-backup-codes');
  const backupCodesList = document.getElementById('backup-codes-list');
  const disableEl = document.getElementById('mfa-disable');
  const errorEl = document.getElementById('mfa-error');

  function showError(message) {
    errorEl.textContent = message;
    errorEl.hidden = false;
  }

  function hideAll() {
    choiceEl.hidden = true;
    totpSetupEl.hidden = true;
    disableEl.hidden = true;
    errorEl.hidden = true;
  }

  function getCookie(name) {
    const match = document.cookie.match(new RegExp('(?:^|; )' + name + '=([^;]*)'));
    return match ? decodeURIComponent(match[1]) : '';
  }

  async function api(path, body) {
    const res = await fetch(path, {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCookie('csrf_token') },
      body: JSON.stringify(body || {}),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.error || 'Something went wrong.');
    return data;
  }

  function renderBackupCodes(codes) {
    backupCodesList.innerHTML = '';
    codes.forEach(function (code) {
      const li = document.createElement('li');
      li.textContent = code;
      backupCodesList.appendChild(li);
    });
    backupCodesEl.hidden = false;
  }

  async function refreshStatus() {
    hideAll();
    backupCodesEl.hidden = true;
    const res = await fetch('/api/auth/mfa/status', { credentials: 'include' });
    const data = await res.json();
    if (data.enabled) {
      statusEl.textContent = 'Two-factor authentication is ON (' + (data.method === 'totp' ? 'authenticator app' : 'email codes') + ').';
      disableEl.hidden = false;
    } else {
      statusEl.textContent = 'Two-factor authentication is OFF.';
      choiceEl.hidden = false;
    }
  }

  document.getElementById('start-totp').addEventListener('click', async function () {
    try {
      const data = await api('/api/auth/mfa/enroll/totp');
      hideAll();
      document.getElementById('totp-qr').src = data.qr_data_uri;
      document.getElementById('totp-secret').textContent = data.secret;
      totpSetupEl.hidden = false;
    } catch (e) { showError(e.message); }
  });

  document.getElementById('confirm-totp').addEventListener('click', async function () {
    try {
      const code = document.getElementById('totp-confirm-code').value;
      const data = await api('/api/auth/mfa/enroll/totp/confirm', { code: code });
      hideAll();
      renderBackupCodes(data.backup_codes);
      await refreshStatus();
      backupCodesEl.hidden = false;
    } catch (e) { showError(e.message); }
  });

  document.getElementById('start-email').addEventListener('click', async function () {
    try {
      const data = await api('/api/auth/mfa/enroll/email');
      hideAll();
      renderBackupCodes(data.backup_codes);
      await refreshStatus();
      backupCodesEl.hidden = false;
    } catch (e) { showError(e.message); }
  });

  document.getElementById('disable-mfa').addEventListener('click', async function () {
    try {
      const password = document.getElementById('disable-password').value;
      await api('/api/auth/mfa/disable', { password: password });
      await refreshStatus();
    } catch (e) { showError(e.message); }
  });

  refreshStatus();
})();
