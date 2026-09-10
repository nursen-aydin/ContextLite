// ============================================================================
// THEME LOGIC (EARLY EXECUTION)
// ============================================================================
function applyTheme(theme) {
    if (theme === 'system') {
        const isDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
        document.documentElement.setAttribute('data-theme', isDark ? 'dark' : 'light');
    } else {
        document.documentElement.setAttribute('data-theme', theme);
    }
}
const savedTheme = localStorage.getItem('theme') || 'system';
applyTheme(savedTheme);

// Watch for system theme changes
window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
    if (localStorage.getItem('theme') === 'system') {
        applyTheme('system');
    }
});

// ============================================================================
// DOM ELEMENTS
// ============================================================================

// Navigation & Views
const navDashboard = document.getElementById('nav-dashboard');
const navChat = document.getElementById('nav-chat');
const navModels = document.getElementById('nav-models');
const navProjects = document.getElementById('nav-projects');
const navFiles = document.getElementById('nav-files');
const navGuides = document.getElementById('nav-guides');
const navSettings = document.getElementById('nav-settings');
const navUsage = document.getElementById('nav-usage');
const navTokenSaver = document.getElementById('nav-token-saver');

const viewDashboard = document.getElementById('view-dashboard');
const viewChat = document.getElementById('view-chat');
const viewModels = document.getElementById('view-models');
const viewProjects = document.getElementById('view-projects');
const viewFiles = document.getElementById('view-files');
const viewGuides = document.getElementById('view-guides');
const viewSettings = document.getElementById('view-settings');
const viewUsage = document.getElementById('view-usage');
const viewTokenSaver = document.getElementById('view-token-saver');

const authContainer = document.getElementById('auth-container');
const setupView = document.getElementById('setup-view');
const loginView = document.getElementById('login-view');
const appContainer = document.getElementById('app-container');

// Sidebar (Mobile)
const appSidebar = document.getElementById('app-sidebar');
const sidebarBackdrop = document.getElementById('sidebar-backdrop');
const sidebarCloseBtn = document.getElementById('sidebar-close');
const sidebarOpeners = document.querySelectorAll('.sidebar-opener, #sidebar-open');
const conversationsScrollArea = document.querySelector('.conversations-scroll-area');
const sidebarResizeHandle = document.getElementById('sidebar-resize-handle');

const SIDEBAR_HISTORY_STORAGE_KEY = 'contextlite_sidebar_history_height';
const SIDEBAR_HISTORY_MIN_HEIGHT = 120;
const SIDEBAR_FOOTER_MIN_HEIGHT = 150;

function getSidebarHistoryMaxHeight() {
    if (!appSidebar || !conversationsScrollArea || !sidebarResizeHandle) return 300;
    const sidebarRect = appSidebar.getBoundingClientRect();
    const historyRect = conversationsScrollArea.getBoundingClientRect();
    const usedAboveHistory = historyRect.top - sidebarRect.top;
    return Math.max(
        SIDEBAR_HISTORY_MIN_HEIGHT,
        appSidebar.clientHeight - usedAboveHistory - SIDEBAR_FOOTER_MIN_HEIGHT - sidebarResizeHandle.offsetHeight
    );
}

function setSidebarHistoryHeight(height, persist = false) {
    if (!appSidebar || !sidebarResizeHandle) return;
    const maxHeight = getSidebarHistoryMaxHeight();
    const nextHeight = Math.round(Math.min(maxHeight, Math.max(SIDEBAR_HISTORY_MIN_HEIGHT, height)));
    appSidebar.style.setProperty('--sidebar-history-height', `${nextHeight}px`);
    sidebarResizeHandle.setAttribute('aria-valuenow', String(nextHeight));
    sidebarResizeHandle.setAttribute('aria-valuemax', String(Math.round(maxHeight)));
    if (persist) {
        try { localStorage.setItem(SIDEBAR_HISTORY_STORAGE_KEY, String(nextHeight)); } catch (_) {}
    }
}

function initializeSidebarResize() {
    if (!appSidebar || !conversationsScrollArea || !sidebarResizeHandle) return;

    let savedHeight = null;
    try { savedHeight = Number.parseInt(localStorage.getItem(SIDEBAR_HISTORY_STORAGE_KEY), 10); } catch (_) {}
    if (Number.isFinite(savedHeight)) setSidebarHistoryHeight(savedHeight);

    let isDragging = false;

    sidebarResizeHandle.addEventListener('pointerdown', event => {
        if (event.button !== 0) return;
        isDragging = true;
        sidebarResizeHandle.setPointerCapture(event.pointerId);
        sidebarResizeHandle.classList.add('is-dragging');
        document.body.classList.add('sidebar-is-resizing');
        event.preventDefault();
    });

    sidebarResizeHandle.addEventListener('pointermove', event => {
        if (!isDragging) return;
        const historyTop = conversationsScrollArea.getBoundingClientRect().top;
        setSidebarHistoryHeight(event.clientY - historyTop);
    });

    const finishResize = event => {
        if (!isDragging) return;
        isDragging = false;
        if (sidebarResizeHandle.hasPointerCapture(event.pointerId)) {
            sidebarResizeHandle.releasePointerCapture(event.pointerId);
        }
        sidebarResizeHandle.classList.remove('is-dragging');
        document.body.classList.remove('sidebar-is-resizing');
        setSidebarHistoryHeight(conversationsScrollArea.getBoundingClientRect().height, true);
    };

    sidebarResizeHandle.addEventListener('pointerup', finishResize);
    sidebarResizeHandle.addEventListener('pointercancel', finishResize);
    sidebarResizeHandle.addEventListener('dblclick', () => {
        const defaultHeight = Math.min(300, Math.max(210, window.innerHeight * 0.32));
        setSidebarHistoryHeight(defaultHeight, true);
    });

    sidebarResizeHandle.addEventListener('keydown', event => {
        const currentHeight = conversationsScrollArea.getBoundingClientRect().height;
        let nextHeight = null;
        if (event.key === 'ArrowUp') nextHeight = currentHeight - 16;
        if (event.key === 'ArrowDown') nextHeight = currentHeight + 16;
        if (event.key === 'Home') nextHeight = SIDEBAR_HISTORY_MIN_HEIGHT;
        if (event.key === 'End') nextHeight = getSidebarHistoryMaxHeight();
        if (nextHeight === null) return;
        event.preventDefault();
        setSidebarHistoryHeight(nextHeight, true);
    });

    window.addEventListener('resize', () => {
        const currentHeight = conversationsScrollArea.getBoundingClientRect().height;
        setSidebarHistoryHeight(currentHeight);
    });
}

initializeSidebarResize();

const themeSelect = document.getElementById('theme-select');
const themePicker = document.getElementById('theme-picker');
const themeMenuButton = document.getElementById('theme-menu-button');
const themeMenu = document.getElementById('theme-menu');
const themeCurrentIcon = document.getElementById('theme-current-icon');

function closeThemeMenu() {
    if (!themeMenu || !themeMenuButton) return;
    themeMenu.classList.add('hidden');
    themeMenuButton.setAttribute('aria-expanded', 'false');
}

function renderThemePicker(theme) {
    if (!themeMenu || !themeMenuButton || !themeCurrentIcon) return;
    const options = [...themeMenu.querySelectorAll('.theme-option')];
    const selected = options.find(option => option.dataset.theme === theme) || options[0];
    options.forEach(option => {
        const active = option === selected;
        option.classList.toggle('active', active);
        option.setAttribute('aria-checked', String(active));
    });
    const icon = selected.querySelector('svg').cloneNode(true);
    themeCurrentIcon.replaceChildren(icon);
    const label = selected.querySelector('span').textContent;
    themeMenuButton.setAttribute('aria-label', `Tema: ${label}`);
    themeMenuButton.title = `Tema: ${label}`;
    const settingsThemeSelect = document.getElementById('settings-theme-select');
    if (settingsThemeSelect) settingsThemeSelect.value = selected.dataset.theme;
}

if (themeSelect) {
    themeSelect.value = localStorage.getItem('theme') || 'system';
    themeSelect.addEventListener('change', (e) => {
        const newTheme = e.target.value || 'system';
        localStorage.setItem('theme', newTheme);
        applyTheme(newTheme);
        renderThemePicker(newTheme);
    });
    renderThemePicker(themeSelect.value);
}

if (themeMenuButton && themeMenu) {
    themeMenuButton.addEventListener('click', event => {
        event.stopPropagation();
        const willOpen = themeMenu.classList.contains('hidden');
        themeMenu.classList.toggle('hidden', !willOpen);
        themeMenuButton.setAttribute('aria-expanded', String(willOpen));
        if (willOpen) themeMenu.querySelector('.theme-option.active')?.focus();
    });

    themeMenu.querySelectorAll('.theme-option').forEach(option => {
        option.addEventListener('click', () => {
            themeSelect.value = option.dataset.theme;
            themeSelect.dispatchEvent(new Event('change'));
            closeThemeMenu();
            themeMenuButton.focus();
        });
    });

    document.addEventListener('click', event => {
        if (!themePicker.contains(event.target)) closeThemeMenu();
    });
    document.addEventListener('keydown', event => {
        if (event.key === 'Escape' && !themeMenu.classList.contains('hidden')) {
            closeThemeMenu();
            themeMenuButton.focus();
        }
    });
}

// Modals
const confirmModal = document.getElementById('confirm-modal');
const modalTitle = document.getElementById('modal-title');
const modalDesc = document.getElementById('modal-desc');
const modalConfirm = document.getElementById('modal-confirm');
const modalCancel = document.getElementById('modal-cancel');
let pendingConfirmAction = null;

