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
    from PIL import Image
    import io
    FACE_RECOGNITION_AVAILABLE = True
except ImportError as e:
    print(f"Face recognition libraries not available: {e}")
    FACE_RECOGNITION_AVAILABLE = False

from database.db_connection import get_db_connection

attendance = Blueprint("attendance", __name__, url_prefix="/attendance")

# Face verification configuration
FACE_VERIFICATION_CONFIG = {
    'threshold': 0.55,  # Similarity threshold for face matching (0-1 range) - lowered to account for real-world variations
    'method': 'opencv',  # Using OpenCV-based face matching
    'description': 'Lower values = stricter matching, Higher values = more tolerant matching'
}


def compare_faces_opencv(img1_path, img2_path, threshold=None):
    """
    Advanced face comparison using OpenCV and multiple matching techniques
    Optimized for real-world variations in lighting, angle, and expression
    Returns a result dict with similarity score, verified status, and confidence
    """
    if threshold is None:
        threshold = FACE_VERIFICATION_CONFIG['threshold']
    
    try:
        # Read images
        img1 = cv2.imread(img1_path)
        img2 = cv2.imread(img2_path)
        
        if img1 is None or img2 is None:
            print(f"Error reading images: img1={img1_path}, img2={img2_path}")
            return {
                'distance': 1.0,
                'verified': False,
                'confidence': 0.0,
                'threshold': threshold,
                'error': 'Could not read image files'
            }
        
        # Convert to grayscale
        gray1 = cv2.cvtColor(img1, cv2.COLOR_BGR2GRAY)
        gray2 = cv2.cvtColor(img2, cv2.COLOR_BGR2GRAY)
        
        # Load face cascade classifier
        face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        )
        
        # Detect faces
        faces1 = face_cascade.detectMultiScale(gray1, 1.1, 4)
        faces2 = face_cascade.detectMultiScale(gray2, 1.1, 4)
        
        if len(faces1) == 0 or len(faces2) == 0:
            return {
                'distance': 1.0,
                'verified': False,
                'confidence': 0.0,
                'threshold': threshold,
                'error': 'No face detected in one or both images'
            }
        
        if len(faces1) > 1 or len(faces2) > 1:
            return {
                'distance': 1.0,
                'verified': False,
                'confidence': 0.0,
                'threshold': threshold,
                'error': 'Multiple faces detected. Please ensure only your face is visible.'
            }
        
        # Extract face regions
        x1, y1, w1, h1 = faces1[0]
        x2, y2, w2, h2 = faces2[0]
        
        face1 = gray1[y1:y1+h1, x1:x1+w1]
        face2 = gray2[y2:y2+h2, x2:x2+w2]
        
        # Resize faces to same size for comparison
        face_size = (100, 100)
        face1 = cv2.resize(face1, face_size)
        face2 = cv2.resize(face2, face_size)
        
        # Apply histogram equalization to handle lighting variations
        face1_eq = cv2.equalizeHist(face1)
        face2_eq = cv2.equalizeHist(face2)
        
        # Method 1: Histogram comparison
        hist1 = cv2.calcHist([face1], [0], None, [256], [0, 256])
        hist2 = cv2.calcHist([face2], [0], None, [256], [0, 256])
        
        # Normalize histograms
        cv2.normalize(hist1, hist1, alpha=0, beta=1, norm_type=cv2.NORM_MINMAX)
        cv2.normalize(hist2, hist2, alpha=0, beta=1, norm_type=cv2.NORM_MINMAX)
        
        histogram_similarity = cv2.compareHist(hist1, hist2, cv2.HISTCMP_BHATTACHARYYA)
        
        # Method 2: Template matching (equalized images for better handling of lighting variations)
        result = cv2.matchTemplate(face1_eq, face2_eq, cv2.TM_CCOEFF_NORMED)
        template_similarity = result[0][0] if result.size > 0 else 0.0
        
        # Method 3: MSE (Mean Squared Error) based similarity
        mse = np.sum((face1.astype(float) - face2.astype(float)) ** 2) / (face1.shape[0] * face1.shape[1])
        mse_similarity = 1.0 / (1.0 + mse / 255.0)
        
        # Method 4: MSE on equalized images (handles brightness variations)
        mse_eq = np.sum((face1_eq.astype(float) - face2_eq.astype(float)) ** 2) / (face1_eq.shape[0] * face1_eq.shape[1])
        mse_eq_similarity = 1.0 / (1.0 + mse_eq / 255.0)
        
        # Combine methods with weighted average
        # Histogram: 0.2 (less weight due to lighting sensitivity)
        # Template (equalized): 0.4 (most reliable)
        # MSE: 0.2
        # MSE Equalized: 0.2 (handles lighting variations)
        combined_similarity = (
            (1 - histogram_similarity) * 0.2 +  # Invert histogram similarity
            template_similarity * 0.4 +
            mse_similarity * 0.2 +
            mse_eq_similarity * 0.2
        )
        
        # Normalize to 0-1 range
        combined_similarity = max(0.0, min(1.0, combined_similarity))
        
        # Confidence percentage
        confidence = combined_similarity * 100
        
        # Calculate distance (inverse of similarity for consistency)
        distance = 1.0 - combined_similarity
        
        # Determine if faces match based on threshold
        face_verified = combined_similarity >= threshold
        
        return {
            'distance': float(distance),
            'verified': face_verified,
            'confidence': float(confidence),
            'threshold': threshold,
            'similarity': float(combined_similarity)
        }
        
    except Exception as e:
        print(f"Face comparison error: {e}")
        return {
            'distance': 1.0,
            'verified': False,
            'confidence': 0.0,
            'threshold': threshold,
            'error': str(e)
        }


def compare_faces_deepface(img1_path, img2_path, threshold=None):
    """
    Wrapper function for backward compatibility.
    Uses OpenCV-based face comparison.
    """
    return compare_faces_opencv(img1_path, img2_path, threshold)


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
            'model': FACE_VERIFICATION_CONFIG['model'],
            'distance_metric': FACE_VERIFICATION_CONFIG['distance_metric'],
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


@attendance.route("/verify-face", methods=["POST"])
def verify_face():
    """Verify employee face against stored face image using OpenCV"""
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
            
            # Perform face verification using OpenCV with tolerance-based matching
            try:
                # Use configurable threshold for flexible matching
                tolerance_threshold = FACE_VERIFICATION_CONFIG['threshold']
                
                result = compare_faces_opencv(stored_image_path, temp_image_path, tolerance_threshold)
                
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
                            'message': 'No face detected in the image. Please try again with better lighting and ensure your face is clearly visible.'
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
                    
            except Exception as opencv_error:
                # Clean up temp file
                if os.path.exists(temp_image_path):
                    os.remove(temp_image_path)
                
                current_app.logger.error(f"OpenCV face verification error: {opencv_error}")
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
            
            # Perform face verification using OpenCV with tolerance-based matching
            try:
                # Use configurable threshold for flexible matching
                tolerance_threshold = FACE_VERIFICATION_CONFIG['threshold']
                
                result = compare_faces_opencv(stored_image_path, temp_image_path, tolerance_threshold)
                
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
                            'message': 'No face detected in the image. Please try again with better lighting and ensure your face is clearly visible.'
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
                    
            except Exception as opencv_error:
                # Clean up temp file
                if os.path.exists(temp_image_path):
                    os.remove(temp_image_path)
                
                cursor.close()
                connection.close()
                
                current_app.logger.error(f"OpenCV face verification error during attendance: {opencv_error}")
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