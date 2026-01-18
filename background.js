chrome.runtime.onMessage.addListener(async (message, sender) => {
    // Iniciar
    if (message.type === 'START_COPILOT') {
        // 1. Cria Offscreen
        await setupOffscreen();
        
        // 2. Pega ID da aba atual
        const tab = await getActiveTab();
        
        // 3. Avisa a aba para mostrar o Overlay
        chrome.tabs.sendMessage(tab.id, { type: 'SHOW_OVERLAY' });
        
        // 4. Começa a captura
        chrome.tabCapture.getMediaStreamId({ targetTabId: tab.id }, (streamId) => {
            chrome.runtime.sendMessage({
                target: 'offscreen',
                type: 'START',
                data: streamId
            });
        });
    }

    // Repassa dados da IA (Offscreen) para a Tela (Content)
    if (message.type === 'AI_DATA') {
        const tab = await getActiveTab();
        const ai = message.data;
        
        if (ai.type === 'transcript') {
            chrome.tabs.sendMessage(tab.id, { type: 'TRANSCRIPT', text: ai.text });
        }
        if (ai.type === 'advice') {
            chrome.tabs.sendMessage(tab.id, { type: 'ADVICE', text: ai.text });
        }
    }
});

async function setupOffscreen() {
    if (await chrome.offscreen.hasDocument()) return;
    await chrome.offscreen.createDocument({
        url: 'offscreen.html',
        reasons: ['USER_MEDIA'],
        justification: 'Live Streaming'
    });
}

async function getActiveTab() {
    const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
    return tabs[0];
}
