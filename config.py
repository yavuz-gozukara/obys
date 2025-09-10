import os

class Config:
    """
    Uygulama ayarlarını ve ortam değişkenlerini tutar.
    """
    SECRET_KEY = os.environ.get('SECRET_KEY', 'sizin_gizli_anahtarınız_buraya_gelecek')
    
    # --- BU BÖLÜMÜ DİKKATLİCE KONTROL EDİN ---
    db_uri = os.environ.get('DATABASE_URL', 'sqlite:///site.db')
    if db_uri and db_uri.startswith("postgres://"):
        db_uri = db_uri.replace("postgres://", "postgresql://", 1)
    SQLALCHEMY_DATABASE_URI = db_uri
    # --- KONTROL EDİLECEK BÖLÜMÜN SONU ---

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = 'uploads'
    ALLOWED_EXTENSIONS = {'csv', 'xlsx', 'xls'}
    MAX_ABSENCE_PERCENTAGE = 30
    QR_REFRESH_SECONDS = 5
    QR_REFRESH_INTERVAL = 5
    QR_CODE_DURATION = 30
