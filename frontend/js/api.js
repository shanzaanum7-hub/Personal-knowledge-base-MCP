/**
 * api.js — Backend API client for Personal Knowledge Base
 *
 * Communicates with FastAPI at http://localhost:8000
 * All requests include the JWT bearer token when available.
 *
 * Endpoints:
 *   POST /auth/login          — obtain JWT
 *   POST /documents/upload    — ingest document
 *   GET  /documents           — list documents
 *   DELETE /documents/{id}    — delete document
 *   POST /search              — semantic search
 */

const API_BASE = 'http://127.0.0.1:8000';

/** Retrieve stored JWT token. */
function getToken() {
  return sessionStorage.getItem('kb_token');
}

/** Store JWT token in session storage (cleared when tab closes). */
function setToken(token) {
  sessionStorage.setItem('kb_token', token);
}

/** Remove token and username on logout. */
function clearAuth() {
  sessionStorage.removeItem('kb_token');
  sessionStorage.removeItem('kb_username');
}

/** Build Authorization header object if token exists. */
function authHeaders() {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

/**
 * Authenticate user and store JWT.
 * Uses OAuth2 form encoding as required by FastAPI's OAuth2PasswordRequestForm.
 * @param {string} username
 * @param {string} password
 * @returns {Promise<{access_token: string, token_type: string}>}
 */
async function apiLogin(username, password) {
  const body = new URLSearchParams({ username, password });
  const resp = await fetch(`${API_BASE}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: body.toString(),
  });

  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}));
    throw new Error(err.detail || `Login failed (${resp.status})`);
  }

  const data = await resp.json();
  setToken(data.access_token);
  sessionStorage.setItem('kb_username', username);
  return data;
}


/**
 * Register a new user on the server.
 * @param {string} username
 * @param {string} password
 * @returns {Promise<{username:string,user_id:string}>}
 */
async function apiRegister(username, password) {
  const resp = await fetch(`${API_BASE}/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  });

  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}));
    throw new Error(err.detail || `Register failed (${resp.status})`);
  }

  return resp.json();
}

/**
 * Upload a document file for ingestion.
 * @param {File} file
 * @returns {Promise<{doc_id, filename, chunk_count, chunks}>}
 */
async function apiUploadDocument(file) {
  const formData = new FormData();
  formData.append('file', file);

  const resp = await fetch(`${API_BASE}/documents/upload`, {
    method: 'POST',
    headers: authHeaders(),
    body: formData,
  });

  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}));
    throw new Error(err.detail || `Upload failed (${resp.status})`);
  }

  return resp.json();
}

/**
 * List documents belonging to the authenticated user.
 * @returns {Promise<Array<{doc_id: string, filename: string}>>}
 */
async function apiListDocuments() {
  const resp = await fetch(`${API_BASE}/documents`, {
    method: 'GET',
    headers: {
      'Content-Type': 'application/json',
      ...authHeaders(),
    },
  });

  if (resp.status === 401) {
    throw new Error('UNAUTHORIZED');
  }

  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}));
    throw new Error(err.detail || `Failed to list documents (${resp.status})`);
  }

  return resp.json();
}

/**
 * Delete a document by its doc_id.
 * @param {string} docId
 * @returns {Promise<{message: string, doc_id: string}>}
 */
async function apiDeleteDocument(docId) {
  const resp = await fetch(`${API_BASE}/documents/${encodeURIComponent(docId)}`, {
    method: 'DELETE',
    headers: {
      'Content-Type': 'application/json',
      ...authHeaders(),
    },
  });

  if (resp.status === 401) {
    throw new Error('UNAUTHORIZED');
  }

  if (resp.status === 404) {
    throw new Error('Document not found.');
  }

  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}));
    throw new Error(err.detail || `Delete failed (${resp.status})`);
  }

  return resp.json();
}

/**
 * Perform semantic search over the user's knowledge base.
 * @param {string} query
 * @param {number} topK  — number of results (1–50)
 * @returns {Promise<{query, results, message}>}
 */
async function apiSearch(query, topK = 5) {
  const resp = await fetch(`${API_BASE}/search`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...authHeaders(),
    },
    body: JSON.stringify({ query, top_k: topK }),
  });

  if (resp.status === 401) {
    throw new Error('UNAUTHORIZED');
  }

  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}));
    throw new Error(err.detail || `Search failed (${resp.status})`);
  }

  return resp.json();
}
