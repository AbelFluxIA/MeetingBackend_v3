// SEU URL DO RAILWAY (Ajuste para ws:// se for local ou wss:// se for https)
// Exemplo Local: ws://localhost:8000/listen
// Exemplo Railway: wss://seu-app.up.railway.app/listen
const WS_URL = 'wss://SEU-APP-NO-RAILWAY.up.railway.app/listen'; 

let recorder;
let socket;

chrome.runtime.onMessage.addListener(async (message) => {
    if (message.target === 'offscreen' && message.type === 'START') {
        startStreaming(message.data);
    }
});

async function startStreaming(streamId) {
    // 1. Conecta no WebSocket
    socket = new WebSocket(WS_URL);
    
    socket.onopen = () => console.log("WS Conectado");
    
    // 2. Recebe dados da IA e repassa para o Background -> Content
    socket.onmessage = (event) => {
        const data = JSON.parse(event.data);
        chrome.runtime.sendMessage({
            target: 'background',
            type: 'AI_DATA',
            data: data
        });
    };

    // 3. Captura Áudio
    const media = await navigator.mediaDevices.getUserMedia({
        audio: {
            mandatory: {
                chromeMediaSource: 'tab',
                chromeMediaSourceId: streamId
            }
        }
    });

    // 4. Grava em pedacinhos (chunks) de 250ms e manda pro socket
    recorder = new MediaRecorder(media, { mimeType: 'audio/webm;codecs=opus' });
    
    recorder.ondataavailable = async (event) => {
        if (event.data.size > 0 && socket.readyState === 1) {
            socket.send(event.data);
        }
    };

    recorder.start(250); // Envia a cada 250ms
}
