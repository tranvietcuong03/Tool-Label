from flask import Flask, request, redirect, url_for, render_template, send_file, jsonify
import pandas as pd
import cv2
import io
import os
import json
import base64
import math
import random

app = Flask(__name__)

df = pd.read_csv('user_id.csv')
accounts = df['user_id'].tolist()
userID = None
print(accounts)

@app.route('/')
def navigate():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    global userID
    if request.method == 'POST':
        user_id = request.form.get('user_id', '').strip()
        if user_id in accounts:
            userID = user_id
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

with open('static/config.json', 'r') as config_file:
    config = json.load(config_file)

all_object_polygon = []
scale = 0.5
object_points = []
drawing_mode = False
image_dir = config['paths']['unlabelled_image_folder']
image_files = [f for f in os.listdir(image_dir)]
current_image_index = 0

def get_image_path():
    if current_image_index < len(image_files):
        return os.path.join(image_dir, image_files[current_image_index])
    return None

imageWidth = 0
imageHeight = 0

@app.route('/get-image')
def get_image():
    image_path = get_image_path()
    if image_path:
        selected_polygon_index = request.args.get('selected_polygon_index', None, type=int)
        image_stream = plot_coordinates_on_image(selected_polygon_index)
        return send_file(image_stream, mimetype='image/png')
    return "No more images.", 404

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

@app.route('/<user_id>/submit-polygons', methods=['POST'])
def submit_polygons(user_id):
    global userID
    user_id = userID
    print(f"Received user_id: {user_id}")
    if user_id not in accounts:
        return ('User not authorized', 403)

    try:
        save_polygons(user_id)
        return ('', 204)
    except Exception as e:
        print(f"Error saving polygons: {e}")
        return ('Failed to submit', 500)

def save_polygons(user_id):
    global all_object_polygon, imageWidth, imageHeight
    image_path = get_image_path()

    if not image_path:
        raise ValueError("No image path found")

    image_name = os.path.splitext(os.path.basename(image_path))[0]

    with open(image_path, "rb") as img_file:
        base64_string = base64.b64encode(img_file.read()).decode('utf-8')

    json_save_dir = os.path.join(config['paths']['labelled_image_folder'], user_id)
    os.makedirs(json_save_dir, exist_ok=True)
    json_file_path = os.path.join(json_save_dir, f"{image_name}.json")

    data = {
        'objects': all_object_polygon,
        'imageData': base64_string,
        'imageHeight': imageHeight,
        'imageWidth': imageWidth,
    }

    with open(json_file_path, 'w') as file:
        json.dump(data, file)

    csv_file_path = config['paths']['csv_file_path']
    if not os.path.exists(csv_file_path):
        df = pd.DataFrame(columns=['image_name', 'labelled_image_path'])
    else:
        df = pd.read_csv(csv_file_path)

    image_relative_path = os.path.join(user_id, f"{image_name}.json")
    if 'image_name' not in df.columns:
        df['image_name'] = ''
    df.loc[df['image_name'] == image_name, 'labelled_image_path'] = image_relative_path
    if df[df['image_name'] == image_name].empty:
        df = pd.concat([df, pd.DataFrame([{'image_name': image_name, 'labelled_image_path': image_relative_path}])], ignore_index=True)

    df.to_csv(csv_file_path, index=False)

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

@app.route('/draw', methods=['POST'])
def draw():
    global object_points, drawing_mode
    if not drawing_mode:
        return ('', 204)

    points = request.json.get('points')
    if points:
        new_point = {
            'x': points[0]['x'] / scale,
            'y': points[0]['y'] / scale
        }
        object_points.append(new_point)

        if len(object_points) > 2 and is_near_first_point(object_points[-1], object_points[0]):
            drawing_mode = False

    return ('', 204)

def is_near_first_point(last_point, first_point, threshold=10):
    distance = math.sqrt((last_point['x'] - first_point['x']) ** 2 + (last_point['y'] - first_point['y']) ** 2)
    return distance < threshold