// Chat
const chatForm = document.getElementById('chat-form');
const chatInput = document.getElementById('chat-input');
const chatMessages = document.getElementById('chat-messages');
const modeSelect = document.getElementById('mode-select');
const modelSelect = document.getElementById('model-select');
const sendButton = document.getElementById('send-button');
const chatProjectSelect = document.getElementById('chat-project-select');

// State
let currentConversationId = null;
let currentProjectId = null;
let currentMessages = [];
let csrfToken = "";
let modelManagerTimer = null;

// ============================================================================
// UTILS & API
// ============================================================================

function getCookie(name) {
    let value = "; " + document.cookie;
    let parts = value.split("; " + name + "=");
    if (parts.length === 2) return parts.pop().split(";").shift();
    return "";
}

async function apiFetch(url, options = {}) {
    if (!options.headers) options.headers = {};
    if (['POST', 'PUT', 'PATCH', 'DELETE'].includes(options.method)) {
        options.headers['X-CSRF-Token'] = csrfToken || getCookie('csrf_token');
    }
    const response = await fetch(url, options);
    if (response.status === 401 || response.status === 403) {
        const errorData = await response.json().catch(() => ({}));
        if (errorData.detail && (errorData.detail.includes("Yetkilendirme") || errorData.detail.includes("CSRF"))) {
            showAuth();
        }
    }
    return response;
}

async function checkAuth() {
    try {
        const res = await fetch('/api/auth/me');
        if (res.ok) {
            const user = await res.json();
            document.getElementById('user-name').textContent = user.name;
            document.getElementById('user-role').textContent = user.role === 'owner' ? 'Sahip' : 'Kullanıcı';
            
            // Set initials
            const initials = user.name.split(' ').map(n => n[0]).join('').substring(0, 2).toUpperCase();
            document.getElementById('user-avatar-initials').textContent = initials;
            
            // Populate Dashboard info
            document.getElementById('dash-user-name').textContent = user.name.split(' ')[0];
            const emailParts = user.email.split('@');
            let maskedEmail = user.email;
            if (emailParts.length === 2 && emailParts[0].length > 2) {
                maskedEmail = emailParts[0].substring(0,2) + '***@' + emailParts[1];
            }
            document.getElementById('dash-user-email').textContent = maskedEmail;
            
            const statusBadge = document.getElementById('dash-email-status');
            if (user.email_verified_at) {
                statusBadge.textContent = 'Doğrulandı';
                statusBadge.className = 'badge badge-success';
                document.getElementById('unverified-banner').classList.add('hidden');
            } else {
                statusBadge.textContent = 'Doğrulanmadı';
                statusBadge.className = 'badge badge-default';
                document.getElementById('unverified-banner').classList.remove('hidden');
            }
            
            csrfToken = getCookie('csrf_token');
            loadProviders();
            loadBudget();
            loadConversations().then(() => {
                const savedView = localStorage.getItem('contextlite_last_view') || 'dashboard';
                switchView(savedView);
                const savedConv = localStorage.getItem('contextlite_last_conv');
                if (savedView === 'chat' && savedConv) {
                    loadConversation(savedConv);
                }
            });
            return true;
        } else {
            window.location.href = '/login';
        }
    } catch (e) {
        window.location.href = '/login';
    }
    return false;
}

// Auth forms have been moved to their respective html pages.

document.getElementById('logout-btn').addEventListener('click', async () => {
    await apiFetch('/api/auth/logout', { method: 'POST' });
    window.location.reload();
});

// Toggle logic moved to auth pages.

// ============================================================================
// NAVIGATION & SIDEBAR
// ============================================================================

function switchView(view) {
    if(navDashboard) navDashboard.classList.remove('active');
    navChat.classList.remove('active');
    navModels.classList.remove('active');
    navProjects.classList.remove('active');
    navFiles.classList.remove('active');
    navGuides.classList.remove('active');
    navSettings.classList.remove('active');
    navUsage.classList.remove('active');
    navTokenSaver.classList.remove('active');
    
    if(viewDashboard) viewDashboard.classList.add('hidden');
    viewChat.classList.add('hidden');
    viewModels.classList.add('hidden');
    viewProjects.classList.add('hidden');
    viewFiles.classList.add('hidden');
    viewGuides.classList.add('hidden');
    viewSettings.classList.add('hidden');
    viewUsage.classList.add('hidden');
    viewTokenSaver.classList.add('hidden');
    
    if (view === 'dashboard') {
        if(navDashboard) navDashboard.classList.add('active');
        if(viewDashboard) viewDashboard.classList.remove('hidden');
        loadProjects(); // to populate dash
        loadUsage();    // to populate dash
    } else if (view === 'chat') {
        navChat.classList.add('active');
        viewChat.classList.remove('hidden');
    } else if (view === 'models') {
        navModels.classList.add('active');
        viewModels.classList.remove('hidden');
        loadModelManager();
    } else if (view === 'projects') {
        navProjects.classList.add('active');
        viewProjects.classList.remove('hidden');
        loadProjects();
    } else if (view === 'files') {
        navFiles.classList.add('active');
        viewFiles.classList.remove('hidden');
    } else if (view === 'guides') {
        navGuides.classList.add('active');
        viewGuides.classList.remove('hidden');
    } else if (view === 'settings') {
        navSettings.classList.add('active');
        viewSettings.classList.remove('hidden');
    } else if (view === 'usage') {
        navUsage.classList.add('active');
        viewUsage.classList.remove('hidden');
        loadUsage();
    } else if (view === 'token-saver') {
        navTokenSaver.classList.add('active');
        viewTokenSaver.classList.remove('hidden');
    }
    
    if (window.innerWidth <= 768) {
        closeSidebar();
    }
    localStorage.setItem('contextlite_last_view', view);

    if (view !== 'models' && modelManagerTimer) {
        clearTimeout(modelManagerTimer);
        modelManagerTimer = null;
    }
}

if(navDashboard) navDashboard.addEventListener('click', () => switchView('dashboard'));
navChat.addEventListener('click', () => switchView('chat'));
navModels.addEventListener('click', () => switchView('models'));
navProjects.addEventListener('click', () => switchView('projects'));
navFiles.addEventListener('click', () => switchView('files'));
navGuides.addEventListener('click', () => switchView('guides'));
navSettings.addEventListener('click', () => switchView('settings'));
navUsage.addEventListener('click', () => switchView('usage'));
navTokenSaver.addEventListener('click', () => switchView('token-saver'));

function openSidebar() {
    appSidebar.classList.add('open');
    sidebarBackdrop.classList.remove('hidden');
}
function closeSidebar() {
    appSidebar.classList.remove('open');
    sidebarBackdrop.classList.add('hidden');
}

sidebarOpeners.forEach(btn => btn.addEventListener('click', openSidebar));
sidebarCloseBtn.addEventListener('click', closeSidebar);
sidebarBackdrop.addEventListener('click', closeSidebar);

// Modal logic
function showConfirmModal(title, desc, onConfirm) {
    modalTitle.textContent = title;
    modalDesc.textContent = desc;
    pendingConfirmAction = onConfirm;
    confirmModal.classList.remove('hidden');
}
modalCancel.addEventListener('click', () => confirmModal.classList.add('hidden'));
modalConfirm.addEventListener('click', async () => {
    if (pendingConfirmAction) await pendingConfirmAction();
    confirmModal.classList.add('hidden');
    pendingConfirmAction = null;
});

// ============================================================================
// CONVERSATIONS
// ============================================================================

document.getElementById('new-chat-btn').addEventListener('click', () => {
    currentConversationId = null;
    currentMessages = [];
    document.getElementById('chat-title').textContent = 'Yeni Sohbet';
    chatMessages.innerHTML = `
        <div class="empty-state" id="welcome-message">
            <div class="empty-icon">
                <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                    <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/>
                </svg>
            </div>
            <h2>Nasıl yardımcı olabilirim?</h2>
            <p>Sorunuzu aşağıdaki alana yazarak sohbete başlayabilirsiniz.</p>
        </div>`;
    switchView('chat');
});

async function loadConversations() {
    const res = await apiFetch('/api/conversations');
    if (res.ok) {
        const convs = await res.json();
        const list = document.getElementById('conversations-list');
        list.innerHTML = '';
        
        convs.forEach(c => {
            const btn = document.createElement('div');
            btn.className = 'nav-item chat-history-item';
            if (c.id === currentConversationId) btn.classList.add('active');
            
            const icon = `<svg viewBox="0 0 24 24" width="16" height="16" stroke="currentColor" stroke-width="2" fill="none"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path></svg>`;
            
            const titleSpan = document.createElement('span');
            titleSpan.className = 'title';
            titleSpan.textContent = c.title || 'İsimsiz Sohbet';
            
            const actionsDiv = document.createElement('div');
            actionsDiv.className = 'chat-actions';
            
            const delBtn = document.createElement('button');
            delBtn.className = 'btn-icon chat-action-btn';
            delBtn.innerHTML = `<svg viewBox="0 0 24 24" width="14" height="14" stroke="currentColor" stroke-width="2" fill="none"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>`;
            delBtn.title = "Sil";
            
            delBtn.onclick = (e) => {
                e.stopPropagation();
                showConfirmModal(
                    "Sohbeti Sil", 
                    "Bu sohbeti silmek istediğinize emin misiniz? Bu işlem geri alınamaz.", 
                    async () => {
                        await apiFetch(`/api/conversations/${c.id}`, { method: 'DELETE' });
                        if(currentConversationId === c.id) {
                            document.getElementById('new-chat-btn').click();
                        }
                        loadConversations();
                    }
                );
            };
            
            actionsDiv.appendChild(delBtn);
            
            btn.innerHTML = icon;
            btn.appendChild(titleSpan);
            btn.appendChild(actionsDiv);
            
            btn.onclick = () => loadConversation(c.id);
            list.appendChild(btn);
        });
    }
}

