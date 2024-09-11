from flask import Flask, request, redirect, url_for, render_template, send_file, jsonify
import pandas as pd
import cv2
import io
import os

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

@app.route('/toggle-draw', methods=['POST'])
def toggle_draw():
    global drawing_mode
    drawing_mode = request.json.get('drawing_mode', False)
    if not drawing_mode:
        all_object_polygon.append(object_points)
        object_points.clear()  # Clear points when ending drawing
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
    global object_points, scale

    img = cv2.imread(image_path)
    if img is None:
        raise FileNotFoundError("Image file not found.")

    img_resized = cv2.resize(img, (0, 0), fx=scale, fy=scale)

    if object_points:
        first_point = object_points[0]
        for i, point in enumerate(object_points):
            x_resized = int(point['x'] * scale)
            y_resized = int(point['y'] * scale)

            # Draw a larger, filled circle to make the points "pop out"
            cv2.circle(img_resized, (x_resized, y_resized), 8, (0, 0, 255), -1)  # Red points

            if i > 0:
                prev_point = object_points[i - 1]
                prev_x_resized = int(prev_point['x'] * scale)
                prev_y_resized = int(prev_point['y'] * scale)
                cv2.line(img_resized, (prev_x_resized, prev_y_resized), (x_resized, y_resized), (0, 255, 0), 2)  # Green line

        # If the last point is near the first point, connect them
        last_point = object_points[-1]
        if is_near_first_point(last_point, first_point):
            first_x_resized = int(first_point['x'] * scale)
            first_y_resized = int(first_point['y'] * scale)
            last_x_resized = int(last_point['x'] * scale)
            last_y_resized = int(last_point['y'] * scale)
            cv2.line(img_resized, (last_x_resized, last_y_resized), (first_x_resized, first_y_resized), (255, 0, 0), 2)  # Blue closing line

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

if __name__ == '__main__':
    app.run(debug=True)