/**
 * app.js — Personal Knowledge Base Frontend Application
 *
 * Manages:
 *  - Page routing (Login ↔ Dashboard)
 *  - View routing (Dashboard / Documents / Search)
 *  - Login / Logout
 *  - Document upload (drag-and-drop + click)
 *  - Document listing with loading/empty/error states
 *  - Document deletion with confirmation modal
 *  - Semantic search with ranked result cards
 *  - Session counter for searches
 *  - Responsive sidebar toggle
 */

'use strict';

/* ============================================================================
   STATE
   ============================================================================ */

const state = {
  documents: [],       // cached document list
  searchCount: 0,      // searches performed this session
  deleteTarget: null,  // { doc_id, filename } pending deletion
};

/* ============================================================================
   DOM REFS
   ============================================================================ */

const $ = (id) => document.getElementById(id);

// Pages
const pagLogin    = $('page-login');
const pagDash     = $('page-dashboard');

// Login form
const loginForm   = $('login-form');
const loginUser   = $('login-username');
const loginPass   = $('login-password');
const loginBtn    = $('login-btn');
const loginBtnTxt = $('login-btn-text');
const loginSpinner= $('login-spinner');
const loginErr    = $('login-error');
const loginErrMsg = $('login-error-msg');

// Sidebar & nav
const sidebar         = $('sidebar');
const sidebarOverlay  = $('sidebar-overlay');
const mobileMenuBtn   = $('mobile-menu-btn');
const logoutBtn       = $('logout-btn');
const sidebarUsername = $('sidebar-username');
const navItems        = document.querySelectorAll('.nav-item');
const viewButtons     = document.querySelectorAll('[data-view]');

// Views
const views = {
  dashboard: $('view-dashboard'),
  documents: $('view-documents'),
  search:    $('view-search'),
};

// Dashboard
const statDocs          = $('stat-docs');
const statSearches      = $('stat-searches');
const dashboardDocsList = $('dashboard-docs-list');
const dashSearchInput   = $('dashboard-search-input');
const dashSearchBtn     = $('dashboard-search-btn');

// Documents
const uploadZone        = $('upload-zone');
const fileInput         = $('file-input');
const uploadProgress    = $('upload-progress');
const uploadFilename    = $('upload-filename');
const uploadSuccess     = $('upload-success');
const uploadSuccessMsg  = $('upload-success-msg');
const uploadError       = $('upload-error');
const uploadErrorMsg    = $('upload-error-msg');
const refreshDocsBtn    = $('refresh-docs-btn');
const docsList          = $('docs-list');

// Search
const searchInput       = $('search-input');
const searchBtn         = $('search-btn');
const searchBtnTxt      = $('search-btn-text');
const searchSpinner     = $('search-spinner');
const topKInput         = $('top-k-input');
const searchError       = $('search-error');
const searchErrorMsg    = $('search-error-msg');
const searchEmptyInit   = $('search-empty-initial');
const searchNoResults   = $('search-no-results');
const searchResultsList = $('search-results-list');
const resultsCountLbl   = $('results-count-label');
const resultsQueryLbl   = $('results-query-label');
const noResultsMsg      = $('no-results-msg');

// Modal
const deleteModal       = $('delete-modal');
const deleteDocName     = $('delete-doc-name');
const deleteCancelBtn   = $('delete-cancel-btn');
const deleteConfirmBtn  = $('delete-confirm-btn');
const deleteConfirmTxt  = $('delete-confirm-text');
const deleteSpinner     = $('delete-spinner');

/* ============================================================================
   HELPERS
   ============================================================================ */

/** Show an element (remove hidden class). */
function show(el) { el.classList.remove('hidden'); }

/** Hide an element (add hidden class). */
function hide(el) { el.classList.add('hidden'); }

/** Set error banner message and show it. */
function showError(banner, msgEl, message) {
  msgEl.textContent = message;
  show(banner);
}

/** Hide error banner. */
function hideError(banner) {
  hide(banner);
}

/** Get file extension icon type. */
function fileType(filename) {
  const ext = filename.toLowerCase().split('.').pop();
  if (ext === 'pdf') return 'pdf';
  if (ext === 'md' || ext === 'markdown') return 'md';
  if (ext === 'txt') return 'txt';
  return 'default';
}

/** Map ext to label for icon. */
function fileLabel(filename) {
  const t = fileType(filename);
  return { pdf: 'PDF', md: 'MD', txt: 'TXT', default: 'DOC' }[t];
}

