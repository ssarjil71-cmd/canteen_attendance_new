import base64
import io
import os
import uuid
from datetime import datetime, date
from math import radians, cos, sin, asin, sqrt
import json

import boto3
import qrcode
from flask import Blueprint, request, jsonify, current_app, render_template
from botocore.exceptions import ClientError, NoCredentialsError, PartialCredentialsError
from PIL import Image

AWS_REKOGNITION_AVAILABLE = True

from database.db_connection import get_db_connection
from module_access import has_module, has_submodule

attendance = Blueprint("attendance", __name__, url_prefix="/attendance")

# Face verification configuration (AWS Rekognition)
FACE_VERIFICATION_CONFIG = {
    'method': 'aws_rekognition',
    'similarity_threshold': 90.0,
    'min_face_confidence': 85.0,
    'description': 'AWS Rekognition based face detection and comparison'
}


def _attendance_module_disabled_response(company_id):
    if has_module(company_id, "attendance"):
        return None
    return jsonify({
        'success': False,
        'message': 'Attendance module is disabled for this company'
    }), 403


def _attendance_has_meal_status(connection):
    cursor = connection.cursor()
    cursor.execute("SHOW COLUMNS FROM attendance LIKE 'meal_status'")
    has_column = cursor.fetchone() is not None
    cursor.close()
    return has_column


def _ensure_attendance_meal_status(connection):
    if _attendance_has_meal_status(connection):
        return
    cursor = connection.cursor()
    cursor.execute("ALTER TABLE attendance ADD COLUMN meal_status ENUM('YES', 'NO') DEFAULT 'NO' AFTER check_out_time")
    cursor.close()
    connection.commit()


def _attendance_has_meal_taken(connection):
    cursor = connection.cursor()
    cursor.execute("SHOW COLUMNS FROM attendance LIKE 'meal_taken'")
    has_column = cursor.fetchone() is not None
    cursor.close()
    return has_column


def _ensure_attendance_meal_taken(connection):
    if _attendance_has_meal_taken(connection):
        return
    cursor = connection.cursor()
    cursor.execute("ALTER TABLE attendance ADD COLUMN meal_taken ENUM('YES', 'NO') DEFAULT 'NO' AFTER meal_status")
    cursor.close()
    connection.commit()


def _table_exists(connection, table_name):
    cursor = connection.cursor()
    cursor.execute("SHOW TABLES LIKE %s", (table_name,))
    exists = cursor.fetchone() is not None
    cursor.close()
    return exists