async function loadConversation(id) {
    const res = await apiFetch(`/api/conversations/${id}`);
    if (res.ok) {
        const msgs = await res.json();
        currentConversationId = id;
        localStorage.setItem('contextlite_last_conv', id);
        currentMessages = msgs.map(m => ({role: m.role, content: m.content}));
        
        chatMessages.innerHTML = '';
        
        // Find title and info
        const convList = await apiFetch('/api/conversations').then(r => r.json());
        const conv = convList.find(c => c.id === id);
        document.getElementById('chat-title').textContent = conv ? conv.title : 'Sohbet';
        
        const infoRes = await apiFetch(`/api/conversations/${id}/info`);
        if (infoRes.ok) {
            const info = await infoRes.json();
            document.getElementById('token-saver-checkbox').checked = info.token_saver_enabled ? true : false;
            currentProjectId = info.project_id || null;
            if (chatProjectSelect) chatProjectSelect.value = currentProjectId || '';
            
            // Set correct mode if saved in DB (if applicable)
            if (info.selected_mode) {
                modeSelect.value = info.selected_mode;
            }
        }

        msgs.forEach(m => {
            appendMessageToUI(m.role, m.content, false);
            if (m.provider_model && m.role === 'assistant') {
                const tokenInfo = m.token_info ? JSON.parse(m.token_info) : {in: 0, out: 0};
                appendMetadataToUI(chatMessages.lastElementChild, {
                    provider: m.provider_model.split('/')[0] || "Bulut",
                    model: m.provider_model.split('/')[1] || "Bilinmiyor",
                    tokens: tokenInfo,
                    token_saver_enabled: Boolean(tokenInfo.token_saver_enabled),
                    prevented_tokens: Number(tokenInfo.saved || 0),
                    savings_percent: Number(tokenInfo.savings_percent || 0),
                    time: m.response_time_ms,
                    cost: 0 
                });
            }
        });
        loadConversations(); 
        switchView('chat');
    }
}

// ============================================================================
// CHAT INTERACTION
// ============================================================================

modeSelect.addEventListener('change', async () => {
    modelSelect.classList.remove('hidden');
    modelSelect.innerHTML = '<option value="">Yükleniyor...</option>';
    
    try {
        const res = await apiFetch(`/api/models?provider=${modeSelect.value}`);
        const models = await res.json();

        if (!res.ok) {
            throw new Error(models.detail || 'Model listesi alınamadı.');
        }
        
        if (!models || models.length === 0) {
            const needsKey = ['openai', 'gemini'].includes(modeSelect.value);
            modelSelect.innerHTML = needsKey
                ? '<option value="">Önce Ayarlar’dan API anahtarı ekleyin.</option>'
                : '<option value="">Model bulunamadı.</option>';
            return;
        }
        
        let html = modeSelect.value === 'foundry'
            ? '<option value="">Otomatik model (önerilen)</option>'
            : '';
        models.forEach(m => {
            let label = m.name;
            if (['foundry', 'lm_studio', 'ollama'].includes(m.provider)) {
                label += m.isCached ? ' (Hazır)' : ' (İndirilebilir)';
            }
            html += `<option value="${m.id}">${label}</option>`;
        });
        modelSelect.innerHTML = html;
        
        const saved = localStorage.getItem(`saved_model_${modeSelect.value}`);
        if (saved) modelSelect.value = saved;
    } catch (e) {
        modelSelect.innerHTML = '<option value="">Hata oluştu</option>';
    }
});

modelSelect.addEventListener('change', () => {
    localStorage.setItem(`saved_model_${modeSelect.value}`, modelSelect.value);
});

// Trigger change on load
window.addEventListener('DOMContentLoaded', () => {
    const savedProvider = localStorage.getItem('saved_provider');
    if (savedProvider) modeSelect.value = savedProvider;
    modeSelect.dispatchEvent(new Event('change'));
});

modeSelect.addEventListener('change', () => {
    localStorage.setItem('saved_provider', modeSelect.value);
});

