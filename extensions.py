from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_socketio import SocketIO

db = SQLAlchemy()  # Veritabanı bağlantısı
login_manager = LoginManager()  # Kullanıcı oturum yönetimi
socketio = SocketIO()  # Gerçek zamanlı iletişim