def _ensure_meal_qr_token_table(connection):
    if _table_exists(connection, "meal_qr_tokens"):
        return

    cursor = connection.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS meal_qr_tokens (
            id INT AUTO_INCREMENT PRIMARY KEY,
            attendance_id INT NOT NULL,
            employee_id VARCHAR(100) NOT NULL,
            company_id INT NOT NULL,
            qr_date DATE NOT NULL,
            token VARCHAR(128) NOT NULL,
            payload TEXT NOT NULL,
            issued_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at DATETIME NOT NULL,
            consumed_at DATETIME NULL,
            is_active TINYINT(1) DEFAULT 1,
            UNIQUE KEY uk_meal_qr_attendance (attendance_id),
            UNIQUE KEY uk_meal_qr_token (token),
            INDEX idx_meal_qr_company_date (company_id, qr_date),
            INDEX idx_meal_qr_employee_date (employee_id, qr_date),
            CONSTRAINT fk_meal_qr_attendance FOREIGN KEY (attendance_id)
              REFERENCES attendance(id) ON DELETE CASCADE,
            CONSTRAINT fk_meal_qr_company FOREIGN KEY (company_id)
              REFERENCES companies(id) ON DELETE CASCADE
        )
        """
    )
    cursor.close()
    connection.commit()


def _build_qr_base64(payload_text):
    buffer = io.BytesIO()
    qr = qrcode.QRCode(version=1, box_size=8, border=3)
    qr.add_data(payload_text)
    qr.make(fit=True)
    image = qr.make_image(fill_color="black", back_color="white")
    image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def _deactivate_today_qr_tokens(cursor, employee_id, company_id, response_date):
    cursor.execute(
        """
        UPDATE meal_qr_tokens
        SET is_active = 0
        WHERE employee_id = %s
          AND company_id = %s
          AND qr_date = %s
          AND consumed_at IS NULL
        """,
        (employee_id, company_id, response_date),
    )


def _get_or_create_today_meal_qr(cursor, employee_id, company_id, response_date):
    cursor.execute(
        """
        SELECT id, check_in_time
        FROM attendance
        WHERE employee_id = %s
          AND company_id = %s
          AND DATE(COALESCE(check_in_time, date)) = %s
        ORDER BY check_in_time DESC, id DESC
        LIMIT 1
        """,
        (employee_id, company_id, response_date),
    )
    attendance_row = cursor.fetchone()
    if not attendance_row:
        return None

    attendance_id = attendance_row['id']
    cursor.execute(
        """
        SELECT token, payload
        FROM meal_qr_tokens
        WHERE attendance_id = %s
          AND qr_date = %s
          AND is_active = 1
        LIMIT 1
        """,
        (attendance_id, response_date),
    )
    existing_qr = cursor.fetchone()

    if existing_qr:
        return {
            'token': existing_qr['token'],
            'payload': existing_qr['payload'],
            'qr_image_b64': _build_qr_base64(existing_qr['payload']),
            'attendance_id': attendance_id,
        }

    issued_at = datetime.now()
    token = uuid.uuid4().hex
    payload_obj = {
        'employee_id': employee_id,
        'company_id': int(company_id),
        'attendance_id': attendance_id,
        'date_time': issued_at.strftime('%Y-%m-%d %H:%M:%S'),
        'token': token,
    }
    payload_text = json.dumps(payload_obj, separators=(',', ':'))
    expires_at = datetime.combine(response_date, datetime.max.time()).replace(microsecond=0)

    cursor.execute(
        """
        INSERT INTO meal_qr_tokens (
            attendance_id, employee_id, company_id, qr_date, token, payload, expires_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s)
        """,
        (attendance_id, employee_id, company_id, response_date, token, payload_text, expires_at),
    )

    return {
        'token': token,
        'payload': payload_text,
        'qr_image_b64': _build_qr_base64(payload_text),
        'attendance_id': attendance_id,
    }


def _rekognition_client():
    return boto3.client(
        "rekognition",
        region_name=os.getenv("AWS_REGION", "us-east-1")
    )


def decode_base64_image_bytes(face_image_data):
    """Decode data URL/base64 string into bytes suitable for Rekognition."""
    if not face_image_data:
        return None

    if ',' in face_image_data:
        face_image_data = face_image_data.split(',', 1)[1]

    try:
        return base64.b64decode(face_image_data)
    except Exception:
        return None


def detect_faces_with_rekognition(image_bytes):
    client = _rekognition_client()
    response = client.detect_faces(
        Image={"Bytes": image_bytes},
        Attributes=["DEFAULT"]
    )
    return response.get("FaceDetails", [])


def _pixel_box_from_rekognition_box(rekognition_box, image_width, image_height):
    left = int(rekognition_box.get("Left", 0.0) * image_width)
    top = int(rekognition_box.get("Top", 0.0) * image_height)
    width = int(rekognition_box.get("Width", 0.0) * image_width)
    height = int(rekognition_box.get("Height", 0.0) * image_height)
    return {
        "left": left,
        "top": top,
        "right": left + width,
        "bottom": top + height,
        "width": width,
        "height": height,
    }


def verify_face_images(stored_image_path, captured_image_bytes, similarity_threshold=None):
    """Compare stored image with captured image using AWS Rekognition."""
    if similarity_threshold is None:
        similarity_threshold = FACE_VERIFICATION_CONFIG['similarity_threshold']

    if not os.path.exists(stored_image_path):
        return {
            'verified': False,
            'confidence': 0.0,
            'similarity': 0.0,
            'threshold': similarity_threshold,
            'error': 'Stored image file not found'
        }

    try:
        with open(stored_image_path, "rb") as source_file:
            source_bytes = source_file.read()

        client = _rekognition_client()
        response = client.compare_faces(
            SourceImage={"Bytes": source_bytes},
            TargetImage={"Bytes": captured_image_bytes},
            SimilarityThreshold=float(similarity_threshold)
        )
        matches = response.get("FaceMatches", [])

        if matches:
            best = max(matches, key=lambda item: item.get("Similarity", 0.0))
            similarity = float(best.get("Similarity", 0.0))
            confidence = float(best.get("Face", {}).get("Confidence", 0.0))
            return {
                'verified': True,
                'confidence': round(confidence, 1),
                'similarity': round(similarity, 2),
                'threshold': similarity_threshold
            }

        return {
            'verified': False,
            'confidence': 0.0,
            'similarity': 0.0,
            'threshold': similarity_threshold,
            'error': 'Face does not match stored employee image'
        }

    except Exception as exc:
        current_app.logger.error(f"AWS face verification error: {exc}")
        return {
            'verified': False,
            'confidence': 0.0,
            'similarity': 0.0,
            'threshold': similarity_threshold,
            'error': str(exc)
        }


def identify_employee_by_face(company_id, captured_image_bytes, similarity_threshold=None):
    """Find the best matching employee in a company using AWS Rekognition."""
    if similarity_threshold is None:
        similarity_threshold = FACE_VERIFICATION_CONFIG['similarity_threshold']

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    cursor.execute(
        """
        SELECT id, emp_id, name, image_path, company_id
        FROM employees
        WHERE company_id = %s
          AND image_path IS NOT NULL
          AND TRIM(image_path) <> ''
        """,
        (company_id,),
    )
    employees = cursor.fetchall()
    cursor.close()
    connection.close()

    best_match = None
    for employee in employees:
        stored_image_path = os.path.join(current_app.root_path, 'static', employee['image_path'])
        if not os.path.exists(stored_image_path):
            continue

        result = verify_face_images(stored_image_path, captured_image_bytes, similarity_threshold)
        if not result.get('verified'):
            continue

        similarity = float(result.get('similarity', 0.0))
        confidence = float(result.get('confidence', 0.0))
        if not best_match or similarity > best_match['similarity']:
            best_match = {
                'employee_id': employee['emp_id'],
                'employee_name': employee['name'],
                'similarity': similarity,
                'confidence': confidence,
            }

    return best_match


@attendance.route("/auto-mark", methods=["POST"])
def auto_mark_attendance():
    """Fully automated attendance: location + face match + mark attendance."""
    try:
        data = request.get_json() or {}
        company_id = data.get('company_id')
        latitude = data.get('latitude')
        longitude = data.get('longitude')
        face_image_data = data.get('face_image_data')

        if not all([company_id, latitude, longitude, face_image_data]):
            return jsonify({
                'success': False,
                'message': 'Location and face image are required'
            }), 400

        module_check = _attendance_module_disabled_response(company_id)
        if module_check:
            return module_check

        if not AWS_REKOGNITION_AVAILABLE:
            return jsonify({
                'success': False,
                'message': 'AWS Rekognition is not available. Please contact administrator.'
            }), 500

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            "SELECT id, company_name, latitude, longitude, radius FROM companies WHERE id = %s",
            (company_id,)
        )
        company = cursor.fetchone()

        if not company:
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Company not found'
            }), 404

        distance_m = 0
        if company['latitude'] and company['longitude']:
            distance_m = calculate_distance(
                float(latitude),
                float(longitude),
                float(company['latitude']),
                float(company['longitude'])
            )
            allowed_radius = company['radius'] or 100
            if distance_m > allowed_radius:
                cursor.close()
                connection.close()
                return jsonify({
                    'success': False,
                    'message': 'You are not in the allowed location'
                }), 403

        captured_bytes = decode_base64_image_bytes(face_image_data)
        if not captured_bytes:
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Face not recognized'
            }), 400

        faces = detect_faces_with_rekognition(captured_bytes)
        if len(faces) != 1:
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Face not recognized'
            }), 400

        threshold = FACE_VERIFICATION_CONFIG['similarity_threshold']
        identified = identify_employee_by_face(company_id, captured_bytes, threshold)
        if not identified:
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Face not recognized'
            }), 404

        employee_id = identified['employee_id']
        employee_name = identified['employee_name']
        similarity = identified['similarity']
        confidence = identified['confidence']

        today = date.today()
        # TESTING MODE: Duplicate attendance restriction is temporarily disabled.
        # Keep this original production logic for future re-enable.
        # cursor.execute(
        #     "SELECT id, check_in_time FROM attendance WHERE employee_id = %s AND company_id = %s AND date = %s",
        #     (employee_id, company_id, today)
        # )
        # existing_attendance = cursor.fetchone()
        # if existing_attendance:
        #     cursor.close()
        #     connection.close()
        #     return jsonify({
        #         'success': False,
        #         'already_marked': True,
        #         'message': f'Attendance already marked today at {existing_attendance["check_in_time"].strftime("%H:%M:%S")}',
        #         'employee_name': employee_name
        #     })

        attendance_image_path = None
        _ensure_attendance_meal_status(connection)
        try:
            unique_filename = f"attendance_{employee_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
            uploads_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'faces')
            os.makedirs(uploads_dir, exist_ok=True)
            image_file_path = os.path.join(uploads_dir, unique_filename)
            with open(image_file_path, 'wb') as image_file:
                image_file.write(captured_bytes)
            attendance_image_path = f"faces/{unique_filename}"
        except Exception as img_error:
            current_app.logger.error(f"Error saving attendance image: {img_error}")

        cursor.execute(
            """
            INSERT INTO attendance (
                employee_id, company_id, date, check_in_time, meal_status, face_image,
                latitude, longitude, location_verified, face_verified, status
            ) VALUES (%s, %s, %s, NOW(), %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                employee_id,
                company_id,
                today,
                'NO',
                attendance_image_path,
                latitude,
                longitude,
                True,
                True,
                'present',
            ),
        )

        connection.commit()
        cursor.close()
        connection.close()

        return jsonify({
            'success': True,
            'message': 'Attendance marked successfully',
            'employee_id': employee_id,
            'employee_name': employee_name,
            'company_name': company['company_name'],
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'verification_details': {
                'location_verified': True,
                'distance': int(distance_m) if distance_m else 0,
                'face_verified': True,
                'similarity': round(similarity, 2),
                'confidence': round(confidence, 1),
            },
        })

    except (NoCredentialsError, PartialCredentialsError):
        current_app.logger.error("AWS credentials are missing for Rekognition")
        return jsonify({
            'success': False,
            'message': 'AWS credentials are not configured for face verification.'
        }), 500
    except ClientError as exc:
        current_app.logger.error(f"AWS Rekognition error in auto attendance: {exc}")
        return jsonify({
            'success': False,
            'message': 'AWS Rekognition error while verifying face.'
        }), 500
    except Exception as exc:
        current_app.logger.error(f"Auto attendance error: {exc}")
        return jsonify({
            'success': False,
            'message': 'Failed to mark attendance due to server error'
        }), 500


