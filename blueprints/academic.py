from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, current_app
from flask_login import login_required, current_user
from extensions import db
from models import Ders, Akademisyen, CourseStudent, Student, DersOturum, YoklamaKayit, User
import os
import pandas as pd
import json
import qrcode
import base64
from io import BytesIO
from datetime import datetime
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash
from collections import defaultdict
from sqlalchemy.exc import IntegrityError

academic_bp = Blueprint('academic', __name__)


@academic_bp.route('/dashboard')
@login_required
def dashboard():
    """
    Akademisyen paneli ana sayfası. Akademisyenin derslerini listeler.
    """
    if not current_user.is_academician():
        flash('Bu sayfaya erişim yetkiniz yok.', 'danger')
        return redirect(url_for('auth.login'))  # Ana sayfaya değil, login sayfasına yönlendir!

    academician_details = current_user.academician_details
    if not academician_details:
        flash('Akademisyen profiliniz bulunamadı.', 'danger')
        return redirect(url_for('auth.login'))

    academician_courses = Ders.query.filter_by(AkademisyenID=academician_details.AkademisyenID).all()
    return render_template('academician_dashboard.html', courses=academician_courses)

@academic_bp.route('/add_course', methods=['GET', 'POST'])
@login_required
def add_course():
    """
    Akademisyen yeni ders ekler. Formdan gelen verileri işler.
    """
    current_year = datetime.now().year
    if request.method == 'POST':
        ders_adi = request.form.get('DersAdi')
        ders_kodu = request.form.get('DersKodu')
        ders_yili = request.form.get('ders_yili').strip()
        ders_donemi = request.form.get('ders_donemi').strip()
        kredi = request.form.get('kredi')
        devam_zorunlulugu = 'devam_zorunlulugu' in request.form

        if not ders_adi or not ders_kodu:
            flash('Tüm alanları doldurunuz.', 'danger')
            return render_template('add_course.html', current_year=current_year)
        
        try:
            kredi = int(kredi) if kredi else None
        except ValueError:
            flash('Kredi değeri sayı olmalıdır.', 'danger')
            return render_template('add_course.html', current_year=current_year)

        academician_details = current_user.academician_details
        if not academician_details:
            flash('Akademisyen profiliniz bulunamadı.', 'danger')
            return redirect(url_for('auth.dashboard'))

        existing_course = Ders.query.filter(
            Ders.DersKodu == ders_kodu,
            Ders.DersYili == ders_yili,
            Ders.DersDonemi == ders_donemi,
            Ders.AkademisyenID == academician_details.AkademisyenID
        ).first()

        if existing_course:
            flash('Bu ders kodu, yılı ve dönemi için zaten bir ders kaydınız mevcut.', 'danger')
            return render_template('add_course.html', current_year=current_year)

        new_course = Ders(
            DersKodu=ders_kodu,
            DersAdi=ders_adi,
            DersYili=ders_yili,
            DersDonemi=ders_donemi,
            Kredi=kredi,
            DevamZorunluluguVarMi=devam_zorunlulugu,
            AkademisyenID=academician_details.AkademisyenID
        )
        db.session.add(new_course)
        db.session.commit()
        flash('Ders başarıyla eklendi!', 'success')
        return redirect(url_for('academic.list_courses'))  # Otomatik yönlendirme
    return render_template('add_course.html', current_year=current_year)

@academic_bp.route('/courses')
@login_required
def list_courses():
    """
    Akademisyenin eklediği tüm dersleri listeler.
    """
    if not current_user.is_academician():
        flash('Bu sayfaya erişim yetkiniz yok.', 'danger')
        return redirect(url_for('auth.dashboard'))

    academician_details = current_user.academician_details
    if not academician_details:
        flash('Akademisyen profiliniz bulunamadı.', 'danger')
        return redirect(url_for('auth.login'))

    courses = Ders.query.filter_by(AkademisyenID=academician_details.AkademisyenID).all()
    return render_template('list_courses.html', courses=courses)

@academic_bp.route('/course_students/<int:course_id>')
@login_required
def course_students(course_id):
    """
    Seçilen dersin öğrenci listesini ve aktif oturumunu gösterir.
    """
    course = Ders.query.get_or_404(course_id)
    students = Student.query.join(CourseStudent).filter(CourseStudent.DersID == course_id).all()
    # Aktif oturum kontrolü
    active_session = DersOturum.query.filter_by(DersID=course_id, AktifMi=True).first()
    return render_template('course_students.html', course=course, students=students, active_session=active_session)

