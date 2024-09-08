from flask import Flask, request, redirect, url_for, render_template, send_file
import pandas as pd
import cv2
import io

app = Flask(__name__)

df = pd.read_csv('user_id.csv')
accounts = df['user_id'].tolist()

@app.route('/')
def navigate():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user_id = request.form.get('user_id')
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

scale = 1
object_points = []
center_x, center_y = None, None

@app.route('/get-image')
def get_image():
    return send_file(generate_image(), mimetype='image/png')

@app.route('/zoom', methods=['POST'])
def zoom():
    global scale, center_x, center_y
    data = request.json
    zoom_in = data.get('zoom_in', True)
    mouse_x = data.get('x', None)
    mouse_y = data.get('y', None)

    if zoom_in:
        scale *= 1.2
    else:
        scale /= 1.2
    if mouse_x is not None and mouse_y is not None:
        center_x, center_y = mouse_x, mouse_y

    return ('', 204)

@app.route('/draw', methods=['POST'])
def draw():
    global object_points
    points = request.json.get('points')
    if points:
        object_points.append(points)
    return ('', 204)

def generate_image():
    global scale, center_x, center_y, object_points

    img = cv2.imread('static/unlable_image/image1.jpg')
    h, w, _ = img.shape

    if center_x is None:
        center_x = w / 2
    if center_y is None:
        center_y = h / 2

    zoom_width = w / scale
    zoom_height = h / scale

    x_min = max(int(center_x - zoom_width / 2), 0)
    x_max = min(int(center_x + zoom_width / 2), w)
    y_min = max(int(center_y - zoom_height / 2), 0)
    y_max = min(int(center_y + zoom_height / 2), h)

    # Crop the zoomed region
    zoomed_img = img[y_min:y_max, x_min:x_max]

    # Draw the points
    for points in object_points:
        if len(points) > 1:
            for i in range(len(points) - 1):
                start_point = (int(points[i]['x'] - x_min), int(points[i]['y'] - y_min))
                end_point = (int(points[i + 1]['x'] - x_min), int(points[i + 1]['y'] - y_min))
                cv2.line(zoomed_img, start_point, end_point, (0, 255, 0), 2) 
    
    # Convert image to PNG format for Flask
    _, buffer = cv2.imencode('.png', zoomed_img)
    buf = io.BytesIO(buffer)

    return buf

if __name__ == '__main__':
    app.run(debug=True)
