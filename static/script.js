// Functions to handle settings modal
function enterChat() {
    // Persist settings for this topic only if user explicitly checked 'remember'
    try {
        const key = getSettingsKey();
        const identityEl = document.getElementById('identityToggle');
        const voiceEl = document.querySelector('.voice-option.active');
        const rememberEl = document.getElementById('rememberSettings');
        const settings = {
            identity: !!(identityEl && identityEl.checked),
            voice: voiceEl ? voiceEl.getAttribute('data-voice') : 'normal',
            remember: !!(rememberEl && rememberEl.checked)
        };
        if (settings.remember) {
            localStorage.setItem('chat_settings:' + key, JSON.stringify(settings));
            // send to server-side storage as well
            try {
                fetchWithCSRF('/api/save_chat_settings', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ key: key, identity: settings.identity, voice: settings.voice, remember: true })
                }).catch(()=>{});
            } catch(e){}
            showToast('Settings saved');
        } else {
            // If they explicitly unchecked remember, remove any previous per-topic key
            try { localStorage.removeItem('chat_settings:' + key); } catch(e){}
            try {
                fetchWithCSRF('/api/save_chat_settings', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ key: key, identity: settings.identity, voice: settings.voice, remember: false })
                }).catch(()=>{});
            } catch(e){}
        }
    } catch (e) { /* ignore storage errors */ }

    const settingsModal = document.getElementById('settingsModal');
    const chatContainer = document.getElementById('chatContainer');
    if (settingsModal && chatContainer) {
        settingsModal.style.display = 'none';
        releaseFocusTrap();
        try { document.body.classList.remove('modal-open'); } catch(e){}
        chatContainer.style.display = 'flex';
        // apply settings to UI (set hidden inputs used by the server-side form)
        try{
            const identityEl = document.getElementById('identityToggle');
            const identityHidden = document.getElementById('identityRevealed');
            if(identityEl && identityHidden) identityHidden.value = identityEl.checked ? 'true' : 'false';
            const voiceEl = document.querySelector('.voice-option.active');
            const voiceHidden = document.getElementById('voiceType');
            if(voiceEl && voiceHidden) voiceHidden.value = voiceEl.getAttribute('data-voice') || 'normal';
        }catch(e){/* ignore */}
        scrollToLatestMessages();
    }
}

function showSettings() {
    const settingsModal = document.getElementById('settingsModal');
    if (settingsModal) {
        settingsModal.style.display = 'flex';
        // prevent background scroll while modal open
        try { document.body.classList.add('modal-open'); } catch(e){}
        trapFocus(settingsModal);
    }
}

// Close settings without saving (shows chat)
function closeSettings() {
    const settingsModal = document.getElementById('settingsModal');
    const chatContainer = document.getElementById('chatContainer');
    if (settingsModal && chatContainer) {
        settingsModal.style.display = 'none';
        releaseFocusTrap();
        try { document.body.classList.remove('modal-open'); } catch(e){}
        chatContainer.style.display = 'flex';
        scrollToLatestMessages();
    }
}

// Simple toast helper
function showToast(text, timeout = 1800){
    let t = document.getElementById('toast');
    if(!t){
        t = document.createElement('div');
        t.id = 'toast';
        t.className = 'toast';
        document.body.appendChild(t);
    }
    t.textContent = text;
    t.style.display = 'block';
    t.style.opacity = '1';
    setTimeout(()=>{ t.style.opacity = '0'; setTimeout(()=>{ t.style.display='none'; }, 220); }, timeout);
}

// Focus trap implementation for modal
let _trapKeydownHandler = null;
let _previouslyFocused = null;
function trapFocus(modal){
    if(!modal) return;
    _previouslyFocused = document.activeElement;
    const focusable = modal.querySelectorAll('a[href], button, textarea, input, select, [tabindex]:not([tabindex="-1"])');
    const first = focusable[0];
    const last = focusable[focusable.length-1];
    if(first) first.focus();

    _trapKeydownHandler = function(e){
        if(e.key === 'Tab'){
            if(focusable.length === 0) { e.preventDefault(); return; }
            if(e.shiftKey){ // shift+tab
                if(document.activeElement === first){
                    e.preventDefault();
                    last.focus();
                }
            } else {
                if(document.activeElement === last){
                    e.preventDefault();
                    first.focus();
                }
            }
        } else if(e.key === 'Escape'){
            // Close modal (without saving)
            closeSettings();
        }
    };
    document.addEventListener('keydown', _trapKeydownHandler);
}

