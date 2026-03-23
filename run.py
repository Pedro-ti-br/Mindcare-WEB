from flask import Flask, render_template, redirect, url_for, request, flash, session, jsonify
import os

# Importa o Blueprint do arquivo de rotas
from routes_app import main_bp
from datetime import date
# Importa a instância do DB e os modelos
from extensions import db
from models import User

app = Flask(__name__)

# Chave secreta para gerenciar sessões e mensagens flash
app.config['SECRET_KEY'] = '10050728p'
# Configuração do Banco de Dados SQLite
DB_PATH = os.path.join(os.path.dirname(__file__), 'mindcare.db')
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{DB_PATH}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Inicializa o SQLAlchemy com o app Flask
db.init_app(app)

app.register_blueprint(main_bp)

def _create_database(app_context):
    """Função interna para criar e popular o banco de dados."""
    with app_context:
        db.create_all()
        # Verifica se os usuários padrão já existem para não duplicar
        if not User.query.filter_by(role='medico').first():
            # Em um app real, a senha seria um hash. Ex: generate_password_hash('123')
            medico = User(name="Dr. House", role="medico", access_code="MED-123")
            sec1 = User(name="Maria", role="secretaria", access_code="SEC-001")
            sec2 = User(name="Ana", role="secretaria", access_code="SEC-002")
            paciente = User(name="João", email="paciente@email.com", password="123", role="paciente", phone="(11) 98765-4321", birth_date=date(1990, 5, 15))
            
            db.session.add_all([medico, sec1, sec2, paciente])
            db.session.commit()
            print("Banco de dados inicializado e populado com usuários padrão.")
        else:
            print("Usuários padrão já existem no banco de dados.")

@app.cli.command("init-db")
def init_db_command():
    """Cria as tabelas do banco de dados e popula com dados iniciais."""
    _create_database(app.app_context())

# Bloco para criar o DB na primeira execução, se não existir.
if not os.path.exists(DB_PATH):
    print("Arquivo de banco de dados não encontrado, criando e inicializando...")
    _create_database(app.app_context())

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)