import os
import sqlite3
from pathlib import Path

import dspy
from fastapi import FastAPI, Query

# cria variável de ambiente com o caminho do bancco de dados do estoque
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = os.environ.get("ESTOQUE_DB_PATH", str(BASE_DIR / "estoque.db"))

# variável de ambiente da LLM 
LM_MODEL = os.environ.get("ESTOQUE_LM_MODEL", "openai/gemma-4-E2B-it-IQ4_XS")
LM_API_BASE = os.environ.get("ESTOQUE_LM_API_BASE", "http://localhost:1337/v1")
LM_API_KEY = os.environ.get("ESTOQUE_LM_API_KEY", "not-needed")

# cria variáveis de tentativas máximas para validação da query
MAX_TENTATIVAS_SQL = int(os.environ.get("ESTOQUE_MAX_TENTATIVAS_SQL", "3"))

# variável de ambiente com os resultados da otimização com gepa
OTIMIZADO_PATH = os.environ.get("ESTOQUE_SQL_AGENT_PATH", str(BASE_DIR/"sql_agent_otimizado.json"))

dspy.configure(lm=dspy.LM(LM_MODEL, api_base=LM_API_BASE, api_key=LM_API_KEY))


# script do banco, tabela e dados iniciais
SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS produtos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    departamento TEXT NOT NULL,
    preco REAL NOT NULL,
    data_fab DATE,
    data_ven DATE,
    marca TEXT,
    quantidade INTEGER NOT NULL DEFAULT 0,
    fornecedor TEXT,
    estoque_minimo INTEGER NOT NULL DEFAULT 0
);
"""

PRODUTOS = [
    ("sabonete", "higiene", 2.50, "2026-10-20", "2029-10-20", "Jhonson", 30, "Distribuidora ABC", 10),
    ("agua", "bebidas", 3.00, "2026-02-05", "2026-03-05", "Cristal", 50, "Distribuidora XYZ", 20),
    ("coca", "bebidas", 7.50, "2026-03-12", "2026-06-12", "Coca-Cola", 34, "Distribuidora XYZ", 15),
]

# conecta com o banco em sqlite
def get_connection(db_path: str = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


# inicia conectando com o banco e executando o script do banco caso esteja vazio
def init_db() -> None:
    conn = get_connection()
    try:
        conn.executescript(SCHEMA_SQL)
        conn.commit()

        if conn.execute("SELECT COUNT(*) FROM produtos").fetchone()[0] == 0:
            conn.executemany(
                """INSERT INTO produtos
                   (nome, departamento, preco, data_fab, data_ven, marca, quantidade, fornecedor, estoque_minimo)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                PRODUTOS,
            )
            conn.commit()
    finally:
        conn.close()

# signature para receber o schema da tabela, a pergunta feita no bot, e a query gerada
class TextToSQL(dspy.Signature):
    dbschema: str = dspy.InputField(desc="Schema das tabelas disponíveis")
    question: str = dspy.InputField(desc="Pergunta em linguagem natural")
    sql_query: str = dspy.OutputField(desc="Consulta SQL SELECT válida para SQLite")

# signature para receber schema da tabela, pergunta feita no bot, guardar query caso haja erro, guardar mensagem de erro e guardar a sql nova corrigida no csao de erro
class SQLRepair(dspy.Signature):
    dbschema: str = dspy.InputField(desc="Schema das tabelas disponíveis")
    question: str = dspy.InputField(desc="Pergunta original em linguagem natural")
    sql_query_com_erro: str = dspy.InputField(desc="SQL que falhou")
    erro: str = dspy.InputField(desc="Mensagem de erro retornada pelo banco")
    sql_query: str = dspy.OutputField(desc="SQL corrigida")


class ConsultaInvalidaError(Exception):
    pass

# verifica se query gerada é do tipo select
def _eh_select(sql_query: str) -> bool:
    return sql_query.strip().lower().startswith("select")

