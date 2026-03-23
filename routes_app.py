from flask import Blueprint, render_template, redirect, url_for, request, flash, session, jsonify
from datetime import datetime
# Importa os modelos do banco de dados
from sqlalchemy import func
from werkzeug.security import generate_password_hash, check_password_hash
from models import User, ConsultationRequest
from extensions import db

# Criando um Blueprint para organizar as rotas
main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def landing():
    return render_template('landing.html')

@main_bp.route('/home')
def home():    
    # Se o usuário não estiver na sessão, redireciona para o login
    if 'user' not in session:
        return redirect(url_for('main.login'))
    
    user = session['user']
    role = user.get('role')

    if role == 'medico':
        # Busca todos os pacientes no banco de dados
        doctor_patients = User.query.filter_by(role='paciente').all()
        return render_template('dashboard_medico.html', user=user, patients=doctor_patients)
    elif role == 'secretaria':
        # Busca todas as solicitações pendentes, ordenadas pela mais recente
        pending_requests = db.session.query(ConsultationRequest).join(User).filter(
            ConsultationRequest.status == 'pending'
        ).order_by(ConsultationRequest.requested_at.desc()).all()
        return render_template('dashboard_secretaria.html', user=user, requests=pending_requests)
    elif role == 'paciente':
        user_id = user['id']
        # Busca os agendamentos futuros do paciente
        upcoming_appointments = ConsultationRequest.query.filter(
            ConsultationRequest.patient_id == user_id,
            ConsultationRequest.status == 'scheduled'
        ).order_by(ConsultationRequest.scheduled_datetime.asc()).all()
        
        return render_template('dashboard_paciente.html', user=user, appointments=upcoming_appointments)
    return redirect(url_for('main.login')) # Fallback

@main_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        role = request.form.get('role')
        user = None

        if role == 'paciente':
            email = request.form.get('email')
            password = request.form.get('password')
            # Busca o usuário pelo email
            user = User.query.filter_by(email=email, role='paciente').first()
            # Validação de senha com hash
            if not user or not check_password_hash(user.password, password):
                user = None
        else:
            access_code = request.form.get('access_code')
            # Busca o usuário pelo código de acesso e perfil
            user = User.query.filter_by(access_code=access_code, role=role).first()
        
        if user:
            session['user'] = {"id": user.id, "email": user.email, "name": user.name, "role": user.role}
            flash('Login realizado com sucesso!', 'success')
            return redirect(url_for('main.home'))
        else:
            if role == 'paciente':
                flash('Email ou senha inválidos.', 'danger')
            else:
                flash('Código de acesso inválido.', 'danger')

    return render_template('login.html')

@main_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')

        # Verifica se o email já existe
        if User.query.filter_by(email=email).first():
            flash('Este email já está cadastrado. Por favor, faça login.', 'warning')
            return redirect(url_for('main.login'))

        # Gera o hash da senha antes de salvar
        hashed_password = generate_password_hash(password)
        new_user = User(name=name, email=email, password=hashed_password, role='paciente')
        db.session.add(new_user)
        db.session.commit()
        flash('Registro realizado com sucesso! Por favor, faça o login.', 'success')
        return redirect(url_for('main.login'))
        
    return render_template('register.html')

@main_bp.route('/logout')
def logout():
    session.pop('user', None) # Remove o usuário da sessão
    flash('Você saiu do sistema.', 'info')
    return redirect(url_for('main.landing'))

@main_bp.route('/solicitar_consulta', methods=['POST'])
def solicitar_consulta():
    if 'user' in session and session['user']['role'] == 'paciente':
        patient_id = session['user']['id']
        today = datetime.utcnow().date()

        # Conta quantas solicitações o paciente já fez hoje
        requests_today = ConsultationRequest.query.filter(
            ConsultationRequest.patient_id == patient_id,
            func.date(ConsultationRequest.requested_at) == today
        ).count()
        
        if requests_today >= 2:
            flash('Você já atingiu o limite de 2 solicitações de agendamento por dia.', 'warning')
        else:
            # Cria uma nova instância do modelo ConsultationRequest
            new_request = ConsultationRequest(patient_id=patient_id)
            
            # Adiciona e salva no banco de dados
            db.session.add(new_request)
            db.session.commit()
            flash('Sua solicitação de agendamento foi enviada com sucesso! A secretaria entrará em contato em breve.', 'success')
    return redirect(url_for('main.home'))

@main_bp.route('/pacientes')
def lista_pacientes():
    # Protege a rota, permitindo acesso apenas para médico e secretária
    if 'user' not in session or session['user']['role'] not in ['medico', 'secretaria']:
        flash('Acesso não autorizado.', 'danger')
        return redirect(url_for('main.login'))

    user = session['user']
    # Busca todos os pacientes no banco de dados, ordenados por nome
    pacientes = User.query.filter_by(role='paciente').order_by(User.name).all()
    
    return render_template('lista_pacientes.html', user=user, pacientes=pacientes)

@main_bp.route('/paciente/<int:patient_id>')
def ficha_paciente(patient_id):
    # Protege a rota
    if 'user' not in session or session['user']['role'] not in ['medico', 'secretaria']:
        flash('Acesso não autorizado.', 'danger')
        return redirect(url_for('main.login'))

    user = session['user']
    paciente = User.query.get_or_404(patient_id)

    # Garante que estamos vendo a ficha de um paciente
    if paciente.role != 'paciente':
        return "Usuário não é um paciente", 404

    return render_template('ficha_paciente.html', user=user, paciente=paciente)

