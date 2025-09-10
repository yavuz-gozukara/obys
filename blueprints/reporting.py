from flask import Blueprint, render_template, redirect, url_for, flash, request, send_file, jsonify
from flask_login import login_required, current_user
from extensions import db
from models import Ders, CourseStudent, YoklamaKayit, DersOturum, Student
from utils.reporting import calculate_attendance, generate_weekly_attendance_chart, generate_overall_attendance_pie, generate_attendance_chart
import io
import csv
import base64
import matplotlib
matplotlib.use('Agg')

reporting_bp = Blueprint('reporting', __name__)

@reporting_bp.route('/reports_dashboard')
@login_required
def reports_dashboard():
    """
    Akademisyen için raporlar ana sayfası. Kendi derslerini listeler.
    """
    if not current_user.is_academician():
        flash('Bu sayfaya erişim yetkiniz yok.', 'danger')
        return redirect(url_for('auth.home'))
    
    academician_details = current_user.academician_details
    if not academician_details:
        flash('Akademisyen profiliniz bulunamadı.', 'danger')
        return redirect(url_for('auth.home'))
    
    courses = Ders.query.filter_by(AkademisyenID=academician_details.AkademisyenID).all()
    return render_template('reports_dashboard.html', courses=courses)

@reporting_bp.route('/reports/<int:course_id>')
@login_required
def course_reports(course_id):
    """
    Seçilen dersin haftalık ve genel yoklama grafiklerini gösterir.
    """
    if not current_user.is_academician():
        flash('Bu sayfaya erişim yetkiniz yok.', 'danger')
        return redirect(url_for('auth.home'))
    
    data = calculate_attendance(course_id)
    weekly_chart = generate_weekly_attendance_chart(data['weekly_data'])
    overall_pie = generate_overall_attendance_pie(data['overall_attendance'])
    
    # Grafikleri base64 formatına çevir
    weekly_chart_base64 = base64.b64encode(weekly_chart.getvalue()).decode('utf-8') if weekly_chart else None
    overall_pie_base64 = base64.b64encode(overall_pie.getvalue()).decode('utf-8') if overall_pie else None
    
    return render_template(
        'course_reports.html',
        data=data,
        weekly_chart=weekly_chart_base64,
        overall_pie=overall_pie_base64
    )

@reporting_bp.route('/reports/<int:course_id>/failing_students')
@login_required
def failing_students_report(course_id):
    """
    Devamsızlıktan kalan öğrencilerin raporunu CSV olarak indirir.
    """
    if not current_user.is_academician():
        return redirect(url_for('auth.home'))
    
    attendance_data = calculate_attendance(course_id)
    failing_students = attendance_data['failing_students']
    
    # CSV raporu oluştur
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Öğrenci No', 'Ad Soyad', 'Katıldığı Hafta', 'Devamsızlık Sayısı', 'Durum'])
    
    for student in failing_students:
        writer.writerow([
            student['student_no'],
            student['name'],
            student['attended_weeks'],
            student['absence_count'],
            student['status']
        ])
    
    output.seek(0)
    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8')),
        mimetype='text/csv',
        as_attachment=True,
        download_name=f'devamsizliktan_kalanlar_{course_id}.csv'
    )

@reporting_bp.route('/reports/<int:course_id>/borderline_students')
@login_required
def borderline_students_report(course_id):
    """
    Devamsızlık sınırında olan öğrencilerin raporunu CSV olarak indirir.
    """
    if not current_user.is_academician():
        return redirect(url_for('auth.home'))
    
    attendance_data = calculate_attendance(course_id)
    borderline_students = [s for s in attendance_data['student_attendance'] 
                          if s['absence_count'] == attendance_data['max_allowed_absences']]
    
    # CSV raporu oluştur
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Öğrenci No', 'Ad Soyad', 'Katıldığı Hafta', 'Devamsızlık', 'Durum'])
    
    for student in borderline_students:
        writer.writerow([
            student['student_no'],
            student['name'],
            student['attended_weeks'],
            student['absence_count'],
            student['status']
        ])
    
    output.seek(0)
    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8')),
        mimetype='text/csv',
        as_attachment=True,
        download_name=f'sinirda_olan_ogrenciler_{course_id}.csv'
    )
    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8')),
        mimetype='text/csv',
        as_attachment=True,
        download_name=f'sinirda_olan_ogrenciler_{course_id}.csv'
    )