function appendMessageToUI(role, content, isStreaming = false) {
    const wrapperDiv = document.createElement('div');
    wrapperDiv.className = `message-wrapper ${role}`;
    
    const bubbleDiv = document.createElement('div');
    bubbleDiv.className = 'message-bubble';
    
    if (role === 'system') {
        bubbleDiv.textContent = content;
        wrapperDiv.appendChild(bubbleDiv);
        chatMessages.appendChild(wrapperDiv);
        return wrapperDiv;
    }
    
    // Güvenli XSS koruması ve formatlama
    let sanitizedContent = content.replace(/</g, "&lt;").replace(/>/g, "&gt;");
    
    // Markdown ve URL parse (Sadece https)
    sanitizedContent = sanitizedContent.replace(/\[([^\]]+)\]\((https:\/\/[^\s\)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer" style="color:var(--accent-primary); text-decoration:underline;">$1</a>');
    
    // Markdown formatına girmemiş ham URL'leri parse et (Sadece https)
    sanitizedContent = sanitizedContent.replace(/(^|\s)(https:\/\/[^\s<]+)/g, '$1<a href="$2" target="_blank" rel="noopener noreferrer" style="color:var(--accent-primary); text-decoration:underline;">$2</a>');
    
    sanitizedContent = sanitizedContent.replace(/\n/g, "<br>");
    
    bubbleDiv.innerHTML = sanitizedContent;
    wrapperDiv.appendChild(bubbleDiv);
    
    if (!isStreaming || role === 'user') {
        chatMessages.appendChild(wrapperDiv);
    }
    
    chatMessages.scrollTop = chatMessages.scrollHeight;
    return wrapperDiv;
}

function appendMetadataToUI(wrapperEl, meta) {
    if (!wrapperEl) return;
    const metaDiv = document.createElement('div');
    metaDiv.className = 'message-meta';
    
    const costStr = (meta.cost !== undefined && meta.cost !== null) ? `$${meta.cost.toFixed(6)}` : 'Bilinmiyor';
    const tokensIn = meta.tokens?.in || meta.prompt_tokens || 0;
    const tokensOut = meta.tokens?.out || meta.completion_tokens || 0;
    
    let reasonBadge = "";
    if (meta.routing_reason) {
        reasonBadge = `<span class="badge ${meta.is_free ? 'badge-success' : 'badge-default'}" style="margin-right: 8px;">ℹ ${meta.routing_reason}</span>`;
    }
    
    let tokenStr = `🪙 In: ${tokensIn}, Out: ${tokensOut}`;
    if (meta.provider === 'Foundry Local' && tokensIn === 0) {
        tokenStr = `🪙 Token ölçümü alınamadı`;
    }
    
    const sourceHtml = Array.isArray(meta.sources) && meta.sources.length
        ? `<div class="message-sources">📚 ${meta.sources.map(source => String(source)
            .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;').replace(/'/g, '&#039;')).join(' · ')}</div>`
        : '';
    const retrievalHtml = meta.retrieval_method
        ? `<span>🔎 ${meta.retrieval_method === 'semantic' ? 'Anlamsal RAG' : 'Kelime araması'}</span>`
        : '';
    const preventedTokens = Number(meta.prevented_tokens ?? meta.tokens?.saved ?? 0);
    const savingBase = tokensIn + preventedTokens;
    const savingPercent = Number.isFinite(Number(meta.savings_percent))
        ? Number(meta.savings_percent)
        : (savingBase ? (preventedTokens / savingBase * 100) : 0);
    const savingsHtml = meta.token_saver_enabled
        ? `<span class="token-saving-meta">Ana istem tasarrufu: ${preventedTokens.toLocaleString('tr-TR')} token (%${savingPercent.toLocaleString('tr-TR', {maximumFractionDigits: 1})})</span>`
        : '';

    metaDiv.innerHTML = `
        ${reasonBadge}
        <span>⚡ ${meta.provider} / ${meta.model}</span>
        <span>⏱ ${meta.time ? Math.round(meta.time) : 0}ms</span>
        <span>${tokenStr}</span>
        ${savingsHtml}
        ${retrievalHtml}
        ${sourceHtml}
    `;
    wrapperEl.appendChild(metaDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function appendSentPromptPreview(wrapperEl, data) {
    if (!wrapperEl || wrapperEl.querySelector('.sent-prompt-preview')) return;

    const details = document.createElement('details');
    details.className = 'sent-prompt-preview';

    const summary = document.createElement('summary');
    const sentTokens = Number(data.sent_prompt_tokens || 0).toLocaleString('tr-TR');
    const normalTokens = Number(data.normal_prompt_tokens || 0).toLocaleString('tr-TR');
    const originalUserTokens = Number(data.original_user_tokens || 0).toLocaleString('tr-TR');
    const optimizedUserTokens = Number(data.optimized_user_tokens || 0).toLocaleString('tr-TR');
    const optimizerModel = String(data.optimizer_model || '').trim();
    const optimizerTokenizer = String(data.optimizer_tokenizer || '').trim();
    const validation = data.optimization_validation || {};
    const validationIssues = Array.isArray(validation.issues) ? validation.issues : [];
    const promptWasShort = validationIssues.includes('prompt_already_short') || Number(data.original_user_tokens || 0) < 18;
    const wasNotShorter = validationIssues.includes('not_shorter');
    summary.textContent = data.optimization_applied
        ? `Token tasarrufu · ${originalUserTokens} → ${optimizedUserTokens} token${optimizerModel ? ` · ${optimizerModel}` : ''}${validation.valid ? ' · görev doğrulandı ✓' : ''}`
        : (promptWasShort
            ? `Token tasarrufu · istem zaten kısa (${originalUserTokens} token)`
            : `Token tasarrufu uygulanmadı · orijinal istem korundu (${originalUserTokens} token)`);

    const body = document.createElement('div');
    body.className = 'sent-prompt-preview-body';

    if (data.optimization_applied) {
        const comparison = document.createElement('div');
        comparison.className = 'prompt-optimization-comparison';

        const createPromptColumn = (label, tokenCount, value, optimized = false) => {
            const column = document.createElement('section');
            column.className = `prompt-optimization-column${optimized ? ' is-optimized' : ''}`;
            const heading = document.createElement('div');
            heading.className = 'prompt-optimization-heading';
            heading.textContent = `${label} · ${tokenCount} token`;
            const text = document.createElement('pre');
            text.textContent = String(value || '');
            column.append(heading, text);
            return column;
        };

        comparison.append(
            createPromptColumn('Orijinal istem', originalUserTokens, data.original_user_prompt),
            createPromptColumn('Optimize edilmiş istem', optimizedUserTokens, data.optimized_user_prompt, true)
        );
        body.appendChild(comparison);
    } else {
        const unchangedNotice = document.createElement('p');
        unchangedNotice.className = 'prompt-optimization-notice';
        if (promptWasShort) {
            unchangedNotice.textContent = 'İstem gerçekten kısa olduğu için ek bir optimizasyon işlemi yapılmadı.';
        } else if (wasNotShorter) {
            unchangedNotice.textContent = 'Yerel model daha kısa bir prompt üretemedi; sahte tasarruf göstermemek için orijinal istem gönderildi.';
        } else if (validationIssues.some(issue => issue.includes('answer') || issue.includes('question_missing'))) {
            unchangedNotice.textContent = 'Üretilen metin prompt yerine cevap içerdiği için güvenlik kontrolü tarafından reddedildi; orijinal istem gönderildi.';
        } else if (validationIssues.length) {
            unchangedNotice.textContent = 'Kısaltılmış sürüm aynı görevi koruma kontrolünden geçemediği için reddedildi; orijinal istem gönderildi.';
        } else {
            unchangedNotice.textContent = 'Optimizasyon uygulanamadı; orijinal istem değiştirilmeden gönderildi.';
        }
        body.appendChild(unchangedNotice);
    }

    const technicalDetails = document.createElement('details');
    technicalDetails.className = 'technical-prompt-details';
    const technicalSummary = document.createElement('summary');
    technicalSummary.textContent = `Teknik ayrıntılar · ana modele ${sentTokens} token (normal: ${normalTokens})${optimizerTokenizer ? ` · ${optimizerTokenizer}` : ''}`;
    const technicalPrompt = document.createElement('pre');
    technicalPrompt.textContent = String(data.sent_prompt || '');
    technicalDetails.append(technicalSummary, technicalPrompt);
    body.appendChild(technicalDetails);

    details.append(summary, body);
    wrapperEl.appendChild(details);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

chatInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        chatForm.dispatchEvent(new Event('submit'));
    }
});

sendButton.disabled = true;

chatInput.addEventListener('input', function() {
    this.style.height = 'auto';
    this.style.height = (this.scrollHeight) + 'px';
    if(this.value === '') this.style.height = 'auto';
    sendButton.disabled = this.value.trim() === '';
});

chatForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const content = chatInput.value.trim();
    if (!content) return;
    
    const welcome = document.getElementById('welcome-message');
    if (welcome) welcome.remove();
    
    const userWrapperDiv = appendMessageToUI('user', content);
    chatInput.value = '';
    chatInput.style.height = 'auto';
    
    const mode = modeSelect.value || 'foundry';
    const customModel = modelSelect.value;
    const payloadMsgs = [{ role: "user", content: content }];
    
    const assistWrapperDiv = appendMessageToUI('assistant', '', true);
    const bubbleDiv = assistWrapperDiv.querySelector('.message-bubble');
    chatMessages.appendChild(assistWrapperDiv);
    
    let responseText = "";
    sendButton.disabled = true;
    const originalSendIcon = sendButton.innerHTML;
    sendButton.innerHTML = `<svg viewBox="0 0 24 24" width="20" height="20" stroke="currentColor" stroke-width="2" fill="none" class="spin"><circle cx="12" cy="12" r="10" stroke-dasharray="32" stroke-dashoffset="16"/></svg>`;
    
    try {
        const response = await fetch('/api/chat/stream', {
            method: 'POST',
            headers: { 
                'Content-Type': 'application/json',
                'X-CSRF-Token': csrfToken
            },
            body: JSON.stringify({
                conversation_id: currentConversationId,
                project_id: currentProjectId,
                messages: payloadMsgs,
                provider: mode,
                model: customModel ? customModel : undefined,
                mode: ['foundry', 'lm_studio', 'ollama'].includes(mode) ? 'Sadece Yerel' : 'Modeli kendim seçerim',
                custom_model: customModel ? `${mode}/${customModel}` : undefined,
                request_id: (window.crypto && crypto.randomUUID) ? crypto.randomUUID() : `req-${Date.now()}-${Math.random()}`,
                token_saver_enabled: document.getElementById('token-saver-checkbox').checked
            })
        });
        
        if (response.status === 401 || response.status === 403) {
            window.location.href = '/login';
            return;
        }
        
        if (!response.ok) {
            bubbleDiv.innerHTML = `<span style="color:var(--error);">Sunucu hatası (${response.status})</span>`;
            return;
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder("utf-8");
        
        let metadata = null;
        let convUpdated = false;

        let sseBuffer = "";
        while (true) {
            const { value, done } = await reader.read();
            if (done) break;

            sseBuffer += decoder.decode(value, { stream: true });
            const events = sseBuffer.split(/\r?\n\r?\n/);
            sseBuffer = events.pop() || "";

            for (const eventBlock of events) {
              for (let line of eventBlock.split(/\r?\n/)) {
                if (line.startsWith('data: ') && line !== 'data: [DONE]') {
                    const isScrolledToBottom = chatMessages.scrollHeight - chatMessages.clientHeight <= chatMessages.scrollTop + 50;
                    try {
                        const data = JSON.parse(line.substring(6));
                        
                        if (data.conversation_id) {
                            currentConversationId = data.conversation_id;
                            localStorage.setItem('contextlite_last_conv', currentConversationId);
                            convUpdated = true;
                        }
                        else if (data.is_prompt_preview) {
                            appendSentPromptPreview(userWrapperDiv, data);
                        }
                        else if (data.error) {
                            let errorHtml = `<br><span style="color:var(--error);">${data.error}</span>`;
                            if (data.category === 'billing_required') {
                                errorHtml += `<br><br><a href="https://platform.openai.com/account/billing" target="_blank" style="color: var(--primary); text-decoration: underline; font-weight: 500;">OpenAI Faturalandırma Ayarlarına Git ↗</a>`;
                            }
                            responseText += errorHtml;
                            bubbleDiv.innerHTML = responseText;
                        }
                        else if (data.is_metadata) {
                            metadata = data;
                        }
                        else if (data.status) {
                            if (!responseText) bubbleDiv.textContent = data.status;
                        }
                        else if (data.content) {
                            let textChunk = data.content;
                            textChunk = textChunk.replace(/</g, "&lt;").replace(/>/g, "&gt;");
                            textChunk = textChunk.replace(/\n/g, "<br>");
                            responseText += textChunk;
                            bubbleDiv.innerHTML = responseText;
                        }
                    } catch (e) {
                        console.error("JSON Parse Error:", e, line);
                    }
                    if (isScrolledToBottom) {
                        chatMessages.scrollTop = chatMessages.scrollHeight;
                    }
                }
              }
            }
        }
        
        if (metadata) appendMetadataToUI(assistWrapperDiv, metadata);
        if (convUpdated || !currentConversationId) loadConversations();
        
    } catch (err) {
        bubbleDiv.innerHTML = `<span style="color:var(--error);">Ağ hatası oluştu: ${err}</span>`;
    } finally {
        sendButton.innerHTML = originalSendIcon;
        sendButton.disabled = chatInput.value.trim() === '';
    }
});

// ============================================================================
// SETTINGS: PROVIDERS & BUDGET
// ============================================================================

async function loadProviders() {
    const res = await apiFetch('/api/providers');
    if (!res.ok) return;
    const providers = (await res.json()).filter(provider => ['openai', 'gemini'].includes(provider.id));
    
    const container = document.getElementById('providers-container');
    if (!container) return;
    container.innerHTML = '';
    
    providers.forEach(p => {
        const card = document.createElement('div');
        card.className = 'card provider-card';
        
        let badgeClass = 'badge-default';
        let badgeText = 'Yapılandırılmadı';
        
        if (p.has_key) {
            if (p.status_code === 'verified') {
                badgeClass = 'badge-success';
                badgeText = 'Bağlantı doğrulandı';
            } else if (p.status_code === 'billing_required') {
                badgeClass = 'badge-warning';
                badgeText = 'API kredisi gerekli';
            } else if (p.status_code === 'invalid_api_key') {
                badgeClass = 'badge-error';
                badgeText = 'Anahtar geçersiz';
            } else if (p.status_code === 'rate_limited') {
                badgeClass = 'badge-warning';
                badgeText = 'Geçici hız sınırı';
            } else if (p.status_code === 'model_unavailable') {
                badgeClass = 'badge-warning';
                badgeText = 'Model kullanılamıyor';
            } else if (p.status_code === 'unauthorized') {
                badgeClass = 'badge-error';
                badgeText = 'Yetki yetersiz';
            } else if (p.status_code === 'untested') {
                badgeClass = 'badge-default';
                badgeText = 'Kaydedildi — test edilmedi';
            } else {
                badgeClass = 'badge-error';
                badgeText = 'Bağlantı hatası';
            }
        }
        
        let actionsHtml = '';
        if (p.requires_key) {
            const providerHelp = p.id === 'openai'
                ? 'OpenAI hesabınızdan oluşturduğunuz gizli API anahtarı.'
                : 'Google AI Studio üzerinden oluşturduğunuz Gemini API anahtarı.';
            actionsHtml = `
                <div class="form-group">
                    <label for="key-${p.id}">API Anahtarı</label>
                    <input type="password" id="key-${p.id}" class="form-input" autocomplete="off" spellcheck="false" placeholder="${p.has_key ? 'Yeni anahtarla değiştirmek için buraya yazın' : 'API anahtarını buraya yapıştırın'}">
                    <span class="input-hint">${providerHelp} Anahtar kaydedildikten sonra ekranda tekrar gösterilmez.</span>
                </div>
                <div class="provider-actions">
                    <button class="btn btn-primary" onclick="saveProvider('${p.id}')">Kaydet</button>
                    ${p.has_key ? `<button class="btn btn-secondary" style="color:var(--error);" onclick="deleteProvider('${p.id}')">Sil</button>` : ''}
                </div>
            `;
        }
        
        const testBtnHtml = p.has_key
            ? `<button class="btn btn-secondary btn-block" style="margin-top:12px;" onclick="testProvider('${p.id}', this)">Bağlantıyı Test Et</button>`
            : '';
            
        card.innerHTML = `
            <div class="provider-header">
                <h4>${p.name}</h4>
                <span class="badge ${badgeClass}">${badgeText}</span>
            </div>
            ${actionsHtml}
            <div id="test-res-${p.id}" style="font-size:13px; margin-top:8px;"></div>
            ${testBtnHtml}
        `;
        container.appendChild(card);
    });
}

window.saveProvider = async (id) => {
    const key = document.getElementById(`key-${id}`).value;
    if (!key) {
        alert("Lütfen bir anahtar girin.");
        return;
    }
    const res = await apiFetch(`/api/providers/${id}`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({api_key: key})
    });
    const data = await res.json().catch(() => ({}));
    if (res.ok) {
        await loadProviders();
    } else {
        alert("Hata: " + (data.detail || "API anahtarı kaydedilemedi."));
    }
};

