import os
import telebot #pip install pytelegrambotapi
import whisper #pip install -U openai-whisper
### whisper requires ffmpeg: on windows: choco install ffmpeg
import json
from server import get_connection
from server import gerar_sql
import dspy

lm = dspy.LM('openai/gemma-4-E2B-it-IQ4_XS', api_base='http://localhost:1337/v1', api_key='not-needed')
dspy.configure(lm=lm)

API_TOKEN = '8876361936:AAH52YTMJHCUa3TD0Uvf6OqrwqpbOS6K0VM'
bot = telebot.TeleBot(API_TOKEN)

@bot.message_handler(func=lambda message: True)
def reply_hi(message):
  result = gerar_sql(message.text)
  bot.reply_to(message, json.dumps(result))

@bot.message_handler(content_types=['voice'])
def transcribe_voice_message(message):
    file_id = message.voice.file_id
    # Get url to audio file.
    file_path = bot.get_file_url(file_id)

    # Transcribe the audio using Whisper AI
    text = whisper_transcribe(file_path)

    result = generate(text)
    bot.reply_to(message, json.dumps(result))

def whisper_transcribe(filepath: str, model="tiny") -> str:
    """
    Function to perform ASR on a .mp3 file
    :param filepath: Path to the .mp3 audiofile.
    :param model: Set the model type for whisper
    ["tiny", "base", "small", "medium", "large"].
    Larger model means more parameters, higher memory requirements and
    slower speed.
    :return: transcribed audio.
    """
    # Choose tiny model for faster output.
    model = whisper.load_model(model)
    result = model.transcribe(filepath)

    return result["text"]

bot.polling()