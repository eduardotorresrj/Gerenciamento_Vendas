from app import app, db
from models import Venda  # Certifique-se de importar o modelo Venda

with app.app_context():
    # Adiciona a coluna `mes_numero` à tabela `venda`
    db.engine.execute('ALTER TABLE venda ADD COLUMN mes_numero INTEGER')

    # Atualiza os registros existentes para preencher o campo `mes_numero`
    vendas = Venda.query.all()
    for venda in vendas:
        venda.mes_numero = venda.data.month  # Preenche com o número do mês
    db.session.commit()

    print("Migração concluída com sucesso!")
