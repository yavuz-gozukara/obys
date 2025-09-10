from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from flask_login import login_user, logout_user, current_user, login_required
from werkzeug.security import generate_password_hash, check_password_hash
from extensions import db
from models import User, Akademisyen, Student, PasswordResetToken, Ders, CourseStudent
import uuid
from datetime import datetime, timedelta
from utils.auth import send_password_reset_email
from werkzeug.security import generate_password_hash, check_password_hash  # check_password_hash eklenmeli

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """
    Kullanıcı giriş işlemini gerçekleştirir. Akademisyen ve öğrenci için yönlendirme yapar.
    """
    if current_user.is_authenticated:
        if current_user.is_academician():
            return redirect(url_for('academic.dashboard'))
        elif current_user.is_student():
            # DÜZELTME: Yönlendirmeden önce öğrenci detaylarını kontrol et
            if hasattr(current_user, 'student_details') and current_user.student_details:
                return redirect(url_for('student.student_dashboard'))
            else:
                flash('Öğrenci profiliniz bulunamadı.', 'danger')
                return redirect(url_for('home'))
    if request.method == 'POST':
        email_or_no = request.form.get('email_or_no')
        password = request.form.get('password')

        user = User.query.filter(
            (User.Email.ilike(email_or_no)) | (User.OgrenciNo.ilike(email_or_no))
        ).first()

        if not user:
            flash('Kullanıcı bulunamadı.', 'danger')
            return render_template('login.html')

        if not user.is_active_user:
            flash('Kullanıcı hesabı aktif değil.', 'danger')
            return render_template('login.html')

        if not user.verify_password(password):
            flash('Şifre yanlış.', 'danger')
            return render_template('login.html')

        if user.is_student():
            # Öğrenci tablosunda da aktif olmalı
            student = user.student_details
            if not student or not student.is_active_user:
                flash('Öğrenci kaydınız aktif değil.', 'danger')
                return render_template('login.html')

        login_user(user)
        flash('Başarıyla giriş yaptınız.', 'success')
        if user.is_academician():
            return redirect(url_for('academic.dashboard'))
        elif user.is_student():
            return redirect(url_for('student.student_dashboard'))
    return render_template('login.html')

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """
    Öğrenci kayıt işlemini gerçekleştirir. Gerekli kontrolleri yapar.
    """
    if current_user.is_authenticated:
        if current_user.is_academician():
            return redirect(url_for('dashboard'))
        elif current_user.is_student():
            return redirect(url_for('student_dashboard'))

    if request.method == 'POST':
        ad = request.form.get('ad')
        soyad = request.form.get('soyad')
        email = request.form.get('email')
        password = request.form.get('password')
        password2 = request.form.get('password2')
        ogrenci_no = request.form.get('ogrenci_no')

        if not ogrenci_no:
            flash('Öğrenci numarası boş bırakılamaz.', 'danger')
            return redirect(url_for('auth.register'))

        if not email or not email.endswith('@ogr.bandirma.edu.tr'):
            flash('Sadece @ogr.bandirma.edu.tr uzantılı e-posta adresi ile kayıt olabilirsiniz.', 'danger')
            return redirect(url_for('auth.register'))

        if len(password) < 6:
            flash('Şifreniz en az 6 karakter uzunluğunda olmalıdır.', 'danger')
            return redirect(url_for('auth.register'))

        if password != password2:
            flash('Şifreler uyuşmuyor.', 'danger')
            return redirect(url_for('auth.register'))

        existing_user_by_no = User.query.filter_by(OgrenciNo=ogrenci_no).first()
        if existing_user_by_no and not existing_user_by_no.is_active_user:
            existing_user_by_no.SifreHash = generate_password_hash(password)
            existing_user_by_no.Isim = ad
            existing_user_by_no.Soyisim = soyad
            existing_user_by_no.Email = email
            existing_user_by_no.is_active_user = True
            db.session.commit()
            flash('Hesabınız başarıyla aktifleştirildi! Şimdi giriş yapabilirsiniz.', 'success')
            return redirect(url_for('auth.login'))

        if existing_user_by_no and existing_user_by_no.is_active_user:
            flash('Bu öğrenci numarası ile zaten aktif bir öğrenci kaydı mevcut.', 'danger')
            return redirect(url_for('auth.register'))

        existing_user_by_email = User.query.filter_by(Email=email).first()
        if existing_user_by_email:
            flash('Bu e-posta adresi ile zaten bir kullanıcı kaydı mevcut.', 'danger')
            return redirect(url_for('auth.register'))

        new_user = User(
            OgrenciNo=ogrenci_no,
            Email=email,
            SifreHash=generate_password_hash(password),
            UserType='student',
            Isim=ad,
            Soyisim=soyad,
            is_active_user=True
        )
        db.session.add(new_user)
        db.session.commit()

        new_student = Student(
            UserID=new_user.id,
            OgrenciNo=ogrenci_no,
            is_active_user=True
        )
        db.session.add(new_student)
        db.session.commit()

        # Otomatik örnek ders ekle (eğer hiç ders yoksa)
        example_course = Ders.query.first()
        if example_course:
            course_student = CourseStudent(DersID=example_course.DersID, OgrenciID=new_student.OgrenciID)
            db.session.add(course_student)
            db.session.commit()

        flash('Öğrenci kaydınız başarıyla oluşturuldu! Şimdi giriş yapabilirsiniz.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('register.html')

@auth_bp.route('/logout')
@login_required
def logout():
    """
    Kullanıcı çıkış işlemini gerçekleştirir.
    """
    logout_user()
    session.pop('user_type', None)
    flash('Başarıyla çıkış yapıldı.', 'info')
    return redirect(url_for('home'))

@auth_bp.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    """
    Şifre sıfırlama linki gönderme işlemini yapar.
    """
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        email_or_no = request.form.get('email_or_no')
        user = User.query.filter((User.Email == email_or_no) | (User.OgrenciNo == email_or_no)).first()

        if user:
            # Önceki tokenları temizle
            PasswordResetToken.query.filter_by(user_id=user.id).delete()
            db.session.commit()

            # Yeni bir token oluştur
            token = str(uuid.uuid4())
            expiration_time = datetime.utcnow() + timedelta(minutes=30)
            
            reset_token = PasswordResetToken(user_id=user.id, token=token, expiration_time=expiration_time)
            db.session.add(reset_token)
            db.session.commit()

            reset_link = url_for('auth.reset_password', token=token, _external=True)
            send_password_reset_email(user.Email or user.OgrenciNo, reset_link)
            flash('Şifre sıfırlama linki e-posta adresinize gönderildi. Lütfen spam klasörünüzü de kontrol edin.', 'info')
            return redirect(url_for('auth.login'))
        else:
            flash('Girilen e-posta veya öğrenci numarasına sahip bir kullanıcı bulunamadı.', 'danger')
            return render_template('forgot_password.html')
    
    return render_template('forgot_password.html')

@auth_bp.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    """
    Şifre sıfırlama işlemini gerçekleştirir.
    """
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    reset_token = PasswordResetToken.query.filter_by(token=token).first()

    if not reset_token or reset_token.expiration_time < datetime.utcnow():
        flash('Geçersiz veya süresi dolmuş bir şifre sıfırlama linki.', 'danger')
        return redirect(url_for('forgot_password'))

    if request.method == 'POST':
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')

        if not new_password or not confirm_password:
            flash('Lütfen tüm alanları doldurun.', 'danger')
            return render_template('reset_password.html', token=token)

        if new_password != confirm_password:
            flash('Şifreler uyuşmuyor.', 'danger')
            return render_template('reset_password.html', token=token)

        # Şifre karmaşıklığı kontrolü
        if len(new_password) < 6:
            flash('Şifre en az 6 karakter uzunluğunda olmalıdır.', 'danger')
            return render_template('reset_password.html', token=token)

        user = User.query.get(reset_token.user_id)
        if user:
            user.SifreHash = generate_password_hash(new_password)
            db.session.delete(reset_token) # Tokenı kullanıldıktan sonra sil
            db.session.commit()
            flash('Şifreniz başarıyla sıfırlandı. Şimdi giriş yapabilirsiniz.', 'success')
            return redirect(url_for('auth.login'))
        else:
            flash('Kullanıcı bulunamadı.', 'danger')
            return redirect(url_for('forgot_password'))

    return render_template('reset_password.html', token=token)

# Şifre sıfırlama işlemi için örnek kod (bu kodu doğrudan çalıştırmayın, sadece referans için)
# from werkzeug.security import generate_password_hash
# from extensions import db
# from models import User

# user = User.query.filter_by(Email='akademisyen_mail_adresiniz').first()
# user.SifreHash = generate_password_hash('şifreniz')
# db.session.commit()

