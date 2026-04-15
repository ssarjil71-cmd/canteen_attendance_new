import base64
import os
import uuid
from datetime import datetime, date
from math import radians, cos, sin, asin, sqrt
import json

from flask import Blueprint, request, jsonify, current_app, render_template

# Required face recognition imports
try:
    import cv2
    import numpy as np
    import face_recognition
    FACE_RECOGNITION_AVAILABLE = True
except ImportError as e:
    print(f"Face recognition libraries not available: {e}")
    FACE_RECOGNITION_AVAILABLE = False

from database.db_connection import get_db_connection

attendance = Blueprint("attendance", __name__, url_prefix="/attendance")

# Face verification configuration
FACE_VERIFICATION_CONFIG = {
    'threshold': 0.55,  # Recommended practical tolerance for face_recognition
    'method': 'face_recognition',
    'detection_model': 'hog',
    'num_jitters': 1,
    'min_brightness': 45,
    'description': 'Lower values = stricter matching, Higher values = more tolerant matching'
}


def preprocess_bgr_image(image_bgr):
    """Normalize lighting and contrast before converting to RGB for detection."""
    if image_bgr is None:
        return None

    processed = image_bgr.copy()
    gray = cv2.cvtColor(processed, cv2.COLOR_BGR2GRAY)
    brightness = float(np.mean(gray))

    if brightness < FACE_VERIFICATION_CONFIG['min_brightness']:
        # Boost dark images to reduce false negatives in low-light scenes.
        processed = cv2.convertScaleAbs(processed, alpha=1.25, beta=20)

    ycrcb = cv2.cvtColor(processed, cv2.COLOR_BGR2YCrCb)
    y, cr, cb = cv2.split(ycrcb)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    y = clahe.apply(y)
    processed = cv2.cvtColor(cv2.merge((y, cr, cb)), cv2.COLOR_YCrCb2BGR)
    return processed


def decode_base64_to_bgr(face_image_data):
    """Decode data URL/base64 string into OpenCV BGR image."""
    if not face_image_data:
        return None

    if ',' in face_image_data:
        face_image_data = face_image_data.split(',', 1)[1]

    image_binary = base64.b64decode(face_image_data)
    np_arr = np.frombuffer(image_binary, np.uint8)
    return cv2.imdecode(np_arr, cv2.IMREAD_COLOR)


def detect_faces_with_boxes(image_bgr):
    """Return face locations in CSS format (top, right, bottom, left)."""
    if image_bgr is None:
        return []

    processed = preprocess_bgr_image(image_bgr)
    rgb = cv2.cvtColor(processed, cv2.COLOR_BGR2RGB)

    # Resize for speed while preserving detection accuracy.
    scale = 0.5
    small_rgb = cv2.resize(rgb, (0, 0), fx=scale, fy=scale)
    locations_small = face_recognition.face_locations(
        small_rgb,
        number_of_times_to_upsample=1,
        model=FACE_VERIFICATION_CONFIG['detection_model']
    )

    locations = []
    inv_scale = int(round(1 / scale))
    for top, right, bottom, left in locations_small:
        locations.append((top * inv_scale, right * inv_scale, bottom * inv_scale, left * inv_scale))

    return locations