def plot_coordinates_on_image(selected_polygon_index=None):
    global all_object_polygon, scale, imageWidth, imageHeight
    image_path = get_image_path()
    img = cv2.imread(image_path)
    if img is None:
        raise FileNotFoundError("Image file not found.")

    imageHeight, imageWidth, _ = img.shape

    img_resized = cv2.resize(img, (0, 0), fx=scale, fy=scale)
    for idx, object in enumerate(all_object_polygon):
        object_points = object['points']
        if object_points:
            color = (0, 255, 0)
            if idx == selected_polygon_index:
                color = (255, 0, 255)
            first_point = object_points[0]
            object_points.append(first_point)
            for i, point in enumerate(object_points):

                x_resized = int(point['x'] * scale)
                y_resized = int(point['y'] * scale)

                cv2.circle(img_resized, (x_resized, y_resized), 8, (0, 0, 255), -1)

                if i > 0 and i < len(object_points):
                    prev_point = object_points[i - 1]
                    prev_x_resized = int(prev_point['x'] * scale)
                    prev_y_resized = int(prev_point['y'] * scale)
                    cv2.line(img_resized, (prev_x_resized, prev_y_resized), (x_resized, y_resized), color , 2)

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
    
    data = request.json
    click_x = data['x']
    click_y = data['y']
    
    original_x = click_x / scale
    original_y = click_y / scale
    point = {'x': original_x, 'y': original_y}
    
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

@app.route('/next-image', methods=['POST'])
def next_image():
    global current_image_index, all_object_polygon
    if current_image_index < len(image_files) - 1:
        all_object_polygon = []
        current_image_index += 1
        return jsonify({'success': True, 'next_image': image_files[current_image_index]})
    else:
        return jsonify({'success': False, 'message': 'No more images.'}), 400

@app.route('/highlight-class')
def highlight_class():
    global scale
    try:
        class_names = request.args.getlist('class_name')
        dict_color = {}
        for class_name in class_names:
            dict_color[class_name] = (random.randint(0, 200), random.randint(0, 200), random.randint(0, 200))
        
        image_path = get_image_path()
        image = cv2.imread(image_path)
        if image is None:
            raise FileNotFoundError("Image file not found")

        img_resized = cv2.resize(image, (0, 0), fx=scale, fy=scale)

        for polygon in all_object_polygon:
            if polygon['label'] in class_names:
                points = polygon['points']
                points.append(points[0])
                for i, point in enumerate(points):
                    
                    x_resized = int(point['x'] * scale)
                    y_resized = int(point['y'] * scale)

                    cv2.circle(img_resized, (x_resized, y_resized), 8, dict_color[polygon['label']], -1)

                    if i > 0:
                        prev_point = points[i - 1]
                        prev_x_resized = int(prev_point['x'] * scale)
                        prev_y_resized = int(prev_point['y'] * scale)
                        cv2.line(img_resized, (prev_x_resized, prev_y_resized), (x_resized, y_resized), dict_color[polygon['label']], 2)
            else:
                points = polygon['points']
                points.append(points[0])
                for i, point in enumerate(points):
                    
                    x_resized = int(point['x'] * scale)
                    y_resized = int(point['y'] * scale)

                    cv2.circle(img_resized, (x_resized, y_resized), 8, (0, 0 , 255), -1)

                    if i > 0:
                        prev_point = points[i - 1]
                        prev_x_resized = int(prev_point['x'] * scale)
                        prev_y_resized = int(prev_point['y'] * scale)
                        cv2.line(img_resized, (prev_x_resized, prev_y_resized), (x_resized, y_resized), (0, 255, 0), 2)
                    

        _, buffer = cv2.imencode('.png', img_resized)
        buf = io.BytesIO(buffer)
        return send_file(buf, mimetype='image/png')

    except Exception as e:
        print(f"Error: {e}")  
        return str(e), 500  

if __name__ == '__main__':
    app.run(debug=True)