function releaseFocusTrap(){
    if(_trapKeydownHandler) document.removeEventListener('keydown', _trapKeydownHandler);
    _trapKeydownHandler = null;
    if(_previouslyFocused && typeof _previouslyFocused.focus === 'function') _previouslyFocused.focus();
    _previouslyFocused = null;
}

// Return a storage key for current topic/chat (fall back to 'global')
function getSettingsKey(){
    try{
        const roomEl = document.querySelector('[data-current-room]');
        if(roomEl){
            return roomEl.getAttribute('data-current-room');
        }
    }catch(e){}
    return 'global';
}

// Mobile detection and responsive adjustments
function isMobile() {
    return window.innerWidth <= 768;
}

// CSRF token helper
function getCSRFToken() {
    return document.querySelector('meta[name="csrf-token"]').getAttribute('content');
}

// Fetch helper with CSRF
async function fetchWithCSRF(url, options = {}) {
    const token = getCSRFToken();
    const defaultOptions = {
        headers: {
            'X-CSRFToken': token,
            ...options.headers
        },
        ...options
    };
    return fetch(url, defaultOptions);
}

// Image modal functionality
function openImageModal(src) {
    const modal = document.getElementById('imageModal');
    const modalImg = document.getElementById('modalImage');
    modal.style.display = 'block';
    modalImg.src = src;
}

function closeImageModal() {
    document.getElementById('imageModal').style.display = 'none';
}

// Close modal when clicking outside
window.onclick = function(event) {
    const modal = document.getElementById('imageModal');
    if (event.target === modal) {
        closeImageModal();
    }
}

// Function to scroll chat to the bottom
function scrollToLatestMessages() {
    // Try all possible message container selectors used in different chat templates
    const selectors = [
        '#messagesContainer',
        '.messages-container',
        '.chat-messages',
        '.message-list',
        '.chat-area'
    ];
    
    for (const selector of selectors) {
        const container = document.querySelector(selector);
        if (container) {
            container.scrollTop = container.scrollHeight;
        }
    }
}

