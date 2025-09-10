from flask import Flask, render_template, redirect, url_for
from config import Config
from extensions import db, login_manager, socketio
from models import init_db, User
from blueprints.auth import auth_bp
from blueprints.academic import academic_bp
from blueprints.attendance import attendance_bp
from blueprints.student import student_bp
from blueprints.reporting import reporting_bp
from flask_login import current_user, login_required
import os

# Ana uygulama oluşturma fonksiyonu. Tüm blueprint ve uzantıları burada başlatıyoruz.

def create_app():
    """
    Flask uygulamasını başlatır, konfigürasyonları yükler ve blueprintleri ekler.
    """
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    socketio.init_app(app)

    # Tüm blueprintleri uygulamaya ekle
    app.register_blueprint(auth_bp)
    app.register_blueprint(academic_bp)
    app.register_blueprint(attendance_bp)
    app.register_blueprint(student_bp)
    app.register_blueprint(reporting_bp)

    @login_manager.user_loader
    def load_user(user_id):
        """
        Kullanıcı oturumu için kullanıcıyı ID ile getirir.
        """
        return User.query.get(int(user_id))

    @app.route('/')
    def home():
        """
        Ana sayfa. Kullanıcı tipine göre yönlendirme yapar.
        """
        from flask_login import current_user
        if current_user.is_authenticated:
            if current_user.is_academician():
                return redirect(url_for('academic.dashboard'))
            elif current_user.is_student():
                return redirect(url_for('student.student_dashboard'))
        return render_template('home.html')

    @app.context_processor
    def inject_user_type():
        """
        Template'lerde kullanıcı tipini kullanmak için context processor.
        """
        from flask_login import current_user
        return dict(user_type=getattr(current_user, 'UserType', None))

    return app

app = create_app()
# Uygulama route haritası: Tüm endpointlerin listesini gösterir (debug için).
# print(app.url_map)  # GEREKSİZ, kaldırıldı.