@reporting_bp.route('/reports/<int:course_id>/weekly_chart')
@login_required
def weekly_attendance_chart(course_id):
    """
    Haftalık yoklama grafiğini PNG olarak döndürür.
    """
    if not current_user.is_academician():
        return redirect(url_for('auth.home'))
    week = request.args.get('week', type=int)
    attendance_data = calculate_attendance(course_id)
    if week:
        weekly_data = [w for w in attendance_data['weekly_data'] if w['week'] == week]
    else:
        weekly_data = attendance_data['weekly_data']
    chart = generate_weekly_attendance_chart(weekly_data)
    return send_file(chart, mimetype='image/png')

@reporting_bp.route('/reports/<int:course_id>/overall_pie')
@login_required
def overall_attendance_pie(course_id):
    """
    Genel yoklama pasta grafiğini PNG olarak döndürür.
    """
    if not current_user.is_academician():
        return redirect(url_for('auth.home'))
    
    attendance_data = calculate_attendance(course_id)
    chart = generate_overall_attendance_pie(attendance_data['overall_attendance'])
    return send_file(chart, mimetype='image/png')

@reporting_bp.route('/reports/<int:course_id>/full_attendance')
@login_required
def full_attendance_report(course_id):
    """
    Tüm öğrencilerin yoklama durumunu CSV olarak indirir.
    """
    if not current_user.is_academician():
        return redirect(url_for('auth.home'))
    
    attendance_data = calculate_attendance(course_id)
    
    # CSV raporu oluştur
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Öğrenci No', 'Ad Soyad', 'Katıldığı Hafta', 'Devamsızlık', 'Durum'])
    
    for student in attendance_data['student_attendance']:
        writer.writerow([
            student['student_no'],
            student['name'],
            student['attended_weeks'],
            student['absence_count'],
            student['status']
        ])
    
    output.seek(0)
    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8')),
        mimetype='text/csv',
        as_attachment=True,
        download_name=f'tum_ogrenciler_{course_id}.csv'
    )

@reporting_bp.route('/reports/<int:course_id>/class_list')
@login_required
def class_list_report(course_id):
    """
    Sınıf listesini CSV olarak indirir.
    """
    if not current_user.is_academician():
        return redirect(url_for('auth.home'))
    
    data = calculate_attendance(course_id)
    
    # CSV raporu oluştur
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['#', 'Öğrenci No', 'Ad Soyad', 'E-posta', 'Sınıf', 'Program', 'Durum'])
    
    for i, student in enumerate(data['class_list'], 1):
        writer.writerow([
            i,
            student['student_no'],
            student['name'],
            student['email'],
            student['class'],
            student['program'],
            student['active']
        ])
    
    output.seek(0)
    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8')),
        mimetype='text/csv',
        as_attachment=True,
        download_name=f'sinif_listesi_{course_id}.csv'
    )

@reporting_bp.route('/reports/<int:course_id>/attendance_chart')
@login_required
def attendance_chart(course_id):
    """
    Seçilen dersin yoklama grafiğini PNG olarak döndürür.
    """
    if not current_user.is_academician():
        return redirect(url_for('auth.home'))
    
    img = generate_attendance_chart(course_id)
    if img:
        return send_file(img, mimetype='image/png')
    else:
        flash('Grafik oluşturmak için yeterli veri yok.', 'warning')
        return redirect(url_for('auth.course_reports', course_id=course_id))