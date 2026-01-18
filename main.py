import os
import json
import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from deepgram import DeepgramClient, LiveTranscriptionEvents, LiveOptions
from groq import Groq
from dotenv import load_dotenv

# Carrega variáveis de ambiente
load_dotenv()

app = FastAPI()

# Configuração de CORS (Permite conexão da extensão)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Chaves de API
DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Validação simples
if not DEEPGRAM_API_KEY or not GROQ_API_KEY:
    print("❌ ERRO: Chaves de API não configuradas no Railway!")

groq_client = Groq(api_key=GROQ_API_KEY)

async def analyze_sales_context(text_chunk):
    """
    Analisa o texto com Llama 3 para extrair:
    - Sentimento (0-100)
    - Perfil DISC
    - Checklist (Temas falados)
    - Dicas (Advice)
    """
    # Ignora frases muito curtas
    if len(text_chunk.split()) < 4: return None
    
    prompt = f"""
    Analise a frase de vendas: "{text_chunk}"
    Retorne JSON estrito:
    {{
        "sentiment": (inteiro 0-100, 0=ruim 100=otimo),
        "disc": ("D", "I", "S", "C" ou "--"),
        "topics": (lista de strings: ["preco", "prazo", "escopo", "geral"]),
        "advice": (string com dica curta de venda ou null)
    }}
    """
    try:
        chat = groq_client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.3-70b-versatile",
            temperature=0.2,
            max_tokens=150,
            response_format={"type": "json_object"}
        )
        return json.loads(chat.choices[0].message.content)
    except Exception as e:
        print(f"Erro Groq: {e}")
        return None

@app.websocket("/listen")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("🟢 (WebSocket) Extensão Conectada")

    # Estado inicial da checklist
    checklist_state = {"preco": False, "prazo": False, "escopo": False}

    try:
        # Inicia cliente Deepgram
        deepgram = DeepgramClient(DEEPGRAM_API_KEY)
        dg_connection = deepgram.listen.live.v("1")

        # --- EVENTOS DEEPGRAM ---
        async def on_message(result, **kwargs):
            sentence = result.channel.alternatives[0].transcript
            if len(sentence) > 0:
                is_final = result.is_final
                
                # 1. Envia Transcrição Imediata
                await websocket.send_json({"type": "transcript", "text": sentence})
                
                # 2. Se a frase acabou, analisa com IA
                if is_final:
                    print(f"📝 Frase detectada: {sentence}")
                    analysis = await analyze_sales_context(sentence)
                    
                    if analysis:
                        # Atualiza Checklist
                        topics = analysis.get("topics", [])
                        for t in ["preco", "prazo", "escopo"]:
                            if t in topics: checklist_state[t] = True
                        
                        # Envia Análise
                        payload = {
                            "type": "analysis",
                            "sentiment": analysis.get("sentiment", 50),
                            "disc": analysis.get("disc", "--"),
                            "advice": analysis.get("advice"),
                            "checklist": checklist_state
                        }
                        await websocket.send_json(payload)
        
        async def on_error(error, **kwargs):
            print(f"❌ Erro Deepgram: {error}")

        # Conecta os eventos
        dg_connection.on(LiveTranscriptionEvents.Transcript, on_message)
        dg_connection.on(LiveTranscriptionEvents.Error, on_error)

        # CONFIGURAÇÃO DE ÁUDIO (A Correção está aqui)
        # Removemos 'encoding' e 'sample_rate' para deixar a Deepgram 
        # detectar automaticamente o formato WebM do Chrome.
        options = LiveOptions(
            model="nova-2",
            language="pt-BR",
            smart_format=True,
            interim_results=True,
            # encoding="opus" <--- REMOVIDO: Isso causava o erro 1011
        )

        if dg_connection.start(options) is False:
            print("❌ Falha ao iniciar conexão com Deepgram")
            await websocket.close()
            return

        print("🚀 Deepgram Iniciada e Ouvindo...")

        # --- LOOP DE RECEBIMENTO DE ÁUDIO ---
        while True:
            try:
                # Recebe áudio da extensão e repassa para Deepgram
                data = await websocket.receive_bytes()
                dg_connection.send(data)
            except WebSocketDisconnect:
                print("🔴 Extensão desconectou")
                break
            except Exception as e:
                print(f"❌ Erro no loop de áudio: {e}")
                break

    except Exception as e:
        print(f"❌ Erro Geral: {e}")
    finally:
        # Limpeza
        if 'dg_connection' in locals():
            dg_connection.finish()
        print("🏁 Conexão Encerrada")
