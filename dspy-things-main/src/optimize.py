import dspy
from evaluate import DATASET, metrica_resultado_correto
from server import ReliableSQLGenerator, init_db


def otimizar(caminho_saida: str = "sql_agent_otimizado.json") -> ReliableSQLGenerator:
    init_db()
    generator = ReliableSQLGenerator()

    exemplos = [
        dspy.Example(question=item["question"], sql_esperado=item["sql_esperado"]).with_inputs("question")
        for item in DATASET
    ]

    metade = max(1, len(exemplos) // 2)
    treino = exemplos[:metade]
    validacao = exemplos[metade:] or exemplos

    otimizador = dspy.GEPA(
        metric=metrica_resultado_correto,
        auto="light",
    )

    generator_otimizado = otimizador.compile(
        generator,
        trainset=treino,
        valset=validacao,
    )

    generator_otimizado.save(caminho_saida)
    print(f"Gerador otimizado salvo em {caminho_saida}")
    return generator_otimizado


if __name__ == "__main__":
    otimizar()
