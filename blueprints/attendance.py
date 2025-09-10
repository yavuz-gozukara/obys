
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, jsonify, send_file
from flask_login import login_required, current_user
from extensions import db
from models import Ders, DersOturum, YoklamaKayit, CourseStudent, Student
from datetime import datetime, timedelta
import json
import qrcode
import base64
from io import BytesIO, StringIO
import uuid
import csv
from collections import defaultdict

attendance_bp = Blueprint('attendance', __name__)

# CSV indirme fonksiyonu
@attendance_bp.route('/download_attendance_report/<int:course_id>')
@login_required
def download_attendance_report(course_id):
    """
    Seçilen dersin yoklama raporunu CSV olarak indirir.
    """
    course = Ders.query.get_or_404(course_id)
    sessions = DersOturum.query.filter_by(DersID=course_id).order_by(DersOturum.OturumNumarasi, DersOturum.OturumSiraNumarasi).all()
    grouped_sessions = defaultdict(list)
    for session_obj in sessions:
        grouped_sessions[session_obj.OturumNumarasi].append(session_obj)
    sorted_week_numbers = sorted(grouped_sessions.keys())
    students = Student.query.join(CourseStudent, Student.OgrenciID == CourseStudent.OgrenciID).filter(CourseStudent.DersID == course_id).all()
    report_data = {}
    for student in students:
        attendance = {}
        for week_num in sorted_week_numbers:
            for session in grouped_sessions[week_num]:
                kayit = YoklamaKayit.query.filter_by(OturumID=session.OturumID, OgrenciID=student.OgrenciID).first()
                session_key = f"{session.OturumNumarasi}-{session.OturumSiraNumarasi}"
                attendance[session_key] = 'X' if kayit else ''
        report_data[student.OgrenciID] = {
            'student_no': student.OgrenciNo,
            'student_name': f"{student.user.Isim} {student.user.Soyisim}",
            'attendance': attendance
        }
    import io
    output = io.StringIO()
    writer = csv.writer(output)
    header = ['Öğrenci No', 'Adı Soyadı']
    for week_num in sorted_week_numbers:
        for session in grouped_sessions[week_num]:
            header.append(f"Hafta {week_num} - Oturum {session.OturumSiraNumarasi}")
    writer.writerow(header)
    for student_id, data in report_data.items():
        row = [data['student_no'], data['student_name']]
        for week_num in sorted_week_numbers:
            for session in grouped_sessions[week_num]:
                session_key = f"{session.OturumNumarasi}-{session.OturumSiraNumarasi}"
                row.append('Var' if data['attendance'][session_key] == 'X' else 'Yok')
        writer.writerow(row)
    csv_bytes = io.BytesIO(output.getvalue().encode('utf-8'))
    return send_file(csv_bytes, mimetype='text/csv', as_attachment=True, download_name=f'yoklama_raporu_{course.DersKodu}.csv')

@attendance_bp.route('/course_sessions/<int:course_id>')
@login_required
def view_course_sessions(course_id):
    """
    Seçilen dersin tüm oturumlarını (hafta/oturum) listeler.
    """
    course = Ders.query.get_or_404(course_id)
    if not current_user.is_academician() or course.AkademisyenID != current_user.academician_details.AkademisyenID:
        flash('Yetkiniz yok', 'danger')
        return redirect(url_for('academicain.dashboard'))

    # Oturumları hafta numarasına ve ardından sıra numarasına göre sırala
    sessions = DersOturum.query.filter_by(DersID=course_id).order_by(DersOturum.OturumNumarasi, DersOturum.OturumSiraNumarasi, DersOturum.BaslangicZamani).all()
    
    # Oturumları haftalara göre gruplamak için
    grouped_sessions = defaultdict(list)
    for session_obj in sessions:
        grouped_sessions[session_obj.OturumNumarasi].append(session_obj)

    # Dictionary'i hafta numarasına göre sırala
    sorted_grouped_sessions = sorted(grouped_sessions.items())

    return render_template('course_sessions.html', course=course, grouped_sessions=sorted_grouped_sessions)

