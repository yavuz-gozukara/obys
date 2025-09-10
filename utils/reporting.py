import base64
from io import BytesIO
import matplotlib.pyplot as plt
import numpy as np
from sqlalchemy import func
from models import DersOturum, YoklamaKayit, CourseStudent, Ders
from config import Config
from extensions import db

def calculate_absence_percentage(course_id, student_id):
    """
    Bir öğrencinin devamsızlık yüzdesini ve katıldığı hafta sayısını hesaplar.
    """
    # Sadece aktif oturumların olduğu haftaları bul
    active_weeks = db.session.query(DersOturum.OturumNumarasi).\
        filter(DersOturum.DersID == course_id, DersOturum.AktifMi == True).\
        distinct().all()
    active_week_numbers = [w[0] for w in active_weeks]
    total_weeks = len(active_week_numbers)

    # Öğrencinin katıldığı aktif haftaları bul
    attended_weeks = db.session.query(DersOturum.OturumNumarasi).\
        join(YoklamaKayit, DersOturum.OturumID == YoklamaKayit.OturumID).\
        filter(
            YoklamaKayit.OgrenciID == student_id,
            DersOturum.DersID == course_id,
            DersOturum.AktifMi == True
        ).distinct().all()
    attended_week_count = len(attended_weeks)

    # Eğer hiç oturum yoksa, devamsızlık %0 olsun (veya 0/0 ise 0 kabul et)
    absence_percentage = ((total_weeks - attended_week_count) / total_weeks * 100) if total_weeks > 0 else 0
    return absence_percentage, attended_week_count, total_weeks

def generate_weekly_attendance_chart(weekly_data):
    """
    Haftalık yoklama verisinden çubuk grafik üretir.
    """

    if not weekly_data:
        return None
        
    # Haftalık katılım için çubuk grafik
    fig, ax = plt.subplots(figsize=(10, 6))
    
    week_numbers = [w['week'] for w in weekly_data]
    present_counts = [w['present'] for w in weekly_data]
    absent_counts = [w['absent'] for w in weekly_data]
    
    # Çubuk grafik oluştur
    bar_width = 0.35
    index = np.arange(len(week_numbers))
    
    bar1 = ax.bar(index, present_counts, bar_width, label='Katılan', color='#4CAF50')
    bar2 = ax.bar(index + bar_width, absent_counts, bar_width, label='Katılmayan', color='#F44336')
    
    ax.set_xlabel('Hafta')
    ax.set_ylabel('Öğrenci Sayısı')
    ax.set_title('Haftalık Katılım Durumu')
    ax.set_xticks(index + bar_width / 2)
    ax.set_xticklabels(week_numbers)
    ax.legend()
    
    # Grafiği PNG olarak döndür
    img = BytesIO()
    plt.savefig(img, format='png', bbox_inches='tight')
    plt.close()
    img.seek(0)
    return img
def generate_overall_attendance_pie(overall_data):
    """
    Genel yoklama verisinden pasta grafik üretir.
    """
    
    # Genel katılım için pasta grafik
    fig, ax = plt.subplots(figsize=(8, 8))
    
    # NaN değerleri kontrol et ve düzelt
    present = overall_data['present'] if not np.isnan(overall_data['present']) else 0
    absent = overall_data['absent'] if not np.isnan(overall_data['absent']) else 0
    
    # Eğer her iki değer de 0 ise, varsayılan değerler ata
    if present == 0 and absent == 0:
        present = 1  # Minimum değer
        absent = 1   # Minimum değer
    
    labels = ['Katılan', 'Katılmayan']
    sizes = [present, absent]
    colors = ['#4CAF50', '#F44336']
    
    try:
        ax.pie(sizes, labels=labels, colors=colors, autopct='%1.1f%%', startangle=90, textprops={'fontsize': 12})
        ax.axis('equal')  # Daireyi daire olarak tut
        ax.set_title('Genel Katılım Oranı', fontsize=14)
    except ValueError as e:
        print(f"Pasta grafiği oluşturulurken hata: {str(e)}")
        return None
    
    # Grafiği PNG olarak döndür
    img = BytesIO()
    plt.savefig(img, format='png', bbox_inches='tight')
    plt.close()
    img.seek(0)
    return img

