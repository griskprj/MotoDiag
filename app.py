from flask import Flask, render_template, redirect, url_for, jsonify, flash, request
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail, Message
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from flask_wtf.csrf import CSRFProtect
from flask_talisman import Talisman
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from dotenv import load_dotenv
from itsdangerous import URLSafeTimedSerializer
import os


load_dotenv()


app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'fallback_secret_key')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URI', 'sqlite:///database.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Email Configuration
app.config['MAIL_PORT'] = 465
app.config['MAIL_SERVER'] = 'smtp.yandex.ru'
app.config['MAIL_USE_SSL'] = True
app.config['MAIL_USE_TLS'] = False
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_DEFAULT_SENDER')

db = SQLAlchemy(app)
csrf = CSRFProtect(app)
mail = Mail(app)

Talisman(
    app,
    content_security_policy=None,
    force_https=True
)

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"]
)

# Flask-Login
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Token Serializer
serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'])



''' PENDING USER REGISTER '''
class PendingRegistration(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    email = db.Column(db.String(120), nullable=False)
    password = db.Column(db.String(128), nullable=False)
    verification_token = db.Column(db.String(32), nullable=False)
    token_expiration = db.Column(db.DateTime, nullable=False)

''' USER '''
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    email = db.Column(db.String(120), nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    first_reg = db.Column(db.Integer, default=1)
    join_date = db.Column(db.DateTime, default=datetime.utcnow())
    image = db.Column(db.LargeBinary)


''' MOTORCYCLE '''
class Motorcycle(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(db.Integer, nullable=False)
    model = db.Column(db.String(120), nullable=False)
    years_create = db.Column(db.Integer, nullable=False)
    mileage = db.Column(db.Integer, nullable=False)
    last_mileage_update = db.Column(db.DateTime, default=datetime.utcnow)
    moto_type = db.Column(db.String, nullable=False)
    engine_volume = db.Column(db.Integer, nullable=False)
    drive_type = db.Column(db.String(20), nullable=False, default="chain") #цепь, кардан, ремень
    condition = db.Column(db.String(40), nullable=False, default="Отличное")
    image = db.Column(db.LargeBinary)


''' ELEMENTS AND FLUID '''
class ElementsFluid(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(db.Integer, nullable=False)
    moto_id = db.Column(db.Integer, nullable=False)
    brake_fluid = db.Column(db.Boolean, default=False) #замена каждые 11000 км
    oil_filter = db.Column(db.Boolean, default=False) #каждые 3000–5000 км
    air_filter = db.Column(db.Boolean, default=False) #каждые 6000–12000 км
    spark_plug = db.Column(db.Boolean, default=False) #каждые 8000–12000 км
    drive_maintenance = db.Column(db.Boolean, default=False)
    drive_change = db.Column(db.Boolean, default=False)

    #last update
    brake_fluid_date = db.Column(db.DateTime)
    oil_filter_date = db.Column(db.DateTime)
    air_filter_date = db.Column(db.DateTime)
    spark_plug_date = db.Column(db.DateTime)
    drive_maintenance_date = db.Column(db.DateTime)
    drive_change_date = db.Column(db.DateTime)

    #last change mileage
    brake_fluid_mileage = db.Column(db.Integer, default=0)
    oil_filter_mileage = db.Column(db.Integer, default=0)
    air_filter_mileage = db.Column(db.Integer, default=0)
    spark_plug_mileage = db.Column(db.Integer, default=0)
    drive_maintenance_mileage = db.Column(db.Integer, default=0)
    drive_change_mileage = db.Column(db.Integer, default=0)


''' MAINTENANCE HISTORY'''
class MaintenanceHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(db.Integer, nullable=False)
    moto_id = db.Column(db.Integer, nullable=False)
    service_type = db.Column(db.String(50), nullable=False)
    mileage = db.Column(db.Integer, nullable=False)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    cost = db.Column(db.Integer)
    notes = db.Column(db.Text)
    image = db.Column(db.LargeBinary)





''' CREATE DATABASE '''
with app.app_context():
    db.create_all()


''' LOAD USER '''
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))




# Helper Functions
def generate_verification_token(email):
    return serializer.dumps(email, salt='email-verification')

def send_verification_email(email, token):
    verification_url = url_for('verify_email', token=token, _external=True)
    msg = Message('Подтверждение email', recipients=[email])
    msg.body = f'Для завершения регистрации перейдите по ссылке: {verification_url}'
    mail.send(msg)


''' ALLOWED FILE CHECK '''
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in {'png', 'jpg', 'jpeg', 'gif'}


''' CALCULATE UPCOMING MAINTENANCE '''
def calculate_upcoming_maintenance(moto, elements):
    maintenance_items = []
    current_mileage = moto.mileage

    MAINTENANCE_INTERVALS = {
        'oil_filter': 5000,
        'air_filter': 8000,
        'spark_plug': 10000,
        'brake_fluid': 11000,
    }

    MAINTENANCE_NAMES = {
        'oil_filter': 'Замена масляного фильтра',
        'air_filter': 'Замена воздушного фильтра',
        'spark_plug': 'Замена свечей зажигания',
        'brake_fluid': 'Замена тормозной жидкости',
    }

    DRIVE_MAINTENANCE = {
        'chain': {'maintenance': 2000, 'change': 10000},
        'belt': {'change': 15000},
        'shaft': {'maintenance': 5000}
    }

    # Проверяем, что elements существует
    if not elements:
        return maintenance_items

    drive_type = moto.drive_type
    drive_intervals = DRIVE_MAINTENANCE.get(drive_type, {})

    # Обработка обслуживания привода
    if 'maintenance' in drive_intervals:
        km_since_last = current_mileage - (elements.drive_maintenance_mileage or 0)
        remaining_km = drive_intervals['maintenance'] - km_since_last

        if not elements.drive_maintenance or km_since_last >= drive_intervals['maintenance']:
            action_name = "Смазка цепи" if drive_type == "chain" else "Замена масла в кардане"
            
            maintenance_items.append({
                'name': action_name,
                'moto_model': moto.model,
                'moto_id': moto.id,
                'interval': f"Каждые {drive_intervals['maintenance']:,} км".replace(',', ''),
                'remaining_km': remaining_km,
                'remaining_days': estimate_days(remaining_km),
                'is_overdue': remaining_km < 0
            })

    if 'change' in drive_intervals:
        km_since_last = current_mileage - (elements.drive_change_mileage or 0)
        remaining_km = drive_intervals['change'] - km_since_last

        if not elements.drive_change or km_since_last >= drive_intervals['change']:
            action_name = "Замена цепи" if drive_type == "chain" else "Замена ремня" if drive_type == "belt" else "Обслуживание кардана"
            
            maintenance_items.append({
                'name': action_name,
                'moto_model': moto.model,
                'moto_id': moto.id,
                'interval': f"Каждые {drive_intervals['change']:,} км".replace(',', ''),
                'remaining_km': remaining_km,
                'remaining_days': estimate_days(remaining_km),
                'is_overdue': remaining_km < 0
            })

    # Обработка остального обслуживания
    for element in MAINTENANCE_INTERVALS.keys():
        last_change_mileage = getattr(elements, f"{element}_mileage", 0) or 0
        interval = MAINTENANCE_INTERVALS[element]
        km_since_last = current_mileage - last_change_mileage
        remaining_km = interval - km_since_last

        # Показываем элемент, если он требует обслуживания (флаг False или пробег превысил интервал)
        if not getattr(elements, element, True) or km_since_last >= interval:
            if remaining_km <= 5000:
                maintenance_items.append({
                    'name': MAINTENANCE_NAMES[element],
                    'moto_model': moto.model,
                    'moto_id': moto.id,
                    'interval': f"Каждые {interval:,} км".replace(',', ''),
                    'remaining_km': remaining_km,
                    'remaining_days': estimate_days(remaining_km),
                    'is_overdue': remaining_km < 0
                })

    return maintenance_items


''' ESTIMATE DAYS '''
def estimate_days(remaining_km):
    km_per_day = 50
    days = remaining_km / km_per_day
    return round(days)


''' CALCULATE MOTORCYCLE CONDITION '''
def calculate_moto_condition(moto, elements):
    if not elements:
        return "Нет данных", 0
    
    WEIGHTS = {
        'oil_filter': 1.5,
        'air_filter': 1.2,
        'spark_plug': 1.3,
        'brake_fluid': 1.7,
        'drive_maintenance': 1.0,
        'drive_change': 1.4
    }

    MAINTENANCE_INTERVALS = {
        'oil_filter': 5000,
        'air_filter': 8000,
        'spark_plug': 10000,
        'brake_fluid': 11000,
        'drive_maintenance': 2000 if moto.drive_type == 'chain' else 5000 if moto.drive_type == 'shaft' else 0,
        'drive_change': 10000 if moto.drive_type == 'chain' else 15000 if moto.drive_type == 'belt' else 0
    }

    current_mileage = moto.mileage
    total_score = 0
    max_score = 0

    for element in MAINTENANCE_INTERVALS.keys():
        # Пропускаем элементы, которые не применимы для данного типа привода
        if MAINTENANCE_INTERVALS[element] == 0:
            continue
            
        last_change_mileage = getattr(elements, f"{element}_mileage", 0) or 0
        interval = MAINTENANCE_INTERVALS[element]
        km_since_last = current_mileage - last_change_mileage

        if km_since_last == 0:
            element_score = 1.0
        else:
            # Насколько превышен интервал (%)
            overdue_percent = max(0, (km_since_last - interval) / interval * 100)
        
            # Оценка элемента: 1.0 если в пределах интервала, уменьшается при превышении
            element_score = max(0, 1 - min(1, overdue_percent / 100))

        weight = WEIGHTS.get(element, 1.0)
        total_score += element_score * weight
        max_score += weight

    if max_score == 0:
        return "Нет данных", 0

    normalized_score = (total_score / max_score) * 100

    if normalized_score >= 80:
        return "Отличное", normalized_score
    elif normalized_score >= 60:
        return "Хорошее", normalized_score
    elif normalized_score >= 40:
        return "Среднее", normalized_score
    elif normalized_score >= 20:
        return "Плохое", normalized_score
    else:
        return "Критическое", normalized_score





''' / '''
@app.route("/")
def basic():
    return redirect(url_for("login" if not current_user.is_authenticated else "index"))


''' LOGIN '''
@app.route("/login", methods=['POST', 'GET'])
@limiter.limit("5 per minute")
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        
        if not user or not check_password_hash(user.password_hash, request.form['password']):
            flash('Неверные учетные данные', 'danger')
            return redirect(url_for('login'))
        
        login_user(user, remember='remember-me' in request.form)
        return redirect(url_for('index'))
    
    return render_template('login.html')
            

''' REGISTER '''
@app.route("/register", methods=['POST', 'GET'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        
        if User.query.filter_by(username=username).first():
            flash('Имя пользователя занято', 'danger')
            return redirect(url_for('register'))
        
        if User.query.filter_by(email=email).first():
            flash('Email уже зарегистрирован', 'danger')
            return redirect(url_for('register'))
        
        try:
            token = generate_verification_token(email)
            pending_user = PendingRegistration(
                username=username,
                email=email,
                password=generate_password_hash(request.form['password']),
                verification_token=token,
                token_expiration=datetime.utcnow() + timedelta(hours=24)
            )
            
            db.session.add(pending_user)
            db.session.commit()
            send_verification_email(email, token)
            flash('Ссылка для подтверждения отправлена на почту', 'success')
            return redirect(url_for('login'))
        
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка: {str(e)}', 'danger')
    
    return render_template('register.html')


@app.route('/verify/<token>')
def verify_email(token):
    try:
        email = serializer.loads(token, salt='email-verification', max_age=86400)
    except:
        flash('Недействительная или просроченная ссылка', 'danger')
        return redirect(url_for('register'))

    pending_user = PendingRegistration.query.filter_by(email=email).first()
    if not pending_user:
        flash('Пользователь не найден', 'danger')
        return redirect(url_for('register'))

    try:
        user = User(
            username=pending_user.username,
            email=pending_user.email,
            password_hash=pending_user.password
        )
        db.session.add(user)
        db.session.delete(pending_user)
        db.session.commit()
        flash('Email подтвержден! Можете войти', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка активации: {str(e)}', 'danger')
    
    return redirect(url_for('login'))


''' LOGOUT '''
@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash('Вы успешно вышли из системы', 'success')
    return redirect(url_for('login'))


''' ADD MOTO INFO '''
@app.route("/add_moto_info")
@login_required
def add_moto_pg():
    user = current_user
    print(user)

    return render_template('add_moto_info.html', user=user)


''' ADD MOTO INFO POST '''
@app.route("/add_motorcycle", methods=['POST'])
@login_required
def add_motorcycle():
    if request.method == 'POST':
        model = request.form.get('model')
        type_moto = request.form.get('type')
        drive_type = request.form.get('drive_type')

        try:
            year = int(request.form.get('year'))
            mileage = int(request.form.get('mileage'))
            engine = int(request.form.get('engine'))

            if year < 1900 or year > datetime.now().year:
                return jsonify({"success": False, "message": "Некорректный год"})
            
            if mileage < 0 or engine < 50:
                return jsonify({"success": False, "message": "Пробег или объем двигателя не могут быть отрицательными"})
        except ValueError:
            return jsonify({"success": False, "message": "Ошибка в данных: ожидалось число"})

        # Получаем фото
        image_file = request.files.get('moto_image')
        image_data = None
        if image_file:
            image_data = image_file.read()

        try:
            user = current_user

            new_moto = Motorcycle(
                owner_id=user.id,
                model=model,
                years_create=year,
                mileage=mileage,
                last_mileage_update=datetime.utcnow(),
                moto_type=type_moto,
                engine_volume=engine,
                drive_type=drive_type,
                image=image_data
            )
            
            db.session.add(new_moto)
            db.session.flush()  # Это нужно, чтобы получить ID нового мотоцикла
            
            # Создаем запись о состоянии
            new_elm_fld = ElementsFluid(
                owner_id=user.id,
                moto_id=new_moto.id,
                oil_filter_mileage=mileage,
                air_filter_mileage=mileage,
                spark_plug_mileage=mileage,
                brake_fluid_mileage=mileage,
                drive_maintenance_mileage=mileage if drive_type in ['chain', 'shaft'] else 0,
                drive_change_mileage=mileage if drive_type in ['chain', 'belt'] else 0,
                oil_filter=True,
                air_filter=True,
                spark_plug=True,
                brake_fluid=True,
                drive_maintenance=True if drive_type in ['chain', 'shaft'] else False,
                drive_change=True if drive_type in ['chain', 'belt'] else False
            )

            current_user.first_reg = 0
            db.session.add(new_elm_fld)
            db.session.commit()  # Теперь коммитим обе записи

            return jsonify({
                "success": True,
                "message": "Мотоцикл успешно добавлен",
                "redirect": url_for('index')
            })

        except Exception as e:
            db.session.rollback()
            return jsonify({
                "success": False,
                "message": f"Ошибка при добавлении: {str(e)}"
            }), 500
    
    return jsonify({"success": False, "message": "Недопустимый метод запроса"}), 405



''' INDEX '''
@app.route('/index')
@login_required
def index():
    user = current_user
    user_moto = Motorcycle.query.filter_by(owner_id=user.id).all()

    if not user_moto:
        return redirect(url_for('add_moto_pg'))

    moto_data = []
    total_mileage = 0
    total_score = 0
    upcoming_maintenance = []

    for moto in user_moto:
        elements = ElementsFluid.query.filter_by(moto_id=moto.id).first()

        # предстоящее обслуживание
        maintenacnce_items = calculate_upcoming_maintenance(moto, elements)
        upcoming_maintenance.extend(maintenacnce_items)
    
        condition, score = calculate_moto_condition(moto, elements)
        total_score += score
        total_mileage += moto.mileage

        moto_data.append({
                "id": moto.id,
                "model": moto.model,
                "year": moto.years_create,
                "mileage": moto.mileage,
                "engine": moto.engine_volume,
                "type": moto.moto_type,
                "image": moto.image,
                "condition": condition,
                "score": round(score),
                "elements": {
                    "brake_fluid": elements.brake_fluid if elements else False,
                    "oil_filter": elements.oil_filter if elements else False,
                    "air_filter": elements.air_filter if elements else False,
                    "spark_plug": elements.spark_plug if elements else False,
                    "chain_lubricate": elements.drive_maintenance if elements else False,
                    "chain_change": elements.drive_change if elements else False,
                    "brake_fluid_date": elements.brake_fluid_date if elements else None,
                    "oil_filter_date": elements.oil_filter_date if elements else None,
                    "air_filter_date": elements.air_filter_date if elements else None,
                    "spark_plug_date": elements.spark_plug_date if elements else None,
                    "chain_lubricate_date": elements.drive_maintenance_date if elements else None,
                    "chain_change_date": elements.drive_change_date if elements else None
                }
        })
    
    avg_score = total_score / len(user_moto) if user_moto else 0
    avg_condition = "Нет данных"

    if avg_score >= 80:
        avg_condition = "Отличное"
    elif avg_score >= 60:
        avg_condition = "Хорошее"
    elif avg_score >= 40:
        avg_condition = "Среднее"
    elif avg_score >= 20:
        avg_condition = "Плохое"
    else:
        avg_condition = "Критическое"


    upcoming_maintenance.sort(key=lambda x: x['remaining_km'])

    db.session.commit()

    return render_template('index.html',
                           user=user,
                           moto_data=moto_data,
                           total_mileage=total_mileage,
                           avg_condition=avg_condition,
                           upcoming_maintenance=upcoming_maintenance[:3])


''' MY MOTO '''
@app.route('/my_moto')
@login_required
def my_moto():
    user = current_user
    user_moto = Motorcycle.query.filter_by(owner_id=user.id).all()

    moto_data = []
    for moto in user_moto:
        elements = ElementsFluid.query.filter_by(moto_id=moto.id).first()

        condition, score = calculate_moto_condition(moto, elements)

        moto_data.append({
            "id": moto.id,
            "model": moto.model,
            "year": moto.years_create,
            "mileage": moto.mileage,
            "engine": moto.engine_volume,
            "type": moto.moto_type,
            "image": moto.image,
            "condition": condition,
            "score": round(score)
        })

    return render_template('my_moto.html', moto_data=moto_data, user=user)


''' MOTO IMAGE '''
@app.route("/moto_image_<int:moto_id>")
@login_required
def moto_image(moto_id):
    moto = Motorcycle.query.get_or_404(moto_id)
    
    from io import BytesIO
    from flask import send_file

    return send_file(
        BytesIO(moto.image),
        mimetype='image/jpg',
        as_attachment=False
    )


'''' SERVICE '''
@app.route('/maintenance')
@login_required
def maintenance():
    user = current_user
    user_moto = Motorcycle.query.filter_by(owner_id=user.id).all()
    
    moto_data = []
    upcoming_maintenance = []
    maintenance_history = []
    
    for moto in user_moto:
        elements = ElementsFluid.query.filter_by(moto_id=moto.id).first()
        maintenance_history_db = MaintenanceHistory.query.filter_by(moto_id=moto.id).all()
        
        # Предстоящее обслуживание
        maintenance_items = calculate_upcoming_maintenance(moto, elements)
        upcoming_maintenance.extend(maintenance_items)

        for maintenance in maintenance_history_db:
            maintenance_history.append({
                "id": maintenance.id,
                "type": maintenance.service_type,
                "moto_model": moto.model,
                "date": maintenance.date,
                "mileage": maintenance.mileage,
                "cost": maintenance.cost,
                "notes": maintenance.notes[:80],
                "image": maintenance.image
            })
        
        moto_data.append({
            "id": moto.id,
            "model": moto.model,
            "mileage": moto.mileage,
            "drive_type": moto.drive_type
        })
    
    upcoming_maintenance.sort(key=lambda x: x['remaining_km'])
    maintenance_history.sort(key=lambda x: x['date'], reverse=True)
    
    return render_template('service.html',
                        user=user,
                        moto_data=moto_data,
                        upcoming_maintenance=upcoming_maintenance[:5],
                        maintenance_history=maintenance_history[:10])


''' ADD MAINTENANCE '''
@app.route('/add_maintenance', methods=['POST'])
@login_required
def add_maintenance():
    if request.method == 'POST':
        try:
            user = current_user
            moto_id = request.form.get('moto_id')
            service_type = request.form.get('service_type')
            mileage = int(request.form.get('mileage'))
            date = datetime.strptime(request.form.get('date'), '%Y-%m-%d')
            cost = int(request.form.get('cost')) if request.form.get('cost') else None
            notes = request.form.get('notes')
            
            moto = Motorcycle.query.get(moto_id)
            if not moto:
                return jsonify({
                    "success": False,
                    "message": "Мотоцикл не найден"
                }), 404
            
            if moto.mileage > mileage:
                return jsonify({
                    "success": False,
                    "message": "Пробег не может быть меньше текущего"
                }), 400
            
            #get_photo
            image_file = request.files.get('meintenance_image')
            image_data = None
            if image_file:
                image_data = image_file.read()

            moto.mileage = mileage
            moto.last_mileage_update = datetime.utcnow()
            
            # Добавляем запись в историю обслуживания
            new_record = MaintenanceHistory(
                owner_id=user.id,
                moto_id=moto_id,
                service_type=service_type,
                mileage=mileage,
                date=date,
                cost=cost,
                notes=notes,
                image=image_data
            )
            
            db.session.add(new_record)

            elements = ElementsFluid.query.filter_by(moto_id=moto_id).first()
            if elements:
                service_mapping = {
                    'Замена масляного фильтра': 'oil_filter',
                    'Замена воздушного фильтра': 'air_filter',
                    'Замена свечей зажигания': 'spark_plug',
                    'Замена тормозной жидкости': 'brake_fluid',
                    'Замена шин': 'tire_change',
                    'Смазка цепи': 'drive_maintenance',
                    'Замена цепи': 'drive_change',
                    'Замена ремня': 'drive_change',
                    'Обслуживание кардана': 'drive_maintenance',
                    'Замена масла в кардане': 'drive_maintenance'
                }

                if service_type in service_mapping:
                    element = service_mapping[service_type]
                    setattr(elements, element, True)
                    setattr(elements, f"{element}_date", date)
                    setattr(elements, f"{element}_mileage", mileage)

            db.session.commit()
            
            return jsonify({'success': True, 'message': 'Обслуживание успешно добавлено'})
        
        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'message': f'Ошибка: {str(e)}'}), 400
        

''' MAINTENANCE IMAGE '''
@app.route("/maintenance_image/<int:maintenance_id>")
@login_required
def maintenance_image(maintenance_id):
    maintenance = MaintenanceHistory.query.get_or_404(maintenance_id)
    
    from io import BytesIO
    from flask import send_file

    if maintenance.image:
        return send_file(
            BytesIO(maintenance.image),
            mimetype='image/jpg',
            as_attachment=False
        )
    

''' USER IMAGE '''
@app.route("/user_image/<int:user_id>")
@login_required
def user_image(user_id):
    user = User.query.get_or_404(user_id)

    from io import BytesIO
    from flask import send_file

    if user.image:
        return send_file(
            BytesIO(user.image),
            mimetype='image/jpg',
            as_attachment=False
        )
        

''' UPDATE MILEAGE '''
@app.route("/update_mileage", methods=['POST'])
@login_required
def update_mileage():
    try:
        moto_id = request.form.get('moto_id')
        new_mileage = int(request.form.get('new_mileage'))
        mileage_date_str = request.form.get('mileage_date')
        
        # Проверяем, что дата передана
        if not mileage_date_str:
            return jsonify({
                "success": False,
                "message": "Дата не указана"
            }), 400
            
        mileage_date = datetime.strptime(mileage_date_str, '%Y-%m-%d')
        
        moto = Motorcycle.query.get(moto_id)
        if not moto or moto.owner_id != current_user.id:
            return jsonify({
                "success": False,
                "message": "Мотоцикл не найден"
            }), 404
        
        # Проверка на уменьшение пробега
        if new_mileage < moto.mileage:
            return jsonify({
                "success": False,
                "message": "Новый пробег не может быть меньше текущего"
            }), 400
            
        # Проверка даты
        if mileage_date.date() > datetime.utcnow().date():
            return jsonify({
                "success": False,
                "message": "Дата не может быть в будущем"
            }), 400

        # Обновляем данные
        moto.mileage = new_mileage
        moto.last_mileage_update = mileage_date
        
        elements = ElementsFluid.query.filter_by(moto_id=moto.id).first()
        if elements:
            # Обновляем флаги обслуживания
            MAINTENANCE_INTERVALS = {
                'oil_filter': 5000,
                'air_filter': 8000,
                'spark_plug': 10000,
                'brake_fluid': 11000,
                'drive_maintenance': 2000 if moto.drive_type == 'chain' else 5000 if moto.drive_type == 'shaft' else 0,
                'drive_change': 10000 if moto.drive_type == 'chain' else 15000 if moto.drive_type == 'belt' else 0
            }

            for element, interval in MAINTENANCE_INTERVALS.items():
                if interval == 0:
                    continue
                    
                last_change_mileage = getattr(elements, f"{element}_mileage", 0)
                if new_mileage - last_change_mileage >= interval:
                    setattr(elements, element, False)

        db.session.commit()

        return jsonify({
            "success": True,
            "message": "Пробег успешно обновлен"
        })
    except ValueError as e:
        return jsonify({
            "success": False,
            "message": f"Ошибка в данных: {str(e)}"
        }), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({
            "success": False,
            "message": f"Ошибка сервера: {str(e)}"
        }), 500


''' MOTO PAGE '''
@app.route("/moto/<int:moto_id>")
@login_required
def moto(moto_id):
    user = current_user
    moto = Motorcycle.query.filter_by(id=moto_id, owner_id=current_user.id).first()
    maintenance_history = []

    print(f"Drive type in DB: {moto.drive_type if moto else 'Moto not found'}")

    if not moto:
        flash('Мотоцикл не найден', 'danger')
        return redirect(url_for('my_moto'))
    
    elements = ElementsFluid.query.filter_by(moto_id=moto.id).first()
    history = MaintenanceHistory.query.filter_by(moto_id=moto.id).all()

    upcoming_maintenance = calculate_upcoming_maintenance(moto, elements)
    condition, score = calculate_moto_condition(moto, elements)
    
    moto_data = ({
        "id": moto.id,
        "model": moto.model,
        "year": moto.years_create,
        "mileage": moto.mileage,
        "engine": moto.engine_volume,
        "type": moto.moto_type,
        "image": moto.image,
        "condition": condition,
        "score": round(score),
        "last_mileage_update": moto.last_mileage_update.strftime('%d.%m.%Y') if moto.last_mileage_update else None,
        "drive_type": moto.drive_type
    })

    for maintenance in history:
        maintenance_history.append({
            "id": maintenance.id,
            "type": maintenance.service_type,
            "moto_model": moto.model,
            "date": maintenance.date,
            "mileage": maintenance.mileage,
            "cost": maintenance.cost,
            "notes": maintenance.notes[:80],
            "image": maintenance.image
        })

    

    return render_template('moto.html',
                           user=user,
                           moto=moto_data,
                           upcoming_maintenance=upcoming_maintenance,
                           maintenance_history=maintenance_history[:10]
                           )


''' PUT LAST MAINTENANCE MOTO '''
@app.route("/update_last_maintenance", methods=['POST'])
def update_last_mainenance():
    if request.method == "POST":
        try:
            moto_id = request.form.get('moto_id')
            moto = Motorcycle.query.filter_by(id=moto_id, owner_id=current_user.id).first()
            if not moto:
                return jsonify({"success": False, "message": "Мотоцикл не найден"}), 404
            
            elements = ElementsFluid.query.filter_by(moto_id=moto_id).first()
            if not elements:
                return jsonify({"success": False, "message": "Данные обслуживания не найдены"}), 404
            
            maintenenace_fields = {
                'brake-liquid': ('brake_fluid', 'brake_fluid_mileage'),
                'oil-filter': ('oil_filter', 'oil_filter_mileage'),
                'air-filter': ('air_filter', 'air_filter_mileage'),
                'spark-plug': ('spark_plug', 'spark_plug_mileage'),
                'chain-lubricate': ('drive_maintenance', 'drive_maintenance_mileage'),
                'chain-change': ('drive_change', 'drive_change_mileage'),
                'belt-change': ('drive_change', 'drive_change_mileage'),
                'change-oil-shift': ('drive_maintenance', 'drive_maintenance_mileage'),
                'tires-change': ('tire_change', 'tire_change_mileage')
            }

            for filed_name, (status_field, mileage_field) in maintenenace_fields.items():
                mileage_value = request.form.get(filed_name)
                if mileage_value:
                    mileage = int(mileage_value)
                    if mileage > 0:
                        setattr(elements, status_field, True)
                        setattr(elements, mileage_field, mileage)
                        setattr(elements, f"{status_field}_date", datetime.utcnow())
            
            db.session.commit()
            
            return jsonify({"success": True, "message": "Данные успешно обновлены"})
        
        except ValueError:
            return jsonify({
                "success": False,
                "message": "Некорректное значение пробега"
            }), 400
        except Exception as e:
            return jsonify({
                "success": False,
                "message": f"Ошибка: {str(e)}"
            }), 500
    
    return jsonify({"success": False, "message": "Недопустимый метод запроса"}), 405


''' UPDATE MOTORCYCLE '''
@app.route("/update_motorcycle", methods=['POST'])
@login_required
def update_motorcycle():
    if request.method == 'POST':
        moto_id = request.form.get('moto_id')
        model = request.form.get('model')
        type_moto = request.form.get('type')
        drive_type = request.form.get('drive_type')

        try:
            year = int(request.form.get('year'))
            mileage = int(request.form.get('mileage'))
            engine = int(request.form.get('engine'))

            if year < 1900 or year > datetime.now().year:
                return jsonify({"success": False, "message": "Некорректный год"})
            
            if mileage < 0 or engine < 50:
                return jsonify({"success": False, "message": "Пробег или объем двигателя не могут быть отрицательными"})
        except ValueError:
            return jsonify({"success":False, "message": "Получена строка, но ожидалось число"})
        
        moto = Motorcycle.query.filter_by(id=moto_id, owner_id=current_user.id).first()
        if not moto:
            return jsonify({"success": False, "message": "Мотоцикл не найден"}), 404

        moto.model = model
        moto.years_create = year
        moto.mileage = mileage
        moto.engine_volume = engine
        moto.moto_type = type_moto
        moto.drive_type = drive_type

        image_file = request.files.get('moto_image')
        if image_file:
            moto.image = image_file.read()

        try:
            db.session.commit()
            return jsonify({"success":True, "message": "Данные мотоцикла обновлены"})
        except Exception as e:
            db.session.rollback()
            return jsonify({"success": True, "message": f"Ошибка при обновлении данных: {str(e)}"})
        
    return jsonify({"success": False, "message": "Недопустимый метод запроса"})


''' DELETE MOTORCYCLE '''
@app.route("/delete_moto/<int:moto_id>", methods=['DELETE'])
@login_required
def delete_moto(moto_id):
    # Проверяем, что мотоцикл принадлежит текущему пользователю
    moto = Motorcycle.query.filter_by(id=moto_id, owner_id=current_user.id).first()

    if not moto:
        return jsonify({"success": False, "message": "Мотоцикл не найден или не принадлежит вам"}), 404
    
    try:
        # Удаляем связанные записи
        MaintenanceHistory.query.filter_by(moto_id=moto_id).delete()
        ElementsFluid.query.filter_by(moto_id=moto_id).delete()
        
        # Удаляем сам мотоцикл
        db.session.delete(moto)
        db.session.commit()
        
        return jsonify({
            "success": True, 
            "message": "Мотоцикл и все связанные данные успешно удалены"
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({
            "success": False, 
            "message": f"При удалении произошла ошибка: {str(e)}"
        }), 500
    

''' PROFILE '''
@app.route("/profile")
@login_required
def profile():
    user = current_user
    motos = Motorcycle.query.filter_by(owner_id=user.id).all()
    maintenance_notes = MaintenanceHistory.query.filter_by(owner_id=user.id).all()

    moto_count = 0
    total_mileage = 0
    for moto in motos:
        moto_count += 1
        total_mileage += moto.mileage
    
    maintenance_count = 0
    for maintenance in maintenance_notes:
        maintenance_count += 1


    return render_template('profile.html',
                           user=user,
                           moto_count=moto_count,
                           maintenance_count=maintenance_count,
                           total_mileage=total_mileage)


''' CHANGE USER DATA '''
@app.route("/profile", methods=['POST'])
@login_required
def update_user():
    user = current_user

    if not user:
        return jsonify({"success": False, "message": "Пользователь не найден"}), 404
    
    username = request.form.get('username')
    email = request.form.get('email')

    if not username or not email:
        return jsonify({"success": False, "message": "Имя пользователя и email обязательны"}), 400

    try:
        # Проверка на уникальность только если значения изменились
        if email != user.email:
            if User.query.filter(User.id != user.id, User.email == email).first():
                return jsonify({"success": False, "message": "Email уже используется другим пользователем"}), 400
        
        if username != user.username:
            if User.query.filter(User.id != user.id, User.username == username).first():
                return jsonify({"success": False, "message": "Имя пользователя уже занято"}), 400

        # Обновляем данные
        user.username = username
        user.email = email
        
        # Обработка загрузки изображения
        if 'avatar' in request.files:
            image_file = request.files['avatar']
            if image_file and allowed_file(image_file.filename):
                user.image = image_file.read()
            elif image_file and not allowed_file(image_file.filename):
                return jsonify({"success": False, "message": "Недопустимый формат изображения"}), 400

        db.session.commit()
        return jsonify({"success": True, "message": "Данные успешно обновлены"})

    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": "Ошибка целостности данных: возможно, такое имя пользователя или email уже существуют"}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": f"Ошибка сервера: {str(e)}"}), 500
    

''' UPDATE PASSWORD '''
@app.route("/change_password", methods=['POST'])
@login_required
def change_password():
    user = current_user

    current_password = request.form.get('current_password')
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')

    try:
        if not check_password_hash(user.password_hash, current_password):
            print("НЕВЕРНЫЙ ПАРОЛЬ")
            return jsonify({"success": False, "message": "Неверный прошлый пароль"}), 400

        if new_password != confirm_password:
            print("ПАРОЛИ НЕ СОВПАДАЮТ")
            return jsonify({"success": False, "message": "Пароли не совпадают"}), 400
        
        user.password_hash = generate_password_hash(new_password)
        print("ПАРОЛЬ УСТАНОВЛЕН")

        db.session.commit()
        print("КОММИТ ПРОЙДЕН")

        return jsonify({"success": True, "message": "Пароль обновлен"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": f"Ошибка: {str(e)}"}), 500
    

''' DELETE ACCOUNT '''
@app.route("/profile", methods=['DELETE'])
@login_required
def delete_account():
    user = current_user
    motos = Motorcycle.query.filter_by(owner_id=user.id).all()

    for moto in motos:
        el_fluid = ElementsFluid.query.filter_by(moto_id=moto.id).first()
        
        db.session.delete(el_fluid)

        maintenance_histoty = MaintenanceHistory.query.filter_by(moto_id=moto.id).all()
        for maintenance in maintenance_histoty:
            db.session.delete(maintenance)

        db.session.delete(moto)

    db.session.delete(user)
    db.session.commit()

    return jsonify({"success": True, "message": "Вы были успешно удалены. Возвращайтесь :'("})


''' PASSWORD RESET REQUEST '''
@app.route("/request_password_reset", methods=['POST'])
@login_required
def request_password_reset():
    user = current_user
    try:
        token = generate_verification_token(user.email)
        reset_url = url_for('reset_password', token=token, _external=True)

        msg = Message('Сбро пароля MotoDiag', recipients=[user.email])
        msg.body = f"Для сброса пароля перейдите по ссылке: {reset_url}\n\nЕсли вы не запрашивали сброс пароля, то просто проигнорируйте это письмо"
        mail.send(msg)
        
        return jsonify({"success": True, "message": "Ссылка для сброся пароля отправлена на ваш email"})
    except Exception as e:
        return jsonify({"success": False, "message": f"Ошибка: {str(e)}"}), 500


''' RESET PASSWORD PAGE '''
@app.route("/reset_password/<token>")
def reset_password(token):
    try:
        email = serializer.loads(token, salt='email-verification', max_age=3600)

        return render_template('reset_password.html', token=token, email=email)
    except Exception as e:
        flash('Ссылка для сброса пароля недействительна или просрочена', 'danger')
        return redirect(url_for('profile'))
    

''' PROCESS PASSWORD RESET '''
@app.route("/process_password_reset", methods=['POST'])
def process_password_reset():
    token = request.form.get('token')
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')

    if not token or not new_password or not confirm_password:
        return jsonify({"success": False, "messaeg": "Не все поля заполнены"}), 400
    
    if new_password != confirm_password:
        return jsonify({"success": False, "message": "Пароли не совпадают"}), 400
    
    try:
        email = serializer.loads(token, salt='email-verification', max_age=3600)
        user = User.query.filter_by(email=email).first()

        if not user:
            return jsonify({"success": False, "message": "Пользователь не найден"}), 404
        
        user.password_hash = generate_password_hash(new_password)
        db.session.commit()

        return jsonify({
            "success": True,
            "message": "Пароль успешно изменен. Теперь вы можете войти с новым паролем",
            "redirect": url_for('login')
        })
    except:
        return jsonify({"success": False, "message": "Недействительная или просроченная ссылка"}), 400

    

    




''' START APP '''
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)