window.deleteProvider = async (id) => {
    showConfirmModal("Anahtarı Sil", "Bu API anahtarını silmek istediğinize emin misiniz?", async () => {
        const res = await apiFetch(`/api/providers/${id}`, { method: 'DELETE' });
        if (res.ok) loadProviders();
    });
};

window.testProvider = async (id, btn) => {
    const resEl = document.getElementById(`test-res-${id}`);
    if(btn) btn.disabled = true;
    resEl.innerHTML = '<span style="color:var(--text-tertiary);">Test ediliyor...</span>';
    try {
        const res = await apiFetch(`/api/providers/${id}/test`, { method: 'POST' });
        const data = await res.json();
        
        if (res.ok && data.success) {
            resEl.innerHTML = `<span style="color:var(--success);">${data.message}</span>`;
            setTimeout(() => loadProviders(), 1500); // Reload to update badges
        } else {
            resEl.textContent = data.detail || data.message || 'Bağlantı testi başarısız oldu.';
            resEl.style.color = 'var(--error)';
            setTimeout(() => loadProviders(), 1500); // Reload to update badges
        }
    } catch(e) {
        resEl.innerHTML = `<span style="color:var(--error);">Bağlantı testi başarısız oldu.</span>`;
    } finally {
        if(btn) btn.disabled = false;
    }
};

async function loadBudget() {
    const dailyInput = document.getElementById('daily-limit');
    const monthlyInput = document.getElementById('monthly-limit');
    if (!dailyInput || !monthlyInput) return;
    const res = await apiFetch('/api/budget');
    if (!res.ok) return;
    const data = await res.json();
    dailyInput.value = data.daily_limit || '';
    monthlyInput.value = data.monthly_limit || '';
}

window.saveBudget = async () => {
    const daily = document.getElementById('daily-limit').value;
    const monthly = document.getElementById('monthly-limit').value;
    
    const res = await apiFetch('/api/budget', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            daily_limit: daily ? parseFloat(daily) : null,
            monthly_limit: monthly ? parseFloat(monthly) : null
        })
    });
    
    if(res.ok) alert("Bütçe ayarları başarıyla kaydedildi.");
};

// ============================================================================
// USAGE STATS
// ============================================================================

async function loadUsage() {
    const [sumRes, histRes] = await Promise.all([
        apiFetch('/api/usage/summary'),
        apiFetch('/api/usage/history')
    ]);
    
    if (sumRes.ok) {
        const sum = await sumRes.json();
        document.getElementById('stat-today-reqs').textContent = sum.today_requests;
        document.getElementById('stat-month-reqs').textContent = sum.month_requests;
        document.getElementById('stat-local-cloud').textContent = `${sum.local_requests} / ${sum.cloud_requests}`;
        document.getElementById('stat-tokens').textContent = sum.total_tokens;
        document.getElementById('stat-cost').textContent = `$${sum.total_cost.toFixed(6)}`;
        document.getElementById('stat-prevented-cost').textContent = `$${(sum.prevented_cost || 0).toFixed(6)}`;
        document.getElementById('stat-prevented-tokens').textContent = sum.prevented_tokens || 0;
        document.getElementById('stat-avg-time').textContent = `${Math.round(sum.avg_response_time)} ms`;
        
        // Update Dashboard Summary
        const dashReqs = document.getElementById('dash-stat-reqs');
        const dashCost = document.getElementById('dash-stat-cost');
        if (dashReqs) dashReqs.textContent = sum.month_requests;
        if (dashCost) dashCost.textContent = `$${sum.total_cost.toFixed(6)}`;
    }
    
    if (histRes.ok) {
        const hist = await histRes.json();
        const tbody = document.getElementById('usage-history-body');
        tbody.innerHTML = '';
        hist.forEach(h => {
            const tr = document.createElement('tr');
            const d = new Date(h.timestamp + "Z");
            const costStr = (h.actual_cost !== null) ? `$${h.actual_cost.toFixed(6)}` : 'Bilinmiyor';
            const statusHtml = h.success ? '<span class="badge badge-success">Başarılı</span>' : '<span class="badge badge-default" style="color:var(--error);">Hata</span>';
            
            tr.innerHTML = `
                <td><div style="font-size:13px">${d.toLocaleDateString()}</div><div style="color:var(--text-secondary);font-size:11px">${d.toLocaleTimeString()}</div></td>
                <td><div style="font-weight:500">${h.provider} / ${h.model}</div><div style="font-size:11px;color:var(--text-secondary)">${h.mode}</div></td>
                <td>${statusHtml}</td>
                <td>${h.prompt_tokens || 0} / ${h.completion_tokens || 0}</td>
                <td>${h.prevented_tokens ? '<span class="success-text">' + h.prevented_tokens + ' tok</span>' : '-'}</td>
                <td>${h.response_time_ms ? Math.round(h.response_time_ms) : 0}ms</td>
                <td>${costStr}</td>
            `;
            tbody.appendChild(tr);
        });
    }
}

// ============================================================================
// PROJECTS
// ============================================================================

async function loadProjects() {
    const res = await apiFetch('/api/projects');
    if (!res.ok) return;
    const projects = await res.json();
    
    const container = document.getElementById('projects-container');
    const dashContainer = document.getElementById('dash-projects-container');
    
    if(container) {
        container.innerHTML = '';
        if (dashContainer) dashContainer.innerHTML = '';
        
        if (projects.length === 0) {
            container.innerHTML = '<div style="grid-column: 1 / -1; text-align: center; color: var(--text-secondary); padding: 40px 0;">Henüz hiç projeniz yok.</div>';
            if(dashContainer) dashContainer.innerHTML = '<div style="grid-column: 1 / -1; text-align: center; color: var(--text-secondary); padding: 20px; background: var(--bg-surface); border-radius: var(--radius-md);">Henüz bir projen yok, ilk projenizi oluşturun.</div>';
        }
        projects.forEach((p, index) => {
            const cardHtml = `
                <div class="provider-header">
                    <h4 style="margin:0; font-size: 16px;">${p.name}</h4>
                </div>
                <p style="color: var(--text-secondary); font-size: 13px; margin-top: 8px; margin-bottom: 16px; min-height: 40px;">${p.description || 'Açıklama yok'}</p>
                <div style="font-size: 11px; color: var(--text-tertiary); margin-bottom: 16px;">Son güncelleme: ${new Date(p.updated_at + "Z").toLocaleDateString()}</div>
                
                <div style="display: flex; gap: 8px;">
                    <button class="btn btn-secondary" style="flex:1;" onclick="openEditProjectModal('${p.id}', '${p.name.replace(/'/g, "\\'")}', '${(p.description||'').replace(/'/g, "\\'")}')">Düzenle</button>
                    <button class="btn btn-secondary" style="color:var(--error);" onclick="deleteProject('${p.id}')">
                        <svg viewBox="0 0 24 24" width="16" height="16" stroke="currentColor" stroke-width="2" fill="none"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
                    </button>
                </div>
            `;
            
            const card = document.createElement('div');
            card.className = 'card provider-card';
            card.style.position = 'relative';
            card.innerHTML = cardHtml;
            container.appendChild(card);
            
            if (dashContainer && index < 3) {
                const dashCard = document.createElement('div');
                dashCard.className = 'card provider-card';
                dashCard.innerHTML = cardHtml;
                dashContainer.appendChild(dashCard);
            }
        });
        
        // Update files project select dropdown
        const filesSelect = document.getElementById('files-project-select');
        if (filesSelect) {
            const currentVal = filesSelect.value;
            filesSelect.innerHTML = '<option value="">Tüm Projeler</option>';
            projects.forEach(p => {
                const opt = document.createElement('option');
                opt.value = p.id;
                opt.textContent = p.name;
                filesSelect.appendChild(opt);
            });
            if (currentVal && projects.find(p => p.id === currentVal)) {
                filesSelect.value = currentVal;
            }
        }

        if (chatProjectSelect) {
            const selectedProject = currentProjectId;
            chatProjectSelect.classList.toggle('hidden', projects.length === 0);
            chatProjectSelect.innerHTML = '<option value="">Belge kullanma</option>';
            projects.forEach(p => {
                const opt = document.createElement('option');
                opt.value = p.id;
                opt.textContent = `Belge: ${p.name}`;
                chatProjectSelect.appendChild(opt);
            });
            if (selectedProject && projects.find(p => p.id === selectedProject)) {
                chatProjectSelect.value = selectedProject;
            } else {
                currentProjectId = null;
            }
        }
    }
}