@main_bp.route('/agendar_consulta/<int:request_id>', methods=['POST'])
def agendar_consulta(request_id):
    """Rota para a secretária agendar uma consulta a partir de uma solicitação."""
    # Protege a rota, permitindo acesso apenas para secretária
    if 'user' not in session or session['user']['role'] != 'secretaria':
        flash('Acesso não autorizado.', 'danger')
        return redirect(url_for('main.login'))

    consulta_req = ConsultationRequest.query.get_or_404(request_id)
    
    data_str = request.form.get('data')
    hora_str = request.form.get('hora')

    if data_str and hora_str:
        # Combina data e hora e converte para um objeto datetime
        scheduled_datetime = datetime.strptime(f'{data_str} {hora_str}', '%Y-%m-%d %H:%M')
        consulta_req.scheduled_datetime = scheduled_datetime
        consulta_req.status = 'scheduled'
        db.session.commit()
        flash(f'Consulta para {consulta_req.patient.name} agendada com sucesso para {scheduled_datetime.strftime("%d/%m/%Y às %H:%M")}.', 'success')
    return redirect(url_for('main.home'))

@main_bp.route('/calendario')
def calendario():
    """Exibe a página com o calendário de agendamentos."""
    # Protege a rota, permitindo acesso apenas para médico e secretária
    if 'user' not in session or session['user']['role'] not in ['medico', 'secretaria']:
        flash('Acesso não autorizado.', 'danger')
        return redirect(url_for('main.login'))

    user = session['user']
    return render_template('calendario.html', user=user)

@main_bp.route('/api/consultas')
def api_consultas():
    """Endpoint que retorna as consultas agendadas em formato JSON para o calendário."""
    # Protege a rota, permitindo acesso para médico e secretária
    if 'user' not in session or session['user']['role'] not in ['medico', 'secretaria']:
        return jsonify({"error": "Acesso não autorizado"}), 403

    # Busca todas as consultas com status 'scheduled'
    consultas_agendadas = ConsultationRequest.query.filter_by(status='scheduled').all()
    
    eventos = []
    for consulta in consultas_agendadas:
        eventos.append({
            'title': f'Consulta com {consulta.patient.name}',
            'start': consulta.scheduled_datetime.isoformat(), # Formato ISO 8601 que o FullCalendar entende
            'id': consulta.id,
            # Adicionamos 'extendedProps' para passar dados extras para o frontend
            'extendedProps': {
                'patientName': consulta.patient.name,
                'formattedDateTime': consulta.scheduled_datetime.strftime('%d/%m/%Y às %H:%M')
            }
        })
        
    return jsonify(eventos)

@main_bp.route('/cancelar_consulta/<int:request_id>', methods=['POST'])
def cancelar_consulta(request_id):
    """Rota para a secretária cancelar um agendamento."""
    # Protege a rota, permitindo acesso apenas para secretária
    if 'user' not in session or session['user']['role'] != 'secretaria':
        flash('Ação não autorizada.', 'danger')
        return redirect(url_for('main.calendario'))

    consulta = ConsultationRequest.query.get_or_404(request_id)
    
    # Altera o status para 'pending' e remove a data de agendamento
    consulta.status = 'pending' 
    consulta.scheduled_datetime = None
    db.session.commit()
    flash(f'O agendamento de {consulta.patient.name} foi cancelado e retornou para pendências.', 'warning')
    return redirect(url_for('main.calendario'))

@main_bp.route('/confirmar_consulta/<int:request_id>', methods=['POST'])
def confirmar_consulta(request_id):
    """Rota para o médico ou secretária confirmar que uma consulta foi realizada."""
    # Protege a rota, permitindo acesso para médico e secretária
    if 'user' not in session or session['user']['role'] not in ['medico', 'secretaria']:
        flash('Ação não autorizada.', 'danger')
        return redirect(url_for('main.calendario'))

    consulta = ConsultationRequest.query.get_or_404(request_id)
    
    # Altera o status para 'done'
    consulta.status = 'done'
    db.session.commit()
    flash(f'A consulta de {consulta.patient.name} foi marcada como concluída.', 'success')
    return redirect(url_for('main.calendario'))

@main_bp.route('/historico_consultas')
def historico_consultas():
    """Exibe o histórico de consultas para o paciente logado."""
    if 'user' not in session or session['user']['role'] != 'paciente':
        flash('Acesso não autorizado.', 'danger')
        return redirect(url_for('main.login'))

    user_id = session['user']['id']
    # Busca todas as consultas com status 'done' para este paciente
    consultas_concluidas = ConsultationRequest.query.filter_by(
        patient_id=user_id, status='done'
    ).order_by(ConsultationRequest.scheduled_datetime.desc()).all()

    return render_template('historico_consultas.html', user=session['user'], consultas=consultas_concluidas)

@main_bp.route('/paciente_cancelar_consulta/<int:request_id>', methods=['POST'])
def paciente_cancelar_consulta(request_id):
    """Rota para o paciente cancelar seu próprio agendamento."""
    if 'user' not in session or session['user']['role'] != 'paciente':
        flash('Acesso não autorizado.', 'danger')
        return redirect(url_for('main.login'))

    consulta = ConsultationRequest.query.get_or_404(request_id)

    # Verificação de segurança: garante que o paciente só pode cancelar suas próprias consultas
    if consulta.patient_id != session['user']['id']:
        flash('Você não tem permissão para cancelar este agendamento.', 'danger')
        return redirect(url_for('main.home'))

    # Altera o status para 'pending' para que a secretária veja a vaga liberada
    consulta.status = 'pending'
    consulta.scheduled_datetime = None
    db.session.commit()
    flash('Seu agendamento foi cancelado com sucesso. A vaga foi liberada.', 'success')
    return redirect(url_for('main.home'))