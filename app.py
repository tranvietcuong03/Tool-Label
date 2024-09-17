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

# Thay đổi image_dir để phù hợp với cấu trúc mới
def update_image_dir(user_id):
    base_dir = config['paths']['unlabelled_image_folder']
    user_dir = os.path.join(base_dir, 'unlabel-image', user_id)
    os.makedirs(user_dir, exist_ok=True)

    # Lấy danh sách ảnh
    image_files = [f for f in os.listdir(base_dir) if os.path.isfile(os.path.join(base_dir, f))]

    # Phân phối ảnh cho người dùng
    num_users = len(accounts)
    for index, image_file in enumerate(image_files):
        user_index = index % num_users
        user = accounts[user_index]
        user_folder = os.path.join(base_dir, 'unlabel-image', user)
        os.makedirs(user_folder, exist_ok=True)
        new_image_path = os.path.join(user_folder, f'image_{index+1}.jpg')
        os.rename(os.path.join(base_dir, image_file), new_image_path)

image_dir = update_image_dir(userID)  # Cập nhật thư mục ảnh cho người dùng
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

    # Đọc và mã hóa hình ảnh thành chuỗi base64
    with open(image_path, "rb") as img_file:
        base64_string = base64.b64encode(img_file.read()).decode('utf-8')

    # Lưu dữ liệu JSON
    json_save_dir = os.path.join(config['paths']['labelled_image_folder'], 'unlabel-image', user_id)
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

    # Cập nhật file CSV
    csv_file_path = config['paths']['csv_file_path']
    if not os.path.exists(csv_file_path):
        # Tạo DataFrame với các cột cần thiết nếu file CSV chưa tồn tại
        df = pd.DataFrame(columns=['user_id', 'path_labelled_file'])
    else:
        # Đọc file CSV nếu nó đã tồn tại
        df = pd.read_csv(csv_file_path)

    image_relative_path = os.path.join('unlabel-image', user_id, f"{image_name}.json")

    # Cập nhật hoặc thêm thông tin vào DataFrame
    if user_id in df['user_id'].values:
        # Nếu user_id đã tồn tại, cập nhật đường dẫn cho user_id đó
        df.loc[df['user_id'] == user_id, 'path_labelled_file'] = image_relative_path
    else:
        # Thêm dòng mới nếu user_id không tồn tại
        df = pd.concat([df, pd.DataFrame([{'user_id': user_id, 'path_labelled_file': image_relative_path}])], ignore_index=True)

    # Lưu DataFrame vào file CSV
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
                    cv2.line(img_resized, (prev_x_resized, prev_y_resized), (x_resized, y_resized), color, 2)

    _, img_encoded = cv2.imencode('.png', img_resized)
    return io.BytesIO(img_encoded.tobytes())

if __name__ == '__main__':
    app.run(debug=True)