def verify_face_images(stored_image_path, captured_image_path, threshold=None):
    """Verify one captured face against one stored face using face encodings."""
    if threshold is None:
        threshold = FACE_VERIFICATION_CONFIG['threshold']

    try:
        stored_bgr = cv2.imread(stored_image_path)
        captured_bgr = cv2.imread(captured_image_path)

        if stored_bgr is None or captured_bgr is None:
            return {
                'distance': 1.0,
                'verified': False,
                'confidence': 0.0,
                'threshold': threshold,
                'error': 'Could not read image files'
            }

        stored_locations = detect_faces_with_boxes(stored_bgr)
        captured_locations = detect_faces_with_boxes(captured_bgr)

        if len(stored_locations) == 0 or len(captured_locations) == 0:
            return {
                'distance': 1.0,
                'verified': False,
                'confidence': 0.0,
                'threshold': threshold,
                'error': 'No face detected in one or both images'
            }

        if len(stored_locations) > 1 or len(captured_locations) > 1:
            return {
                'distance': 1.0,
                'verified': False,
                'confidence': 0.0,
                'threshold': threshold,
                'error': 'Multiple faces detected. Please ensure only your face is visible.'
            }

        stored_rgb = cv2.cvtColor(preprocess_bgr_image(stored_bgr), cv2.COLOR_BGR2RGB)
        captured_rgb = cv2.cvtColor(preprocess_bgr_image(captured_bgr), cv2.COLOR_BGR2RGB)

        stored_encodings = face_recognition.face_encodings(
            stored_rgb,
            known_face_locations=stored_locations,
            num_jitters=FACE_VERIFICATION_CONFIG['num_jitters']
        )
        captured_encodings = face_recognition.face_encodings(
            captured_rgb,
            known_face_locations=captured_locations,
            num_jitters=FACE_VERIFICATION_CONFIG['num_jitters']
        )

        if not stored_encodings or not captured_encodings:
            return {
                'distance': 1.0,
                'verified': False,
                'confidence': 0.0,
                'threshold': threshold,
                'error': 'Face encoding could not be extracted. Keep face straight with better lighting.'
            }

        distance = float(face_recognition.face_distance([stored_encodings[0]], captured_encodings[0])[0])
        verified = distance <= threshold

        # Convert distance to a user-friendly confidence estimate.
        confidence = max(0.0, min(100.0, (1.0 - (distance / max(threshold, 1e-6))) * 100.0))

        return {
            'distance': round(distance, 4),
            'verified': verified,
            'confidence': round(confidence, 1),
            'threshold': threshold
        }

    except Exception as exc:
        current_app.logger.error(f"Face verification error: {exc}")
        return {
            'distance': 1.0,
            'verified': False,
            'confidence': 0.0,
            'threshold': threshold,
            'error': str(exc)
        }


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
            'current_threshold': FACE_VERIFICATION_CONFIG['threshold'],
            'model': FACE_VERIFICATION_CONFIG['method'],
            'detection_model': FACE_VERIFICATION_CONFIG['detection_model'],
            'recommended_range': '0.5 - 0.7',
            'description': 'Lower values = stricter matching, Higher values = more tolerant matching'
        })
    
    elif request.method == "POST":
        try:
            data = request.get_json()
            new_threshold = float(data.get('threshold', FACE_VERIFICATION_CONFIG['threshold']))
            
            # Validate threshold range
            if not (0.3 <= new_threshold <= 1.0):
                return jsonify({
                    'success': False,
                    'message': 'Threshold must be between 0.3 and 1.0'
                }), 400
            
            # Update configuration
            FACE_VERIFICATION_CONFIG['threshold'] = new_threshold
            
            return jsonify({
                'success': True,
                'message': f'Face verification threshold updated to {new_threshold}',
                'new_threshold': new_threshold
            })
            
        except (ValueError, TypeError):
            return jsonify({
                'success': False,
                'message': 'Invalid threshold value. Must be a number between 0.3 and 1.0'
            }), 400
        except Exception as e:
            return jsonify({
                'success': False,
                'message': f'Error updating threshold: {str(e)}'
            }), 500


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


