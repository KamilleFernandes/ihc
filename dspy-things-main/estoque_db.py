import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.join(BASE_DIR, "lojas.db")

def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def create_db():
  conn = get_connection()
  c = conn.cursor()

  # Create tables
  c.execute("""CREATE TABLE IF NOT EXISTS produtos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT, 
                departamento TEXT,
                preco float,
                data_fab date,
                data_val date,
                marca TEXT,
                quantidade INT

            )""")
  c.execute("SELECT COUNT(*) FROM produtos")
  if c.fetchone()[0] == 0:
        c.executemany("INSERT INTO produtos (nome, departamento, preco, data_fab, data_val, marca, quantidade) VALUES (?, ?, ?, ?, ?, ?, ?)", [
    ("sabonete", "higiene", 2.50, '2026-10-20', '2029-10-20', "jhonson", 30 ),
    ("agua", "bebidas", 3.00, '2026-2-5', '2026-3-5', "cristal", 50 ),
    ("coca", "bebidas", 7.50, '2026-3-12', '2026-6-12', "Coca-Cola", 34),
  ])

  conn.commit()
  conn.close()

create_db()


