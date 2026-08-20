from fastapi import FastAPI
from queries import listar_produtos

app = FastAPI()

@app.get("/estoque")
def get_estoque():
    return listar_produtos()