@academic_bp.route('/upload_students/<int:course_id>', methods=['GET', 'POST'])
@login_required
def upload_students_to_course(course_id):
    """
    Excel dosyasından öğrenci yükleme işlemini yapar.
    """
    if not current_user.is_academician():
        flash('Bu sayfaya erişim yetkiniz yok.', 'danger')
        return redirect(url_for('auth.dashboard'))

    academician_details = current_user.academician_details
    if not academician_details:
        flash('Akademisyen profiliniz bulunamadı.', 'danger')
        return redirect(url_for('auth.login'))

    course = Ders.query.get_or_404(course_id)

    if course.AkademisyenID != academician_details.AkademisyenID:
        flash('Bu derse öğrenci yükleme yetkiniz yok.', 'danger')
        return redirect(url_for('auth.dashboard'))

    current_students_in_course = [cs.ogrenci_objesi for cs in course.kayitli_ogrenciler]

    if request.method == 'POST':
        if 'file' not in request.files:
            flash('Dosya yüklenmedi.', 'danger')
            return redirect(request.url)

        file = request.files['file']
        if file.filename == '':
            flash('Dosya seçilmedi.', 'danger')
            return redirect(request.url)

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            uploads_folder = current_app.config['UPLOAD_FOLDER']
            if not os.path.exists(uploads_folder):
                os.makedirs(uploads_folder)
            filepath = os.path.join(uploads_folder, filename)
            file.save(filepath)

            try:
                df = pd.read_excel(filepath)

                # Gerekli sütunları kontrol et
                required_columns = ['Öğrenci No', 'Adı', 'Soyadı']
                missing_columns = [col for col in required_columns if col not in df.columns]

                if missing_columns:
                    flash(f'Excel dosyasında eksik sütunlar bulundu: {", ".join(missing_columns)}. Lütfen kontrol edin.', 'danger')
                    return redirect(request.url)

                added_count = 0
                already_in_course_count = 0
                updated_passive_count = 0
                new_passive_student_created_count = 0

                for index, row in df.iterrows():
                    student_no = str(row['Öğrenci No']).strip()
                    student_ad = str(row['Adı']).strip()
                    student_soyad = str(row['Soyadı']).strip()
                    
                    # İsteğe bağlı sütunlar
                    student_sinif = str(row['Sınıfı']).strip() if 'Sınıfı' in df.columns and pd.notna(row['Sınıfı']) else None
                    student_birim_program = str(row['Birim Program']).strip() if 'Birim Program' in df.columns and pd.notna(row['Birim Program']) else None

                    if not student_no.isdigit():
                        flash(f'Geçersiz öğrenci numarası formatı: {student_no} (satır {index + 2}). Sadece rakamlardan oluşmalıdır.', 'warning')
                        continue

                    user_with_student_no = User.query.filter_by(OgrenciNo=student_no).first()
                    if user_with_student_no:
                        if user_with_student_no.UserType != 'student':
                            # Bu kullanıcı öğrenci değilse, güncelleme yapma!
                            continue
                        # Sadece öğrenci kullanıcılarının adı/soyadı güncellensin
                        user_with_student_no.Isim = student_ad
                        user_with_student_no.Soyisim = student_soyad
                        
                        student_obj = None

                        # Öğrenci detaylarını güncelle
                        student_obj = user_with_student_no.student_details

                        if student_obj:
                            student_obj.Sinif = student_sinif
                            student_obj.BirimProgram = student_birim_program

                        # Pasif hesap durumunu kontrol et
                        if not user_with_student_no.is_active_user:
                            updated_passive_count += 1

                        # Eğer User objesi var ama Student objesi eksikse
                        if not student_obj:
                            student_obj = Student(
                                UserID=user_with_student_no.id,
                                OgrenciNo=student_no,
                                Sinif=student_sinif,
                                BirimProgram=student_birim_program
                            )
                            db.session.add(student_obj)

                    else:
                        # Yeni öğrenci hesabı oluştur
                        new_user = User(
                            OgrenciNo=student_no,
                            Isim=student_ad,
                            Soyisim=student_soyad,
                            Email=None,
                            SifreHash=generate_password_hash(os.urandom(16).hex()),
                            UserType='student',
                            is_active_user=False
                        )
                        db.session.add(new_user)
                        db.session.flush()

                        new_student = Student(
                            UserID=new_user.id,
                            OgrenciNo=student_no,
                            Sinif=student_sinif,
                            BirimProgram=student_birim_program
                        )
                        db.session.add(new_student)
                        student_obj = new_student
                        new_passive_student_created_count += 1
                    
                    db.session.flush()

                    # Ders kaydını kontrol et ve ekle
                    existing_enrollment = CourseStudent.query.filter_by(
                        OgrenciID=student_obj.OgrenciID,
                        DersID=course.DersID
                    ).first()

                    if not existing_enrollment:
                        new_enrollment = CourseStudent(
                            OgrenciID=student_obj.OgrenciID,
                            DersID=course.DersID,
                            KayitTarihi=datetime.utcnow()
                        )
                        db.session.add(new_enrollment)
                        added_count += 1
                    else:
                        already_in_course_count += 1

                db.session.commit()

                flash(f'"{course.DersAdi}" dersine {added_count} öğrenci başarıyla eklendi.', 'success')
                if new_passive_student_created_count > 0:
                    flash(f'{new_passive_student_created_count} yeni pasif öğrenci hesabı oluşturuldu. Öğrenciler sisteme giriş yapabilmek için kendi öğrenci numaralarıyla kayıt olmalılar.', 'info')
                if updated_passive_count > 0:
                    flash(f'{updated_passive_count} mevcut pasif öğrenci bilgisi güncellendi.', 'info')
                if already_in_course_count > 0:
                    flash(f'{already_in_course_count} öğrenci zaten derse kayıtlıydı.', 'info')

            except Exception as e:
                db.session.rollback()
                flash(f'Dosya işlenirken bir hata oluştu: {str(e)}', 'danger')
            finally:
                if os.path.exists(filepath):
                    os.remove(filepath)

            return redirect(url_for('academic.course_students', course_id=course.DersID))

    return render_template('upload_students_to_course.html', course=course, current_students=current_students_in_course)