// Simple HTML escape helper to avoid injecting unsafe HTML
function escapeHtml(unsafe) {
    if (unsafe === null || unsafe === undefined) return '';
    return String(unsafe)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

// Call scrollToLatestMessages when page loads and after any chat updates

// DOM-ready handler for settings modal load and voice-option wiring
document.addEventListener('DOMContentLoaded', function() {
    // Show settings modal on page load and wire modal controls
    const settingsModal = document.getElementById('settingsModal');
    const chatContainer = document.getElementById('chatContainer');
    if (settingsModal && chatContainer) {
        // Load saved settings for this topic (server-side or localStorage) and pre-select
        let parsed = null;
        try {
            // server-side settings embedded on the page take precedence
            const server = window.serverSavedSettings || null;
            if (server) {
                parsed = server;
            } else {
                const key = getSettingsKey();
                const saved = localStorage.getItem('chat_settings:' + key) || localStorage.getItem('chat_settings:global');
                if (saved) parsed = JSON.parse(saved);
            }

            if (parsed) {
                const identityEl = document.getElementById('identityToggle');
                if (identityEl && typeof parsed.identity === 'boolean') identityEl.checked = parsed.identity;
                if (parsed.voice) {
                    const vo = document.querySelector(`.voice-option[data-voice="${parsed.voice}"]`);
                    if (vo) {
                        document.querySelectorAll('.voice-option').forEach(el => el.classList.remove('active'));
                        vo.classList.add('active');
                        // update aria-pressed for voice options
                        document.querySelectorAll('.voice-option').forEach(el => el.setAttribute('aria-pressed', el.classList.contains('active') ? 'true' : 'false'));
                    }
                }
                // set remember checkbox to reflect saved choice
                const rememberEl = document.getElementById('rememberSettings');
                if(rememberEl && parsed.remember) rememberEl.checked = true;
            }
        } catch(e){/* ignore */}

        // If parsed and remembered, auto-enter immediately (server or local)
        if(parsed && parsed.remember){
            // slight defer so rendering completes
            setTimeout(()=> enterChat(), 150);
        } else {
            settingsModal.style.display = 'flex';
            try { document.body.classList.add('modal-open'); } catch(e){}
            chatContainer.style.display = 'none';
            trapFocus(settingsModal);
        }

        // Wire close button
        const closeBtn = document.getElementById('settingsCloseBtn');
        if(closeBtn) closeBtn.addEventListener('click', closeSettings);
    }

    // Voice option selection (click and keyboard)
    const voiceOptions = document.querySelectorAll('.voice-option');
    voiceOptions.forEach(option => {
        option.addEventListener('click', function() {
            voiceOptions.forEach(opt => opt.classList.remove('active'));
            this.classList.add('active');
            // reflect aria-pressed
            voiceOptions.forEach(opt => opt.setAttribute('aria-pressed', opt.classList.contains('active') ? 'true' : 'false'));
            // update hidden input live
            const voiceHidden = document.getElementById('voiceType');
            if(voiceHidden) voiceHidden.value = this.getAttribute('data-voice') || 'normal';
        });
        option.addEventListener('keydown', function(e){
            if(e.key === 'Enter' || e.key === ' '){
                e.preventDefault();
                this.click();
            }
        });
    });

    // Identity toggle live update to hidden input
    const identityToggle = document.getElementById('identityToggle');
    if(identityToggle){
        identityToggle.addEventListener('change', function(){
            const identityHidden = document.getElementById('identityRevealed');
            if(identityHidden) identityHidden.value = this.checked ? 'true' : 'false';
        });
    }

});

// Real-time message updates
let lastMessageTimestamp = null;
let currentChatId = null;
let currentChatType = null;

// Initialize chat polling
document.addEventListener('DOMContentLoaded', function() {
    // Detect current chat context
    const relationshipChat = document.querySelector('[data-current-room^="relationship:"]');
    const privateChat = document.querySelector('[data-current-room^="chat:"]');
    const topicChat = document.querySelector('[data-current-room^="topic:"]');
    
    if (relationshipChat) {
        currentChatType = 'relationship';
        currentChatId = relationshipChat.getAttribute('data-current-room').split(':')[1];
    } else if (privateChat) {
        currentChatType = 'private';
        currentChatId = privateChat.getAttribute('data-current-room').split(':')[1];
    } else if (topicChat) {
        currentChatType = 'topic';
        currentChatId = topicChat.getAttribute('data-current-room').split(':')[1];
    }

    if (currentChatId) {
        // Get initial last message timestamp
        const messages = document.querySelectorAll('.message');
        if (messages.length > 0) {
            const lastMessage = messages[messages.length - 1];
            const timestamp = lastMessage.querySelector('.timestamp');
            if (timestamp) {
                lastMessageTimestamp = new Date(timestamp.getAttribute('data-timestamp') || timestamp.textContent).getTime();
            }
        }

        // Start polling for new messages
        pollForNewMessages();
        // Try to open SSE for real-time updates (preferred)
        startSSE();
    }
});

// Start Server-Sent Events connection for the current room
function startSSE(){
    if (!('EventSource' in window)) return;
    const roomEl = document.querySelector('[data-current-room]');
    if(!roomEl) return;
    const room = roomEl.getAttribute('data-current-room');
    if(!room) return;

    // If an EventSource already exists for this page, don't recreate immediately
    if (window._es && window._esRoom === room) return;

    // Exponential backoff for reconnect attempts
    window._sseBackoff = window._sseBackoff || 1000; // start at 1s
    const url = '/stream?room=' + encodeURIComponent(room);
    try{
        // Use withCredentials where supported so same-origin cookies are sent
        const es = (typeof EventSource !== 'undefined') ? new EventSource(url, { withCredentials: true }) : new EventSource(url);
        window._es = es;
        window._esRoom = room;

        es.onopen = function() {
            console.info('SSE connected to', url);
            // reset backoff on successful connect
            window._sseBackoff = 1000;
        };

        es.onmessage = function(e){
            try{
                const payload = JSON.parse(e.data);
                handleSSEPayload(payload);
            }catch(err){
                console.error('Invalid SSE payload', err, e.data);
            }
        };

        es.onerror = function(e){
            console.warn('SSE connection error, falling back to polling', e);
            try{ es.close(); }catch(_){}
            // Exponential backoff capped at 60s
            const delay = Math.min(window._sseBackoff, 60000);
            window._sseBackoff = Math.min(60000, window._sseBackoff * 2);
            setTimeout(startSSE, delay);
        };
    }catch(err){
        console.warn('Failed to start SSE', err);
        // Try again with backoff
        const delay = window._sseBackoff || 2000;
        window._sseBackoff = Math.min(60000, (window._sseBackoff || 2000) * 2);
        setTimeout(startSSE, delay);
    }
}

function handleSSEPayload(payload){
    if(!payload || !payload.type || !payload.message) return;
    const message = payload.message;
    // Defensive duplicate detection: skip if a matching message already exists
    if (messageExists(message)) return;

    // Prefer explicit messages container when present
    let container = document.getElementById('messagesContainer');
    if (!container) container = document.querySelector('.chat-messages, .message-list, .chat-area');
    if (!container) return;

    const wasAtBottom = isUserNearBottom(container);

    const safeSender = escapeHtml(message.sender_name || '');
    const safeContent = escapeHtml(message.content || '');
    const msgHtml = `\n                        <div class="message ${message.is_own ? 'sent' : 'received'}" data-message-id="${message.id}">\n                            <div class="message-header">\n                                <span class="sender">${safeSender}</span>\n                                <span class="timestamp" data-timestamp="${message.timestamp}">${escapeHtml(message.formatted_time || '')}</span>\n                            </div>\n                            <div class="message-content">${safeContent}</div>\n                        </div>\n                    `;
    container.insertAdjacentHTML('beforeend', msgHtml);
    if (wasAtBottom) scrollToLatestMessages();
    // update lastMessageTimestamp
    if(message.timestamp) lastMessageTimestamp = new Date(message.timestamp).getTime();
}

// Poll for new messages
async function pollForNewMessages() {
    // If SSE is active for this room, skip polling to avoid duplicate work
    if (window._es && window._es.readyState === 1) return;
    if (!currentChatId || !currentChatType) return;

    try {
        const response = await fetchWithCSRF(`/api/new_messages`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                chat_id: currentChatId,
                chat_type: currentChatType,
                last_timestamp: lastMessageTimestamp
            })
        });

        const data = await response.json();
        
        if (data.status === 'success' && data.messages && data.messages.length > 0) {
            // Add new messages to the chat (avoid duplicates)
                let container = document.getElementById('messagesContainer');
            if (!container) container = document.querySelector('.chat-messages, .message-list, .chat-area');
            if (container) {
                // Determine whether user is near the bottom before inserting
                const wasAtBottom = isUserNearBottom(container);

                data.messages.forEach(message => {
                    // Defensive duplicate detection: skip if message already in DOM
                    if (messageExists(message)) return;

                    const safeSender = escapeHtml(message.sender_name || '');
                    const safeContent = escapeHtml(message.content || '');
                    const msgHtml = `\n                        <div class="message ${message.is_own ? 'sent' : 'received'}" data-message-id="${message.id}">\n                            <div class="message-header">\n                                <span class="sender">${safeSender}</span>\n                                <span class="timestamp" data-timestamp="${message.timestamp}">${escapeHtml(message.formatted_time || '')}</span>\n                            </div>\n                            <div class="message-content">${safeContent}</div>\n                        </div>\n                    `;
                    container.insertAdjacentHTML('beforeend', msgHtml);
                });

                // Update last message timestamp
                const lastMsg = data.messages[data.messages.length - 1];
                if (lastMsg && lastMsg.timestamp) {
                    lastMessageTimestamp = new Date(lastMsg.timestamp).getTime();
                }

                // Scroll only if user was at (or near) bottom before new messages
                if (wasAtBottom) scrollToLatestMessages();
            }
        }
    } catch (error) {
        console.error('Error fetching new messages:', error);
    }

    // Continue polling
    setTimeout(pollForNewMessages, 3000); // Poll every 3 seconds
}

