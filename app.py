from flask import Flask, render_template, request, redirect, url_for, flash, session
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
import os
from sqlalchemy.orm import joinedload

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Configuração do Banco de Dados
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///meu_banco.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Lista de meses em português para evitar problemas com locale
MESES = [
    "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"
]

# Modelo de Usuário
class Usuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    senha = db.Column(db.String(150), nullable=False)

# Modelo de Produto
class Produto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    descricao = db.Column(db.String(200))
    preco = db.Column(db.Float, nullable=False)
    quantidade = db.Column(db.Integer, nullable=False)
    quantidade_inicial = db.Column(db.Integer)
    linha = db.Column(db.String(100), nullable=False)

    def __repr__(self):
        return f'<Produto {self.nome}>'

# Modelo de Venda
class Venda(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    produto_id = db.Column(db.Integer, db.ForeignKey('produto.id'), nullable=False)
    quantidade = db.Column(db.Integer, nullable=False)
    preco = db.Column(db.Float, nullable=False)
    total = db.Column(db.Float, nullable=False)
    data = db.Column(db.Date, nullable=False)
    mes = db.Column(db.String(20), nullable=False)
    ano = db.Column(db.Integer, nullable=False)

    produto_relacionado = db.relationship('Produto')

    def __init__(self, produto_id, quantidade, preco, total, data, mes, ano):
        self.produto_id = produto_id
        self.quantidade = quantidade
        self.preco = preco
        self.total = total
        self.data = data
        self.mes = mes
        self.ano = ano


# Modelo para Relatório Mensal
class RelatorioMensal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    mes = db.Column(db.String(50), nullable=False)
    ano = db.Column(db.Integer, nullable=False)
    quantidade_vendida = db.Column(db.Integer, nullable=False)
    soma_mensal = db.Column(db.Float, nullable=False)

# Criação do Banco e das Tabelas
with app.app_context():
    db.create_all()

# Rota principal
@app.route('/')
def index():
    if 'usuario_id' not in session:
        return redirect(url_for('login_view'))

    # Agrupando os produtos por linha
    produtos_por_linha = {}
    produtos = Produto.query.all()

    for produto in produtos:
        if produto.linha not in produtos_por_linha:
            produtos_por_linha[produto.linha] = []
        produtos_por_linha[produto.linha].append(produto)

    return render_template('index.html', produtos_por_linha=produtos_por_linha, titulo="Produtos")

# Adicionar produto
@app.route('/adicionar_produto', methods=['GET', 'POST'])
def adicionar_produto():
    if request.method == 'POST':
        nome = request.form['nome']
        quantidade = int(request.form['quantidade'])
        preco = float(request.form['preco'])
        linha = request.form.get('linha')

        if not linha:
            flash('Por favor, selecione uma linha do produto!', 'danger')
            return redirect(url_for('adicionar_produto'))

        produto = Produto(
            nome=nome,
            quantidade=quantidade,
            quantidade_inicial=quantidade,
            preco=preco,
            linha=linha
        )
        db.session.add(produto)
        db.session.commit()
        flash('Produto adicionado com sucesso!', 'success')
        return redirect(url_for('index'))

    linhas = db.session.query(Produto.linha).distinct().all()
    linhas = [l[0] for l in linhas]
    return render_template('adicionar_produto.html', linhas=linhas)


# Selecionar Linha
@app.route('/selecionar_linha', methods=['GET', 'POST'])
def selecionar_linha():
    linhas = db.session.query(Produto.linha).distinct().all()
    linhas = [l[0] for l in linhas]  # Ajuste para pegar apenas os valores

    if not linhas:
        flash("Nenhuma linha cadastrada. Adicione produtos com linhas antes de vender.", "danger")
        return redirect(url_for('index'))

    if request.method == 'POST':
        linha_escolhida = request.form.get('linha')  # Usa get() para evitar o erro de KeyError

        if not linha_escolhida:
            flash("Erro: Nenhuma linha selecionada!", "danger")
            return redirect(url_for('selecionar_linha'))

        return redirect(url_for('selecionar_produto', linha=linha_escolhida))

    return render_template('selecionar_linha.html', linhas=linhas)


# Selecionar Produto por Linha
@app.route('/selecionar_produto/<linha>', methods=['GET', 'POST'])
def selecionar_produto(linha):
    produtos = Produto.query.filter_by(linha=linha).all()

    if request.method == 'POST':
        produto_id = request.form['produto']
        return redirect(url_for('vender_produto', produto_id=produto_id))

    return render_template('selecionar_produto.html', produtos=produtos, linha=linha)




# Editar produto
@app.route('/editar_produto/<int:produto_id>', methods=['GET', 'POST'])
def editar_produto(produto_id):
    produto = Produto.query.get_or_404(produto_id)
    if request.method == 'POST':
        produto.nome = request.form['nome']
        produto.preco = float(request.form['preco'])
        produto.quantidade = int(request.form['quantidade'])
        produto.quantidade_inicial = int(request.form['quantidade'])  # Atualiza a quantidade inicial

        db.session.commit()
        flash('Produto atualizado com sucesso!', 'success')
        return redirect(url_for('index'))

    return render_template('editar_produto.html', produto=produto)


# Vender produto
@app.route('/vender_produto/<int:produto_id>', methods=['GET', 'POST'])
def vender_produto(produto_id):
    produto = Produto.query.get_or_404(produto_id)
    estoque_inicial = produto.quantidade
    hoje = datetime.today().date()

    if request.method == 'POST':
        quantidade_venda = int(request.form['quantidade_venda'])
        data_venda_str = request.form.get('data_venda', '').strip()

        if quantidade_venda > produto.quantidade:
            flash('Quantidade insuficiente em estoque!', 'danger')
        else:
            produto.quantidade -= quantidade_venda

            if data_venda_str:
                try:
                    data_venda = datetime.strptime(data_venda_str, "%Y-%m-%d").date()
                except ValueError:
                    flash("Data inválida! Use o formato correto (AAAA-MM-DD).", "danger")
                    return redirect(url_for('vender_produto', produto_id=produto.id))
            else:
                data_venda = hoje

            # Usa a lista de meses em português
            mes = MESES[data_venda.month - 1]
            ano = data_venda.year

            venda = Venda(
                produto_id=produto.id,
                quantidade=quantidade_venda,
                preco=produto.preco,
                total=quantidade_venda * produto.preco,
                data=data_venda,
                mes=mes,
                ano=ano
            )
            db.session.add(venda)
            db.session.commit()

            flash('Venda registrada com sucesso!', 'success')
            return redirect(url_for('index'))

    return render_template('vender_produto.html', produto=produto, estoque_inicial=estoque_inicial, hoje=hoje)



from sqlalchemy.orm import joinedload


# noinspection PyTypeChecker
@app.route('/relatorio_diario', methods=['GET', 'POST'])
def relatorio_diario():
    data_consulta = request.args.get('data', datetime.today().strftime('%Y-%m-%d'))  # Pega a data informada ou a atual
    try:
        data_formatada = datetime.strptime(data_consulta, '%Y-%m-%d').date()
    except ValueError:
        flash("Data inválida! Use o formato correto (AAAA-MM-DD).", "danger")
        return redirect(url_for('relatorio_diario'))

    vendas = Venda.query.options(joinedload(Venda.produto_relacionado)).filter_by(data=data_formatada).all()

    soma_diaria = sum(venda.total for venda in vendas)
    quantidade_vendida = sum(venda.quantidade for venda in vendas)

    return render_template(
        'relatorio_diario.html',
        hoje=data_formatada.strftime('%d/%m/%Y'),
        vendas_do_dia=vendas,
        soma_diaria=soma_diaria,
        quantidade_vendida=quantidade_vendida,
        data_consulta=data_consulta  # Para manter o valor no formulário
    )



# Relatório Mensal
@app.route('/relatorio_mensal')
def relatorio_mensal():
    hoje = datetime.today()
    mes = MESES[hoje.month - 1]  # Usa a lista de meses em português
    ano = hoje.year

    vendas = Venda.query.options(joinedload(Venda.produto_relacionado)).filter_by(mes=mes, ano=ano).all()
    soma_mensal = sum(venda.total for venda in vendas)
    quantidade_mensal = sum(venda.quantidade for venda in vendas)

    titulo_mensal = f"{mes} {ano}"
    return render_template(
        'relatorio_mensal.html',
        vendas_do_mes=vendas,
        soma_mensal=soma_mensal,
        quantidade_mensal=quantidade_mensal,
        titulo_mensal=titulo_mensal
    )


from datetime import datetime, timedelta

# Relatório Mensal Anterior
@app.route('/relatorio_mensal_anterior')
def relatorio_mensal_anterior():
    hoje = datetime.today()
    primeiro_dia_do_mes_atual = hoje.replace(day=1)
    ultimo_dia_do_mes_anterior = primeiro_dia_do_mes_atual - timedelta(days=1)
    mes_anterior = MESES[ultimo_dia_do_mes_anterior.month - 1]  # Usa a lista de meses
    ano_anterior = ultimo_dia_do_mes_anterior.year

    vendas = Venda.query.options(joinedload(Venda.produto_relacionado)).filter_by(mes=mes_anterior, ano=ano_anterior).all()
    soma_mensal = sum(venda.total for venda in vendas)
    quantidade_mensal = sum(venda.quantidade for venda in vendas)

    titulo_mensal = f"{mes_anterior} {ano_anterior}"
    return render_template(
        'relatorio_mensal.html',
        vendas_do_mes=vendas,
        soma_mensal=soma_mensal,
        quantidade_mensal=quantidade_mensal,
        titulo_mensal=titulo_mensal
    )


@app.route('/relatorios_historicos')
def relatorios_historicos():
    relatorios = (
        db.session.query(
            Venda.mes,
            Venda.ano,
            db.func.sum(Venda.quantidade).label('quantidade_vendida'),
            db.func.sum(Venda.total).label('soma_mensal')
        )
        .group_by(Venda.mes, Venda.ano)
        .order_by(Venda.ano, Venda.mes)
        .all()
    )
    return render_template('relatorios_historicos.html', relatorios=relatorios)


# Excluir produto
@app.route('/excluir_produto/<int:produto_id>', methods=['GET'])
def excluir_produto(produto_id):
    produto = Produto.query.get_or_404(produto_id)
    db.session.delete(produto)
    db.session.commit()
    flash('Produto excluído com sucesso!', 'success')
    return redirect(url_for('index'))

@app.route('/excluir_venda/<int:venda_id>', methods=['POST', 'GET'])
def excluir_venda(venda_id):
    venda = Venda.query.get_or_404(venda_id)
    db.session.delete(venda)
    db.session.commit()
    flash('Venda excluída com sucesso!', 'success')
    return redirect(url_for('relatorio_diario'))  # Ou redirecione para 'relatorio_mensal', dependendo de onde você está


# Login
@app.route('/login', methods=['GET', 'POST'])
def login_view():
    if request.method == 'POST':
        email = request.form['email']
        senha = request.form['senha']

        usuario = Usuario.query.filter_by(email=email).first()
        if usuario and check_password_hash(usuario.senha, senha):
            session['usuario_id'] = usuario.id
            flash('Login bem-sucedido!', 'success')
            return redirect(url_for('index'))
        else:
            flash('E-mail ou senha incorretos!', 'danger')

    return render_template('login.html')

# Registro de usuário
@app.route('/registro', methods=['GET', 'POST'])
def registro():
    if request.method == 'POST':
        email = request.form['email']
        senha = request.form['senha']
        senha_confirmada = request.form['senha_confirmada']

        if senha != senha_confirmada:
            flash('As senhas não coincidem!', 'danger')
            return redirect(url_for('registro'))

        if Usuario.query.filter_by(email=email).first():
            flash('Este e-mail já está registrado!', 'danger')
            return redirect(url_for('registro'))

        novo_usuario = Usuario(email=email, senha=generate_password_hash(senha))
        db.session.add(novo_usuario)
        db.session.commit()

        flash('Usuário registrado com sucesso!', 'success')
        return redirect(url_for('login_view'))

    return render_template('registro.html')

@app.route('/redefinir_senha', methods=['GET', 'POST'])
def redefinir_senha():
    if request.method == 'POST':
        email = request.form['email']
        nova_senha = request.form['nova_senha']
        confirmar_senha = request.form['confirmar_senha']

        if nova_senha != confirmar_senha:
            flash('As senhas não coincidem!', 'danger')
            return redirect(url_for('redefinir_senha'))

        # Verificar se o e-mail está registrado
        usuario = Usuario.query.filter_by(email=email).first()
        if not usuario:
            flash('E-mail não encontrado!', 'danger')
            return redirect(url_for('redefinir_senha'))

        # Atualizar a senha do usuário
        usuario.senha = generate_password_hash(nova_senha)
        db.session.commit()
        flash('Senha redefinida com sucesso!', 'success')
        return redirect(url_for('login_view'))

    return render_template('redefinir_senha.html')


# Logout
@app.route('/logout')
def logout():
    session.pop('usuario_id', None)
    flash('Você saiu com sucesso!', 'success')
    return redirect(url_for('login_view'))

if __name__ == '__main__':
    app.run(debug=True)
