import asyncio
import os
import json
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from deepgram import DeepgramClient, DeepgramClientOptions, LiveTranscriptionEvents, LiveOptions
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Chaves (Pode pegar do os.environ no Railway)
DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Cliente Groq para a Inteligência
groq_client = Groq(api_key=GROQ_API_KEY)

# Buffer para guardar o contexto da conversa
transcript_buffer = []

async def get_sales_advice(text_chunk):
    """Analisa o texto e decide se o vendedor precisa de ajuda"""
    if len(text_chunk.split()) < 5: return None # Ignora frases muito curtas

    prompt = f"""
    Você é um Coach de Vendas Experiente ouvindo uma reunião em tempo real.
    Contexto recente: "{text_chunk}"
    
    Se o cliente fez uma OBJEÇÃO ou PERGUNTA DIFÍCIL, me dê uma dica curta e direta de como responder.
    Se for apenas conversa normal, retorne PARE.
    
    Responda APENAS a dica ou PARE. Não use markdown. Seja breve (máx 15 palavras).
    """
    
    try:
        chat = groq_client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.3-70b-versatile",
            temperature=0.3,
            max_tokens=50
        )
        response = chat.choices[0].message.content
        if "PARE" in response or len(response) < 3:
            return None
        return response
    except:
        return None

@app.websocket("/listen")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("🔌 Cliente conectado ao WebSocket")

    try:
        deepgram = DeepgramClient(DEEPGRAM_API_KEY)
        
        # Callback: O que fazer quando a Deepgram manda texto?
        async def on_message(result, **kwargs):
            sentence = result.channel.alternatives[0].transcript
            if len(sentence) > 0:
                is_final = result.is_final
                
                # Manda a transcrição ao vivo pro Frontend (para ver o que tá rolando)
                await websocket.send_json({"type": "transcript", "text": sentence, "is_final": is_final})
                
                if is_final:
                    transcript_buffer.append(sentence)
                    # A cada frase finalizada, consulta o Oráculo de Vendas
                    advice = await get_sales_advice(sentence)
                    if advice:
                        print(f"💡 DICA IA: {advice}")
                        await websocket.send_json({"type": "advice", "text": advice})

        # Configura conexão Deepgram Live
        dg_connection = deepgram.listen.live.v("1")
        dg_connection.on(LiveTranscriptionEvents.Transcript, on_message)

        options = LiveOptions(
            model="nova-2", 
            language="pt-BR", 
            smart_format=True,
            interim_results=True # Mostra o texto enquanto fala
        )

        if dg_connection.start(options) is False:
            print("Erro ao conectar na Deepgram")
            return

        # Loop principal: Recebe áudio do Chrome e joga na Deepgram
        while True:
            data = await websocket.receive_bytes()
            dg_connection.send(data)

    except Exception as e:
        print(f"Erro: {e}")
    finally:
        if 'dg_connection' in locals():
            dg_connection.finish()
        await websocket.close()