// Return true if user is near the bottom of a scrollable container
function isUserNearBottom(container, threshold = 150) {
    try {
        const distance = container.scrollHeight - (container.scrollTop + container.clientHeight);
        return distance <= threshold;
    } catch (e) {
        return true;
    }
}

// Check if a message already exists in DOM by id or by content signature
function messageExists(message){
    try{
        if(!message) return false;
        // If id present, check for element with that data-message-id
        if(message.id){
            if(document.querySelector(`[data-message-id="${message.id}"]`)) return true;
        }

        // Else, compute a signature from sender+timestamp+content and compare to existing messages
        const sig = ((message.sender_name||'').trim() + '|' + (message.timestamp||message.formatted_time||'') + '|' + (message.content||'')).replace(/\s+/g,' ').trim();
        if(!sig) return false;

        const nodes = document.querySelectorAll('.message');
        for(const n of nodes){
            try{
                const s = (n.querySelector('.sender') ? n.querySelector('.sender').textContent : '').trim();
                const tEl = n.querySelector('.timestamp');
                const t = tEl ? (tEl.getAttribute('data-timestamp') || tEl.textContent) : '';
                const c = (n.querySelector('.message-content') ? n.querySelector('.message-content').textContent : '').trim();
                const existingSig = (s + '|' + t + '|' + c).replace(/\s+/g,' ').trim();
                if(existingSig && existingSig === sig) return true;
            }catch(e){/* ignore per-node parse errors */}
        }
    }catch(e){ console.warn('messageExists failed', e); }
    return false;
}