@attendance.route("/meal-response", methods=["POST"])
def meal_response():
    """Save meal participation response and return today's menu when employee is coming."""
    try:
        data = request.get_json() or {}
        employee_id = data.get('employee_id')
        company_id = data.get('company_id')
        status = (data.get('status') or '').strip()
        meal_status = 'YES' if status == 'Coming' else 'NO'

        if not employee_id or not company_id or status not in {"Coming", "Not Coming"}:
            return jsonify({
                'success': False,
                'message': 'Invalid meal response payload'
            }), 400

        module_check = _attendance_module_disabled_response(company_id)
        if module_check:
            return module_check

        qr_generation_enabled = has_submodule(company_id, "attendance", "qr_generation")

        response_date = date.today()
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        _ensure_meal_qr_token_table(connection)

        cursor.execute("SELECT id FROM canteen WHERE company_id = %s", (company_id,))
        canteen = cursor.fetchone()
        if not canteen:
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Canteen is not configured for this company'
            }), 404

        canteen_id = canteen['id']
        _ensure_attendance_meal_status(connection)
        cursor.execute(
            """
            UPDATE attendance
            SET meal_status = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE employee_id = %s
              AND company_id = %s
              AND DATE(check_in_time) = CURDATE()
              AND check_in_time IS NOT NULL
            """,
            (meal_status, employee_id, company_id),
        )

        if cursor.rowcount == 0:
            current_app.logger.warning(
                "Meal response update matched no attendance row for employee_id=%s company_id=%s date=%s",
                employee_id,
                company_id,
                response_date,
            )

        menu_payload = None
        qr_payload = None
        if status == "Coming":
            cursor.execute(
                """
                SELECT morning_item, afternoon_item, evening_item
                FROM canteen_menus
                WHERE canteen_id = %s AND menu_date = %s
                """,
                (canteen_id, response_date),
            )
            today_menu = cursor.fetchone()
            if today_menu:
                menu_payload = {
                    'morning': today_menu['morning_item'],
                    'afternoon': today_menu['afternoon_item'],
                    'evening': today_menu['evening_item'],
                }

            if qr_generation_enabled:
                qr_payload = _get_or_create_today_meal_qr(cursor, employee_id, company_id, response_date)
                if not qr_payload:
                    cursor.close()
                    connection.close()
                    return jsonify({
                        'success': False,
                        'message': 'Attendance record not found for today. Please mark attendance first.'
                    }), 400
            else:
                _deactivate_today_qr_tokens(cursor, employee_id, company_id, response_date)
        else:
            _deactivate_today_qr_tokens(cursor, employee_id, company_id, response_date)

        connection.commit()
        current_app.logger.info(
            "Meal response saved for employee_id=%s company_id=%s attendance_status=%s",
            employee_id,
            company_id,
            meal_status,
        )
        cursor.close()
        connection.close()

        if status == "Not Coming":
            return jsonify({
                'success': True,
                'status': status,
                'meal_selected': 'NO',
                'show_qr': False,
                'message': 'Meal selection saved'
            })

        return jsonify({
            'success': True,
            'status': status,
            'meal_selected': 'YES',
            'show_qr': bool(qr_generation_enabled and qr_payload),
            'qr_image_b64': qr_payload['qr_image_b64'] if qr_payload else None,
            'qr_token': qr_payload['token'] if qr_payload else None,
            'qr_data': qr_payload['payload'] if qr_payload else None,
            'menu': menu_payload,
            'message': 'Meal response saved'
        })

    except Exception as exc:
        current_app.logger.error(f"Meal response error: {exc}")
        return jsonify({
            'success': False,
            'message': 'Failed to save meal response'
        }), 500


