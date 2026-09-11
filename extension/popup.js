// TL;DR URL Bot - Chrome Extension Popup Script

const MASTODON_URL_WEIGHT = 23;
const FOOTER_PREFIX = '\n\nRead more: ';
const DEFAULT_API_URL = 'http://localhost:8000/api';

// DOM Elements
const urlInput = document.getElementById('urlInput');
const summarizeBtn = document.getElementById('summarizeBtn');
const mastodonBtn = document.getElementById('mastodonBtn');
const okBtn = document.getElementById('okBtn');

const limitInput = document.getElementById('limit');
const stripHiddenCheckbox = document.getElementById('stripHidden');
const stripUnicodeCheckbox = document.getElementById('stripUnicode');
const usePytectorCheckbox = document.getElementById('usePytector');
const stripQueryCheckbox = document.getElementById('stripQuery');
const useHumanizerCheckbox = document.getElementById('useHumanizer');
const forceOllamaCheckbox = document.getElementById('forceOllama');

const toggleServerConfigBtn = document.getElementById('toggleServerConfigBtn');
const serverConfigPanel = document.getElementById('serverConfigPanel');
const apiUrlInput = document.getElementById('apiUrlInput');
const saveApiUrlBtn = document.getElementById('saveApiUrlBtn');

const errorContainer = document.getElementById('errorContainer');
const resultContainer = document.getElementById('resultContainer');
const summaryEdit = document.getElementById('summaryEdit');
const charCountEl = document.getElementById('charCount');
const modelContainer = document.getElementById('modelContainer');
const modelNameEl = document.getElementById('modelName');
const durationSpan = document.getElementById('durationSpan');
const durationTimeEl = document.getElementById('durationTime');
const standaloneDurationContainer = document.getElementById('standaloneDurationContainer');
const standaloneDurationTimeEl = document.getElementById('standaloneDurationTime');
const urlMetaEl = document.getElementById('urlMeta');
const mastodonStatusBar = document.getElementById('mastodonStatusBar');

// State
let apiUrl = DEFAULT_API_URL;
let currentUrl = '';
let lastUrl = '';
let currentSummary = '';
let rawSummary = '';
let filteredSummary = '';
let currentModel = '';
let currentDuration = null;
let mastodonSuccess = null;
let isLoading = false;
let isPostingToMastodon = false;

// Initialize
document.addEventListener('DOMContentLoaded', async () => {
  await loadSettings();
  initActiveTabUrl();
  setupEventListeners();
  updateUiState();
});

// Storage operations
async function loadSettings() {
  try {
    if (typeof chrome !== 'undefined' && chrome.storage && chrome.storage.sync) {
      const data = await chrome.storage.sync.get(['apiUrl', 'limit', 'stripHidden', 'stripUnicode', 'usePytector', 'stripQuery', 'forceOllama', 'useHumanizer']);
      if (data.apiUrl) apiUrl = data.apiUrl;
      if (data.limit !== undefined) limitInput.value = data.limit;
      if (data.stripHidden !== undefined) stripHiddenCheckbox.checked = data.stripHidden;
      if (data.stripUnicode !== undefined) stripUnicodeCheckbox.checked = data.stripUnicode;
      if (data.usePytector !== undefined) usePytectorCheckbox.checked = data.usePytector;
      if (data.stripQuery !== undefined) stripQueryCheckbox.checked = data.stripQuery;
      if (data.useHumanizer !== undefined) useHumanizerCheckbox.checked = data.useHumanizer;
      if (data.forceOllama !== undefined) forceOllamaCheckbox.checked = data.forceOllama;
    } else if (window.localStorage) {
      const savedApiUrl = localStorage.getItem('tldr_api_url');
      if (savedApiUrl) apiUrl = savedApiUrl;
    }
  } catch (err) {
    console.warn('Could not load stored settings:', err);
  }
  apiUrlInput.value = apiUrl;
}

async function saveSettings() {
  const newApiUrl = apiUrlInput.value.trim().replace(/\/+$/, '') || DEFAULT_API_URL;
  apiUrl = newApiUrl;
  apiUrlInput.value = newApiUrl;

  const settings = {
    apiUrl: newApiUrl,
    limit: parseInt(limitInput.value, 10) || 500,
    stripHidden: stripHiddenCheckbox.checked,
    stripUnicode: stripUnicodeCheckbox.checked,
    usePytector: usePytectorCheckbox.checked,
    stripQuery: stripQueryCheckbox.checked,
    useHumanizer: useHumanizerCheckbox.checked,
    forceOllama: forceOllamaCheckbox.checked
  };

  try {
    if (typeof chrome !== 'undefined' && chrome.storage && chrome.storage.sync) {
      await chrome.storage.sync.set(settings);
    } else if (window.localStorage) {
      localStorage.setItem('tldr_api_url', newApiUrl);
    }
  } catch (err) {
    console.warn('Could not persist settings:', err);
  }
}

