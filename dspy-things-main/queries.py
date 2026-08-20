from estoque_db import get_connection

def listar_produtos():
    conn = get_connection()
    c = conn.cursor()
    
    c.execute ("SELECT * FROM produtos")
    produtos = c.fetchall()

    conn.close()

    return [dict(produtos) for produtos in produtos]