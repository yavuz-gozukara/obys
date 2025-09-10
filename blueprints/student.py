from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from extensions import db
from models import Student, CourseStudent, Ders, YoklamaKayit, DersOturum
from datetime import datetime
from flask_login import current_user
import json
from flask_socketio import SocketIO

socketio = SocketIO()

student_bp = Blueprint('student', __name__)
def get_current_student_details():
    """
    Şu an giriş yapan öğrencinin detaylarını döndürür.
    """
    if hasattr(current_user, 'student_details') and current_user.student_details:
        return current_user.student_details
    return None

@student_bp.route('/student_dashboard')
@login_required
def student_dashboard():
    """
    Öğrenci paneli ana sayfası. Kayıtlı dersleri ve devamsızlık durumunu gösterir.
    """
    if not current_user.is_student():
        flash('Bu sayfaya erişim yetkiniz yok.', 'danger')
        return redirect(url_for('auth.login'))

    student_details = get_current_student_details()
    student_name = f"{student_details.user.Isim} {student_details.user.Soyisim}"
    if not student_details:
        flash('Öğrenci profiliniz bulunamadı.', 'danger')
        return redirect(url_for('home'))

    registered_courses_relations = student_details.dersleri
    registered_courses = []
    # ...devamı aynı...

    for rel in registered_courses_relations:
        course = rel.ders_objesi
        # Tüm oturumlar
        sessions = DersOturum.query.filter_by(DersID=course.DersID).all()
        total_sessions = len(sessions)
        attended_sessions = db.session.query(DersOturum.OturumID).\
            join(YoklamaKayit, DersOturum.OturumID == YoklamaKayit.OturumID).\
            filter(
                YoklamaKayit.OgrenciID == student_details.OgrenciID,
                DersOturum.DersID == course.DersID
            ).distinct().count()
        max_allowed_absence = 4  # veya sisteminizdeki değeri kullanın
        remaining_absence = max_allowed_absence - (total_sessions - attended_sessions)

        # Durum belirle
        if total_sessions == 0:
            absence_status = 'success'
        elif (total_sessions - attended_sessions) > max_allowed_absence:
            absence_status = 'danger'
        elif (total_sessions - attended_sessions) == max_allowed_absence:
            absence_status = 'warning'
        else:
            absence_status = 'success'

        # Kurs nesnesine ek bilgiler ekle
        course.total_sessions = total_sessions
        course.attended_sessions = attended_sessions
        course.remaining_absence = remaining_absence
        course.absence_status = absence_status
        registered_courses.append(course)

    return render_template('student_dashboard.html', registered_courses=registered_courses)


@student_bp.route('/student/my_courses')
@login_required
def student_my_courses():
    """
    Öğrencinin kayıtlı olduğu dersleri listeler.
    """
    if not current_user.is_student():
        flash('Bu sayfaya erişim yetkiniz yok.', 'danger')
        return redirect(url_for('auth.home'))

    student_details = get_current_student_details()
    if not student_details:
        flash('Öğrenci profiliniz bulunamadı.', 'danger')
        return redirect(url_for('auth.home'))

    registered_course_relations = student_details.dersleri
    my_courses = [rel.ders_objesi for rel in registered_course_relations]

    return render_template('student_my_courses.html', my_courses=my_courses)

