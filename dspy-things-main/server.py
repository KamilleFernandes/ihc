import sqlite3
import os
import dspy

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.join(BASE_DIR, "estoque.db")
MAX_TENTATIVAS_SQL = int(os.environ.get("ESTOQUE_MAX_TENTATIVAS_SQL", "3"))

#criação do banco e preenchimento da tabela

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS produtos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    departamento TEXT NOT NULL UNIQUE,
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

def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def create_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA_SQL)
    conn.commit()

def if_empty(conn: sqlite3.Connection) -> None:
    count = conn.execute("SELECT COUNT(*) FROM produtos").fetchone()[0]
    if count > 0:
        return

    conn.executemany(
        """INSERT INTO produtos
           (nome, departamento, preco, data_fab, data_ven, marca, quantidade, fornecedor, estoque_minimo)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        [
            (nome, departamento, preco, data_fab, data_ven, marca, qtd, fornecedor, minimo)
            for nome, depto, preco, data_fab, data_ven, marca, qtd, fornecedor, minimo in PRODUTOS
        ],
    )
    conn.commit()

def init_db() -> None:
    conn = get_connection()
    try:
        create_schema(conn)
        seed_if_empty(conn)
    finally:
        conn.close()

__all__ = ["get_connection", "create_schema", "if_empty", "init_db", "SCHEMA_SQL", "ReliableSQLGenerator", "gerar_sql", "ConsultaInvalidaError"]

#Validação das consultas (apenas select), recebimento da consulta sql e teste no banco in memory, e retorno da consulta sql validada

class TextToSQL(dspy.Signature):
    dbschema: str = dspy.InputField(desc="Schema das tabelas disponíveis")
    question: str = dspy.InputField(desc="Pergunta em linguagem natural")
    sql_query: str = dspy.OutputField(desc="Consulta SQL SELECT válida")


class SQLRepair(dspy.Signature):
    dbschema: str = dspy.InputField(desc="Schema das tabelas disponíveis")
    question: str = dspy.InputField(desc="Pergunta original em linguagem natural")
    sql_query_com_erro: str = dspy.InputField(desc="SQL que falhou")
    erro: str = dspy.InputField(desc="Mensagem de erro retornada pelo banco")
    sql_query: str = dspy.OutputField(desc="SQL corrigida")

class ConsultaInvalidaError(Exception):

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
        self._eh_select = dspy.Predict(ConsultaInvalidaError)

    def forward(self, question: str, schema: str = SCHEMA_SQL):
        pred = self.generate_sql(dbschema=schema, question=question)
        sql_query = pred.sql_query
        ultimo_erro = None

        for _ in range(self.max_tentativas):
            if not self._eh_select(sql_query):
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
    generator = ReliableSQLGenerator()
    pred = generator(question=question)
    return pred.sql_query