if (chatProjectSelect) {
    chatProjectSelect.addEventListener('change', () => {
        currentProjectId = chatProjectSelect.value || null;
        document.getElementById('new-chat-btn').click();
        document.getElementById('chat-title').textContent = currentProjectId
            ? chatProjectSelect.options[chatProjectSelect.selectedIndex].textContent
            : 'Sohbet';
    });
}

window.openCreateProjectModal = () => {
    document.getElementById('project-modal-title').textContent = 'Yeni Proje';
    document.getElementById('project-id-input').value = '';
    document.getElementById('project-name-input').value = '';
    document.getElementById('project-desc-input').value = '';
    document.getElementById('project-modal').classList.remove('hidden');
};

window.openEditProjectModal = (id, name, desc) => {
    document.getElementById('project-modal-title').textContent = 'Projeyi Düzenle';
    document.getElementById('project-id-input').value = id;
    document.getElementById('project-name-input').value = name;
    document.getElementById('project-desc-input').value = desc;
    document.getElementById('project-modal').classList.remove('hidden');
};

window.closeProjectModal = () => {
    document.getElementById('project-modal').classList.add('hidden');
};

window.saveProject = async () => {
    const id = document.getElementById('project-id-input').value;
    const name = document.getElementById('project-name-input').value.trim();
    const desc = document.getElementById('project-desc-input').value.trim();
    
    if(!name) {
        alert("Proje adı boş olamaz.");
        return;
    }
    
    let res;
    let projectId = id;
    if (id) {
        res = await apiFetch(`/api/projects/${id}`, {
            method: 'PUT',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({name: name, description: desc})
        });
    } else {
        res = await apiFetch(`/api/projects`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({name: name, description: desc})
        });
    }
    
    if (res.ok) {
        if (!id) {
            const data = await res.json();
            projectId = data.project_id;
        }
        
        // Handle file uploads
        const fileInput = document.getElementById('project-files-input');
        if (fileInput && fileInput.files.length > 0 && projectId) {
            const formData = new FormData();
            for (let i = 0; i < fileInput.files.length; i++) {
                formData.append('files', fileInput.files[i]);
            }
            try {
                // Use apiFetch to correctly include CSRF and Authorization headers
                const uploadRes = await apiFetch(`/api/projects/${projectId}/files`, {
                    method: 'POST',
                    body: formData
                });
                if (!uploadRes.ok) {
                    const err = await uploadRes.json();
                    alert("Proje oluşturuldu ancak dosyalar yüklenirken hata oluştu: " + err.detail);
                }
            } catch(e) {
                console.error(e);
            }
        }
        
        closeProjectModal();
        loadProjects();
        // Clear files input
        if (fileInput) fileInput.value = '';
    } else {
        const data = await res.json();
        alert("Hata: " + data.detail);
    }
};

window.deleteProject = (id) => {
    showConfirmModal("Projeyi Sil", "Bu projeyi silmek istediğinize emin misiniz? Projeye bağlı tüm sohbetler de silinecektir.", async () => {
        const res = await apiFetch(`/api/projects/${id}`, { method: 'DELETE' });
        if (res.ok) {
            loadProjects();
            loadConversations(); // update sidebar
        } else {
            alert("Silme işlemi başarısız.");
        }
    });
};

// ============================================================================
// FOUNDRY MODEL MANAGER
// ============================================================================

function formatModelSize(sizeMb) {
    const value = Number(sizeMb || 0);
    if (!value) return 'Boyut bilgisi yok';
    return value >= 1024 ? `${(value / 1024).toFixed(1)} GB` : `${Math.round(value)} MB`;
}

function scheduleModelManagerRefresh(delay = 1500) {
    if (modelManagerTimer) clearTimeout(modelManagerTimer);
    modelManagerTimer = setTimeout(() => {
        if (!document.getElementById('view-models').classList.contains('hidden')) {
            loadModelManager();
        }
    }, delay);
}

async function installFoundryModel(modelId) {
    const statusEl = document.getElementById('model-manager-status');
    statusEl.textContent = `${modelId} kurulum sırasına alınıyor…`;
    try {
        const res = await apiFetch('/api/models/install', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({model_id: modelId})
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) {
            statusEl.textContent = data.detail || 'Model kurulumu başlatılamadı.';
            return;
        }
        await loadModelManager();
    } catch (error) {
        statusEl.textContent = `Bağlantı hatası: ${error.message || error}`;
    }
}