def calculate_distance(lat1, lon1, lat2, lon2):
    """
    Calculate the great circle distance between two points 
    on the earth (specified in decimal degrees)
    Returns distance in meters
    """
    # Convert decimal degrees to radians
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    
    # Haversine formula
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    
    # Radius of earth in meters
    r = 6371000
    
    return c * r


@attendance.route("/config/threshold", methods=["GET", "POST"])
def face_threshold_config():
    """Configure face verification threshold (admin only)"""
    if request.method == "GET":
        return jsonify({
            'current_threshold': FACE_VERIFICATION_CONFIG['similarity_threshold'],
            'model': FACE_VERIFICATION_CONFIG['method'],
            'recommended_range': '80 - 99',
            'description': 'Higher values = stricter AWS Rekognition matching'
        })
    
    elif request.method == "POST":
        try:
            data = request.get_json()
            new_threshold = float(data.get('threshold', FACE_VERIFICATION_CONFIG['similarity_threshold']))
            
            # Validate threshold range
            if not (50 <= new_threshold <= 99.9):
                return jsonify({
                    'success': False,
                    'message': 'Threshold must be between 50 and 99.9'
                }), 400
            
            # Update configuration
            FACE_VERIFICATION_CONFIG['similarity_threshold'] = new_threshold
            
            return jsonify({
                'success': True,
                'message': f'Face verification threshold updated to {new_threshold}',
                'new_threshold': new_threshold
            })
            
        except (ValueError, TypeError):
            return jsonify({
                'success': False,
                'message': 'Invalid threshold value. Must be a number between 50 and 99.9'
            }), 400
        except Exception as e:
            return jsonify({
                'success': False,
                'message': f'Error updating threshold: {str(e)}'
            }), 500


