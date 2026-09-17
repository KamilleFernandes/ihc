import sqlite3
import dspy
from server import ReliableSQLGenerator, get_connection, init_db

DATASET = [
    {
        "question": "qual o departamento do sabonete?",
        "sql_esperado": "SELECT departamento FROM produtos WHERE nome = 'sabonete'",
    },
    {
        "question": "quantos produtos de bebidas existem?",
        "sql_esperado": "SELECT COUNT(*) FROM produtos WHERE departamento = 'bebidas'",
    },
    {
        "question": "qual o preço da coca?",
        "sql_esperado": "SELECT preco FROM produtos WHERE nome = 'coca'",
    },
    {
        "question": "quais produtos estão abaixo do estoque mínimo?",
        "sql_esperado": "SELECT nome FROM produtos WHERE quantidade < estoque_minimo",
    },
    {
        "question": "qual a marca da agua?",
        "sql_esperado": "SELECT marca FROM produtos WHERE nome = 'agua'",
    },
    {
        "question": "quantos produtos existem no total?",
        "sql_esperado": "SELECT COUNT(*) FROM produtos",
    },
    {
        "question": "qual é o produto mais caro?",
        "sql_esperado": "SELECT nome FROM produtos ORDER BY preco DESC LIMIT 1",
    },
    {
        "question": "qual é o produto mais barato?",
        "sql_esperado": "SELECT nome FROM produtos ORDER BY preco ASC LIMIT 1",
    },
    {
        "question": "qual a quantidade total em estoque, somando todos os produtos?",
        "sql_esperado": "SELECT SUM(quantidade) FROM produtos",
    },
    {
        "question": "qual o preço médio dos produtos?",
        "sql_esperado": "SELECT AVG(preco) FROM produtos",
    },
    {
        "question": "quais produtos são fornecidos pela Distribuidora XYZ?",
        "sql_esperado": "SELECT nome FROM produtos WHERE fornecedor = 'Distribuidora XYZ'",
    },
    {
        "question": "quantos departamentos diferentes existem cadastrados nos produtos?",
        "sql_esperado": "SELECT COUNT(DISTINCT departamento) FROM produtos",
    },
    {
        "question": "quais são os departamentos cadastrados?",
        "sql_esperado": "SELECT DISTINCT departamento FROM produtos",
    },
    {
        "question": "quais produtos custam mais de 5 reais?",
        "sql_esperado": "SELECT nome FROM produtos WHERE preco > 5",
    },
]


def _executar(sql: str) -> set:
    conn = get_connection()
    try:
        return {tuple(row) for row in conn.execute(sql).fetchall()}
    finally:
        conn.close()


def metrica_resultado_correto(example, pred, trace=None) -> bool:
    try:
        return _executar(example.sql_esperado) == _executar(pred.sql_query)
    except sqlite3.Error:
        return False


def avaliar() -> float:
    init_db()
    generator = ReliableSQLGenerator()

    exemplos = [
        dspy.Example(question=item["question"], sql_esperado=item["sql_esperado"]).with_inputs("question")
        for item in DATASET
    ]

    avaliador = dspy.Evaluate(
        devset=exemplos,
        metric=metrica_resultado_correto,
        display_progress=True,
        display_table=True,
    )
    return avaliador(generator)


if __name__ == "__main__":
    print(f"Avaliação: {avaliar()}")