// Reply and Reaction helpers (global)
function showReplyBox(messageId) {
    // Remove any existing active reply boxes
    document.querySelectorAll('.reply-box.active').forEach(box => {
        box.classList.remove('active');
    });
    
    // Find or create reply box
    let replyBox = document.getElementById(`reply-box-${messageId}`);
    if (!replyBox) {
        replyBox = document.createElement('div');
        replyBox.id = `reply-box-${messageId}`;
        replyBox.className = 'reply-box';
        replyBox.innerHTML = `
            <textarea placeholder="Type your reply..."></textarea>
            <div class="reply-box-actions">
                <button type="button" class="btn-secondary" onclick="hideReplyBox('${messageId}')">Cancel</button>
                <button type="button" class="btn-primary" onclick="submitReply('${messageId}')">Reply</button>
            </div>
        `;
        
        // Insert after the message actions
        const message = document.querySelector(`[data-message-id="${messageId}"]`);
        if (message) {
            message.appendChild(replyBox);
        }
    }
    
    replyBox.classList.add('active');
    replyBox.querySelector('textarea').focus();
}

function hideReplyBox(messageId) {
    const replyBox = document.getElementById(`reply-box-${messageId}`);
    if (replyBox) {
        replyBox.classList.remove('active');
        replyBox.querySelector('textarea').value = '';
    }
}

function submitReply(messageId) {
    const replyBox = document.getElementById(`reply-box-${messageId}`);
    if (!replyBox) return;
    
    const textarea = replyBox.querySelector('textarea');
    const content = textarea.value.trim();
    if (!content) return;
    
    const submitBtn = replyBox.querySelector('.btn-primary');
    const cancelBtn = replyBox.querySelector('.btn-secondary');
    submitBtn.disabled = true;
    cancelBtn.disabled = true;
    
    fetchWithCSRF('/api/reply_message', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ parent_id: messageId, content: content })
    })
    .then(r => r.json())
    .then(data => {
        if (data.status === 'success') {
            // Inject reply into DOM without reloading
            try {
                const parentEl = document.querySelector(`[data-message-id="${messageId}"]`);
                const replyHtml = `\n                    <div class="message reply" data-message-id="${data.message_id}">\n                        <div class="message-header">\n                            <span class="sender">${escapeHtml(data.user_name || 'You')}</span>\n                            <span class="timestamp" data-timestamp="${escapeHtml(data.timestamp || '')}">${escapeHtml(data.timestamp || '')}</span>\n                        </div>\n                        <div class="message-content">${escapeHtml(data.content || '')}</div>\n                    </div>\n                `;
                if (parentEl && parentEl.parentNode) {
                    parentEl.insertAdjacentHTML('afterend', replyHtml);
                    // scroll the messages container if present
                    scrollToLatestMessages();
                }
            } catch (e) {
                console.error('Failed to inject reply DOM', e);
            }
            hideReplyBox(messageId);
        } else {
            alert('Error sending reply: ' + (data.message || 'Unknown error'));
        }
    })
    .catch(err => alert('Error sending reply: ' + err))
    .finally(() => {
        submitBtn.disabled = false;
        cancelBtn.disabled = false;
    });
}

function replyToMessage(messageId) {
    showReplyBox(messageId);
}

