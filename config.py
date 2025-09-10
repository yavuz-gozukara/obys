import os

class Config:
    """
    Uygulama ayarlarını ve ortam değişkenlerini tutar.
    """
    SECRET_KEY = os.environ.get('SECRET_KEY', 'sizin_gizli_anahtarınız_buraya_gelecek')
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///site.db').replace('postgres://site_2p6b_user:YRqQKAvWG5bucK3FaX93lIj6sLsyrqZ5@dpg-d26lkfggjchc73e3stu0-a/site_2p6b', 'postgresql://site_2p6b_user:YRqQKAvWG5bucK3FaX93lIj6sLsyrqZ5@dpg-d26lkfggjchc73e3stu0-a/site_2p6b')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = 'uploads'
    ALLOWED_EXTENSIONS = {'csv', 'xlsx', 'xls'}
    MAX_ABSENCE_PERCENTAGE = 30
    QR_REFRESH_SECONDS = 5
    QR_REFRESH_INTERVAL = 5
    QR_CODE_DURATION = 30