/** Handle global 401 — force logout. */
function handleUnauthorized() {
  clearAuth();
  showLoginPage();
  showError(loginErr, loginErrMsg, 'Your session expired. Please sign in again.');
}

/* ============================================================================
   PAGE ROUTING
   ============================================================================ */

function showLoginPage() {
  pagLogin.classList.remove('hidden');
  pagLogin.classList.add('active');
  pagDash.classList.add('hidden');
  pagDash.classList.remove('active');
}

function showDashboardPage() {
  pagLogin.classList.add('hidden');
  pagLogin.classList.remove('active');
  pagDash.classList.remove('hidden');
  pagDash.classList.add('active');

  // Set username in sidebar
  const username = sessionStorage.getItem('kb_username') || 'User';
  sidebarUsername.textContent = username;

  // Set first letter of avatar
  const avatar = sidebar.querySelector('.user-avatar');
  if (avatar) avatar.textContent = username[0].toUpperCase();

  // Load initial data
  loadDocuments();
  navigateToView('dashboard');
}

/* ============================================================================
   VIEW ROUTING
   ============================================================================ */

function navigateToView(viewName) {
  // Hide all views
  Object.values(views).forEach((v) => {
    v.classList.remove('active');
    v.classList.add('hidden');
  });

  // Activate target view
  const target = views[viewName];
  if (target) {
    target.classList.remove('hidden');
    target.classList.add('active');
  }

  // Update nav items
  navItems.forEach((item) => {
    const isActive = item.dataset.view === viewName;
    item.classList.toggle('active', isActive);
    item.setAttribute('aria-current', isActive ? 'page' : 'false');
  });

  // Close mobile sidebar
  closeMobileSidebar();

  // View-specific actions
  if (viewName === 'documents') {
    loadDocuments();
  }

  if (viewName === 'dashboard') {
    renderDashboardDocs();
    statSearches.textContent = state.searchCount;
  }
}

/* ============================================================================
   MOBILE SIDEBAR
   ============================================================================ */

function openMobileSidebar() {
  sidebar.classList.add('open');
  mobileMenuBtn.setAttribute('aria-expanded', 'true');
  sidebarOverlay.style.opacity = '1';
  sidebarOverlay.style.pointerEvents = 'auto';
}

function closeMobileSidebar() {
  sidebar.classList.remove('open');
  mobileMenuBtn.setAttribute('aria-expanded', 'false');
  sidebarOverlay.style.opacity = '0';
  sidebarOverlay.style.pointerEvents = 'none';
}

/* ============================================================================
   AUTHENTICATION
   ============================================================================ */

async function handleLogin(e) {
  e.preventDefault();
  hideError(loginErr);

  const username = loginUser.value.trim();
  const password = loginPass.value;

  if (!username || !password) {
    showError(loginErr, loginErrMsg, 'Please enter your username and password.');
    return;
  }

  // Loading state
  loginBtnTxt.textContent = 'Signing in...';
  show(loginSpinner);
  loginBtn.disabled = true;

  try {
    await apiLogin(username, password);
    showDashboardPage();
  } catch (err) {
    const msg = err.message || 'Login failed. Please check your credentials.';
    showError(loginErr, loginErrMsg, msg);
  } finally {
    loginBtnTxt.textContent = 'Sign In';
    hide(loginSpinner);
    loginBtn.disabled = false;
  }
}

function handleLogout() {
  clearAuth();
  state.documents = [];
  state.searchCount = 0;
  state.deleteTarget = null;

  // Clear form
  loginUser.value = '';
  loginPass.value = '';
  hideError(loginErr);

  showLoginPage();
}

/* ============================================================================
   DOCUMENT MANAGEMENT
   ============================================================================ */

/** Load documents from API and cache them. */
async function loadDocuments() {
  renderDocsLoading();

  try {
    const docs = await apiListDocuments();
    state.documents = docs;
    renderDocsList();
    // Also update dashboard if visible
    renderDashboardDocs();
    updateStatDocs();
  } catch (err) {
    if (err.message === 'UNAUTHORIZED') {
      handleUnauthorized();
      return;
    }
    renderDocsError(err.message);
  }
}

/** Render loading state in document list. */
function renderDocsLoading() {
  docsList.innerHTML = `
    <div class="docs-loading">
      <div class="progress-spinner"></div>
      <span>Loading your documents...</span>
    </div>
  `;
}