@attendance.route("/portal/<int:company_id>")
def attendance_portal(company_id):
    """Public attendance portal for employees"""
    if not has_module(company_id, "attendance"):
        return render_template("attendance/error.html", message="Attendance module is disabled for this company."), 403

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    
    # Get company information
    cursor.execute("SELECT * FROM companies WHERE id = %s", (company_id,))
    company = cursor.fetchone()
    
    cursor.close()
    connection.close()
    
    if not company:
        return "Company not found", 404
    
    return render_template("attendance/portal.html", company=company, company_id=company_id)


@attendance.route("/employee/attendance")
def employee_attendance():
    """Employee attendance page accessible via QR code - auto-detects company"""
    # Get company_id from query parameter or default to first company
    company_id = request.args.get('company_id')
    
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    
    if company_id:
        # Get specific company
        cursor.execute("SELECT * FROM companies WHERE id = %s", (company_id,))
        company = cursor.fetchone()
        if company and not has_module(company_id, "attendance"):
            cursor.close()
            connection.close()
            return render_template("attendance/error.html", message="Attendance module is disabled for this company."), 403
    else:
        # Get first available company (for QR codes without company_id)
        cursor.execute("SELECT * FROM companies ORDER BY id")
        companies = cursor.fetchall()
        company = next((row for row in companies if has_module(row['id'], "attendance")), None)
        if company:
            company_id = company['id']
    
    cursor.close()
    connection.close()
    
    if not company:
        return "No company found with attendance enabled", 404
    
    return render_template("attendance/portal.html", company=company, company_id=company_id)


@attendance.route("/verify-location", methods=["POST"])
def verify_location():
    """Verify if employee is within company location radius"""
    try:
        data = request.get_json()
        company_id = data.get('company_id')
        employee_lat = float(data.get('latitude'))
        employee_lon = float(data.get('longitude'))

        module_check = _attendance_module_disabled_response(company_id)
        if module_check:
            return module_check
        
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        
        # Get company location settings
        cursor.execute(
            "SELECT latitude, longitude, radius, company_name FROM companies WHERE id = %s", 
            (company_id,)
        )
        company = cursor.fetchone()
        
        cursor.close()
        connection.close()
        
        if not company:
            return jsonify({
                'success': False,
                'message': 'Company not found'
            }), 404
        
        # Check if company has location configured
        if not company['latitude'] or not company['longitude']:
            return jsonify({
                'success': True,
                'message': 'Location verification disabled - No company location set'
            })
        
        # Calculate distance between employee and company location
        distance = calculate_distance(
            employee_lat, employee_lon,
            float(company['latitude']), float(company['longitude'])
        )
        
        # Check if within radius (default 100 meters if not set)
        allowed_radius = company['radius'] or 100
        
        if distance <= allowed_radius:
            return jsonify({
                'success': True,
                'message': f'Location verified - Within {int(distance)}m of {company["company_name"]}',
                'distance': int(distance),
                'allowed_radius': allowed_radius
            })
        else:
            return jsonify({
                'success': False,
                'message': 'You are not in the allowed location',
                'distance': int(distance),
                'allowed_radius': allowed_radius
            })
            
    except Exception as e:
        current_app.logger.error(f"Location verification error: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'Location verification failed due to server error'
        }), 500