def generate_attendance_chart(course_id):
    course = Ders.query.get_or_404(course_id)
    course_students = CourseStudent.query.filter_by(DersID=course_id).all()
    
    if not course_students:
        return None
    
    # Öğrenci başına devamsızlık verilerini hesapla
    attendance_data = []
    for student_rel in course_students:
        student = student_rel.ogrenci_objesi
        absence_percentage, attended_weeks, total_weeks = calculate_absence_percentage(course_id, student.OgrenciID)
        status = "Güvenli" if absence_percentage < app.config['MAX_ABSENCE_PERCENTAGE'] else "Riskli"
        
        attendance_data.append({
            'student_no': student.OgrenciNo,
            'name': f"{student.user.Isim} {student.user.Soyisim}",
            'attended_weeks': attended_weeks,
            'total_weeks': total_weeks,
            'absence_percentage': absence_percentage,
            'status': status
        })
    
    # Verileri devamsızlık yüzdesine göre sırala
    attendance_data.sort(key=lambda x: x['absence_percentage'], reverse=True)
    
    # Grafik oluştur
    fig, ax = plt.subplots(figsize=(10, 8))
    
    # Sadece ilk 20 öğrenciyi göster (daha fazlası karışık olabilir)
    display_data = attendance_data[:20]
    
    student_names = [f"{d['student_no']} - {d['name']}" for d in display_data]
    absence_percentages = [d['absence_percentage'] for d in display_data]
    
    colors = ['red' if p >= app.config['MAX_ABSENCE_PERCENTAGE'] else 'green' for p in absence_percentages]
    y_pos = np.arange(len(display_data))
    
    bars = ax.barh(y_pos, absence_percentages, color=colors)
    ax.set_yticks(y_pos)
    ax.set_yticklabels(student_names, fontsize=9)
    ax.set_xlabel('Devamsızlık Yüzdesi (%)', fontsize=10)
    ax.set_title(f'{course.DersAdi} - Devamsızlık Durumu (14 Hafta Üzerinden)', fontsize=12)
    ax.axvline(x=app.config['MAX_ABSENCE_PERCENTAGE'], color='blue', linestyle='--', label='Maksimum Devamsızlık Sınırı')
    
    # Çubukların üzerine değerleri yaz
    for i, bar in enumerate(bars):
        width = bar.get_width()
        ax.text(width + 1, bar.get_y() + bar.get_height()/2, 
                f'{absence_percentages[i]:.1f}%', 
                ha='left', va='center', fontsize=8)
    
    plt.tight_layout()
    ax.legend()
    
    # Grafiği PNG olarak döndür
    img = BytesIO()
    plt.savefig(img, format='png', bbox_inches='tight', dpi=100)
    plt.close()
    img.seek(0)
    return img