// Populate URL from active tab if it's a web page
function initActiveTabUrl() {
  if (typeof chrome !== 'undefined' && chrome.tabs && chrome.tabs.query) {
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      if (tabs && tabs[0] && tabs[0].url) {
        const tabUrl = tabs[0].url;
        if (tabUrl.startsWith('http://') || tabUrl.startsWith('https://')) {
          urlInput.value = tabUrl;
          currentUrl = tabUrl;
          updateUiState();
        }
      }
      urlInput.focus();
    });
  } else {
    urlInput.focus();
  }
}

function setupEventListeners() {
  urlInput.addEventListener('input', () => {
    currentUrl = urlInput.value.trim();
    updateUiState();
  });

  urlInput.addEventListener('keyup', (e) => {
    if (e.key === 'Enter' && !summarizeBtn.disabled) {
      summarize();
    }
  });

  limitInput.addEventListener('input', () => {
    saveSettings();
    updateCharCount();
  });
  limitInput.addEventListener('change', () => {
    saveSettings();
    updateCharCount();
  });
  stripHiddenCheckbox.addEventListener('change', () => saveSettings());
  stripUnicodeCheckbox.addEventListener('change', () => saveSettings());
  usePytectorCheckbox.addEventListener('change', () => saveSettings());
  stripQueryCheckbox.addEventListener('change', () => saveSettings());
  useHumanizerCheckbox.addEventListener('change', () => {
    saveSettings();
    onHumanizerToggle();
  });
  forceOllamaCheckbox.addEventListener('change', () => saveSettings());

  summarizeBtn.addEventListener('click', summarize);
  mastodonBtn.addEventListener('click', postToMastodon);
  okBtn.addEventListener('click', reloadPage);

  summaryEdit.addEventListener('input', () => {
    currentSummary = summaryEdit.value;
    updateCharCount();
  });

  toggleServerConfigBtn.addEventListener('click', () => {
    serverConfigPanel.classList.toggle('hidden');
  });

  saveApiUrlBtn.addEventListener('click', async () => {
    await saveSettings();
    serverConfigPanel.classList.add('hidden');
  });
}

function onHumanizerToggle() {
  if (rawSummary || filteredSummary) {
    if (useHumanizerCheckbox.checked && filteredSummary) {
      currentSummary = filteredSummary;
      summaryEdit.value = filteredSummary;
    } else if (!useHumanizerCheckbox.checked && rawSummary) {
      currentSummary = rawSummary;
      summaryEdit.value = rawSummary;
    }
    updateCharCount();
  }
}

function updateCharCount() {
  const text = summaryEdit.value || '';
  const count = text.length + FOOTER_PREFIX.length + MASTODON_URL_WEIGHT;
  const currentLimit = parseInt(limitInput.value, 10) || 500;
  charCountEl.textContent = `${count} / ${currentLimit} characters (incl. 23 for URL)`;
  if (count > currentLimit) {
    charCountEl.classList.add('over-limit');
  } else {
    charCountEl.classList.remove('over-limit');
  }
}

function updateUiState() {
  const hasUrl = Boolean(urlInput.value.trim());
  summarizeBtn.disabled = isLoading || !hasUrl;
  summarizeBtn.textContent = isLoading ? 'Summarizing...' : 'Summarize';

  urlInput.disabled = isLoading;
  limitInput.disabled = isLoading;
  stripHiddenCheckbox.disabled = isLoading;
  stripUnicodeCheckbox.disabled = isLoading;
  usePytectorCheckbox.disabled = isLoading;
  stripQueryCheckbox.disabled = isLoading;
  useHumanizerCheckbox.disabled = isLoading;
  forceOllamaCheckbox.disabled = isLoading;

  if (currentSummary) {
    resultContainer.classList.remove('hidden');
    mastodonBtn.classList.remove('hidden');
    okBtn.classList.remove('hidden');

    if (isPostingToMastodon) {
      mastodonBtn.disabled = true;
      mastodonBtn.textContent = 'Posting...';
    } else if (mastodonSuccess === true) {
      mastodonBtn.disabled = true;
      mastodonBtn.textContent = 'Posted';
    } else {
      mastodonBtn.disabled = false;
      mastodonBtn.textContent = 'Post to Mastodon';
    }

    if (currentModel) {
      modelContainer.classList.remove('hidden');
      modelNameEl.textContent = currentModel;
      if (currentDuration !== null && currentDuration !== undefined) {
        durationSpan.classList.remove('hidden');
        durationTimeEl.textContent = currentDuration;
      } else {
        durationSpan.classList.add('hidden');
      }
      standaloneDurationContainer.classList.add('hidden');
    } else if (currentDuration !== null && currentDuration !== undefined) {
      modelContainer.classList.add('hidden');
      standaloneDurationContainer.classList.remove('hidden');
      standaloneDurationTimeEl.textContent = `${currentDuration}s`;
    } else {
      modelContainer.classList.add('hidden');
      standaloneDurationContainer.classList.add('hidden');
    }

    urlMetaEl.textContent = `URL: ${lastUrl}`;

    if (mastodonSuccess !== null) {
      mastodonStatusBar.classList.remove('hidden');
      if (mastodonSuccess) {
        mastodonStatusBar.className = 'mastodon-status-bar success';
        mastodonStatusBar.textContent = '✓ Successfully posted to Mastodon';
      } else {
        mastodonStatusBar.className = 'mastodon-status-bar failure';
        mastodonStatusBar.textContent = '✗ Failed to post to Mastodon';
      }
    } else {
      mastodonStatusBar.classList.add('hidden');
    }
  } else {
    resultContainer.classList.add('hidden');
    mastodonBtn.classList.add('hidden');
    okBtn.classList.add('hidden');
  }
}