@student_bp.route('/student/course_attendance/<int:course_id>')
@login_required
def student_course_attendance(course_id):
    """
    Seçilen dersin haftalık yoklama durumunu gösterir.
    """
    if not current_user.is_student():
        flash('Bu sayfaya erişim yetkiniz yok.', 'danger')
        return redirect(url_for('auth.home'))

    student_details = get_current_student_details()
    if not student_details:
        flash('Öğrenci profiliniz bulunamadı.', 'danger')
        return redirect(url_for('auth.home'))

    # ...devamı aynı...

    # Tüm oturumlar (hafta ve sıra numarası ile)
    sessions = DersOturum.query.filter_by(DersID=course_id).order_by(DersOturum.OturumNumarasi, DersOturum.OturumSiraNumarasi).all()

    # Haftalara göre grupla
    weeks = {}
    for session in sessions:
        week = session.OturumNumarasi
        if week not in weeks:
            weeks[week] = []
        weeks[week].append(session)

    # Öğrencinin katıldığı oturumlar
    attended_session_ids = set(
        r[0] for r in db.session.query(YoklamaKayit.OturumID)
        .filter(YoklamaKayit.OgrenciID == student_details.OgrenciID)
        .all()
    )

    weekly_attendance = []
    total_absence = 0.0

    for week_num in sorted(weeks.keys()):
        week_sessions = weeks[week_num]
        total_sessions = len(week_sessions)
        attended_sessions = sum(1 for s in week_sessions if s.OturumID in attended_session_ids)
        missed_sessions = total_sessions - attended_sessions
        # Hafta için devamsızlık oranı
        week_absence = missed_sessions / total_sessions if total_sessions > 0 else 0
        total_absence += week_absence

        weekly_attendance.append({
            'week': week_num,
            'sessions': [
                {
                    'order': s.OturumSiraNumarasi,
                    'attended': s.OturumID in attended_session_ids
                } for s in week_sessions
            ],
            'attended_sessions': attended_sessions,
            'total_sessions': total_sessions,
            'week_absence': week_absence
        })

    max_allowed_absence = 4  # 4 hafta
    remaining_absence = max_allowed_absence - total_absence

    course = Ders.query.get_or_404(course_id)

    return render_template(
        'student_course_attendance.html',
        course=course,
        weekly_attendance=weekly_attendance,
        total_absence=total_absence,
        remaining_absence=remaining_absence,
        max_allowed_absence=max_allowed_absence
    )


@student_bp.route('/qr_scan', methods=['GET', 'POST'])
def qr_scan():
    """
    Öğrenci QR kodu okutarak yoklama kaydı oluşturur.
    """
    # Eğer öğrenci giriş yapmamışsa login sayfasına yönlendir
    if not current_user.is_authenticated or not hasattr(current_user, 'is_student') or not current_user.is_student():
        # QR koddan gelen session_id varsa login sonrası tekrar yönlendirme için sakla
        session_id = request.args.get('session_id') or request.form.get('session_id')
        login_url = url_for('auth.login')
        if session_id:
            # login sonrası otomatik yönlendirme için session_id parametresi ekle
            login_url += f'?next={url_for("student.qr_scan")}?session_id={session_id}'
        return redirect(login_url)

    student_details = get_current_student_details()
    if not student_details:
        flash('Öğrenci profiliniz bulunamadı.', 'danger')
        return redirect(url_for('student.student_dashboard'))

    if request.method == 'GET':
        session_id = request.args.get('session_id', '')
        return render_template('student_scan_qr.html', session_id=session_id)

    # POST işlemi
    qr_data = request.form.get('qr_data')
    try:
        qr_dict = json.loads(qr_data)
        session_id = qr_dict.get('session_id')
        session_obj = DersOturum.query.get(session_id)
        if not session_obj:
            flash('Oturum bulunamadı.', 'danger')
            return redirect(url_for('student.student_dashboard'))
    except Exception:
        flash('Geçersiz QR kod.', 'danger')
        return redirect(url_for('student.student_dashboard'))

    # Otomatik yoklama kaydı oluştur
    # Zaten kaydı varsa tekrar eklenmesin
    existing_record = YoklamaKayit.query.filter_by(OturumID=session_obj.OturumID, OgrenciID=student_details.OgrenciID).first()
    if not existing_record:
        new_record = YoklamaKayit(OturumID=session_obj.OturumID, OgrenciID=student_details.OgrenciID, KayitZamani=datetime.utcnow())
        db.session.add(new_record)
        db.session.commit()

    # SocketIO ile canlı güncelleme gönder
    student_full_name = f"{current_user.Isim} {current_user.Soyisim}"
    student_no = current_user.OgrenciNo

    socketio.emit('attendance_update',
                  {'student_name': student_full_name, 
                   'student_no': student_no, 
                   'student_id': student_details.OgrenciID},
                  room=f'session_{session_obj.OturumID}')