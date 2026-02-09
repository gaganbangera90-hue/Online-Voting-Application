function submitVoteViaForm(form, candidateId) {
  // ensure candidate radio is set and submit the form normally (server-side handles validation)
  const candidateInput = form.querySelector('input[name="candidate"][value="' + candidateId + '"]');
  if (candidateInput) candidateInput.checked = true;
  // disable submit buttons to prevent double submission
  const submits = form.querySelectorAll('button[type="submit"], input[type="submit"]');
  submits.forEach(s => { s.disabled = true; s.classList.add('disabled'); });
  form.submit();
}

document.addEventListener('DOMContentLoaded', function () {
  const form = document.getElementById('vote-form');
  if (!form) return;
  const modalEl = document.getElementById('voteConfirmModal');
  const confirmBtn = document.getElementById('confirm-vote-btn');
  const bsModal = modalEl ? new bootstrap.Modal(modalEl, {}) : null;
  form.addEventListener('submit', function (e) {
    e.preventDefault();
    const fd = new FormData(form);
    const candidate = fd.get('candidate');
    const electionId = form.dataset.electionId;
    if (!candidate) { alert('Select a candidate'); return; }
    const radio = form.querySelector('input[name="candidate"][value="' + candidate + '"]');
    const candidateName = radio ? radio.dataset.name : '';
    if (bsModal && modalEl) {
      modalEl.querySelector('.candidate-name').textContent = candidateName || 'the selected candidate';
      // set confirm handler: submit the enclosing form normally
      confirmBtn.onclick = function () { submitVoteViaForm(form, candidate); bsModal.hide(); };
      bsModal.show();
    } else {
      submitVoteViaForm(form, candidate);
    }
  });
  // keyboard navigation for candidate radio list
  try {
    const radios = Array.from(document.querySelectorAll('form#vote-form input[name="candidate"]'));
    if (radios.length) {
      radios.forEach(r => r.addEventListener('keydown', function (ev) {
        const idx = radios.indexOf(this);
        if (ev.key === 'ArrowDown' || ev.key === 'ArrowRight') {
          ev.preventDefault();
          const next = radios[(idx + 1) % radios.length];
          next.focus();
          next.checked = true;
        } else if (ev.key === 'ArrowUp' || ev.key === 'ArrowLeft') {
          ev.preventDefault();
          const prev = radios[(idx - 1 + radios.length) % radios.length];
          prev.focus();
          prev.checked = true;
        }
      }));
    }
  } catch (err) {
    /* ignore */
  }

  // Global behavior: auto-dismiss success/info alerts after 6s
  try {
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(a => {
      if (a.classList.contains('alert-success') || a.classList.contains('alert-info')) {
        setTimeout(() => {
          try { bootstrap.Alert.getOrCreateInstance(a).close(); } catch(e){}
        }, 6000);
      }
    });
  } catch (err) {}

  // Global: disable submit buttons on normal form submit to prevent double submits
  document.addEventListener('submit', function (e) {
    // delay to allow forms that call preventDefault to cancel
    setTimeout(() => {
      if (e.defaultPrevented) return;
      const form = e.target;
      if (!(form instanceof HTMLFormElement)) return;
      const submits = form.querySelectorAll('button[type="submit"], input[type="submit"]');
      submits.forEach(s => { s.disabled = true; s.classList.add('disabled'); });
    }, 0);
  });

  // Create election form client-side validation (UX only)
  const createForm = document.getElementById('create-election-form');
  if (createForm) {
    createForm.addEventListener('submit', function (e) {
      const title = (createForm.querySelector('input[name="title"]') || {}).value || '';
      const candidates = (createForm.querySelector('input[name="candidates"]') || {}).value || '';
      // basic UX validation
      if (!title.trim()) {
        e.preventDefault();
        alert('Title is required');
        return false;
      }
      if (!candidates.trim()) {
        e.preventDefault();
        alert('Please provide at least one candidate (comma-separated)');
        return false;
      }
      // ensure at least one non-empty candidate
      const list = candidates.split(',').map(s=>s.trim()).filter(Boolean);
      if (list.length === 0) {
        e.preventDefault();
        alert('Please provide at least one candidate');
        return false;
      }
      // allow submit; global handler will disable buttons
    });
  }
});
