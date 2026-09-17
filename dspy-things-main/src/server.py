import os
import sqlite3
from pathlib import Path

import dspy
from fastapi import FastAPI, Query

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = os.environ.get("ESTOQUE_DB_PATH", str(BASE_DIR / "estoque.db"))

LM_MODEL = os.environ.get("ESTOQUE_LM_MODEL", "openai/gemma-4-E2B-it-IQ4_XS")
LM_API_BASE = os.environ.get("ESTOQUE_LM_API_BASE", "http://localhost:1337/v1")
LM_API_KEY = os.environ.get("ESTOQUE_LM_API_KEY", "not-needed")
MAX_TENTATIVAS_SQL = int(os.environ.get("ESTOQUE_MAX_TENTATIVAS_SQL", "3"))

dspy.configure(lm=dspy.LM(LM_MODEL, api_base=LM_API_BASE, api_key=LM_API_KEY))

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


def get_connection(db_path: str = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


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


class TextToSQL(dspy.Signature):
    """Gera uma consulta SQL SQLite a partir de uma pergunta em português.

    Gere APENAS comandos SELECT. Nunca gere INSERT, UPDATE, DELETE ou DROP.
    """
    dbschema: str = dspy.InputField(desc="Schema das tabelas disponíveis")
    question: str = dspy.InputField(desc="Pergunta em linguagem natural")
    sql_query: str = dspy.OutputField(desc="Consulta SQL SELECT válida para SQLite")


class SQLRepair(dspy.Signature):
    """Corrige uma consulta SQL que falhou, usando a mensagem de erro do banco."""
    dbschema: str = dspy.InputField(desc="Schema das tabelas disponíveis")
    question: str = dspy.InputField(desc="Pergunta original em linguagem natural")
    sql_query_com_erro: str = dspy.InputField(desc="SQL que falhou")
    erro: str = dspy.InputField(desc="Mensagem de erro retornada pelo banco")
    sql_query: str = dspy.OutputField(desc="SQL corrigida")


class ConsultaInvalidaError(Exception):
    pass


def _eh_select(sql_query: str) -> bool:
    return sql_query.strip().lower().startswith("select")


def _validar_no_banco_sombra(sql_query: str) -> str | None:
    try:
        sombra = sqlite3.connect(":memory:")
        sombra.executescript(SCHEMA_SQL)
        sombra.execute(sql_query)
        sombra.close()
        return None
    except sqlite3.Error as e:
        return str(e)


class ReliableSQLGenerator(dspy.Module):
    def __init__(self, max_tentativas: int = MAX_TENTATIVAS_SQL):
        super().__init__()
        self.generate_sql = dspy.ChainOfThought(TextToSQL)
        self.repair_sql = dspy.ChainOfThought(SQLRepair)
        self.max_tentativas = max_tentativas

    def forward(self, question: str, schema: str = SCHEMA_SQL):
        pred = self.generate_sql(dbschema=schema, question=question)
        sql_query = pred.sql_query
        ultimo_erro = None

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


def gerar_sql(question: str) -> str:
    pred = ReliableSQLGenerator()(question=question)
    return pred.sql_query


app = FastAPI(title="Estoque API")


@app.on_event("startup")
def _startup() -> None:
    init_db()


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