@attendance.route("/detect-face", methods=["POST"])
def detect_face():
    """Realtime face detection endpoint used by live camera preview."""
    try:
        if not AWS_REKOGNITION_AVAILABLE:
            return jsonify({
                'success': False,
                'message': 'AWS Rekognition is not available. Please contact administrator.'
            }), 500

        data = request.get_json() or {}
        face_image_data = data.get('face_image_data')

        if not face_image_data:
            return jsonify({
                'success': False,
                'face_detected': False,
                'message': 'Face image is required'
            }), 400

        image_bytes = decode_base64_image_bytes(face_image_data)
        if image_bytes is None:
            return jsonify({
                'success': False,
                'face_detected': False,
                'message': 'Could not decode image'
            }), 400

        image = Image.open(io.BytesIO(image_bytes))
        image_width, image_height = image.size
        faces = detect_faces_with_rekognition(image_bytes)

        if len(faces) == 0:
            return jsonify({
                'success': True,
                'face_detected': False,
                'can_capture': False,
                'message': 'Face not detected. Please align your face properly.'
            })

        if len(faces) > 1:
            return jsonify({
                'success': True,
                'face_detected': False,
                'can_capture': False,
                'message': 'Multiple faces detected. Ensure only one face is visible.'
            })

        top_face = faces[0]
        bounding_box = _pixel_box_from_rekognition_box(
            top_face.get('BoundingBox', {}),
            image_width,
            image_height
        )
        face_confidence = float(top_face.get('Confidence', 0.0))
        can_capture = (
            bounding_box['width'] > 40
            and bounding_box['height'] > 40
            and face_confidence >= FACE_VERIFICATION_CONFIG['min_face_confidence']
        )

        return jsonify({
            'success': True,
            'face_detected': True,
            'can_capture': can_capture,
            'bounding_box': {
                'top': int(bounding_box['top']),
                'right': int(bounding_box['right']),
                'bottom': int(bounding_box['bottom']),
                'left': int(bounding_box['left'])
            },
            'confidence': round(face_confidence, 1),
            'message': 'Face detected. You can capture now.' if can_capture else 'Face detected. Move closer and improve framing for capture.'
        })

    except (NoCredentialsError, PartialCredentialsError):
        current_app.logger.error("AWS credentials are missing for Rekognition")
        return jsonify({
            'success': False,
            'face_detected': False,
            'can_capture': False,
            'message': 'AWS credentials are not configured for face verification.'
        }), 500
    except ClientError as exc:
        current_app.logger.error(f"AWS Rekognition detect_faces error: {exc}")
        return jsonify({
            'success': False,
            'face_detected': False,
            'can_capture': False,
            'message': 'AWS Rekognition error while detecting face.'
        }), 500

    except Exception as exc:
        current_app.logger.error(f"Face detection error: {exc}")
        return jsonify({
            'success': False,
            'face_detected': False,
            'can_capture': False,
            'message': 'Failed to detect face due to server error'
        }), 500


@attendance.route("/verify-face", methods=["POST"])
def verify_face():
    """Verify employee face against stored face image using AWS Rekognition."""
    try:
        if not AWS_REKOGNITION_AVAILABLE:
            return jsonify({
                'success': False,
                'message': 'AWS Rekognition is not available. Please contact administrator.'
            }), 500
        
        data = request.get_json()
        employee_id = data.get('employee_id')
        face_image_data = data.get('face_image_data')
        
        if not employee_id or not face_image_data:
            return jsonify({
                'success': False,
                'message': 'Employee ID and face image are required'
            })
        
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        
        # Get employee's stored image path
        cursor.execute(
            "SELECT id, name, image_path, company_id FROM employees WHERE emp_id = %s", 
            (employee_id,)
        )
        employee = cursor.fetchone()
        
        cursor.close()
        connection.close()
        
        if not employee:
            return jsonify({
                'success': False,
                'message': 'Employee not found. Please check your Employee ID.'
            })

        if not has_module(employee.get('company_id'), "attendance"):
            return jsonify({
                'success': False,
                'message': 'Attendance module is disabled for this company'
            }), 403
        
        if not employee['image_path']:
            return jsonify({
                'success': False,
                'message': f'No face image registered for {employee["name"]}. Please contact HR to register your face.'
            })
        captured_bytes = decode_base64_image_bytes(face_image_data)
        if not captured_bytes:
            return jsonify({
                'success': False,
                'message': 'Failed to process face image. Please try again.'
            })

        stored_image_path = os.path.join(current_app.root_path, 'static', employee['image_path'])
        if not os.path.exists(stored_image_path):
            return jsonify({
                'success': False,
                'message': f'Stored face image not found for {employee["name"]}. Please contact HR.'
            })

        threshold = FACE_VERIFICATION_CONFIG['similarity_threshold']
        result = verify_face_images(stored_image_path, captured_bytes, threshold)

        if result.get('verified'):
            similarity = float(result.get('similarity', 0.0))
            confidence = float(result.get('confidence', similarity))
            return jsonify({
                'success': True,
                'message': f'Face verified successfully for {employee["name"]} (Similarity: {similarity:.1f}%)',
                'confidence': round(confidence, 1),
                'similarity': round(similarity, 2),
                'threshold': threshold,
                'employee_name': employee['name']
            })

        return jsonify({
            'success': False,
            'message': f'Face verification failed. Face does not match {employee["name"]}.',
            'similarity': round(float(result.get('similarity', 0.0)), 2),
            'threshold': threshold,
            'employee_name': employee['name']
        })

    except (NoCredentialsError, PartialCredentialsError):
        current_app.logger.error("AWS credentials are missing for Rekognition")
        return jsonify({
            'success': False,
            'message': 'AWS credentials are not configured for face verification.'
        }), 500
    except ClientError as exc:
        current_app.logger.error(f"AWS Rekognition compare_faces error: {exc}")
        return jsonify({
            'success': False,
            'message': 'AWS Rekognition error while verifying face.'
        }), 500
            
    except Exception as e:
        current_app.logger.error(f"Face verification error: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'Face verification failed due to server error'
        }), 500