@attendance_bp.route('/start_attendance/<int:course_id>', methods=['GET', 'POST'])
@login_required
def start_attendance(course_id):
    """
    Yeni yoklama oturumu başlatır (hafta ve oturum).
    """
    course = Ders.query.get_or_404(course_id)
    active_session = DersOturum.query.filter_by(DersID=course_id, AktifMi=True).first()
    
    if active_session:
        flash(f'Önce {active_session.OturumNumarasi}. haftadaki aktif oturumu durdurun!', 'danger')
        return redirect(url_for('attendance.view_course_sessions', course_id=course_id))
    
    last_session = DersOturum.query.filter_by(DersID=course_id).order_by(DersOturum.OturumNumarasi.desc()).first()
    last_week = last_session.OturumNumarasi if last_session else 0
    next_week = last_week + 1
    if not course.kayitli_ogrenciler:
        flash('Bu derse kayıtlı öğrenci olmadığı için yoklama oturumu başlatılamaz!', 'danger')
        return redirect(url_for('attendance.view_course_sessions', course_id=course_id))
    if not current_user.is_academician() or course.AkademisyenID != current_user.academician_details.AkademisyenID:
        flash('Yetkiniz yok', 'danger')
        return redirect(url_for('auth.dashboard'))

    if request.method == 'POST':
        week_number_str = request.form.get('week_number')
        action_type = request.form.get('action_type')
        
        if action_type == 'new_week':
            week_number = next_week
        elif action_type == 'add_session_to_week':
            week_number = last_week
        else:
            flash('Geçersiz işlem türü', 'danger')
            return redirect(url_for('attendance.start_attendance', course_id=course_id))

        if not week_number_str:
            flash('Hafta numarası boş bırakılamaz.', 'danger')
            return redirect(url_for('attendance.start_attendance', course_id=course_id))

        try:
            week_number = int(week_number_str)
            if not (1 <= week_number <= 14):
                flash('Hafta numarası 1 ile 14 arasında olmalıdır.', 'danger')
                return redirect(url_for('attendance.start_attendance', course_id=course_id))
        except ValueError:
            flash('Geçersiz hafta numarası formatı.', 'danger')
            return redirect(url_for('attendance.start_attendance', course_id=course_id))

        try:
            # Aynı hafta için mevcut oturumları kontrol et
            existing_sessions_in_week = DersOturum.query.filter_by(
                DersID=course.DersID,
                OturumNumarasi=week_number
            ).order_by(DersOturum.OturumSiraNumarasi.desc()).all()

            if action_type == 'new_week' and existing_sessions_in_week:
                flash(f'Hafta {week_number} için zaten oturum(lar) mevcut.', 'warning')
                return redirect(url_for('attendance.start_attendance', course_id=course_id))
            
            # Yeni oturum sıra numarasını belirle
            if existing_sessions_in_week:
                next_session_order_number = existing_sessions_in_week[0].OturumSiraNumarasi + 1
            else:
                next_session_order_number = 1

            # QR kodu verisini oluştur
            qr_data_dict = {
                'course_id': course.DersID,
                'week_num': week_number,
                'session_order': next_session_order_number
            }
            qr_data_string = json.dumps(qr_data_dict)

            # Yeni oturumu oluştur
            new_session = DersOturum(
            DersID=course.DersID,
            OturumNumarasi=week_number,
            OturumSiraNumarasi=next_session_order_number,
            BaslangicZamani=datetime.now(),
            AktifMi=True,
            QRCodeData=qr_data_string,
            QR_Olusma_Zamani=datetime.now(),  # Bu satırı ekleyin
            QR_CODE_VERSION=1
            )
            db.session.add(new_session)
            db.session.commit()
            flash(f"Hafta {week_number} için {next_session_order_number}. oturum başarıyla başlatıldı!", 'success')
            return redirect(url_for('attendance.view_course_sessions', course_id=course_id))

        except Exception as e:
            db.session.rollback()
            flash(f"Oturum başlatılırken bir hata oluştu: {str(e)}", 'danger')

    existing_week_numbers = db.session.query(DersOturum.OturumNumarasi).filter_by(DersID=course_id).distinct().order_by(DersOturum.OturumNumarasi).all()
    existing_week_numbers = [wn[0] for wn in existing_week_numbers]

    aktif_oturumlar = DersOturum.query.filter_by(DersID=course_id, AktifMi=True).all()

    return render_template(
        'start_attendance.html',
        course=course,
        next_week=next_week,
        last_week=last_week,
        course_id=course_id,
        existing_week_numbers=existing_week_numbers,
        aktif_oturumlar=aktif_oturumlar
    )

@attendance_bp.route('/stop_attendance/<int:session_id>')
@login_required
def stop_attendance(session_id):
    """
    Aktif yoklama oturumunu durdurur.
    """
    session_to_stop = DersOturum.query.get_or_404(session_id)
    if not current_user.is_academician() or session_to_stop.ders.AkademisyenID != current_user.academician_details.AkademisyenID:
        flash('Yetkiniz yok', 'danger')
        return redirect(url_for('auth.dashboard'))

    session_to_stop.AktifMi = False
    session_to_stop.BitisZamani = datetime.utcnow()
    db.session.commit()
    flash('Yoklama oturumu durduruldu', 'success')
    return redirect(url_for('attendance.view_course_sessions', course_id=session_to_stop.DersID))