function updateReactionCounts(messageId, reactions) {
    const container = document.getElementById(`reactions-${messageId}`);
    if (!container) return;

    // Parse reactions JSON if it's a string
    if (typeof reactions === 'string') {
        try {
            reactions = JSON.parse(reactions);
        } catch (e) {
            console.error('Failed to parse reactions:', e);
            return;
        }
    }

    // Build counts HTML
    const counts = [];
    for (const [emoji, userIds] of Object.entries(reactions)) {
        if (Array.isArray(userIds) && userIds.length > 0) {
            counts.push(`${emoji} ${userIds.length}`);
        }
    }

    // Update DOM
    container.textContent = counts.join(' • ');
    
    // Update aria-pressed state on reaction buttons
    const messageActions = container.closest('.message-actions');
    if (messageActions) {
        messageActions.querySelectorAll('.message-action[data-emoji]').forEach(btn => {
            const emoji = btn.getAttribute('data-emoji');
            const userIds = reactions[emoji] || [];
            // Normalize to strings for comparison with currentUserId (template injects it as string)
            const userIdStrs = (Array.isArray(userIds) ? userIds.map(u => String(u)) : []);
            const isPressed = userIdStrs.includes(String(currentUserId));
            btn.setAttribute('aria-pressed', isPressed);
        });
    }
}

function reactToMessage(messageId, emoji) {
    const btn = document.querySelector(`.message-action[data-emoji="${emoji}"][data-message-id="${messageId}"]`);
    if (btn) btn.disabled = true;

    fetchWithCSRF('/api/react_message', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message_id: messageId, emoji: emoji })
    })
    .then(r => r.json())
    .then(data => {
        if (data.status === 'success' && data.reactions) {
            updateReactionCounts(messageId, data.reactions);
        } else {
            alert('Error adding reaction: ' + (data.message || 'Unknown'));
        }
    })
    .catch(err => alert('Error adding reaction: ' + err))
    .finally(() => {
        if (btn) btn.disabled = false;
    });
}

// Voice recording and playback
let mediaRecorder;
let audioChunks = [];

async function startRecording() {
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        mediaRecorder = new MediaRecorder(stream);
        audioChunks = [];

        mediaRecorder.ondataavailable = event => {
            audioChunks.push(event.data);
        };

        mediaRecorder.start();
        document.getElementById('recordBtn').textContent = 'Stop Recording';
        document.getElementById('recordBtn').onclick = stopRecording;
    } catch (error) {
        alert('Error accessing microphone: ' + error.message);
    }
}

function stopRecording() {
    if (mediaRecorder) {
        mediaRecorder.stop();
        mediaRecorder.onstop = () => {
            const audioBlob = new Blob(audioChunks, { type: 'audio/wav' });
            const audioUrl = URL.createObjectURL(audioBlob);
            
            // Create audio player
            const audioPlayer = document.getElementById('audioPlayer');
            audioPlayer.src = audioUrl;
            audioPlayer.style.display = 'block';
            
            // Reset button
            document.getElementById('recordBtn').textContent = 'Start Recording';
            document.getElementById('recordBtn').onclick = startRecording;
        };
    }
}

// File upload handling
function handleImageUpload(event) {
    const file = event.target.files[0];
    if (file) {
        if (file.size > 5 * 1024 * 1024) { // 5MB limit
            alert('Image must be smaller than 5MB');
            return;
        }
        
        const reader = new FileReader();
        reader.onload = function(e) {
            const preview = document.getElementById('imagePreview');
            preview.innerHTML = `<img src="${e.target.result}" style="max-width: 200px; border-radius: 8px;" onclick="openImageModal('${e.target.result}')">`;
        };
        reader.readAsDataURL(file);
    }
}

// Message reactions
function addReaction(messageId, emoji) {
    // In production, this would make an API call
    console.log(`Added ${emoji} reaction to message ${messageId}`);
}

// Real-time updates (simulated)
function simulateRealTimeUpdates() {
    setInterval(() => {
        // In production, this would use WebSockets or Server-Sent Events
        if (Math.random() > 0.7) {
            const event = new Event('newMessage');
            window.dispatchEvent(event);
        }
    }, 5000);
}

// Initialize when page loads
document.addEventListener('DOMContentLoaded', function() {
    // Mobile-specific adjustments
    if (isMobile()) {
        document.body.classList.add('mobile');
    }
    
    // Initialize tooltips
    const tooltips = document.querySelectorAll('[data-tooltip]');
    tooltips.forEach(tooltip => {
        tooltip.addEventListener('mouseenter', showTooltip);
        tooltip.addEventListener('mouseleave', hideTooltip);
    });
    
    // Start real-time updates (SSE preferred). The simulateRealTimeUpdates helper is disabled in production.

    // Start active-count polling (updates elements with data-active-target)
    startActiveCountPolling();
});