/** Render error state in document list. */
function renderDocsError(message) {
  docsList.innerHTML = `
    <div class="docs-error">
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
        <circle cx="8" cy="8" r="7" stroke="#EF4444" stroke-width="1.5"/>
        <path d="M8 5v3.5M8 10.5v.5" stroke="#EF4444" stroke-width="1.5" stroke-linecap="round"/>
      </svg>
      <span>Failed to load documents: ${escHtml(message)}</span>
    </div>
  `;
}

/** Render empty state for documents. */
function renderDocsEmpty() {
  docsList.innerHTML = `
    <div class="docs-empty">
      <svg width="40" height="40" viewBox="0 0 40 40" fill="none" style="margin: 0 auto 12px;" aria-hidden="true">
        <path d="M22 4H10A2 2 0 008 6v28a2 2 0 002 2h20a2 2 0 002-2V14L22 4z" stroke="#3F3F46" stroke-width="1.5" stroke-linejoin="round"/>
        <path d="M22 4v10h10" stroke="#3F3F46" stroke-width="1.5" stroke-linecap="round"/>
        <path d="M14 20h12M14 25h8" stroke="#3F3F46" stroke-width="1.5" stroke-linecap="round"/>
      </svg>
      <p style="font-size:0.9375rem; font-weight:600; color:#F4F4F5; margin-bottom:4px;">No documents yet</p>
      <p style="font-size:0.875rem; color:#A1A1AA;">Upload your first document using the area above.</p>
    </div>
  `;
}

/** Escape HTML special characters. */
function escHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

/** Render the document list. */
function renderDocsList() {
  if (!state.documents || state.documents.length === 0) {
    renderDocsEmpty();
    return;
  }

  docsList.innerHTML = state.documents.map((doc) => {
    const type  = fileType(doc.filename);
    const label = fileLabel(doc.filename);
    return `
      <div class="doc-card" data-doc-id="${escHtml(doc.doc_id)}" role="listitem">
        <div class="doc-card-icon ${type}" aria-hidden="true">${label}</div>
        <div class="doc-card-info">
          <div class="doc-card-name" title="${escHtml(doc.filename)}">${escHtml(doc.filename)}</div>
          <div class="doc-card-meta">${escHtml(doc.doc_id)}</div>
        </div>
        <div class="doc-card-actions">
          <button
            class="btn-delete"
            data-doc-id="${escHtml(doc.doc_id)}"
            data-filename="${escHtml(doc.filename)}"
            aria-label="Delete document ${escHtml(doc.filename)}"
          >
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden="true">
              <path d="M2 3.5h10M5.5 3.5V2.5h3v1M6 6v4M8 6v4M3 3.5l.5 8h7l.5-8" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
            Delete
          </button>
        </div>
      </div>
    `;
  }).join('');

  // Attach delete listeners
  docsList.querySelectorAll('.btn-delete').forEach((btn) => {
    btn.addEventListener('click', () => {
      openDeleteModal(btn.dataset.docId, btn.dataset.filename);
    });
  });
}

/** Update stat counter on dashboard. */
function updateStatDocs() {
  statDocs.textContent = state.documents.length;
}

/** Render small preview cards on dashboard. */
function renderDashboardDocs() {
  updateStatDocs();

  if (!state.documents || state.documents.length === 0) {
    dashboardDocsList.innerHTML = `
      <div style="grid-column:1/-1; text-align:center; padding:32px 0;">
        <p style="color:#A1A1AA; font-size:0.875rem;">No documents yet. <button class="btn-ghost btn-sm" style="display:inline-flex;" data-view="documents">Upload one</button></p>
      </div>
    `;
    // Re-attach view buttons in dynamic content
    dashboardDocsList.querySelectorAll('[data-view]').forEach((btn) => {
      btn.addEventListener('click', () => navigateToView(btn.dataset.view));
    });
    return;
  }

  const preview = state.documents.slice(0, 6);
  dashboardDocsList.innerHTML = preview.map((doc) => {
    const type  = fileType(doc.filename);
    const label = fileLabel(doc.filename);
    return `
      <div class="doc-preview-card">
        <div class="doc-preview-icon ${type}">${label}</div>
        <div class="doc-preview-name">${escHtml(doc.filename)}</div>
        <div class="doc-preview-id">${escHtml(doc.doc_id.substring(0, 16))}…</div>
      </div>
    `;
  }).join('');
}

