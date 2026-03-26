import base64
import os
import uuid
from datetime import datetime, date
from math import radians, cos, sin, asin, sqrt
import json

from flask import Blueprint, request, jsonify, current_app, render_template

# Optional face recognition imports
try:
    import face_recognition
    import numpy as np
    FACE_RECOGNITION_AVAILABLE = True
except ImportError:
    FACE_RECOGNITION_AVAILABLE = False
    face_recognition = None
    np = None

try:
    from PIL import Image
    import io
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    Image = None
    io = None

from database.db_connection import get_db_connection

attendance = Blueprint("attendance", __name__, url_prefix="/attendance")


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


@attendance.route("/portal/<int:company_id>")
def attendance_portal(company_id):
    """Public attendance portal for employees"""
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
    else:
        # Get first available company (for QR codes without company_id)
        cursor.execute("SELECT * FROM companies ORDER BY id LIMIT 1")
        company = cursor.fetchone()
        if company:
            company_id = company['id']
    
    cursor.close()
    connection.close()
    
    if not company:
        return "No company found", 404
    
    return render_template("attendance/portal.html", company=company, company_id=company_id)


@attendance.route("/verify-location", methods=["POST"])
def verify_location():
    """Verify if employee is within company location radius"""
    try:
        data = request.get_json()
        company_id = data.get('company_id')
        employee_lat = float(data.get('latitude'))
        employee_lon = float(data.get('longitude'))
        
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
                'message': f'Location verification failed - You are {int(distance)}m away (max allowed: {allowed_radius}m)',
                'distance': int(distance),
                'allowed_radius': allowed_radius
            })
            
    except Exception as e:
        current_app.logger.error(f"Location verification error: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'Location verification failed due to server error'
        }), 500


@attendance.route("/verify-face", methods=["POST"])
def verify_face():
    """Verify employee face against stored face encoding"""
    try:
        # Check if face recognition is available
        if not FACE_RECOGNITION_AVAILABLE:
            return jsonify({
                'success': True,
                'message': 'Face recognition not available - Skipping face verification',
                'confidence': 0,
                'skip_reason': 'Face recognition library not installed'
            })
        
        if not PIL_AVAILABLE:
            return jsonify({
                'success': True,
                'message': 'Image processing not available - Skipping face verification',
                'confidence': 0,
                'skip_reason': 'Pillow library not installed'
            })
        
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
        
        # Get employee's stored face encoding
        cursor.execute(
            "SELECT id, name, face_encoding, image_path FROM employees WHERE emp_id = %s", 
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
        
        if not employee['face_encoding']:
            return jsonify({
                'success': True,
                'message': f'No face data registered for {employee["name"]} - Skipping face verification',
                'confidence': 0,
                'skip_reason': 'No face encoding stored',
                'employee_name': employee['name']
            })
        
        try:
            # Process the captured face image
            # Remove data URL prefix if present
            if ',' in face_image_data:
                face_image_data = face_image_data.split(',')[1]
            
            # Decode base64 image
            image_binary = base64.b64decode(face_image_data)
            
            # Convert to PIL Image
            image = Image.open(io.BytesIO(image_binary))
            
            # Convert PIL image to numpy array for face_recognition
            image_array = np.array(image)
            
            # Find face encodings in the captured image
            captured_encodings = face_recognition.face_encodings(image_array)
            
            if len(captured_encodings) == 0:
                return jsonify({
                    'success': False,
                    'message': 'No face detected in the captured image. Please try again with better lighting.'
                })
            
            if len(captured_encodings) > 1:
                return jsonify({
                    'success': False,
                    'message': 'Multiple faces detected. Please ensure only your face is visible.'
                })
            
            # Get the captured face encoding
            captured_encoding = captured_encodings[0]
            
            # Convert stored encoding string back to numpy array
            stored_encoding_str = employee['face_encoding']
            stored_encoding = np.array([float(x) for x in stored_encoding_str.split(',')])
            
            # Compare faces using face_recognition library
            matches = face_recognition.compare_faces([stored_encoding], captured_encoding, tolerance=0.6)
            face_distance = face_recognition.face_distance([stored_encoding], captured_encoding)[0]
            
            # Calculate confidence percentage (lower distance = higher confidence)
            confidence = max(0, (1 - face_distance) * 100)
            
            current_app.logger.info(f"Face verification for {employee_id}: match={matches[0]}, distance={face_distance:.3f}, confidence={confidence:.1f}%")
            
            if matches[0] and confidence >= 40:  # 40% minimum confidence
                return jsonify({
                    'success': True,
                    'message': f'Face verified successfully for {employee["name"]} (Confidence: {confidence:.1f}%)',
                    'confidence': round(confidence, 1),
                    'employee_name': employee['name']
                })
            else:
                return jsonify({
                    'success': False,
                    'message': f'Face verification failed. Face does not match registered employee (Confidence: {confidence:.1f}%)',
                    'confidence': round(confidence, 1)
                })
                
        except Exception as face_error:
            current_app.logger.error(f"Face processing error: {str(face_error)}")
            return jsonify({
                'success': False,
                'message': 'Face verification failed due to image processing error'
            })
            
    except Exception as e:
        current_app.logger.error(f"Face verification error: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'Face verification failed due to server error'
        }), 500


