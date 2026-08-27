import dspy
from estoque_db import get_connection

lm = dspy.LM('openai/gemma-4-E2B-it-IQ4_XS', api_base='http://localhost:1337/v1', api_key='not-needed')
dspy.configure(lm=lm)

SCHEMA_SQL =  """
    CREATE TABLE produtos (
      id INT,
      nome VARCHAR(50),
      departamento VARCHAR(50),
      preco float,
      data_fab DATE,
      data_val DATE,
      marca VARCHAR(50),
      quantidade INT
    );
    """

class TextToSQL(dspy.Signature):
    """Generate SQL from natural language.

        Database schema:
          - produtos: id, nome, departamento, preco, data_fab, data_val, marca, quantidade
    """
    dbschema = dspy.InputField(desc="Databases schema")
    question = dspy.InputField(desc="Natural language question")

    sql_query = dspy.OutputField(desc="Valid SQL query")

class RepairSQL(dspu.Signature):
    dbschema = dspy.InputField(desc="Databases schema")
    question = dspy.InputField(desc="Natural language question")
    sql_query_erro = dspy.OutputField(desc="SQL query failed")
    erro = dspy.InputField(desc="Error message returned by databases")
    sql_query = dspy.OutputField(desc="Correct valid SQL query")


class ReliableSQLGenerator(dspy.Module):
    def __init__(self, max_tentativas: int = 3):
        super().__init__()
        self.generate_sql = dspy.ChainOfThought(TextToSQL)
        self.repair_sql = dspy.ChainOfThought(RepairSQL)
        self.max_tentativas = max_tentativas
        

    def validar(self, sql_query:str) str | NONE:
        try:
            conn = sqlite3.connect(':memory:')
            conn.executescript(SCHEMA_SQL)
            conn.execute(sql_query)
            conn.close()
            return NONE

        except sqlite3.Eror as e:
            return str(e)


    def forward(self, schema, question):
        pred = self.generate_sql(schema=schema, question=question)
        sql_query = pred.sql_query

        for tentativas in range(self.max_tentativas):
            erro = self._validar(sql_query)

            if erro is NONE:
                pred.sql_query = sql_query
                return pred
            
            print(f'[tentativas {tentativas + 1} ] SQL inválida: {erro} \n SQL: {sql_query}')
            
            pred = self.repair_sql(
                schema = schema,
                question = question,
                sql_query_erro = sql_query,
                erro = erro
            )
            sql_query = pred.sql_query
    
        pred.sql_query = NONE
        pred.erro = f"Não foi possível gerar consulta SQL válida após {self.max_tentativas}"
        return pred



def generate(ques9tion):
    schema = """
    CREATE TABLE produtos (
      id INT,
      nome VARCHAR(50),
      departamento VARCHAR(50),
      preco float,
      data_fab DATE,
      data_val DATE,
      marca VARCHAR(50),
      quantidade INT
    );
    """
    generator = ReliableSQLGenerator()
    sql = generator.forward(schema, question)
    print(sql)
    conn = get_connection()
    print(sql.sql_query)
    results = conn.execute(sql.sql_query).fetchall()
    return [dict(row) for row in results]