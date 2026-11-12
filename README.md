# Projeto de Interação Humano-Computador

Bot do Telegram que usa um LLM para traduzir perguntas em linguagem natural
em consultas SQL (apenas `SELECT`) e devolve o resultado ao usuário também em
linguagem natural.

## Como funciona

1. O usuário envia uma pergunta ao bot no Telegram.
2. O LLM converte a pergunta em uma consulta SQL somente de leitura (`SELECT`).
3. A consulta é executada no banco de dados.
4. O LLM transforma o resultado em uma resposta em linguagem natural.
5. O bot envia a resposta ao usuário.

## Pré-requisitos

- Python 3.x 
- Token de um bot do Telegram (criado via [@BotFather](https://t.me/BotFather))
- Servidor de LLM local em execução 

## Instalação

1. Instale as dependências:

   ```bash
   pip install -r requirements.txt
   ```

2. Crie o arquivo de configuração a partir do exemplo. Dentro da pasta `src`:

   ```bash
   # Windows
   copy .env.example .env

   # Linux / macOS
   cp .env.example .env
   ```

## Configuração

Edite o arquivo `src/.env`:

| Variável            | Descrição                                           |
|---------------------|-----------------------------------------------------|
| `TELEGRAM_TOKEN`    | Token do seu bot do Telegram <!-- confirmar nome -->|
| `ESTOQUE_LM_MODEL`  | Nome do modelo LLM que será utilizado               |

> Antes de executar, confirme que o servidor do LLM está rodando

## Execução

Rode os comandos a partir da pasta `src`:

| Arquivo        | Função                                      | Comando                |
|----------------|---------------------------------------------|------------------------|
| `server.py`    | Inicia o servidor                           | `python server.py`     |
| `bot.py`       | Inicia o bot do Telegram                    | `python bot.py`        |
| `evaluate.py`  | Valida/avalia a qualidade das consultas     | `python evaluate.py`   |
| `optimize.py`  | Otimiza os prompts usando GEPA              | `python optimize.py`   |

Para uso normal, mantenha `server.py` e `bot.py` rodando ao mesmo tempo, em
terminais separados. 