// Sanitize overlays that may be left visible after redirects (defensive)
function sanitizeOverlays(){
    try{
        // Hide any modal-like elements
        document.querySelectorAll('.modal, .confirm-modal').forEach(m => {
            m.classList.remove('open');
            m.style.display = 'none';
            m.setAttribute('aria-hidden', 'true');
        });

        // Hide sidebar backdrop
        document.querySelectorAll('.sidebar-backdrop').forEach(b => {
            b.classList.remove('visible');
        });

        // Hide toast
        const t = document.getElementById('toast');
        if(t) t.style.display = 'none';

        console.debug('sanitizeOverlays: overlays hidden');
    }catch(e){ console.warn('sanitizeOverlays failed', e); }
}

// Run sanitizer early on load
document.addEventListener('DOMContentLoaded', sanitizeOverlays);


// Active counts polling
let _activeCountInterval = null;
function startActiveCountPolling(intervalMs = 30000){
    // Run immediately and then every interval
    updateActiveCounts();
    if(_activeCountInterval) clearInterval(_activeCountInterval);
    _activeCountInterval = setInterval(updateActiveCounts, intervalMs);
}

// Pause/resume polling based on page visibility
document.addEventListener('visibilitychange', function(){
    if (document.hidden){
        if(_activeCountInterval) clearInterval(_activeCountInterval);
        if(_roomPingInterval) clearInterval(_roomPingInterval);
    } else {
        startActiveCountPolling();
        startRoomPing();
    }
});

async function updateActiveCounts(){
    try{
        // Find elements with data-active-target attribute
        // Format: data-active-target="type:id" where type is chat|topic|relationship
        const targets = document.querySelectorAll('[data-active-target]');
        if(!targets.length) return;

        // Collect ids per type
        const idsByType = { chat: new Set(), topic: new Set(), relationship: new Set() };
        const elementsByKey = {}; // key -> [els]

        targets.forEach(el => {
            const val = el.getAttribute('data-active-target');
            if(!val) return;
            const [type, id] = val.split(':');
            if(!type || !id) return;
            if(!elementsByKey[`${type}:${id}`]) elementsByKey[`${type}:${id}`] = [];
            elementsByKey[`${type}:${id}`].push(el);
            if(idsByType[type]) idsByType[type].add(id);
        });

        // Build query params
        const params = [];
        if(idsByType.topic.size) params.push(`topic_ids=${encodeURIComponent(Array.from(idsByType.topic).join(','))}`);
        if(idsByType.relationship.size) params.push(`relationship_ids=${encodeURIComponent(Array.from(idsByType.relationship).join(','))}`);
        if(idsByType.chat.size) params.push(`chat_ids=${encodeURIComponent(Array.from(idsByType.chat).join(','))}`);

        let url = '/api/active_counts';
        if(params.length) url += '?' + params.join('&');

        try{
            const res = await fetchWithCSRF(url, { method: 'GET' });
            if(!res.ok) return;
            const data = await res.json();
            if(data.status === 'disabled'){
                // Admin disabled active counts — stop polling and mark badges offline
                document.querySelectorAll('[data-active-target]').forEach(el => {
                    el.classList.add('offline');
                    el.textContent = 'Active counts disabled';
                });
                if(_activeCountInterval) clearInterval(_activeCountInterval);
                return;
            }
            if(data.status !== 'success') return;

            // Update topic elements
            if(data.topic_active){
                for(const [id, count] of Object.entries(data.topic_active)){
                    const key = `topic:${id}`;
                    const els = elementsByKey[key] || [];
                    els.forEach(el => {
                        el.textContent = `Active now: ${count} users`;
                        el.dataset.activeCount = count;
                    });
                }
            }

            if(data.relationship_active){
                for(const [id, count] of Object.entries(data.relationship_active)){
                    const key = `relationship:${id}`;
                    const els = elementsByKey[key] || [];
                    els.forEach(el => {
                        el.textContent = `Active now: ${count} users`;
                        el.dataset.activeCount = count;
                    });
                }
            }

            if(data.chat_active){
                for(const [id, count] of Object.entries(data.chat_active)){
                    const key = `chat:${id}`;
                    const els = elementsByKey[key] || [];
                    els.forEach(el => {
                        el.textContent = `Active now: ${count} users`;
                        el.dataset.activeCount = count;
                    });
                }
            }
        }catch(e){
            // ignore
        }
    }catch(e){
        // ignore
    }
}