@attendance.route("/mark", methods=["POST"])
def mark_attendance():
    """Legacy endpoint blocked to enforce touchless auto attendance flow."""
    return jsonify({
        'success': False,
        'message': 'Manual employee selection is not allowed. Use automated attendance flow.'
    }), 403

    """Mark employee attendance with face and location verification"""
    try:
        data = request.get_json()
        employee_id = data.get('employee_id')
        company_id = data.get('company_id')
        latitude = data.get('latitude')
        longitude = data.get('longitude')
        face_image_data = data.get('face_image_data')
        
        if not all([employee_id, company_id, latitude, longitude, face_image_data]):
            return jsonify({
                'success': False,
                'message': 'All fields are required: employee_id, company_id, location, and face_image'
            }), 400
        
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        
        # Verify employee exists and belongs to company
        cursor.execute(
            """
            SELECT e.id, e.name, e.emp_id, e.image_path, c.company_name, c.latitude as company_lat, 
                   c.longitude as company_lon, c.radius
            FROM employees e 
            JOIN companies c ON e.company_id = c.id 
            WHERE e.emp_id = %s AND e.company_id = %s
            """, 
            (employee_id, company_id)
        )
        employee = cursor.fetchone()
        
        if not employee:
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Employee not found or does not belong to this company'
            }), 404
        
        # Check if attendance already marked today
        today = date.today()
        cursor.execute(
            "SELECT id, check_in_time FROM attendance WHERE employee_id = %s AND company_id = %s AND date = %s", 
            (employee_id, company_id, today)
        )
        existing_attendance = cursor.fetchone()
        
        if existing_attendance:
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': f'Attendance already marked for {employee["name"]} today at {existing_attendance["check_in_time"].strftime("%H:%M:%S")}',
                'already_marked': True,
                'check_in_time': existing_attendance["check_in_time"].strftime("%H:%M:%S")
            })
        
        # Verify location (if company location is set)
        location_verified = True
        distance_m = 0
        
        if employee['company_lat'] and employee['company_lon']:
            distance_m = calculate_distance(
                float(latitude), float(longitude),
                float(employee['company_lat']), float(employee['company_lon'])
            )
            allowed_radius = employee['radius'] or 100
            location_verified = distance_m <= allowed_radius
            
            if not location_verified:
                cursor.close()
                connection.close()
                return jsonify({
                    'success': False,
                    'message': f'Location verification failed. You are {int(distance_m)}m away (max allowed: {allowed_radius}m)'
                })
        
        # Verify face (MANDATORY - no skipping allowed)
        face_verified = False
        confidence = 0.0
        similarity = 0.0
        
        if not AWS_REKOGNITION_AVAILABLE:
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'AWS Rekognition is not available. Please contact administrator.'
            }), 500
        
        if not employee['image_path']:
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': f'No face image registered for {employee["name"]}. Please contact HR to register your face.'
            })
        
        try:
            captured_bytes = decode_base64_image_bytes(face_image_data)
            if not captured_bytes:
                cursor.close()
                connection.close()
                return jsonify({
                    'success': False,
                    'message': 'Failed to process face image.'
                })

            stored_image_path = os.path.join(current_app.root_path, 'static', employee['image_path'])
            if not os.path.exists(stored_image_path):
                cursor.close()
                connection.close()
                return jsonify({
                    'success': False,
                    'message': f'Stored face image not found for {employee["name"]}. Please contact HR.'
                })

            threshold = FACE_VERIFICATION_CONFIG['similarity_threshold']
            result = verify_face_images(stored_image_path, captured_bytes, threshold)
            face_verified = bool(result.get('verified'))
            similarity = float(result.get('similarity', 0.0))
            confidence = float(result.get('confidence', similarity))

            if not face_verified:
                cursor.close()
                connection.close()
                return jsonify({
                    'success': False,
                    'message': f'Face verification failed. Face does not match {employee["name"]}.',
                    'similarity': round(similarity, 2),
                    'threshold': threshold
                })

        except (NoCredentialsError, PartialCredentialsError):
            current_app.logger.error("AWS credentials are missing for Rekognition")
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'AWS credentials are not configured for face verification.'
            }), 500
        except ClientError as exc:
            current_app.logger.error(f"AWS Rekognition compare_faces error during attendance: {exc}")
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'AWS Rekognition error while verifying face.'
            }), 500
        except Exception as face_error:
            current_app.logger.error(f"Face verification error during attendance: {str(face_error)}")
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Face verification failed due to processing error'
            })
        
        # Save attendance image
        attendance_image_path = None
        if face_image_data:
            try:
                unique_filename = f"attendance_{employee_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
                uploads_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'faces')
                os.makedirs(uploads_dir, exist_ok=True)
                
                image_file_path = os.path.join(uploads_dir, unique_filename)
                with open(image_file_path, 'wb') as f:
                    f.write(base64.b64decode(face_image_data.split(',')[1] if ',' in face_image_data else face_image_data))
                
                attendance_image_path = f"faces/{unique_filename}"
            except Exception as img_error:
                current_app.logger.error(f"Error saving attendance image: {str(img_error)}")
        
        # Mark attendance in database
        _ensure_attendance_meal_status(connection)
        cursor.execute(
            """
            INSERT INTO attendance (
                employee_id, company_id, date, check_in_time, meal_status, face_image, 
                latitude, longitude, location_verified, face_verified, status
            ) VALUES (%s, %s, %s, NOW(), %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                employee_id, company_id, today, 'NO', attendance_image_path,
                latitude, longitude, location_verified, face_verified, 'present'
            )
        )
        
        connection.commit()
        cursor.close()
        connection.close()
        
        # Prepare success message
        verification_details = []
        if location_verified:
            verification_details.append(f"Location verified ({int(distance_m)}m)")
        
        # Face verification is now mandatory
        if face_verified and confidence > 0:
            verification_details.append(f"Face verified ({similarity:.1f}% similarity)")
        
        verification_text = " • ".join(verification_details) if verification_details else "Verification completed"
        
        current_app.logger.info(f"Attendance marked successfully for {employee_id} at company {company_id}")
        
        return jsonify({
            'success': True,
            'message': f'Attendance marked successfully for {employee["name"]}!\n{verification_text}',
            'employee_name': employee['name'],
            'company_name': employee['company_name'],
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'verification_details': {
                'location_verified': bool(location_verified),
                'face_verified': bool(face_verified),
                'confidence': round(float(confidence), 1) if confidence > 0 else None,
                'similarity': round(float(similarity), 2) if similarity > 0 else None,
                'distance': int(distance_m) if distance_m > 0 else None
            }
        })
        
    except Exception as e:
        current_app.logger.error(f"Attendance marking error: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'Failed to mark attendance due to server error'
        }), 500


@attendance.route("/status/<employee_id>")
def attendance_status(employee_id):
    """Check if employee has already marked attendance today"""
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        
        # Get employee info
        cursor.execute("SELECT name, company_id FROM employees WHERE emp_id = %s", (employee_id,))
        employee = cursor.fetchone()
        
        if not employee:
            cursor.close()
            connection.close()
            return jsonify({
                'success': True,
                'employee_found': False,
                'already_marked': False,
                'message': 'Employee not found'
            })

        if not has_module(employee['company_id'], "attendance"):
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Attendance module is disabled for this company'
            }), 403
        
        # Check today's attendance
        today = date.today()
        cursor.execute(
            """
            SELECT check_in_time, status, location_verified, face_verified
            FROM attendance 
            WHERE employee_id = %s AND company_id = %s AND date = %s
            """,
            (employee_id, employee['company_id'], today)
        )
        attendance_record = cursor.fetchone()
        
        cursor.close()
        connection.close()
        
        if attendance_record:
            return jsonify({
                'success': True,
                'already_marked': True,
                'employee_name': employee['name'],
                'check_in_time': attendance_record['check_in_time'].strftime('%H:%M:%S'),
                'status': attendance_record['status'],
                'location_verified': bool(attendance_record['location_verified']),
                'face_verified': bool(attendance_record['face_verified'])
            })
        else:
            return jsonify({
                'success': True,
                'already_marked': False,
                'employee_name': employee['name']
            })
        
    except Exception as e:
        current_app.logger.error(f"Attendance status check error: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'Failed to check attendance status'
        }), 500


@attendance.route("/history/<employee_id>")
def attendance_history(employee_id):
    """Get attendance history for an employee"""
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        
        # Get employee info
        cursor.execute("SELECT name, company_id FROM employees WHERE emp_id = %s", (employee_id,))
        employee = cursor.fetchone()
        
        if not employee:
            cursor.close()
            connection.close()
            return jsonify({'success': False, 'message': 'Employee not found'}), 404

        if not has_module(employee['company_id'], "attendance"):
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Attendance module is disabled for this company'
            }), 403
        
        # Get attendance records for last 30 days
        cursor.execute(
            """
            SELECT date, check_in_time, check_out_time, status, location_verified, 
                   face_verified, latitude, longitude
            FROM attendance 
            WHERE employee_id = %s AND company_id = %s 
            ORDER BY date DESC, check_in_time DESC 
            LIMIT 30
            """,
            (employee_id, employee['company_id'])
        )
        attendance_records = cursor.fetchall()
        
        cursor.close()
        connection.close()
        
        # Convert datetime objects to strings for JSON serialization
        for record in attendance_records:
            if record['date']:
                record['date'] = record['date'].strftime('%Y-%m-%d')
            if record['check_in_time']:
                record['check_in_time'] = record['check_in_time'].strftime('%H:%M:%S')
            if record['check_out_time']:
                record['check_out_time'] = record['check_out_time'].strftime('%H:%M:%S')
        
        return jsonify({
            'success': True,
            'employee_name': employee['name'],
            'records': attendance_records
        })
        
    except Exception as e:
        current_app.logger.error(f"Attendance history error: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'Failed to retrieve attendance history'
        }), 500