@attendance.route("/mark", methods=["POST"])
def mark_attendance():
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
            SELECT e.id, e.name, e.emp_id, e.face_encoding, c.company_name, c.latitude as company_lat, 
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
        distance = 0
        
        if employee['company_lat'] and employee['company_lon']:
            distance = calculate_distance(
                float(latitude), float(longitude),
                float(employee['company_lat']), float(employee['company_lon'])
            )
            allowed_radius = employee['radius'] or 100
            location_verified = distance <= allowed_radius
            
            if not location_verified:
                cursor.close()
                connection.close()
                return jsonify({
                    'success': False,
                    'message': f'Location verification failed. You are {int(distance)}m away (max allowed: {allowed_radius}m)'
                })
        
        # Verify face (if face encoding exists and face recognition is available)
        face_verified = True
        confidence = 0
        
        if employee['face_encoding'] and FACE_RECOGNITION_AVAILABLE and PIL_AVAILABLE:
            try:
                # Process captured face image
                if ',' in face_image_data:
                    face_image_data = face_image_data.split(',')[1]
                
                image_binary = base64.b64decode(face_image_data)
                image = Image.open(io.BytesIO(image_binary))
                image_array = np.array(image)
                
                # Find face encodings
                captured_encodings = face_recognition.face_encodings(image_array)
                
                if len(captured_encodings) == 0:
                    cursor.close()
                    connection.close()
                    return jsonify({
                        'success': False,
                        'message': 'No face detected in the image. Please try again.'
                    })
                
                if len(captured_encodings) > 1:
                    cursor.close()
                    connection.close()
                    return jsonify({
                        'success': False,
                        'message': 'Multiple faces detected. Please ensure only your face is visible.'
                    })
                
                # Compare with stored encoding
                captured_encoding = captured_encodings[0]
                stored_encoding = np.array([float(x) for x in employee['face_encoding'].split(',')])
                
                matches = face_recognition.compare_faces([stored_encoding], captured_encoding, tolerance=0.6)
                face_distance = face_recognition.face_distance([stored_encoding], captured_encoding)[0]
                confidence = max(0, (1 - face_distance) * 100)
                
                face_verified = matches[0] and confidence >= 40
                
                if not face_verified:
                    cursor.close()
                    connection.close()
                    return jsonify({
                        'success': False,
                        'message': f'Face verification failed. Face does not match registered employee (Confidence: {confidence:.1f}%)'
                    })
                    
            except Exception as face_error:
                current_app.logger.error(f"Face verification error during attendance: {str(face_error)}")
                cursor.close()
                connection.close()
                return jsonify({
                    'success': False,
                    'message': 'Face verification failed due to processing error'
                })
        elif employee['face_encoding'] and not FACE_RECOGNITION_AVAILABLE:
            # Face encoding exists but face recognition not available - skip verification with info
            current_app.logger.info(f"Face recognition not available for employee {employee_id} - skipping face verification")
            face_verified = True  # Allow attendance but note the skip
        elif not employee['face_encoding']:
            # No face encoding stored - skip verification
            current_app.logger.info(f"No face encoding stored for employee {employee_id} - skipping face verification")
            face_verified = True  # Allow attendance but note the skip
        
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
        cursor.execute(
            """
            INSERT INTO attendance (
                employee_id, company_id, date, check_in_time, face_image, 
                latitude, longitude, location_verified, face_verified, status
            ) VALUES (%s, %s, %s, NOW(), %s, %s, %s, %s, %s, %s)
            """,
            (
                employee_id, company_id, today, attendance_image_path,
                latitude, longitude, location_verified, face_verified, 'present'
            )
        )
        
        connection.commit()
        cursor.close()
        connection.close()
        
        # Prepare success message
        verification_details = []
        if location_verified:
            verification_details.append(f"Location verified ({int(distance)}m)")
        
        # Handle face verification status
        if employee['face_encoding'] and FACE_RECOGNITION_AVAILABLE and PIL_AVAILABLE and confidence > 0:
            verification_details.append(f"Face verified ({confidence:.1f}% confidence)")
        elif employee['face_encoding'] and not FACE_RECOGNITION_AVAILABLE:
            verification_details.append("Face verification skipped (library not available)")
        elif not employee['face_encoding']:
            verification_details.append("Face verification skipped (no face data)")
        else:
            verification_details.append("Basic verification")
        
        verification_text = " • ".join(verification_details) if verification_details else "Basic verification"
        
        current_app.logger.info(f"Attendance marked successfully for {employee_id} at company {company_id}")
        
        return jsonify({
            'success': True,
            'message': f'Attendance marked successfully for {employee["name"]}!\n{verification_text}',
            'employee_name': employee['name'],
            'company_name': employee['company_name'],
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'verification_details': {
                'location_verified': location_verified,
                'face_verified': face_verified,
                'confidence': round(confidence, 1) if confidence > 0 else None,
                'distance': int(distance) if distance > 0 else None
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
            return jsonify({'success': False, 'message': 'Employee not found'}), 404
        
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