# init_db.py

import os
from werkzeug.security import generate_password_hash
from app import app  # Ana app nesnesini import ediyoruz
from extensions import db
from models import init_db, User, Akademisyen

print("Render Build: Veritabanı ve başlangıç verileri oluşturuluyor...")

# Flask uygulama contexte'i içinde çalıştırıyoruz
with app.app_context():
    # Veritabanı tablolarını oluşturur
    init_db(app)
    print("Tablolar oluşturuldu.")

    # akademisyen_kayit.txt dosyasından ilk kullanıcıyı ekler
    akademisyen_txt = 'akademisyen_kayit.txt'
    if os.path.exists(akademisyen_txt):
        print(f"'{akademisyen_txt}' dosyası bulundu, okunuyor...")
        with open(akademisyen_txt, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                parts = line.split(',')
                if len(parts) < 4:
                    continue

                ad, soyad, email, sifre = [p.strip() for p in parts[:4]]

                # Akademisyen zaten var mı diye kontrol et
                existing_user = User.query.filter_by(Email=email, UserType='academician').first()
                if not existing_user:
                    new_user = User(
                        Isim=ad,
                        Soyisim=soyad,
                        Email=email,
                        SifreHash=generate_password_hash(sifre),
                        UserType='academician',
                        is_active_user=True
                    )
                    db.session.add(new_user)
                    db.session.flush()  # ID'nin oluşması için

                    new_akademisyen = Akademisyen(UserID=new_user.id)
                    db.session.add(new_akademisyen)
                    db.session.commit()
                    print(f"'{email}' email adresi ile akademisyen kullanıcısı başarıyla oluşturuldu.")
                else:
                    print(f"'{email}' email adresli akademisyen zaten mevcut, işlem atlanıyor.")
    else:
        print(f"UYARI: '{akademisyen_txt}' dosyası bulunamadı, ilk kullanıcı oluşturulmadı.")

print("Render Build: Kurulum betiği tamamlandı.")