async function cancelFoundryModelInstall(modelId) {
    const statusEl = document.getElementById('model-manager-status');
    statusEl.textContent = `${modelId} kurulumu iptal ediliyor…`;
    try {
        const res = await apiFetch(`/api/models/install/${encodeURIComponent(modelId)}`, {
            method: 'DELETE'
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) {
            statusEl.textContent = data.detail || 'Model kurulumu iptal edilemedi.';
            return;
        }
        await loadModelManager();
    } catch (error) {
        statusEl.textContent = `İptal bağlantı hatası: ${error.message || error}`;
    }
}

function removeFoundryModel(modelId) {
    showConfirmModal(
        'Modeli Kaldır',
        `${modelId} modelini ve indirilen dosyalarını bilgisayardan kaldırmak istediğinize emin misiniz?`,
        async () => {
            const statusEl = document.getElementById('model-manager-status');
            statusEl.textContent = `${modelId} kaldırılıyor…`;
            try {
                const res = await apiFetch(`/api/models/${encodeURIComponent(modelId)}`, {
                    method: 'DELETE'
                });
                const data = await res.json().catch(() => ({}));
                if (!res.ok) {
                    statusEl.textContent = data.detail || 'Model kaldırılamadı.';
                    return;
                }
                statusEl.textContent = data.message || `${modelId} kaldırıldı.`;
                await loadModelManager();
                await loadModels();
            } catch (error) {
                statusEl.textContent = `Kaldırma hatası: ${error.message || error}`;
            }
        }
    );
}

async function loadModelManager() {
    const grid = document.getElementById('models-grid');
    const statusEl = document.getElementById('model-manager-status');
    if (!grid || !statusEl) return;

    try {
        const [modelsRes, jobsRes] = await Promise.all([
            apiFetch('/api/models?provider=foundry'),
            apiFetch('/api/models/installations')
        ]);
        if (!modelsRes.ok || !jobsRes.ok) throw new Error('Model listesi alınamadı.');

        const models = await modelsRes.json();
        const jobs = await jobsRes.json();
        const jobsByModel = new Map(jobs.map(job => [job.model_id, job]));
        const hasActiveJob = jobs.some(job => ['queued', 'downloading', 'cancelling'].includes(job.status));
        const queuedCount = jobs.filter(job => job.status === 'queued').length;
        const downloadingCount = jobs.filter(job => job.status === 'downloading').length;
        const installedCount = models.filter(model => model.isCached || model.isLoaded).length;

        const queueStatus = hasActiveJob
            ? ` · ${downloadingCount ? '1 model indiriliyor' : 'İndirme hazırlanıyor'}${queuedCount ? ` · ${queuedCount} model sırada` : ''}`
            : '';
        statusEl.textContent = `${models.length} model bulundu · ${installedCount} model kurulu${queueStatus}`;
        grid.innerHTML = '';

        models.forEach(model => {
            const job = jobsByModel.get(model.id);
            const installed = Boolean(model.isCached || model.isLoaded || job?.status === 'completed');
            const active = Boolean(job && ['queued', 'downloading', 'cancelling'].includes(job.status));
            const failed = job?.status === 'failed';
            const cancelled = job?.status === 'cancelled';

            const card = document.createElement('article');
            card.className = 'card model-card';

            const header = document.createElement('div');
            header.className = 'model-card-header';
            const title = document.createElement('h4');
            title.textContent = model.id;
            const badge = document.createElement('span');
            badge.className = `badge ${installed ? 'badge-success' : (failed ? 'badge-error' : (active ? 'badge-warning' : 'badge-default'))}`;
            badge.textContent = installed
                ? (model.isLoaded ? 'Hazır' : 'Kuruldu')
                : (failed ? 'Hata' : (cancelled ? 'İptal' : (active ? 'Kuruluyor' : 'Kurulmadı')));
            header.append(title, badge);

            const details = document.createElement('div');
            details.className = 'model-card-details';
            const detailParts = [formatModelSize(model.fileSizeMb)];
            if (model.contextLength) detailParts.push(`${Number(model.contextLength).toLocaleString('tr-TR')} bağlam`);
            if (model.capabilities) detailParts.push(model.capabilities);
            details.textContent = detailParts.join(' · ');

            const progressArea = document.createElement('div');
            progressArea.className = 'model-progress-area';
            if (active) {
                const progress = Math.max(0, Math.min(100, Number(job.progress || 0)));
                const label = document.createElement('div');
                label.className = 'model-progress-label';
                label.textContent = job.status === 'queued'
                    ? 'Sırada…'
                    : (job.status === 'cancelling' ? 'İptal ediliyor…' : `%${Math.round(progress)} indiriliyor`);
                const track = document.createElement('div');
                track.className = 'model-progress-track';
                const bar = document.createElement('div');
                bar.className = 'model-progress-bar';
                bar.style.width = `${progress}%`;
                track.appendChild(bar);
                progressArea.append(label, track);
            } else if (failed) {
                progressArea.className += ' model-install-error';
                progressArea.textContent = job.error || 'Kurulum başarısız oldu.';
            } else if (cancelled) {
                progressArea.textContent = 'Kurulum iptal edildi.';
            }

            const button = document.createElement('button');
            button.className = installed ? 'btn btn-danger btn-sm' : 'btn btn-primary btn-sm';
            button.textContent = installed
                ? 'Kaldır'
                : (active ? (job.status === 'queued' ? 'Sırada…' : 'Kuruluyor…') : (failed ? 'Tekrar Dene' : 'Kur'));
            button.disabled = active;
            if (!button.disabled) {
                button.addEventListener('click', () => {
                    if (installed) removeFoundryModel(model.id);
                    else installFoundryModel(model.id);
                });
            }

            const actions = document.createElement('div');
            actions.className = 'model-card-actions';
            actions.appendChild(button);
            if (active) {
                const cancelButton = document.createElement('button');
                cancelButton.className = 'btn btn-danger btn-sm';
                cancelButton.textContent = job.status === 'cancelling' ? 'İptal Ediliyor…' : 'İptal Et';
                cancelButton.disabled = job.status === 'cancelling';
                if (!cancelButton.disabled) {
                    cancelButton.addEventListener('click', () => cancelFoundryModelInstall(model.id));
                }
                actions.appendChild(cancelButton);
            }

            card.append(header, details);
            if (progressArea.childNodes.length || progressArea.textContent) card.appendChild(progressArea);
            card.appendChild(actions);
            grid.appendChild(card);
        });

        if (hasActiveJob) scheduleModelManagerRefresh();
    } catch (error) {
        statusEl.textContent = error.message || 'Model listesi yüklenemedi.';
        grid.innerHTML = '';
    }
}

const modelsRefreshBtn = document.getElementById('models-refresh-btn');
if (modelsRefreshBtn) modelsRefreshBtn.addEventListener('click', loadModelManager);

// ============================================================================
// INITIALIZATION
// ============================================================================
checkAuth();

// ============================================================================
// TOKEN SAVER LOGIC
// ============================================================================
const tsInput = document.getElementById('ts-input-prompt');
const tsOutput = document.getElementById('ts-output-prompt');
const tsOrigTokens = document.getElementById('ts-original-tokens');
const tsOptStats = document.getElementById('ts-optimized-stats');
const tsOptimizeBtn = document.getElementById('ts-optimize-btn');
const tsStopBtn = document.getElementById('ts-stop-btn');
const tsClearBtn = document.getElementById('ts-clear-btn');
const tsCopyBtn = document.getElementById('ts-copy-btn');
const tsUseInChatBtn = document.getElementById('ts-use-in-chat-btn');
const tsModelSelect = document.getElementById('ts-model-select');

let tsAbortController = null;

async function loadTSModels() {
    if (!tsModelSelect) return;
    try {
        const res = await apiFetch('/api/models?provider=local');
        if (res.ok) {
            const models = await res.json();
            tsModelSelect.innerHTML = '<option value="">Foundry Modeli Seç...</option>';
            models.forEach(m => {
                const modelId = typeof m === 'string' ? m : (m.id || m.name || '');
                if (!modelId) return;
                const opt = document.createElement('option');
                opt.value = modelId;
                const modelName = typeof m === 'string' ? m : (m.name || modelId);
                const status = typeof m === 'object' && m.status === 'ready' ? ' (Hazır)' : '';
                opt.textContent = `${modelName}${status}`;
                tsModelSelect.appendChild(opt);
            });
            if(models.length > 0) tsModelSelect.selectedIndex = 1;
        }
    } catch(e) {}
}
// Load when viewing token saver
if (navTokenSaver) {
    navTokenSaver.addEventListener('click', () => {
        loadTSModels();
    });
}

if (tsInput) {
    tsInput.addEventListener('input', () => {
        const text = tsInput.value.trim();
        const tokens = text ? Math.floor(text.split(/\s+/).length * 1.3) : 0;
        tsOrigTokens.textContent = `${tokens} Yaklaşık Token`;
    });
}

if (tsClearBtn) {
    tsClearBtn.addEventListener('click', () => {
        tsInput.value = '';
        tsOutput.value = '';
        tsOrigTokens.textContent = '0 Yaklaşık Token';
        tsOptStats.style.display = 'none';
        tsCopyBtn.disabled = true;
        tsUseInChatBtn.disabled = true;
    });
}

if (tsStopBtn) {
    tsStopBtn.addEventListener('click', () => {
        if (tsAbortController) {
            tsAbortController.abort();
            tsAbortController = null;
        }
    });
}

if (tsOptimizeBtn) {
    tsOptimizeBtn.addEventListener('click', async () => {
        const text = tsInput.value.trim();
        const selectedModel = tsModelSelect ? tsModelSelect.value : null;
        const selectedProvider = document.getElementById('ts-provider-select') ? document.getElementById('ts-provider-select').value : 'foundry';
        
        if (!text) {
            alert("Lütfen kısaltılacak metni girin.");
            return;
        }
        if (!selectedModel) {
            alert("Lütfen bir yerel model seçin.");
            return;
        }
        
        tsOptimizeBtn.classList.add('hidden');
        if(tsStopBtn) tsStopBtn.classList.remove('hidden');
        
        tsAbortController = new AbortController();
        
        try {
            const projectId = currentProjectId;
            
            const res = await apiFetch('/api/optimize-prompt', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    project_id: projectId,
                    prompt: text,
                    provider: selectedProvider,
                    model: selectedModel
                }),
                signal: tsAbortController.signal
            });
            
            const data = await res.json();
            if (res.ok) {
                tsOutput.value = data.optimized_prompt;
                tsOrigTokens.textContent = `${data.original_tokens} Token · ${data.tokenizer_name}`;
                tsOptStats.textContent = `%${data.saved_percent} Tasarruf (${data.saved_tokens} Token) · Görev Doğrulandı ✓`;
                tsOptStats.style.display = 'inline-block';
                tsCopyBtn.disabled = false;
                tsUseInChatBtn.disabled = false;
            } else {
                alert("Hata: " + (data.detail || "Optimizasyon başarısız"));
            }
        } catch (e) {
            if (e.name === 'AbortError') {
                tsOutput.value = "İşlem iptal edildi.";
            } else {
                alert("Ağ hatası oluştu veya model cevap vermedi.");
            }
        } finally {
            tsOptimizeBtn.classList.remove('hidden');
            if(tsStopBtn) tsStopBtn.classList.add('hidden');
            tsAbortController = null;
        }
    });
}

if (tsCopyBtn) {
    tsCopyBtn.addEventListener('click', () => {
        if (tsOutput.value) {
            navigator.clipboard.writeText(tsOutput.value);
            const originalText = tsCopyBtn.innerHTML;
            tsCopyBtn.innerHTML = 'Kopyalandı!';
            setTimeout(() => { tsCopyBtn.innerHTML = originalText; }, 2000);
        }
    });
}

if (tsUseInChatBtn) {
    tsUseInChatBtn.addEventListener('click', () => {
        if (tsOutput.value) {
            document.getElementById('chat-input').value = tsOutput.value;
            switchView('chat');
        }
    });
}

window.loadFilesList = async () => {
    const projSelect = document.getElementById('files-project-select');
    const table = document.getElementById('files-table');
    const tbody = document.getElementById('files-table-body');
    const warning = document.getElementById('no-project-warning');
    
    if (!projSelect || !projSelect.value) {
        if(table) table.style.display = 'none';
        if(warning) warning.style.display = 'block';
        return;
    }
    
    if(warning) warning.style.display = 'none';
    const res = await apiFetch(`/api/files?project_id=${projSelect.value}`);
    if (res.ok) {
        const data = await res.json();
        tbody.innerHTML = '';
        if (data.files && data.files.length > 0) {
            table.style.display = 'table';
            data.files.forEach(f => {
                const tr = document.createElement('tr');
                tr.style.borderBottom = '1px solid var(--border-color)';
                const sizeKb = (f.size / 1024).toFixed(1);
                const dateStr = new Date(f.created_at).toLocaleString('tr-TR');
                
                tr.innerHTML = `
                    <td style="padding: 10px;">${f.filename}</td>
                    <td style="padding: 10px;">${sizeKb} KB</td>
                    <td style="padding: 10px;">${dateStr}</td>
                    <td style="padding: 10px;"><span class="badge" style="background-color:var(--success-color);color:white">Hazır</span></td>
                    <td style="padding: 10px;">
                        <button class="btn btn-danger btn-sm" onclick="deleteFile('${f.id}')">Sil</button>
                    </td>
                `;
                tbody.appendChild(tr);
            });
        } else {
            table.style.display = 'none';
            warning.style.display = 'block';
            warning.innerHTML = '<p>Bu projede henüz dosya yok.</p>';
        }
    }
};

window.deleteFile = (fileId) => {
    showConfirmModal("Dosyayı Sil", "Bu dosyayı silmek istediğinize emin misiniz?", async () => {
        const res = await apiFetch(`/api/files/${fileId}`, { method: 'DELETE' });
        if (res.ok) {
            loadFilesList();
        } else {
            alert("Dosya silinemedi.");
        }
    });
};