@attendance_bp.route('/generate_qr/<int:session_id>')
@login_required
def generate_qr(session_id):
    """
    Oturum için QR kodu üretir ve görüntüler.
    """
    # Oturum bilgilerini al ve yetki kontrolü yap
    session_obj = DersOturum.query.get_or_404(session_id)
    if not current_user.is_academician() or session_obj.ders.AkademisyenID != current_user.academician_details.AkademisyenID:
        flash('Yetkiniz yok', 'danger')
        return redirect(url_for('auth.dashboard'))

    # QR kodu verisini oluştur (zaman damgası ve rastgele versiyon ekleyerek)
    qr_data = {
        'course_id': session_obj.DersID,
        'session_id': session_obj.OturumID,
        'week': session_obj.OturumNumarasi,
        'session_order': session_obj.OturumSiraNumarasi,
        'timestamp': datetime.utcnow().isoformat(),  # Zaman damgası
        'random': uuid.uuid4().hex[:8]  # Rastgele değer
    }
    
    # Veritabanını güncelle
    session_obj.QRCodeData = json.dumps(qr_data)
    session_obj.QR_Olusma_Zamani = datetime.utcnow()
    session_obj.QR_CODE_VERSION = session_obj.QR_CODE_VERSION + 1 if session_obj.QR_CODE_VERSION else 1
    db.session.commit()

    # QR kodu oluştur
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(session_obj.QRCodeData)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    # Base64'e çevir
    buffered = BytesIO()
    img.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode('utf-8')

    # Template'e gönder
    return render_template('view_qr.html',
                         qr_image=img_str,
                         session=session_obj,
                         refresh_interval=5000,  # 5 saniye (milisaniye)
                         now=datetime.utcnow(),
                         remaining_seconds=30)  # 30 saniye geçerlilik

@attendance_bp.route('/delete_session/<int:session_id>', methods=['POST'])
@login_required
def delete_session(session_id):
    """
    Oturumu ve ilişkili yoklama kayıtlarını siler.
    """
    session_to_delete = DersOturum.query.get_or_404(session_id)
    course_id = session_to_delete.DersID

    if not current_user.is_academician() or session_to_delete.ders.AkademisyenID != current_user.academician_details.AkademisyenID:
        return jsonify({'status': 'error', 'message': 'Yetkiniz yok'}), 403

    # İlişkili yoklama kayıtlarını sil
    YoklamaKayit.query.filter_by(OturumID=session_id).delete()
    db.session.delete(session_to_delete)
    db.session.commit()

    return jsonify({'status': 'success'})

@attendance_bp.route('/attendance_report/<int:course_id>')
@login_required
def attendance_report(course_id):
    """
    Seçilen dersin yoklama raporunu hazırlar ve görüntüler.
    """
    course = Ders.query.get_or_404(course_id)
    if not current_user.is_academician() or course.AkademisyenID != current_user.academician_details.AkademisyenID:
        flash('Yetkiniz yok', 'danger')
        return redirect(url_for('auth.dashboard'))

    # Yoklama verilerini hazırla
    sessions = DersOturum.query.filter_by(DersID=course_id).order_by(DersOturum.OturumNumarasi, DersOturum.OturumSiraNumarasi, DersOturum.BaslangicZamani).all()
    course_students = CourseStudent.query.filter_by(DersID=course_id).all()
    students_in_course = [rel.ogrenci_objesi for rel in course_students]

    report_data = {}
    for student in students_in_course:
        report_data[student.OgrenciID] = {
            'student_no': student.OgrenciNo,
            'student_name': f"{student.user.Isim} {student.user.Soyisim}",
            'attendance': {}
        }
        for session_obj in sessions:
            attended = YoklamaKayit.query.filter_by(
                OturumID=session_obj.OturumID,
                OgrenciID=student.OgrenciID
            ).first()
            session_key = f"{session_obj.OturumNumarasi}-{session_obj.OturumSiraNumarasi}"
            report_data[student.OgrenciID]['attendance'][session_key] = 'X' if attended else ''

    grouped_sessions_for_header = defaultdict(list)
    for session_obj in sessions:
        grouped_sessions_for_header[session_obj.OturumNumarasi].append(session_obj)

    for week_num in grouped_sessions_for_header:
        grouped_sessions_for_header[week_num].sort(key=lambda x: x.OturumSiraNumarasi)

    sorted_week_numbers = sorted(grouped_sessions_for_header.keys())

    return render_template('attendance_report.html',
                           course=course,
                           report_data=report_data,
                           grouped_sessions=grouped_sessions_for_header,
                           sorted_week_numbers=sorted_week_numbers)

@attendance_bp.route('/refresh_qr/<int:session_id>')
@login_required
def refresh_qr(session_id):
    """
    Oturum için QR kodunu yeniler ve JSON olarak döndürür.
    """
    # QR kodunu üret ve JSON döndür
    session_obj = DersOturum.query.get_or_404(session_id)
    
    # QR kod verisini güncelle (zaman damgası ekleyerek)
    qr_data = {
        'course_id': session_obj.DersID,
        'session_id': session_obj.OturumID,
        'timestamp': datetime.utcnow().isoformat()  # Zaman damgası ekleyin
    }
    session_obj.QRCodeData = json.dumps(qr_data)
    session_obj.QR_Olusma_Zamani = datetime.utcnow()
    db.session.commit()

    # Yeni QR kodu oluştur
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(session_obj.QRCodeData)
    img = qr.make_image(fill_color="black", back_color="white")
    
    buffered = BytesIO()
    img.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode('utf-8')
    
    return jsonify({
        'qr_image': img_str,
        'last_refresh': datetime.utcnow().strftime('%H:%M:%S'),
        'status': 'success'
    })

