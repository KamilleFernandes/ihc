from fastapi import FastAPI, Query
from query import generate

app = FastAPI()


@app.get("/consulta")
def get_consulta(pergunta: str = Query(..., description="Pergunta em linguagem natural")):
    resultado = generate(pergunta)
    return {"pergunta": pergunta, "resultado": resultado}