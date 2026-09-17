import os
import dspy
from evaluate import DATASET, metrica_resultado_correto
from server import LM_API_BASE, LM_API_KEY, LM_MODEL, ReliableSQLGenerator, init_db

REFLECTION_LM_MODEL = os.environ.get("ESTOQUE_REFLECTION_LM_MODEL", LM_MODEL)
REFLECTION_LM_API_BASE = os.environ.get("ESTOQUE_REFLECTION_LM_API_BASE", LM_API_BASE)
REFLECTION_LM_API_KEY = os.environ.get("ESTOQUE_REFLECTION_LM_API_KEY", LM_API_KEY)


def metrica_gepa(gold, pred, trace=None, pred_name=None, pred_trace=None) -> bool:
    return metrica_resultado_correto(gold, pred, trace)


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

    reflection_lm = dspy.LM(
        REFLECTION_LM_MODEL,
        api_base=REFLECTION_LM_API_BASE,
        api_key=REFLECTION_LM_API_KEY,
    )

    otimizador = dspy.GEPA(
        metric=metrica_gepa,
        auto="light",
        reflection_lm=reflection_lm,
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
