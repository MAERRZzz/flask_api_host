from flask import jsonify, abort
import rsa
import time
import datetime
import base64
from app.controllers import StudentController, VisitController
from app.extensions import db_session
from app.models import Event, Class, Student


def get_lesson_start_time(current_time: float, decrypted_qr_time: int):
    today = datetime.datetime.fromtimestamp(current_time)
    pattern_date, pattern_timestamp = '%Y-%m-%d', '%Y-%m-%d %H:%M:%S'
    time_list = {
        '08:00': '09:30',
        '09:40': '11:10',
        '11:30': '13:00',
        '13:10': '14:40',
        '14:50': '16:20',
        '16:30': '18:00'
    }
    for start, end in time_list.items():
        start_timestamp = int(
            time.mktime(time.strptime(f"{today.strftime(pattern_date)} {start}:00", pattern_timestamp)))
        end_timestamp = int(
            time.mktime(time.strptime(f"{today.strftime(pattern_date)} {end}:00", pattern_timestamp)))
        if start_timestamp < decrypted_qr_time < end_timestamp:
            print(start)
            return start
    else:
        return False


def qr_validate(request):
    if not request or 'qr_data' not in request or 'audience' not in request:
        abort(400)

    data = request["qr_data"].split("|")
    audience = request["audience"]

    google_id = data[0]
    encrypted_qr_time = base64.b64decode(data[1])

    student = StudentController.get_student(student_google_id=google_id)

    private_key = rsa.PrivateKey.load_pkcs1(student.privateKey)
    decrypted_qr_time = int((rsa.decrypt(encrypted_qr_time, private_key)).decode())

    qr_weekday = time.strftime('%A', time.localtime(decrypted_qr_time))[:2].upper()
    print(qr_weekday)
    current_time = time.time()

    if not (lesson_start_time := get_lesson_start_time(current_time, decrypted_qr_time)):
        return jsonify({'status': 'failure'})

    event = db_session.query(Event, Class).filter(Event.summaryId == Class.id, Event.location.contains(audience),
                                                  Event.start.contains(lesson_start_time),
                                                  Event.recurrence[1].like(f'%BYDAY={qr_weekday}%')).all()

    print(len(list(event)))
    print(list(event)[0])
    # fisrt() для имитации того, что отмечаемся на единственной паре (по разделению на чис. и знам.)

    if (current_time - decrypted_qr_time) < 35:
        visit_time = int(current_time)
        in_visit_list = VisitController.get_visit(student.id)
        if in_visit_list:
            in_visit_list = in_visit_list[0] if len(in_visit_list) == 1 else in_visit_list[-1]
            if (current_time - in_visit_list.visit_time) > 30:
                VisitController.create_visit(student.id, visit_time, event[0].id)
                status = "success"
            else:
                status = "neutral"

        else:
            VisitController.create_visit(student.id, visit_time, event[0].id)
            status = "success"
    else:
        status = "failure"

    return jsonify({'status': status})