/* ============================================================================
   FILE UPLOAD
   ============================================================================ */

function resetUploadUI() {
  hide(uploadProgress);
  hide(uploadSuccess);
  hide(uploadError);
  fileInput.value = '';
}

async function handleFileUpload(file) {
  if (!file) return;

  resetUploadUI();

  // Validate extension
  const ext = file.name.toLowerCase().split('.').pop();
  if (!['pdf', 'txt', 'md'].includes(ext)) {
    showError(uploadError, uploadErrorMsg, 'Unsupported file type. Please upload a PDF, TXT, or Markdown file.');
    return;
  }

  // Show progress
  uploadFilename.textContent = file.name;
  show(uploadProgress);

  try {
    const result = await apiUploadDocument(file);
    hide(uploadProgress);
    uploadSuccessMsg.textContent = `"${result.filename}" uploaded — ${result.chunk_count} chunks stored.`;
    show(uploadSuccess);

    // Refresh document list
    await loadDocuments();

    // Auto-hide success after 4s
    setTimeout(() => { hide(uploadSuccess); }, 4000);

  } catch (err) {
    if (err.message === 'UNAUTHORIZED') {
      handleUnauthorized();
      return;
    }
    hide(uploadProgress);
    showError(uploadError, uploadErrorMsg, err.message || 'Upload failed. Please try again.');
  }
}

/* ============================================================================
   DELETE MODAL
   ============================================================================ */

function openDeleteModal(docId, filename) {
  state.deleteTarget = { doc_id: docId, filename };
  deleteDocName.textContent = filename;
  show(deleteModal);
  deleteConfirmBtn.focus();
}

function closeDeleteModal() {
  state.deleteTarget = null;
  hide(deleteModal);
}

async function handleDeleteConfirm() {
  if (!state.deleteTarget) return;

  const { doc_id, filename } = state.deleteTarget;

  // Loading state
  deleteConfirmTxt.textContent = 'Deleting...';
  show(deleteSpinner);
  deleteConfirmBtn.disabled = true;
  deleteCancelBtn.disabled = true;

  try {
    await apiDeleteDocument(doc_id);

    // Remove from local state
    state.documents = state.documents.filter((d) => d.doc_id !== doc_id);

    closeDeleteModal();
    renderDocsList();
    renderDashboardDocs();
    updateStatDocs();

  } catch (err) {
    if (err.message === 'UNAUTHORIZED') {
      handleUnauthorized();
      return;
    }
    // Show error inside modal briefly
    alert(`Failed to delete "${filename}": ${err.message}`);
  } finally {
    deleteConfirmTxt.textContent = 'Delete';
    hide(deleteSpinner);
    deleteConfirmBtn.disabled = false;
    deleteCancelBtn.disabled = false;
  }
}

/* ============================================================================
   SEMANTIC SEARCH
   ============================================================================ */

async function performSearch(query) {
  if (!query || !query.trim()) return;

  const topK = parseInt(topKInput.value, 10) || 5;

  // Clear previous state
  hideError(searchError);
  hide(searchEmptyInit);
  hide(searchNoResults);
  hide(searchResultsList);

  // Loading state
  searchBtnTxt.textContent = 'Searching...';
  show(searchSpinner);
  searchBtn.disabled = true;

  try {
    const response = await apiSearch(query.trim(), topK);

    // Increment session counter
    state.searchCount++;
    statSearches.textContent = state.searchCount;

    if (response.results && response.results.length > 0) {
      renderSearchResults(response);
    } else {
      // No confident match
      const msg = response.message || 'No confident match found in your knowledge base.';
      noResultsMsg.textContent = msg;
      show(searchNoResults);
    }

  } catch (err) {
    if (err.message === 'UNAUTHORIZED') {
      handleUnauthorized();
      return;
    }
    showError(searchError, searchErrorMsg, err.message || 'Search failed. Please try again.');
    show(searchEmptyInit);
  } finally {
    searchBtnTxt.textContent = 'Search';
    hide(searchSpinner);
    searchBtn.disabled = false;
  }
}

