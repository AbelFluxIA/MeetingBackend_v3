import os
import json
import asyncio
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from deepgram import DeepgramClient, LiveTranscriptionEvents, LiveOptions
from groq import Groq
from dotenv import load_dotenv

# Carrega as variáveis de ambiente (Railway)
load_dotenv()

app = FastAPI()

# Permissões de CORS (para a extensão conseguir conectar)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuração das Chaves de API
DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Cliente da Inteligência Artificial (Groq)
groq_client = Groq(api_key=GROQ_API_KEY)

async def analyze_sales_context(text_chunk):
    """
    Função que envia o texto para a IA e pede uma análise completa
    retornando um JSON estruturado com Sentimento, DISC e Dicas.
    """
    # Ignora frases muito curtas para economizar e evitar alucinações
    if len(text_chunk.split()) < 4: 
        return None

    prompt = f"""
    Você é um Analista de Vendas IA em tempo real.
    Analise a frase do cliente: "{text_chunk}"
    
    Retorne APENAS um JSON com este formato estrito:
    {{
        "sentiment": (inteiro de 0 a 100, onde 0=irritado/frio, 100=empolgado/quente),
        "disc": (string: "D" para Dominante, "I" para Influente, "S" para Estável, ou "C" para Conforme),
        "topics": (lista de strings com os temas falados, ex: ["preco", "prazo", "escopo", "geral"]),
        "advice": (string curta com uma dica de venda se houver objeção ou dúvida, ou null se estiver tudo bem)
    }}
    """
    
    try:
        chat = groq_client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.3-70b-versatile",
            temperature=0.2,
            max_tokens=150,
            response_format={"type": "json_object"} # Garante que volta JSON puro
        )
        return json.loads(chat.choices[0].message.content)
    except Exception as e:
        print(f"Erro na IA: {e}")
        return None

@app.websocket("/listen")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("🔌 Cliente conectado (Extensão V3.1)")

    # Estado da Checklist (Reinicia a cada nova conexão)
    checklist_state = {
        "preco": False,
        "prazo": False,
        "escopo": False
    }

    try:
        # Conecta na Deepgram
        deepgram = DeepgramClient(DEEPGRAM_API_KEY)
        
        # Função chamada toda vez que a Deepgram manda um texto
        async def on_message(result, **kwargs):
            sentence = result.channel.alternatives[0].transcript
            
            if len(sentence) > 0:
                is_final = result.is_final
                
                # 1. Envia a transcrição instantânea para a tela (Legenda)
                await websocket.send_json({"type": "transcript", "text": sentence})
                
                # 2. Se a frase foi finalizada, chama a Inteligência
                if is_final:
                    analysis = await analyze_sales_context(sentence)
                    
                    if analysis:
                        # Atualiza a Checklist se o tema foi citado
                        topics = analysis.get("topics", [])
                        if "preco" in topics: checklist_state["preco"] = True
                        if "prazo" in topics: checklist_state["prazo"] = True
                        if "escopo" in topics: checklist_state["escopo"] = True
                        
                        # Monta o pacote de dados para o Frontend
                        payload = {
                            "type": "analysis",
                            "sentiment": analysis.get("sentiment", 50),
                            "disc": analysis.get("disc", "--"),
                            "advice": analysis.get("advice"),
                            "checklist": checklist_state
                        }
                        
                        # Envia para a extensão atualizar os gráficos
                        await websocket.send_json(payload)

        # Configurações da Deepgram Live
        dg_connection = deepgram.listen.live.v("1")
        dg_connection.on(LiveTranscriptionEvents.Transcript, on_message)
        
        options = LiveOptions(
            model="nova-2", 
            language="pt-BR", 
            smart_format=True, 
            interim_results=True
        )

        if dg_connection.start(options) is False:
            print("Erro ao conectar na Deepgram")
            return

        # Loop principal: Recebe áudio do WebSocket e joga na Deepgram
        while True:
            data = await websocket.receive_bytes()
            dg_connection.send(data)

    except Exception as e:
        print(f"Erro WebSocket: {e}")
    finally:
        # Limpeza ao desconectar
        if 'dg_connection' in locals():
            dg_connection.finish()
        await websocket.close()
        print("🔌 Cliente desconectado")
