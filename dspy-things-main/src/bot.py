import json
import os
import telebot
import whisper
from dotenv import load_dotenv
from server import ConsultaInvalidaError, gerar_sql, get_connection, init_db

load_dotenv()
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
if not TELEGRAM_BOT_TOKEN:
    raise RuntimeError("Defina a variável de ambiente TELEGRAM_BOT_TOKEN antes de rodar o bot.")

init_db()
bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)

_modelo_whisper = None


def _transcrever(filepath: str, modelo: str = "tiny") -> str:
    global _modelo_whisper
    if _modelo_whisper is None:
        _modelo_whisper = whisper.load_model(modelo)
    return _modelo_whisper.transcribe(filepath)["text"]


def _responder(pergunta: str) -> str:
    try:
        sql = gerar_sql(pergunta)
    except ConsultaInvalidaError as e:
        return f"Não consegui montar uma consulta válida: {e}"

    conn = get_connection()
    try:
        rows = conn.execute(sql).fetchall()
        return json.dumps([dict(r) for r in rows], ensure_ascii=False, default=str)
    finally:
        conn.close()


@bot.message_handler(func=lambda message: True, content_types=["text"])
def responder_texto(message):
    bot.reply_to(message, _responder(message.text))


@bot.message_handler(content_types=["voice"])
def responder_voz(message):
    file_path = bot.get_file_url(message.voice.file_id)
    texto = _transcrever(file_path)
    bot.reply_to(message, _responder(texto))