function showError(msg) {
  errorContainer.textContent = msg;
  errorContainer.classList.remove('hidden');
}

function clearError() {
  errorContainer.textContent = '';
  errorContainer.classList.add('hidden');
}

async function summarize() {
  const targetUrl = urlInput.value.trim();
  if (!targetUrl || isLoading) return;

  isLoading = true;
  clearError();
  currentSummary = '';
  currentModel = '';
  currentDuration = null;
  mastodonSuccess = null;
  updateUiState();

  const payload = {
    url: targetUrl,
    limit: parseInt(limitInput.value, 10) || 500,
    strip_hidden: stripHiddenCheckbox.checked,
    strip_unicode: stripUnicodeCheckbox.checked,
    use_pytector: usePytectorCheckbox.checked,
    strip_query: stripQueryCheckbox.checked,
    use_humanizer: useHumanizerCheckbox.checked,
    force_ollama: forceOllamaCheckbox.checked
  };

  try {
    const endpoint = `${apiUrl}/summarize`;
    const response = await fetch(endpoint, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(payload)
    });

    if (!response.ok) {
      let errorDetail = 'An unexpected error occurred. Please try again.';
      try {
        const errorJson = await response.json();
        if (errorJson && errorJson.detail) {
          errorDetail = errorJson.detail;
        }
      } catch (e) {
        errorDetail = `Server error (${response.status}): ${response.statusText}`;
      }
      showError(errorDetail);
      isLoading = false;
      updateUiState();
      return;
    }

    const data = await response.json();
    rawSummary = data.raw_summary || '';
    filteredSummary = data.filtered_summary || '';
    currentSummary = data.summary || '';
    lastUrl = data.url || targetUrl;
    urlInput.value = data.url || targetUrl;
    currentModel = data.model || '';
    currentDuration = (data.duration !== undefined && data.duration !== null) ? data.duration : null;

    summaryEdit.value = currentSummary;
    updateCharCount();
    isLoading = false;
    updateUiState();

    // Focus Mastodon button following frontend behavior
    setTimeout(() => {
      if (mastodonBtn && !mastodonBtn.classList.contains('hidden')) {
        mastodonBtn.focus();
      }
    }, 50);
  } catch (err) {
    console.error('Summarize request failed:', err);
    showError(
      `Could not connect to API server at ${apiUrl}. Please ensure the backend is running (e.g. 'uv run python api.py') and accessible.`
    );
    isLoading = false;
    updateUiState();
  }
}

async function postToMastodon() {
  const textToPost = summaryEdit.value.trim();
  if (!textToPost || !lastUrl || isPostingToMastodon) return;

  isPostingToMastodon = true;
  mastodonSuccess = null;
  clearError();
  updateUiState();

  try {
    const endpoint = `${apiUrl}/mastodon`;
    const response = await fetch(endpoint, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        summary: textToPost,
        url: lastUrl
      })
    });

    if (!response.ok) {
      mastodonSuccess = false;
      let errorDetail = 'Failed to post to Mastodon.';
      try {
        const errJson = await response.json();
        if (errJson && errJson.detail) {
          errorDetail = errJson.detail;
        }
      } catch (e) {
        errorDetail = `Mastodon post failed (${response.status}): ${response.statusText}`;
      }
      console.error(errorDetail);
    } else {
      mastodonSuccess = true;
    }
  } catch (err) {
    console.error('Mastodon post request failed:', err);
    mastodonSuccess = false;
  } finally {
    isPostingToMastodon = false;
    updateUiState();
  }
}

function reloadPage() {
  currentSummary = '';
  currentModel = '';
  currentDuration = null;
  mastodonSuccess = null;
  clearError();
  initActiveTabUrl();
  updateUiState();
}
