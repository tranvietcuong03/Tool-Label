from flask import Flask, request, redirect, url_for, render_template, send_file, jsonify
import pandas as pd
from PIL import Image
import os
import json
import base64
import math

app = Flask(__name__)

df = pd.read_csv('user_id.csv')
accounts = df['user_id'].tolist()
userID = None
print(accounts)
def distribute_images():
    # Đọc dữ liệu từ file CSV
    df = pd.read_csv('user_id.csv')
    accounts = df['user_id'].tolist()
    
    # Thư mục chứa ảnh chưa được gán nhãn
    image_dir = config['paths']['unlabelled_image_folder']
    image_files = [f for f in os.listdir(image_dir) if os.path.isfile(os.path.join(image_dir, f))]
    
    num_users = len(accounts)
    num_images = len(image_files)
    
    if num_users == 0:
        raise ValueError("No user IDs found in CSV.")
    
    # Nếu số lượng ảnh ít hơn số người dùng, gán tất cả ảnh cho người dùng đầu tiên
    if num_images < num_users:
        user_folder = os.path.join(image_dir, accounts[0])
        os.makedirs(user_folder, exist_ok=True)
        
        for image_file in image_files:
            src_path = os.path.join(image_dir, image_file)
            dest_path = os.path.join(user_folder, image_file)
            os.rename(src_path, dest_path)
    else:
        # Phân phối đều ảnh cho mỗi người dùng
        images_per_user = math.floor(num_images / num_users)
        remainder = num_images % num_users

        for idx, user_id in enumerate(accounts):
            user_folder = os.path.join(image_dir, user_id)
            os.makedirs(user_folder, exist_ok=True)
            
            if idx < num_users - 1:
                # Phân phối đều ảnh cho mỗi user trừ người cuối
                start_index = idx * images_per_user
                end_index = start_index + images_per_user
            else:
                # Người dùng cuối nhận số ảnh còn lại
                start_index = idx * images_per_user
                end_index = start_index + images_per_user + remainder
            
            for image_file in image_files[start_index:end_index]:
                src_path = os.path.join(image_dir, image_file)
                dest_path = os.path.join(user_folder, image_file)
                os.rename(src_path, dest_path)

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
    global userID
    if user_id in accounts:
        userID = user_id
        # Phân phối ảnh vào các thư mục con nếu chưa làm
        distribute_images()
        return render_template('home.html', user_id=user_id)
    else:
        return "User ID not found", 404


with open('static/config.json', 'r') as config_file:
    config = json.load(config_file)

all_object_polygon = []

image_dir = config['paths']['unlabelled_image_folder']
image_files = [f for f in os.listdir(image_dir)]

def fetch_image_path(current_image_index):
    global userID
    if userID is None:
        raise ValueError("User ID is not set.")
    
    user_image_dir = os.path.join(config['paths']['unlabelled_image_folder'], userID)
    image_files = [f for f in os.listdir(user_image_dir) if os.path.isfile(os.path.join(user_image_dir, f))]
    
    if current_image_index < len(image_files):
        return os.path.join(user_image_dir, image_files[current_image_index])
    return None 

@app.route('/get-image-path/<int:current_image_index>', methods=['POST'])
def get_image_path(current_image_index):
    global userID
    image_path = fetch_image_path(current_image_index)
    if image_path:
        return jsonify({"image_path": image_path})
    return jsonify({"error": "No more images."}), 404


@app.route('/<user_id>/submit-polygons', methods=['POST'])
def submit_polygons(user_id):
    global userID, all_object_polygon
    data = request.get_json()
    all_object_polygon = data.get('all_points', [])
    idx = data.get('current_idx', 0)
    user_id = userID
    data = request.json
    if user_id not in accounts:
        return ('User not authorized', 403)
    try:
        save_polygons(user_id, idx)
        return ('', 204)
    except Exception as e:
        print(f"Error saving polygons: {e}")
        return ('Failed to submit', 500)

def save_polygons(user_id, idx):
    global all_object_polygon, imageWidth, imageHeight
    
    image_path = fetch_image_path(idx)

    if not image_path:
        raise ValueError("No image path found")

    image_name = os.path.splitext(os.path.basename(image_path))[0]

    # Đọc và mã hóa hình ảnh thành chuỗi base64
    with open(image_path, "rb") as img_file:
        base64_string = base64.b64encode(img_file.read()).decode('utf-8')

    # Lưu dữ liệu JSON
    json_save_dir = os.path.join(config['paths']['labelled_image_folder'], user_id)
    os.makedirs(json_save_dir, exist_ok=True)
    json_file_path = os.path.join(json_save_dir, f"{image_name}.json")

    with Image.open(image_path) as img:
        imageWidth, imageHeight = img.size 
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

    image_relative_path = os.path.join(user_id, f"{image_name}.json")

    # Cập nhật hoặc thêm thông tin vào DataFrame
    if user_id in df['user_id'].values:
        # Nếu user_id đã tồn tại, cập nhật đường dẫn cho user_id đó
        df.loc[df['user_id'] == user_id, 'path_labelled_file'] = image_relative_path
    else:
        # Thêm dòng mới nếu user_id không tồn tại
        df = pd.concat([df, pd.DataFrame([{'user_id': user_id, 'path_labelled_file': image_relative_path}])], ignore_index=True)

    # Lưu DataFrame vào file CSV
    df.to_csv(csv_file_path, index=False)
    all_object_polygon = []


if __name__ == '__main__':
    app.run(host='0.0.0.0')