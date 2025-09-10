from extensions import db
from flask_login import UserMixin
from datetime import datetime
import json
from werkzeug.security import check_password_hash


class User(UserMixin, db.Model):
    """
    Sistemdeki kullanıcıları temsil eder. Akademisyen ve öğrenci bilgileri burada tutulur.
    """
    __tablename__ = 'Kullanicilar'
    id = db.Column(db.Integer, primary_key=True)
    Email = db.Column(db.String(120), unique=True, nullable=True)
    OgrenciNo = db.Column(db.String(20), unique=True, nullable=True)
    SifreHash = db.Column(db.String(128), nullable=False)
    UserType = db.Column(db.String(20), nullable=False)
    Isim = db.Column(db.String(50), nullable=False)
    Soyisim = db.Column(db.String(50), nullable=False)
    is_active_user = db.Column(db.Boolean, default=True, nullable=False)

    academician_details = db.relationship('Akademisyen', backref='user_account', uselist=False, lazy=True)
    student_details = db.relationship('Student', backref='user', uselist=False, lazy=True)

    def is_academician(self):
        return self.UserType == 'academician'

    def is_student(self):
        return self.UserType == 'student'

    def get_id(self):
        return str(self.id)
    def verify_password(self, password):
        return check_password_hash(self.SifreHash, password)

    @property
    def student_detail(self):
        return self.student_details[0] if self.student_details else None

class Akademisyen(db.Model):
    """
    Akademisyenlerin temel bilgilerini tutar. User ile ilişkilidir.
    """
    __tablename__ = 'Akademisyenler'
    AkademisyenID = db.Column(db.Integer, primary_key=True)
    UserID = db.Column(db.Integer, db.ForeignKey('Kullanicilar.id'), unique=True, nullable=False)

class Student(db.Model):
    """
    Öğrencilerin temel bilgilerini tutar. User ile ilişkilidir.
    """
    __tablename__ = 'Ogrenciler'
    OgrenciID = db.Column(db.Integer, primary_key=True)
    UserID = db.Column(db.Integer, db.ForeignKey('Kullanicilar.id'), unique=True, nullable=False)
    OgrenciNo = db.Column(db.String(20), unique=True, nullable=False)
    is_active_user = db.Column(db.Boolean, default=True, nullable=False)
    Sinif = db.Column(db.String(20))
    BirimProgram = db.Column(db.String(100))


class Ders(db.Model):
    """
    Ders bilgilerini ve akademisyen ile ilişkisini tutar.
    """
    __tablename__ = 'Dersler'
    DersID = db.Column(db.Integer, primary_key=True)
    DersKodu = db.Column(db.String(50), nullable=False)
    DersAdi = db.Column(db.String(100), nullable=False)
    DersYili = db.Column(db.String(10), nullable=False)
    DersDonemi = db.Column(db.String(20), nullable=False)
    Kredi = db.Column(db.Integer, nullable=True)
    DevamZorunluluguVarMi = db.Column(db.Boolean, default=True, nullable=False)
    AkademisyenID = db.Column(db.Integer, db.ForeignKey('Akademisyenler.AkademisyenID'), nullable=False)

    akademisyen = db.relationship('Akademisyen', backref=db.backref('verdii_dersler', lazy=True))

    __table_args__ = (db.UniqueConstraint('DersKodu', 'DersYili', 'DersDonemi', 'AkademisyenID', name='_ders_akademisyen_uc'),)

class CourseStudent(db.Model):
    """
    Bir dersin hangi öğrenciler tarafından alındığını tutar (ilişki tablosu).
    """
    __tablename__ = 'DersOgrenciler'
    id = db.Column(db.Integer, primary_key=True)
    DersID = db.Column(db.Integer, db.ForeignKey('Dersler.DersID'), nullable=False)
    OgrenciID = db.Column(db.Integer, db.ForeignKey('Ogrenciler.OgrenciID'), nullable=False)
    KayitTarihi = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    ders_objesi = db.relationship('Ders', backref=db.backref('kayitli_ogrenciler', lazy=True, cascade="all, delete-orphan"))
    ogrenci_objesi = db.relationship('Student', foreign_keys=[OgrenciID], backref=db.backref('dersleri', lazy=True, cascade="all, delete-orphan"))

    __table_args__ = (db.UniqueConstraint('DersID', 'OgrenciID', name='_ders_ogrenci_uc'),)

class DersOturum(db.Model):
    """
    Her dersin oturumlarını (hafta/oturum) ve QR kod verisini tutar.
    """
    __tablename__ = 'DersOturumlari'
    OturumID = db.Column(db.Integer, primary_key=True)
    DersID = db.Column(db.Integer, db.ForeignKey('Dersler.DersID'), nullable=False)
    OturumNumarasi = db.Column(db.Integer, nullable=False)
    OturumSiraNumarasi = db.Column(db.Integer, nullable=False, default=1)
    BaslangicZamani = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    BitisZamani = db.Column(db.DateTime)
    AktifMi = db.Column(db.Boolean, default=True)
    QRCodeData = db.Column(db.String(200))
    QR_Olusma_Zamani = db.Column(db.DateTime)
    QR_CODE_VERSION = db.Column(db.Integer, default=1)
    
    # İlişki tanımı
    ders = db.relationship('Ders', backref=db.backref('oturumlar', lazy=True))
    
    # DÜZELTİLMİŞ __table_args__ tanımı (tuple olarak)
    __table_args__ = (
        db.UniqueConstraint('DersID', 'OturumNumarasi', 'OturumSiraNumarasi', name='_ders_hafta_oturum_uc'),
    )
    
    def generate_qr_data(self):
        """
        Oturum için QR kodu verisi üretir.
        """
        """Dinamik QR kodu verisi oluşturur"""
        return json.dumps({
            'course_id': self.DersID,
            'session_id': self.OturumID,
            'version': self.QR_CODE_VERSION,
            'week': self.OturumNumarasi,
            'created_at': datetime.utcnow().isoformat()
        })
class YoklamaKayit(db.Model):
    """
    Yoklama kayıtlarını (hangi öğrenci, hangi oturumda) tutar.
    """
    __tablename__ = 'YoklamaKayitlari'
    KayitID = db.Column(db.Integer, primary_key=True)
    OturumID = db.Column(db.Integer, db.ForeignKey('DersOturumlari.OturumID'), nullable=False)
    OgrenciID = db.Column(db.Integer, db.ForeignKey('Ogrenciler.OgrenciID'), nullable=False)
    KayitZamani = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    oturum = db.relationship('DersOturum', backref=db.backref('yoklama_kayitlari', lazy=True))
    ogrenci = db.relationship('Student', backref=db.backref('yoklama_kayitlari', lazy=True))

class PasswordResetToken(db.Model):
    """
    Şifre sıfırlama işlemleri için token bilgisini tutar.
    """
    __tablename__ = 'password_reset_tokens'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('Kullanicilar.id'), nullable=False)
    token = db.Column(db.String(128), unique=True, nullable=False)
    expiration_time = db.Column(db.DateTime, nullable=False)

    user = db.relationship('User', backref=db.backref('password_reset_tokens', lazy=True))

def init_db(app):
    """
    Veritabanı tablolarını oluşturur.
    """
    with app.app_context():
        db.create_all()