window.checkFoundryStatus = async () => {
    const badge = document.getElementById('foundry-status-badge');
    const msg = document.getElementById('foundry-status-message');
    const list = document.getElementById('foundry-models-list');
    const select = document.getElementById('foundry-default-model');
    const timeSpan = document.getElementById('foundry-last-check');
    
    if (!badge) return;
    
    badge.textContent = "Kontrol ediliyor...";
    badge.style.backgroundColor = "var(--text-muted)";
    
    try {
        const res = await apiFetch('/api/models?provider=local');
        if (res.ok) {
            const models = await res.json();
            if (models && models.length > 0) {
                badge.textContent = "Aktif";
                badge.style.backgroundColor = "var(--success-color)";
                msg.textContent = "Foundry Local bağlantısı başarılı. Modeller kullanıma hazır.";
                list.innerHTML = '';
                select.innerHTML = '<option value="">Seçiniz...</option>';
                
                models.forEach(m => {
                    const li = document.createElement('li');
                    li.textContent = m.name;
                    list.appendChild(li);
                    
                    const opt = document.createElement('option');
                    opt.value = m.id;
                    opt.textContent = m.name;
                    select.appendChild(opt);
                });
                
                const savedModel = localStorage.getItem('foundry_default_model');
                if (savedModel) select.value = savedModel;
                
                select.onchange = () => {
                    localStorage.setItem('foundry_default_model', select.value);
                };
            } else {
                badge.textContent = "Model Yok";
                badge.style.backgroundColor = "var(--warning-color)";
                msg.textContent = "Foundry Local SDK'ya ulaşıldı ancak kurulu model bulunamadı.";
                list.innerHTML = '<li>Model bulunamadı.</li>';
                select.innerHTML = '<option value="">Model bulunamadı</option>';
            }
        } else {
            throw new Error();
        }
    } catch (e) {
        badge.textContent = "Bağlantı Hatası";
        badge.style.backgroundColor = "var(--danger-color)";
        msg.textContent = "Foundry Local'e bağlanılamadı. Servisin çalıştığından emin olun.";
        list.innerHTML = '<li>Ulaşılamıyor</li>';
        select.innerHTML = '<option value="">Bağlanılamadı</option>';
    }
    
    if(timeSpan) {
        const now = new Date();
        timeSpan.textContent = "Son kontrol: " + now.toLocaleTimeString('tr-TR');
    }
};

const oldSwitchView = window.switchView;
window.switchView = (viewId) => {
    oldSwitchView(viewId);
    if (viewId === 'settings') {
        checkFoundryStatus();
    }
    if (viewId === 'files') {
        const pSelect = document.getElementById('files-project-select');
        if (pSelect) {
            const currentVal = pSelect.value;
            pSelect.innerHTML = '<option value="">Lütfen Bir Proje Seçin</option>';
            const projectsList = document.querySelectorAll('.project-list-item');
            projectsList.forEach(li => {
                const id = li.dataset.id;
                const name = li.querySelector('.project-name').textContent;
                const opt = document.createElement('option');
                opt.value = id;
                opt.textContent = name;
                pSelect.appendChild(opt);
            });
            if (currentVal) pSelect.value = currentVal;
            loadFilesList();
        }
    }
};

document.addEventListener('DOMContentLoaded', () => {
    const s = document.getElementById('view-settings');
    if (s && !s.classList.contains('hidden')) {
        checkFoundryStatus();
    }
});

// Provider Test logic
document.addEventListener('DOMContentLoaded', () => {
    const testBtn = document.getElementById('test-provider-btn');
    if (testBtn) {
        testBtn.addEventListener('click', async () => {
            const select = document.getElementById('test-provider-select');
            if(!select) return;
            const provider = select.value;
            testBtn.disabled = true;
            testBtn.textContent = 'Test Ediliyor...';
            try {
                const res = await apiFetch(`/api/providers/${provider}/test`, { method: 'POST' });
                const data = await res.json();
                if (data.success) {
                    alert('Bağlantı başarılı: ' + data.message);
                } else {
                    alert('Bağlantı başarısız: ' + (data.message || 'Bilinmeyen hata'));
                }
                loadProviders(); // Refresh statuses
            } catch(e) {
                alert('Test sırasında hata oluştu.');
            }
            testBtn.disabled = false;
            testBtn.textContent = 'Bağlantıyı Test Et';
        });
    }
});

document.addEventListener('DOMContentLoaded', () => {
    const tsProvider = document.getElementById('ts-provider-select');
    const tsModel = document.getElementById('ts-model-select');
    if(tsProvider && tsModel) {
        tsProvider.addEventListener('change', async () => {
            tsModel.classList.remove('hidden');
            tsModel.innerHTML = '<option value="">Yükleniyor...</option>';
            try {
                const res = await apiFetch(`/api/models?provider=${tsProvider.value}`);
                const models = await res.json();
                if (!models || models.length === 0) {
                    tsModel.innerHTML = '<option value="">Model bulunamadı.</option>';
                    return;
                }
                let html = '';
                models.forEach(m => {
                    html += `<option value="${m.id}">${m.name}</option>`;
                });
                tsModel.innerHTML = html;
            } catch (e) {
                tsModel.innerHTML = '<option value="">Hata</option>';
            }
        });
        
        const saveTsBtn = document.getElementById('save-ts-settings');
        if(saveTsBtn) {
            saveTsBtn.addEventListener('click', () => {
                if(!tsModel.value) {
                    alert('Lütfen geçerli bir model seçin');
                    return;
                }
                localStorage.setItem('ts_provider', tsProvider.value);
                localStorage.setItem('ts_model', tsModel.value);
                alert('Token tasarrufu ayarları kaydedildi!');
            });
        }
    }
});


// ============================================================================
// SETTINGS & SANDBOX LOGIC
// ============================================================================

window.testLocalProvider = async (provider) => {
    const badge = document.getElementById(`settings-${provider}-badge`);
    const message = document.getElementById(`settings-${provider}-message`);
    const modelsList = document.getElementById(`settings-${provider}-models`);
    
    if(badge) { badge.textContent = 'Test Ediliyor'; badge.style.backgroundColor = 'var(--warning)'; }
    if(message) message.textContent = 'Bağlantı kurulmaya çalışılıyor...';
    
    try {
        const res = await apiFetch(`/api/providers/${provider}/test`, { method: 'POST' });
        const data = await res.json();
        
        if(res.ok && data.success) {
            if(badge) { badge.textContent = 'Hazır'; badge.style.backgroundColor = 'var(--success)'; }
            if(message) message.textContent = 'Bağlantı başarılı.';
            if(modelsList) {
                modelsList.innerHTML = '';
                const mRes = await apiFetch(`/api/models?provider=${provider}`);
                if (mRes.ok) {
                    const models = await mRes.json();
                    if(models.length === 0) {
                        modelsList.innerHTML = '<li>Çalışıyor fakat model bulunamadı.</li>';
                    } else {
                        models.forEach(m => {
                            const li = document.createElement('li');
                            li.textContent = m.name;
                            modelsList.appendChild(li);
                        });
                    }
                }
            }
        } else {
            if(badge) { badge.textContent = 'Hata'; badge.style.backgroundColor = 'var(--error)'; }
            if(message) message.textContent = data.message || data.detail || 'Bağlantı başarısız.';
            if(modelsList) modelsList.innerHTML = '<li>-</li>';
        }
    } catch (e) {
        if(badge) { badge.textContent = 'Hata'; badge.style.backgroundColor = 'var(--error)'; }
        if(message) message.textContent = 'Ağ hatası veya sunucuya ulaşılamadı.';
        if(modelsList) modelsList.innerHTML = '<li>-</li>';
    }
};

window.loadSandboxModels = async () => {
    const provider = document.getElementById('test-sandbox-provider').value;
    const select = document.getElementById('test-sandbox-model');
    if(!select) return;
    
    select.innerHTML = '<option value="">Yükleniyor...</option>';
    try {
        const res = await apiFetch(`/api/models?provider=${provider}`);
        if(res.ok) {
            const models = await res.json();
            if(models.length === 0) {
                select.innerHTML = '<option value="">Model bulunamadı</option>';
            } else {
                let html = '';
                models.forEach(m => {
                    html += `<option value="${m.id}">${m.name}</option>`;
                });
                select.innerHTML = html;
            }
        } else {
            select.innerHTML = '<option value="">Hata</option>';
        }
    } catch(e) {
        select.innerHTML = '<option value="">Hata</option>';
    }
};

window.runSandboxTest = async () => {
    const provider = document.getElementById('test-sandbox-provider').value;
    const model = document.getElementById('test-sandbox-model').value;
    const resultDiv = document.getElementById('sandbox-test-result');
    const btn = document.getElementById('sandbox-test-btn');
    
    if(!model) {
        alert("Lütfen bir model seçin.");
        return;
    }
    
    resultDiv.style.display = 'block';
    resultDiv.innerHTML = '<span style="color:var(--text-secondary);">Test mesajı gönderiliyor... Lütfen bekleyin.</span>';
    btn.disabled = true;
    
    try {
        const res = await apiFetch('/api/chat/stream', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                messages: [{role: "user", content: "Test mesajı. Sadece 'Sistem Aktif' yanıtı ver."}],
                provider: provider,
                model: model,
                mode: "custom"
            })
        });
        
        if(!res.ok) {
            const err = await res.json().catch(()=>({detail: 'Bilinmeyen hata'}));
            resultDiv.innerHTML = `<span style="color:var(--error);">Başarısız: ${err.detail}</span>`;
        } else {
            resultDiv.innerHTML = `<span style="color:var(--success);">Bağlantı Başarılı. Yanıt alınıyor...</span>`;
            // Real stream logic is omitted for brief sandbox test, we just confirm it connected successfully
            // (Normally you'd read the reader here)
        }
    } catch(e) {
        resultDiv.innerHTML = `<span style="color:var(--error);">Bağlantı Hatası: ${e.message}</span>`;
    }
    
    btn.disabled = false;
};

// Initial load for settings
document.addEventListener('DOMContentLoaded', () => {
    const themeSelectSettings = document.getElementById('settings-theme-select');
    if(themeSelectSettings) {
        themeSelectSettings.value = localStorage.getItem('theme') || 'system';
    }
});