# validação no banco in memory:
# cria banco in memory, executa o schema da tabela 
# executa a query gerada pela llm
# retorna None caso sucesso, caso der erro retorna a string do erro. 
def _validar_no_banco_sombra(sql_query: str) -> str | None:
    try:
        sombra = sqlite3.connect(":memory:")
        sombra.executescript(SCHEMA_SQL)
        sombra.executemany(
                """INSERT INTO produtos
                   (nome, departamento, preco, data_fab, data_ven, marca, quantidade, fornecedor, estoque_minimo)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                PRODUTOS,
            )
        sombra.execute(sql_query)
        sombra.close()
        return None
    except sqlite3.Error as e:
        return str(e)

# validação da query testada no banco in memory 
# recebe a variável de máximo de tentativas
# executa a sql, verifica o ultimo erro, e gera novamente a sql 
class ReliableSQLGenerator(dspy.Module):
    def __init__(self, max_tentativas: int = MAX_TENTATIVAS_SQL):
        super().__init__()
        self.generate_sql = dspy.ChainOfThought(TextToSQL)
        self.repair_sql = dspy.ChainOfThought(SQLRepair)
        self.max_tentativas = max_tentativas

    # recebe a tabela do banco, a questão e gera o sql
    # cria um laço for para verificar resultado da sql gerada, em caso de erro gera uma nova, no máximo 3 vezes
    def forward(self, question: str, schema: str = SCHEMA_SQL):
        pred = self.generate_sql(dbschema=schema, question=question)
        sql_query = pred.sql_query
        ultimo_erro = None

        # primeiramente valida se é select, se não erro recebe mensagem de "não é select" 
        # caso seja select, valida no banco sombra e caso dê erro, variável ultimo_erro recebe o resultado do erro
        # recebe erro, manda para llm gerar nova sql
        # a cada tentativa gera uma correção, na terceira retorna o último resultado
        # caso tenha erro exibe a mensagem de que não foi possível gerar uma consulta válida e mostra o erro 

        for _ in range(self.max_tentativas):
            if not _eh_select(sql_query):
                ultimo_erro = "Consulta bloqueada: apenas SELECT é permitido."
            else:
                ultimo_erro = _validar_no_banco_sombra(sql_query)

            if ultimo_erro is None:
                pred.sql_query = sql_query
                return pred

            pred = self.repair_sql(
                dbschema=schema,
                question=question,
                sql_query_com_erro=sql_query,
                erro=ultimo_erro,
            )
            sql_query = pred.sql_query

        raise ConsultaInvalidaError(
            f"Não foi possível gerar SQL válido em {self.max_tentativas} tentativas. "
            f"Último erro: {ultimo_erro}"
        )


# se já existir o arquivo otimizado o gerador de query, carrega os resultados da otimização 
_generator = ReliableSQLGenerator()
if os.path.exists(OTIMIZADO_PATH):
    _generator.load(OTIMIZADO_PATH)

# função que gera as querys, utilizando o generator otimizado caso tenha sido carregado, e retorna query final '''
def gerar_sql(question: str) -> str:
    pred = _generator(question=question)
    return pred.sql_query

# rotas GET do fastapi, para comunicação com banco, llm recebe questões e retorna query gerada'''
app = FastAPI(title="Estoque API")


@app.on_event("startup")
def _startup() -> None:
    init_db()

# rota principal que retorna ao bot o resultado da consulta, e recebe a questão 
@app.get("/consulta")
def consulta_natural(pergunta: str = Query(..., description="Pergunta em linguagem natural")):
    try:
        sql = gerar_sql(pergunta)
    except ConsultaInvalidaError as e:
        return {"pergunta": pergunta, "erro": str(e)}

    conn = get_connection()
    try:
        rows = conn.execute(sql).fetchall()
        return {"pergunta": pergunta, "sql": sql, "resultado": [dict(r) for r in rows]}
    finally:
        conn.close()

# execução do server
import uvicorn

if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
