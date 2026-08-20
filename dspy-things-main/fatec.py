import sqlite3
import dspy
import os
import telebot #pip install pytelegrambotapi
import whisper #pip install -U openai-whisper
### whisper requires ffmpeg: on windows: choco install ffmpeg
import json
from estoque_db import get_connection

lm = dspy.LM('openai/gemma-4-E2B-it-IQ4_XS', api_base='http://localhost:1337/v1', api_key='not-needed')
dspy.configure(lm=lm)

class TextToSQL(dspy.Signature):
    """Generate SQL from natural language.

        Database schema:
          - produtos: id, nome, departamento, preco, data_fab, data_val, marca, quantidade
    """
    dbschema = dspy.InputField(desc="Databases schema")
    question = dspy.InputField(desc="Natural language question")

    sql_query = dspy.OutputField(desc="Valid SQL query")

class ReliableSQLGenerator(dspy.Module):
    def __init__(self):
        super().__init__()
        self.generate_sql = dspy.ChainOfThought(TextToSQL)

    def forward(self, schema, question):
        pred = self.generate_sql(schema=schema, question=question)
        return pred
    

question = "qual o departamento do sabonete?"

def generate(question):
    schema = """
    CREATE TABLE produtos (
      id INT,
      nome VARCHAR(50),
      departamento VARCHAR(50),
      preco float,
      data_fab DATE,
      data_val DATE,
      marca VARCHAR(50),
      quantidade INT
    );
    """
    generator = ReliableSQLGenerator()
    sql = generator.forward(schema, question)
    print(sql)
    conn = get_connection()
    print(sql.sql_query)
    results = conn.execute(sql.sql_query).fetchall()
    return [row[0] for row in results]

API_TOKEN = 'TOKEN'
bot = telebot.TeleBot(API_TOKEN)

@bot.message_handler(func=lambda message: True)
def reply_hi(message):
  result = generate(message.text)
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