@attendance.route("/detect-face", methods=["POST"])
def detect_face():
    """Realtime face detection endpoint used by live camera preview."""
    try:
        if not FACE_RECOGNITION_AVAILABLE:
            return jsonify({
                'success': False,
                'message': 'Face recognition system not available. Please contact administrator.'
            }), 500

        data = request.get_json() or {}
        face_image_data = data.get('face_image_data')

        if not face_image_data:
            return jsonify({
                'success': False,
                'face_detected': False,
                'message': 'Face image is required'
            }), 400

        image_bgr = decode_base64_to_bgr(face_image_data)
        if image_bgr is None:
            return jsonify({
                'success': False,
                'face_detected': False,
                'message': 'Could not decode image'
            }), 400

        gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
        brightness = float(np.mean(gray))
        locations = detect_faces_with_boxes(image_bgr)

        if len(locations) == 0:
            return jsonify({
                'success': True,
                'face_detected': False,
                'can_capture': False,
                'brightness': round(brightness, 1),
                'message': 'Face not detected. Please align your face properly.'
            })

        if len(locations) > 1:
            return jsonify({
                'success': True,
                'face_detected': False,
                'can_capture': False,
                'brightness': round(brightness, 1),
                'message': 'Multiple faces detected. Ensure only one face is visible.'
            })

        top, right, bottom, left = locations[0]
        box_w = right - left
        box_h = bottom - top
        can_capture = box_w > 80 and box_h > 80 and brightness >= 30

        return jsonify({
            'success': True,
            'face_detected': True,
            'can_capture': can_capture,
            'brightness': round(brightness, 1),
            'bounding_box': {
                'top': int(top),
                'right': int(right),
                'bottom': int(bottom),
                'left': int(left)
            },
            'message': 'Face detected. You can capture now.' if can_capture else 'Face detected, adjust lighting/position for a clearer capture.'
        })

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
    """Verify employee face against stored face image using face_recognition."""
    try:
        # Check if face recognition is available
        if not FACE_RECOGNITION_AVAILABLE:
            return jsonify({
                'success': False,
                'message': 'Face recognition system not available. Please contact administrator.'
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
            "SELECT id, name, image_path FROM employees WHERE emp_id = %s", 
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
        
        if not employee['image_path']:
            return jsonify({
                'success': False,
                'message': f'No face image registered for {employee["name"]}. Please contact HR to register your face.'
            })
        
        try:
            # Process the captured face image
            # Remove data URL prefix if present
            if ',' in face_image_data:
                face_image_data = face_image_data.split(',')[1]
            
            # Decode base64 image and save temporarily
            image_binary = base64.b64decode(face_image_data)
            
            # Create temp directory for captured images
            temp_dir = os.path.join(current_app.root_path, 'static', 'temp')
            os.makedirs(temp_dir, exist_ok=True)
            
            # Save captured image temporarily
            temp_filename = f"temp_capture_{employee_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
            temp_image_path = os.path.join(temp_dir, temp_filename)
            
            with open(temp_image_path, 'wb') as f:
                f.write(image_binary)
            
            # Get stored image path
            stored_image_path = os.path.join(current_app.root_path, 'static', employee['image_path'])
            
            # Check if stored image exists
            if not os.path.exists(stored_image_path):
                # Clean up temp file
                if os.path.exists(temp_image_path):
                    os.remove(temp_image_path)
                return jsonify({
                    'success': False,
                    'message': f'Stored face image not found for {employee["name"]}. Please contact HR.'
                })
            
            # Perform face verification using face encodings and tolerance-based matching
            try:
                # Use configurable threshold for flexible matching
                tolerance_threshold = FACE_VERIFICATION_CONFIG['threshold']
                
                result = verify_face_images(stored_image_path, temp_image_path, tolerance_threshold)
                
                # Clean up temp file
                if os.path.exists(temp_image_path):
                    os.remove(temp_image_path)
                
                distance = result['distance']
                confidence = result['confidence']
                face_verified = result['verified']
                
                # Check for errors in result
                if 'error' in result:
                    error_msg = result['error'].lower()
                    if 'no face detected' in error_msg:
                        return jsonify({
                            'success': False,
                            'message': 'Face not detected. Please align your face properly.'
                        })
                    elif 'multiple faces' in error_msg:
                        return jsonify({
                            'success': False,
                            'message': 'Multiple faces detected. Please ensure only your face is visible in the camera.'
                        })
                
                if face_verified:
                    return jsonify({
                        'success': True,
                        'message': f'Face verified successfully for {employee["name"]} (Confidence: {confidence:.1f}%)',
                        'confidence': round(float(confidence), 1),
                        'distance': round(float(distance), 3),
                        'threshold': tolerance_threshold,
                        'employee_name': employee['name']
                    })
                else:
                    return jsonify({
                        'success': False,
                        'message': f'Face verification failed. Face does not match {employee["name"]} (Distance: {distance:.3f}, Confidence: {confidence:.1f}%)',
                        'confidence': round(float(confidence), 1),
                        'distance': round(float(distance), 3),
                        'threshold': tolerance_threshold,
                        'employee_name': employee['name']
                    })
                    
            except Exception as verification_error:
                # Clean up temp file
                if os.path.exists(temp_image_path):
                    os.remove(temp_image_path)
                
                current_app.logger.error(f"Face verification error: {verification_error}")
                return jsonify({
                    'success': False,
                    'message': 'Face verification failed due to processing error. Please try again with better lighting.'
                })
                
        except Exception as processing_error:
            current_app.logger.error(f"Face image processing error: {str(processing_error)}")
            return jsonify({
                'success': False,
                'message': 'Failed to process face image. Please try again.'
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
        
        # Verify face (MANDATORY - no skipping allowed)
        face_verified = False
        confidence = 0
        
        if not FACE_RECOGNITION_AVAILABLE:
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Face recognition system not available. Please contact administrator.'
            }), 500
        
        if not employee['image_path']:
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': f'No face image registered for {employee["name"]}. Please contact HR to register your face.'
            })
        
        try:
            # Process captured face image
            if ',' in face_image_data:
                face_image_data = face_image_data.split(',')[1]
            
            image_binary = base64.b64decode(face_image_data)
            
            # Create temp directory for captured images
            temp_dir = os.path.join(current_app.root_path, 'static', 'temp')
            os.makedirs(temp_dir, exist_ok=True)
            
            # Save captured image temporarily
            temp_filename = f"attendance_capture_{employee_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
            temp_image_path = os.path.join(temp_dir, temp_filename)
            
            with open(temp_image_path, 'wb') as f:
                f.write(image_binary)
            
            # Get stored image path
            stored_image_path = os.path.join(current_app.root_path, 'static', employee['image_path'])
            
            # Check if stored image exists
            if not os.path.exists(stored_image_path):
                # Clean up temp file
                if os.path.exists(temp_image_path):
                    os.remove(temp_image_path)
                cursor.close()
                connection.close()
                return jsonify({
                    'success': False,
                    'message': f'Stored face image not found for {employee["name"]}. Please contact HR.'
                })
            
            # Perform face verification using face encodings and tolerance-based matching
            try:
                # Use configurable threshold for flexible matching
                tolerance_threshold = FACE_VERIFICATION_CONFIG['threshold']
                
                result = verify_face_images(stored_image_path, temp_image_path, tolerance_threshold)
                
                # Clean up temp file
                if os.path.exists(temp_image_path):
                    os.remove(temp_image_path)
                
                distance = result['distance']
                confidence = result['confidence']
                face_verified = result['verified']
                
                # Check for errors in result
                if 'error' in result:
                    error_msg = result['error'].lower()
                    cursor.close()
                    connection.close()
                    if 'no face detected' in error_msg:
                        return jsonify({
                            'success': False,
                            'message': 'Face not detected. Please align your face properly.'
                        })
                    elif 'multiple faces' in error_msg:
                        return jsonify({
                            'success': False,
                            'message': 'Multiple faces detected. Please ensure only your face is visible in the camera.'
                        })
                    else:
                        return jsonify({
                            'success': False,
                            'message': 'Face verification failed due to processing error. Please try again with better lighting.'
                        })
                
                if not face_verified:
                    cursor.close()
                    connection.close()
                    return jsonify({
                        'success': False,
                        'message': f'Face verification failed. Face does not match {employee["name"]} (Distance: {distance:.3f}, Confidence: {confidence:.1f}%)'
                    })
                    
            except Exception as verification_error:
                # Clean up temp file
                if os.path.exists(temp_image_path):
                    os.remove(temp_image_path)
                
                cursor.close()
                connection.close()
                
                current_app.logger.error(f"Face verification error during attendance: {verification_error}")
                return jsonify({
                    'success': False,
                    'message': 'Face verification failed due to processing error. Please try again with better lighting.'
                })
                    
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
        
        # Face verification is now mandatory
        if face_verified and confidence > 0:
            verification_details.append(f"Face verified ({confidence:.1f}% confidence)")
        
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