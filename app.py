from flask import Flask, request, redirect, url_for, render_template, send_file, jsonify
import pandas as pd
import cv2
import io
import os
import json

app = Flask(__name__)

df = pd.read_csv('user_id.csv')
accounts = df['user_id'].tolist()

@app.route('/')
def navigate():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user_id = request.form.get('user_id', '').strip()
        if user_id in accounts:
            return redirect(url_for('user_home', user_id=user_id))
        else:
            return redirect(url_for('login'))
    return render_template('login.html')

@app.route('/<user_id>/home')
def user_home(user_id):
    if user_id in accounts:
        return render_template('home.html', user_id=user_id)
    else:
        return "User ID not found", 404
    

# File to store the polygons data
    
all_object_polygon = []
scale = 0.5
object_points = []
drawing_mode = False  # Track if drawing mode is active
image_path = os.path.join('static', 'unlable_image', 'image1.jpg')

@app.route('/get-image')
def get_image():
    return send_file(plot_coordinates_on_image(), mimetype='image/png')

@app.route('/zoom', methods=['POST'])
def zoom():
    global scale
    data = request.json or {}
    zoom_in = data.get('zoom_in', True)

    if zoom_in:
        scale *= 1.2
    else:
        scale /= 1.2

    return ('', 204)

# json file
POLYGON_FILE = 'polygons.json'
imageHeight = None
imageWidth = None
def load_polygons():
    global all_object_polygon, imageWidth, imageHeight 
    if os.path.exists(POLYGON_FILE):
        with open(POLYGON_FILE, 'r') as file:
            data = json.load(file)
            all_object_polygon = data['objects']

            imageHeight = data['imageHeight']
            imageWidth = data['imageWidth']

def save_polygons():
    global all_object_polygon, imageWidth, imageHeight
    data = {
        'objects': all_object_polygon,
        'imageHeight': imageHeight,  # Use your actual image height
        'imageWidth': imageHeight    # Use your actual image width
    }
    with open(POLYGON_FILE, 'w') as file:
        json.dump(data, file)


@app.route('/toggle-draw', methods=['POST'])
def toggle_draw():
    global drawing_mode, all_object_polygon, object_points
    drawing_mode = request.json.get('drawing_mode', False)
    label = request.json.get('label', 'Unknown')
    if not drawing_mode:
        all_object_polygon.append({
            'label': label,  
            'points': object_points
        })
        object_points = []  
    return ('', 204)

@app.route('/submit-polygons', methods=['POST'])
def save_polygons_route():
    global all_object_polygon
    save_polygons()
    return ('', 204)

@app.route('/draw', methods=['POST'])
def draw():
    global object_points, drawing_mode
    if not drawing_mode:
        return ('', 204)

    points = request.json.get('points')
    if points:
        # Add new point based on the current scale
        new_point = {
            'x': points[0]['x'] / scale,
            'y': points[0]['y'] / scale
        }
        object_points.append(new_point)

        # Check if last point matches the first to close the shape
        if len(object_points) > 2 and object_points[0] == object_points[-1]:
            drawing_mode = False  # Automatically end drawing
            print("Closed shape detected, drawing mode ended.")

    return ('', 204)

import math

# Check if the last point is close to the first point
def is_near_first_point(last_point, first_point, threshold=10):
    distance = math.sqrt((last_point['x'] - first_point['x']) ** 2 + (last_point['y'] - first_point['y']) ** 2)
    return distance < threshold

def plot_coordinates_on_image():
    global all_object_polygon, scale

    img = cv2.imread(image_path)
    if img is None:
        raise FileNotFoundError("Image file not found.")

    img_resized = cv2.resize(img, (0, 0), fx=scale, fy=scale)
    for object in all_object_polygon:
        object_points = object['points']
        if object_points:
            first_point = object_points[0]
            object_points.append(first_point)
            for i, point in enumerate(object_points):
                x_resized = int(point['x'] * scale)
                y_resized = int(point['y'] * scale)
    
                # Draw a larger, filled circle to make the points "pop out"
                cv2.circle(img_resized, (x_resized, y_resized), 8, (0, 0, 255), -1)  # Red points
    
                if i > 0 and i < len(object_points):
                    prev_point = object_points[i - 1]
                    prev_x_resized = int(prev_point['x'] * scale)
                    prev_y_resized = int(prev_point['y'] * scale)
                    cv2.line(img_resized, (prev_x_resized, prev_y_resized), (x_resized, y_resized), (0, 255, 0), 2)  

    _, buffer = cv2.imencode('.png', img_resized)
    buf = io.BytesIO(buffer)
    return buf

@app.route('/delete-last', methods=['POST'])
def delete_last_point():
    global object_points, drawing_mode
    if drawing_mode and object_points:
        object_points.pop()  
    return ('', 204) 

@app.route('/get-objects', methods=['GET'])
def get_objects():
    global all_object_polygon
    return jsonify(all_object_polygon)

@app.route('/check-point', methods=['POST'])
def check_point():
    global all_object_polygon, scale
    
    # Get the click coordinates from the frontend
    data = request.json
    click_x = data['x']
    click_y = data['y']
    
    # Adjust the click coordinates based on the scale
    original_x = click_x / scale
    original_y = click_y / scale
    point = {'x': original_x, 'y': original_y}
    
    # Loop through all polygons to check if the point is inside any
    for i, polygon_object in enumerate(all_object_polygon):
        polygon = polygon_object['points']
        if is_point_inside_polygon(point, polygon):
            return jsonify({'inside': True, 'polygon_index': i})  
    
    return jsonify({'inside': False})


def is_point_inside_polygon(point, polygon):
    x = point['x']
    y = point['y']
    inside = False
    num_points = len(polygon)

    for i in range(num_points):
        j = (i - 1) % num_points
        xi, yi = polygon[i]['x'], polygon[i]['y']
        xj, yj = polygon[j]['x'], polygon[j]['y']

        intersect = ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi) + xi)
        if intersect:
            inside = not inside

    return inside

@app.route('/delete-polygon', methods=['POST'])
def delete_polygon():
    data = request.json
    polygon_index = data.get('polygon_index')

    if polygon_index is not None and 0 <= polygon_index < len(all_object_polygon):
        del all_object_polygon[polygon_index]
        return jsonify({'success': True})

    return jsonify({'success': False})

if __name__ == '__main__':
    app.run(debug=True)