@academic_bp.route('/edit_course/<int:course_id>', methods=['GET', 'POST'])
@login_required
def edit_course(course_id):
    """
    Ders bilgilerini güncelleme işlemini yapar.
    """
    current_year = datetime.now().year
    course = Ders.query.get_or_404(course_id)
    all_courses = Ders.query.filter_by(AkademisyenID=current_user.academician_details.AkademisyenID).all()

    if not current_user.is_academician() or course.AkademisyenID != current_user.academician_details.AkademisyenID:
        flash('Yetkiniz yok', 'danger')
        return redirect(url_for('auth.list_courses'))

    if request.method == 'POST':
        yeni_kod = request.form.get('ders_kodu')
        yeni_yil = request.form.get('ders_yili')
        yeni_donem = request.form.get('ders_donemi')
        akademisyen_id = course.AkademisyenID

        # Aynı kombinasyona sahip başka bir ders var mı kontrol et
        ayni_ders = Ders.query.filter(
            Ders.DersID != course.DersID,
            Ders.DersKodu == yeni_kod,
            Ders.DersYili == yeni_yil,
            Ders.DersDonemi == yeni_donem,
            Ders.AkademisyenID == akademisyen_id
        ).first()
        if ayni_ders:
            flash('Bu ders kodu, yıl ve dönem ile zaten bir ders mevcut!', 'danger')
            return redirect(url_for('academic.edit_course', course_id=course.DersID))

        # Güncelle ve kaydet
        course.DersKodu = yeni_kod
        course.DersAdi = request.form.get('ders_adi')
        course.DersYili = yeni_yil
        course.DersDonemi = yeni_donem
        course.Kredi = request.form.get('kredi')
        course.DevamZorunluluguVarMi = 'devam_zorunlulugu' in request.form
        try:
            db.session.commit()
            flash('Ders başarıyla güncellendi!', 'success')
        except IntegrityError:
            db.session.rollback()
            flash('Veritabanı hatası: Aynı ders zaten mevcut.', 'danger')
    return redirect(url_for('academic.list_courses'))

    return render_template('edit_course.html', course=course, all_courses=all_courses, current_year=current_year)

@academic_bp.route('/delete_course/<int:course_id>', methods=['POST'])
@login_required
def delete_course(course_id):
    """
    Ders ve bağlı oturumları siler.
    """
    course = Ders.query.get_or_404(course_id)
    # Önce bağlı oturumları sil
    for oturum in course.oturumlar:
        db.session.delete(oturum)
    db.session.delete(course)
    db.session.commit()
    flash('Ders ve bağlı oturumlar silindi.', 'success')
    return redirect(url_for('academic.list_courses'))

@academic_bp.route('/remove_student_from_course/<int:course_id>/<int:student_id>', methods=['POST'])
@login_required
def remove_student_from_course(course_id, student_id):
    """
    Dersten öğrenci silme işlemini yapar.
    """
    if not current_user.is_academician():
        flash('Yetkiniz yok', 'danger')
        return redirect(url_for('auth.list_courses'))

    course = Ders.query.get_or_404(course_id)
    student = Student.query.get_or_404(student_id)
    enrollment = CourseStudent.query.filter_by(DersID=course_id, OgrenciID=student_id).first()
    if enrollment:
        db.session.delete(enrollment)
        db.session.commit()
        flash('Öğrenci dersten silindi.', 'success')
    else:
        flash('Öğrenci bu derse kayıtlı değil.', 'warning')
    return redirect(url_for('academic.course_students', course_id=course.DersID))

@academic_bp.route('/reports')
def reports_dashboard():
    """
    Raporlar ana sayfası.
    """
    # Raporlar sayfası kodları
    return render_template('reports_dashboard.html')

def allowed_file(filename):
    """
    Dosya uzantısı kontrolü yapar.
    """
    allowed_extensions = current_app.config['ALLOWED_EXTENSIONS']
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions

