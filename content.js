// Cria a Interface na Página
const overlayHTML = `
<div id="fluxia-overlay">
    <div id="fluxia-header">
        <span id="fluxia-title">FluxIA Copilot ⚡</span>
        <div style="width: 8px; height: 8px; background: #00b894; border-radius: 50%; box-shadow: 0 0 10px #00b894;"></div>
    </div>
    <div id="fluxia-live-text">Ouvindo...</div>
    <div id="fluxia-suggestion-box"></div>
</div>
`;

// Injeta no corpo do site
document.body.insertAdjacentHTML('beforeend', overlayHTML);

const overlay = document.getElementById('fluxia-overlay');
const liveText = document.getElementById('fluxia-live-text');
const suggestionBox = document.getElementById('fluxia-suggestion-box');

// Escuta mensagens do Background (Vindas da IA)
chrome.runtime.onMessage.addListener((message) => {
    if (message.type === 'SHOW_OVERLAY') {
        overlay.style.display = 'block';
    }
    
    if (message.type === 'TRANSCRIPT') {
        liveText.innerText = message.text;
    }
    
    if (message.type === 'ADVICE') {
        suggestionBox.style.display = 'block';
        suggestionBox.innerText = "💡 " + message.text;
        
        // Esconde a dica depois de 10 segundos para não poluir
        setTimeout(() => {
            suggestionBox.style.display = 'none';
        }, 10000);
    }
});
