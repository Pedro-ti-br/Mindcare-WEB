from datetime import datetime
from extensions import db

class User(db.Model):
    """Modelo para todos os usuários do sistema (Médicos, Secretárias, Pacientes)."""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True) # Único, mas pode ser nulo para logins com código
    password = db.Column(db.String(200)) # Armazenará o hash da senha
    role = db.Column(db.String(20), nullable=False) # 'paciente', 'medico', 'secretaria'
    access_code = db.Column(db.String(50), unique=True) # Único, mas pode ser nulo para pacientes

    # Novos campos para detalhes do paciente
    phone = db.Column(db.String(20), nullable=True)
    birth_date = db.Column(db.Date, nullable=True)

    # Relacionamento: um usuário (paciente) pode ter várias solicitações
    requests = db.relationship('ConsultationRequest', backref='patient', lazy=True)

    def __repr__(self):
        return f"<User {self.name} ({self.role})>"

class ConsultationRequest(db.Model):
    """Modelo para solicitações de agendamento feitas pelos pacientes."""
    id = db.Column(db.Integer, primary_key=True)
    requested_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    status = db.Column(db.String(20), nullable=False, default='pending') # 'pending', 'scheduled', 'done'
    patient_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    # Novo campo para armazenar a data e hora do agendamento
    scheduled_datetime = db.Column(db.DateTime, nullable=True)

    def __repr__(self):
        return f"<Request {self.id} from Patient {self.patient_id}>"