/** Render ranked search result cards. */
function renderSearchResults(response) {
  const { query, results } = response;
  const count = results.length;

  resultsCountLbl.textContent = `${count} result${count !== 1 ? 's' : ''}`;
  resultsQueryLbl.textContent = `for "${query}"`;

  // Build result cards (keep header, replace cards)
  const headerHtml = searchResultsList.querySelector('.results-header').outerHTML;
  searchResultsList.innerHTML = headerHtml;

  results.forEach((result, idx) => {
    const pct    = Math.round(result.score * 100);
    const page   = result.page != null ? ` · Page ${result.page}` : '';
    const chunk  = `Chunk ${result.chunk_id}`;
    const source = `${escHtml(result.filename)}${page} · ${chunk}`;

    const card = document.createElement('div');
    card.className = 'result-card';
    card.setAttribute('role', 'listitem');
    card.innerHTML = `
      <div class="result-card-header">
        <div class="relevance-badge">
          <div class="relevance-dot" aria-hidden="true"></div>
          ${pct}% relevant
        </div>
        <span class="result-rank" aria-label="Result number ${idx + 1}">#${idx + 1}</span>
      </div>
      <div class="result-text">${escHtml(result.text)}</div>
      <div class="result-citation">
        <span class="citation-label">Source</span>
        <span class="citation-text">${source}</span>
      </div>
    `;

    searchResultsList.appendChild(card);
  });

  show(searchResultsList);
}

/** Handle dashboard quick-search — navigate to search view first. */
function handleDashboardSearch() {
  const q = dashSearchInput.value.trim();
  if (!q) return;

  // Copy query to search view and navigate
  searchInput.value = q;
  navigateToView('search');

  // Trigger search after a short delay so view is visible
  setTimeout(() => performSearch(q), 50);
}

/* ============================================================================
   EVENT LISTENERS
   ============================================================================ */

/** Attach all event listeners once DOM is ready. */
function attachListeners() {
  // --- Login ---
  loginForm.addEventListener('submit', handleLogin);

  // --- Logout ---
  logoutBtn.addEventListener('click', handleLogout);

  // --- Mobile sidebar ---
  mobileMenuBtn.addEventListener('click', openMobileSidebar);
  sidebarOverlay.addEventListener('click', closeMobileSidebar);

  // --- Nav items (sidebar buttons with data-view) ---
  navItems.forEach((item) => {
    item.addEventListener('click', () => {
      navigateToView(item.dataset.view);
    });
  });

  // --- All [data-view] buttons across the app (header buttons, etc.) ---
  // We handle these via delegation on document to catch dynamically added ones too.
  document.addEventListener('click', (e) => {
    const btn = e.target.closest('[data-view]');
    if (btn && !btn.classList.contains('nav-item')) {
      navigateToView(btn.dataset.view);
    }
  });

  // --- Upload zone ---
  uploadZone.addEventListener('click', () => fileInput.click());
  uploadZone.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      fileInput.click();
    }
  });

  // Drag and drop
  uploadZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    uploadZone.classList.add('drag-over');
  });

  uploadZone.addEventListener('dragleave', (e) => {
    if (!uploadZone.contains(e.relatedTarget)) {
      uploadZone.classList.remove('drag-over');
    }
  });

  uploadZone.addEventListener('drop', (e) => {
    e.preventDefault();
    uploadZone.classList.remove('drag-over');
    const file = e.dataTransfer.files[0];
    if (file) handleFileUpload(file);
  });

  fileInput.addEventListener('change', () => {
    if (fileInput.files[0]) {
      handleFileUpload(fileInput.files[0]);
    }
  });

  // --- Refresh button ---
  refreshDocsBtn.addEventListener('click', loadDocuments);

  // --- Search ---
  searchBtn.addEventListener('click', () => {
    performSearch(searchInput.value.trim());
  });

  searchInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') performSearch(searchInput.value.trim());
  });

  // --- Dashboard quick search ---
  dashSearchBtn.addEventListener('click', handleDashboardSearch);
  dashSearchInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') handleDashboardSearch();
  });

  // --- Delete modal ---
  deleteCancelBtn.addEventListener('click', closeDeleteModal);
  deleteConfirmBtn.addEventListener('click', handleDeleteConfirm);

  // Close modal on overlay click
  deleteModal.addEventListener('click', (e) => {
    if (e.target === deleteModal) closeDeleteModal();
  });

  // Escape key closes modal
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && !deleteModal.classList.contains('hidden')) {
      closeDeleteModal();
    }
  });
}

/* ============================================================================
   INIT
   ============================================================================ */

function init() {
  attachListeners();

  // Check if already authenticated (e.g., page refresh with active session)
  const token = getToken();
  if (token) {
    showDashboardPage();
  } else {
    showLoginPage();
  }
}

// Bootstrap when DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}