def calculate_attendance(course_id):
    course = Ders.query.get_or_404(course_id)
    total_weeks = 14
    max_allowed_absences = 4
    
    # Oturum oluşturulmuş haftaları al
    weeks_with_sessions = get_weeks_with_sessions(course_id)
    completed_weeks = len(weeks_with_sessions)
    
    # Haftalık katılım verilerini topla (sadece oturum oluşturulmuş haftalar için)
    weekly_data = []
    for week in weeks_with_sessions:
        # Bu hafta için oturumlar
        sessions = DersOturum.query.filter_by(
            DersID=course_id,
            OturumNumarasi=week
        ).all()
        
        # Bu hafta için katılım kayıtları
        attendance_records = YoklamaKayit.query.filter(
            YoklamaKayit.OturumID.in_([s.OturumID for s in sessions])
        ).count()
        
        total_students = CourseStudent.query.filter_by(DersID=course_id).count()
        absent_count = total_students - attendance_records
        
        weekly_data.append({
            'week': week,
            'present': attendance_records,
            'absent': absent_count,
            'total_students': total_students,
            'attendance_rate': (attendance_records / total_students * 100) if total_students > 0 else 0
        })
    
    # Genel katılım istatistikleri (sadece oturum oluşturulmuş haftalar için)
    total_present = sum(w['present'] for w in weekly_data)
    total_absent = sum(w['absent'] for w in weekly_data)
    overall_attendance_rate = (total_present / (total_present + total_absent) * 100) if (total_present + total_absent) > 0 else 0
    
    # Öğrenci bazında devamsızlık durumu (sadece oturum oluşturulmuş haftalar için)
    student_attendance = []
    course_students = CourseStudent.query.filter_by(DersID=course_id).all()
    
    for student_rel in course_students:
        student = student_rel.ogrenci_objesi
        # Öğrencinin katıldığı haftaları bul (sadece oturum oluşturulmuş haftalar)
        attended_weeks = db.session.query(DersOturum.OturumNumarasi).\
            join(YoklamaKayit, DersOturum.OturumID == YoklamaKayit.OturumID).\
            filter(
                YoklamaKayit.OgrenciID == student.OgrenciID,
                DersOturum.DersID == course_id
            ).distinct().all()
        
        attended_week_count = len(attended_weeks)
        absence_count = completed_weeks - attended_week_count
        
        # Durumu belirle
        if completed_weeks == 0:
            status = "Henüz yoklama yapılmadı"
            status_class = "text-info"
        elif absence_count <= max_allowed_absences:
            status = "Geçiyor"
            status_class = "text-success"
        else:
            status = "Kalıyor"
            status_class = "text-danger"
        
        # Sisteme kayıt olmamış öğrenciler için ek kontrol
        user = student.user
        is_passive = not student.is_active_user or not user.Email or not user.SifreHash or user.SifreHash == ''
        student_attendance.append({
            'student_no': student.OgrenciNo,
            'name': f"{user.Isim} {user.Soyisim}",
            'attended_weeks': attended_week_count,
            'absence_count': absence_count,
            'status': status,
            'status_class': status_class,
            'active': 'Aktif' if not is_passive else 'Pasif'
        })
    
    # Sınıf listesi (tüm öğrenciler)
    class_list = []
    for student_rel in course_students:
        student = student_rel.ogrenci_objesi
        user = student.user
        # Sisteme kayıt olmamış öğrenciler için ek kontrol
        is_passive = not student.is_active_user or not user.Email or not user.SifreHash or user.SifreHash == ''
        class_list.append({
            'student_no': student.OgrenciNo,
            'name': f"{user.Isim} {user.Soyisim}",
            'email': user.Email or '-',
            'class': student.Sinif or '-',
            'program': student.BirimProgram or '-',
            'active': 'Aktif' if not is_passive else 'Pasif'
        })
    
    # Devamsızlıktan kalan öğrenciler
    failing_students = [s for s in student_attendance if s['status'] == "Kalıyor"]
    
    # Sınırda olan öğrenciler
    borderline_students = [s for s in student_attendance if s['absence_count'] == max_allowed_absences]
    
    return {
        'course': course,
        'weekly_data': weekly_data,
        'overall_attendance': {
            'present': total_present,
            'absent': total_absent,
            'rate': overall_attendance_rate
        },
        'student_attendance': student_attendance,
        'failing_students': failing_students,
        'borderline_students': borderline_students,
        'class_list': class_list,
        'total_weeks': total_weeks,
        'completed_weeks': completed_weeks,
        'max_allowed_absences': max_allowed_absences
    }

def get_weeks_with_sessions(course_id):
    """Verilen ders için oturum oluşturulmuş hafta numaralarını döndürür."""
    from models import DersOturum
    weeks = db.session.query(DersOturum.OturumNumarasi).filter_by(DersID=course_id).distinct().order_by(DersOturum.OturumNumarasi).all()
    return [w[0] for w in weeks]