// Room presence pinging: if a page exposes data-current-room="type:id", ping server periodically
let _roomPingInterval = null;
function startRoomPing(intervalMs = 20000){
    // Find the page-level room key
    const roomEl = document.querySelector('[data-current-room]');
    if(!roomEl) return;
    const val = roomEl.getAttribute('data-current-room');
    if(!val) return;
    const [type, id] = val.split(':');

    async function ping(){
        try{
            await fetchWithCSRF('/api/room_ping', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({type: type, id: id}) });
        }catch(e){ /* ignore */ }
    }

    // Do one immediately and then start interval
    ping();
    if(_roomPingInterval) clearInterval(_roomPingInterval);
    _roomPingInterval = setInterval(ping, intervalMs);
}

// Attempt to start room ping on load
document.addEventListener('DOMContentLoaded', function(){
    startRoomPing();
});

function showTooltip(event) {
    const tooltipText = event.target.getAttribute('data-tooltip');
    const tooltip = document.createElement('div');
    tooltip.className = 'tooltip';
    tooltip.textContent = tooltipText;
    tooltip.style.position = 'absolute';
    tooltip.style.background = 'rgba(0,0,0,0.8)';
    tooltip.style.color = 'white';
    tooltip.style.padding = '5px 10px';
    tooltip.style.borderRadius = '4px';
    tooltip.style.zIndex = '1000';
    
    document.body.appendChild(tooltip);
    
    const rect = event.target.getBoundingClientRect();
    tooltip.style.left = rect.left + 'px';
    tooltip.style.top = (rect.top - tooltip.offsetHeight - 5) + 'px';
    
    event.target._tooltip = tooltip;
}

function hideTooltip(event) {
    if (event.target._tooltip) {
        event.target._tooltip.remove();
    }
}

// Simple modal confirm helper (returns a Promise<boolean>)
function showConfirmModal(title, body) {
    return new Promise(resolve => {
        const modal = document.getElementById('confirmModal');
        if (!modal) return resolve(confirm(body)); // fallback
        document.getElementById('confirmModalTitle').textContent = title || 'Confirm';
        document.getElementById('confirmModalBody').textContent = body || '';
        const okBtn = document.getElementById('confirmOk');
        const cancelBtn = document.getElementById('confirmCancel');

        function cleanup() {
            modal.style.display = 'none';
            modal.classList.remove('open');
            modal.setAttribute('aria-hidden', 'true');
            okBtn.removeEventListener('click', onOk);
            cancelBtn.removeEventListener('click', onCancel);
        }

        function onOk() { cleanup(); resolve(true); }
        function onCancel() { cleanup(); resolve(false); }

        okBtn.addEventListener('click', onOk);
        cancelBtn.addEventListener('click', onCancel);
        modal.style.display = 'block';
        // make it interactable via CSS
        modal.classList.add('open');
        modal.setAttribute('aria-hidden', 'false');
    });
}

// Sidebar functionality removed

// Wire hamburger button when available
document.addEventListener('DOMContentLoaded', function(){
    const ham = document.querySelector('.hamburger');
    if(ham){
        ham.addEventListener('click', function(e){
            e.preventDefault();
            toggleSidebar();
        });
    }

    // Ensure backdrop exists and closes on click (in case CSS created it but not JS)
    createSidebarBackdrop();
    
    // Inject a simple mobile header with hamburger when on small screens
    try{
        if(isMobile()){
            if(!document.querySelector('.mobile-header')){
                const header = document.querySelector('header');
                const mobileHeader = document.createElement('div');
                mobileHeader.className = 'mobile-header';
                // Hamburger
                const hamBtn = document.createElement('a');
                hamBtn.className = 'hamburger';
                hamBtn.href = '#';
                hamBtn.innerHTML = '&#9776;';
                hamBtn.addEventListener('click', function(e){ e.preventDefault(); toggleSidebar(); });

                // Title (short)
                const title = document.createElement('div');
                title.style.flex = '1';
                title.style.textAlign = 'center';
                title.style.fontWeight = '600';
                title.style.color = 'var(--white)';
                title.textContent = document.querySelector('header h1') ? document.querySelector('header h1').textContent : 'Chat';

                mobileHeader.appendChild(hamBtn);
                mobileHeader.appendChild(title);

                if(header && header.parentNode){
                    header.parentNode.insertBefore(mobileHeader, header);
                } else {
                    document.body.insertBefore(mobileHeader, document.body.firstChild);
                }
            }
        }
    }catch(e){ /* ignore injection failures */ }
});