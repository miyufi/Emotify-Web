from flask import Flask, render_template, url_for, redirect, session, request
from flask_socketio import SocketIO, emit
import io
from PIL import Image
import base64
import cv2
import numpy as np
from flask_cors import CORS
from engineio.payload import Payload
import os
from flask_session import Session
import spotipy
import uuid
from spotipy.oauth2 import SpotifyClientCredentials
import random
import time
from object_detection import *

MODEL = cv2.dnn.readNet(
    'models/yolov4.weights',
    'models/yolov4.cfg'
)

count = 0

os.environ["SPOTIPY_CLIENT_ID"] = "422d3c4bafca45dca6bc25c771adfd0b"
os.environ["SPOTIPY_CLIENT_SECRET"] = "8fa3b252caae42b48b47fb794324507d"
os.environ["SPOTIPY_REDIRECT_URI"] = "https://www.emotify.online"

Payload.max_decode_packets = 2048

app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(64)
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_FILE_DIR'] = './.flask_session/'
Session(app)
socketio = SocketIO(app, manage_session=False, cors_allowed_origins='*')

caches_folder = './.spotify_caches/'
if not os.path.exists(caches_folder):
    os.makedirs(caches_folder)


def session_cache_path():
    return caches_folder + session.get('uuid')


def change(emotion):
    emotion_dict = {
        "anger": ["rock", "pop", "chill"],
        "disgust": ["0JQ5DAqbMKFQIL0AXnG5AK", "toplists", "mood", "pop"],
        "fear": ["0JQ5DAqbMKFCuoRTxhYWow", "country"],
        "happy": ["mood", "party", "0JQ5DAqbMKFQIL0AXnG5AK", "toplists"],
        "neutral": ["0JQ5DAqbMKFQIL0AXnG5AK", "toplists"],
        "sad": ["opm", "0JQ5DAqbMKFAUsdyVjCQuL", "in_the_car", "mood", "chill"],
        "surprised": ["rock", "0JQ5DAqbMKFQIL0AXnG5AK", "toplists"],
    }
    emotion = emotion_dict.get(emotion)
    random.shuffle(emotion)
    return emotion[0]


def readable(category):
    category_dict = {
        "0JQ5DAqbMKFCuoRTxhYWow": "sleep",
        "0JQ5DAqbMKFQIL0AXnG5AK": "trending",
        "0JQ5DAqbMKFAUsdyVjCQuL": "romance",
        "chill": "chill",
        "jazz": "jazz",
        "country": "country",
        "mood": "mood",
        "party": "party",
        "toplists": "toplists",
        "opm": "opm",
        "in_the_car": "in_the_car",
        "rock": "rock",
        "pop": "pop",
    }
    return category_dict.get(category)


@app.route('/')
def index():
    if not session.get('uuid'):
        session['uuid'] = str(uuid.uuid4())

    cache_handler = spotipy.cache_handler.CacheFileHandler(
        cache_path=session_cache_path())
    auth_manager = spotipy.oauth2.SpotifyOAuth(scope='user-read-currently-playing playlist-modify-private',
                                               cache_handler=cache_handler,
                                               show_dialog=True)

    if request.args.get("code"):
        auth_manager.get_access_token(request.args.get("code"))
        return redirect('/')

    if not auth_manager.validate_token(cache_handler.get_cached_token()):
        auth_url = auth_manager.get_authorize_url()
        return render_template('signin.html', auth_url=auth_url)
    spotify = spotipy.Spotify(auth_manager=auth_manager)

    if session.get('emotion') is None:
        try:
            artist = spotify.artist(artist_id="0gxyHStUsqpMadRV0Di1Qt")
        except:
            return render_template('noaccess.html')

        return redirect('/detect')

    emo = session.get('emotion')
    category = change(str(session.get('emotion')))
    try:
        results = spotify.category_playlists(
            category_id=category, country="PH", limit="30")
    except:
        return render_template('noaccess.html')

    playlists = []
    for idx, playlist in enumerate(results['playlists']['items']):
        playlists.append((playlist['name'], playlist['id']))
    random.shuffle(playlists)
    try:
        dp = spotify.me()["images"][0]["url"]
    except:
        dp = "https://www.oseyo.co.uk/wp-content/uploads/2020/05/empty-profile-picture-png-2-2.png"
    return render_template('home.html', emo=emo, category=readable(category), name=spotify.me()["display_name"], dp=dp, playlists=playlists)


@app.route('/detect', methods=['POST', 'GET'])
def detect():
    cache_handler = spotipy.cache_handler.CacheFileHandler(
        cache_path=session_cache_path())
    auth_manager = spotipy.oauth2.SpotifyOAuth(scope='user-read-currently-playing playlist-modify-private',
                                               cache_handler=cache_handler,
                                               show_dialog=True)
    if not auth_manager.validate_token(cache_handler.get_cached_token()):
        return redirect('/')
    spotify = spotipy.Spotify(auth_manager=auth_manager)

    try:
        artist = spotify.artist(artist_id="0gxyHStUsqpMadRV0Di1Qt")
    except:
        return redirect('/')

    return render_template('detect.html')


@app.route('/sign_out')
def sign_out():
    try:
        os.remove(session_cache_path())
        session.clear()
    except OSError as e:
        print("Error: %s - %s." % (e.filename, e.strerror))
    return redirect('/')


def readb64(base64_string):
    idx = base64_string.find('base64,')
    base64_string = base64_string[idx+7:]

    sbuf = io.BytesIO()

    sbuf.write(base64.b64decode(base64_string, ' /'))
    pimg = Image.open(sbuf)

    return cv2.cvtColor(np.array(pimg), cv2.COLOR_RGB2BGR)


@socketio.on('catch-frame')
def catch_frame(data):
    emit('response_back', data)


def bbox(frame):
    cv2.rectangle(frame, (session.get('x'), session.get('y')), (session.get(
        'x') + session.get('w'), session.get('y') + session.get('h')), session.get('color'), 2)
    cv2.putText(frame, session.get('emotion'), (session.get('x'), session.get(
        'y') - 5), cv2.FONT_HERSHEY_PLAIN, 2, session.get('color'), 2)
    cv2.putText(frame, session.get('percent'), (session.get('x'), session.get(
        'y') - 25), cv2.FONT_HERSHEY_PLAIN, 2, session.get('color'), 2)
    return frame


@socketio.on('image')
def image(data_image):
    global count
    frame = (readb64(data_image))

    count += 1
    if count > 50 and session.get('emotion') != "No label":
        count = 0
        emit('redirect', {'url': url_for('index')})
        time.sleep(5)
    elif count % 3 == 0:
        detectObj(frame)
        try:
            session['emotion'], session['x'], session['y'], session['w'], session['h'], session['color'], session[
                'percent'] = detectObj.lbl, detectObj.x, detectObj.y, detectObj.w, detectObj.h, detectObj.clr, detectObj.percent
        except:
            pass
        if session.get('emotion') != "No label":
            frame = bbox(frame)

    else:
        try:
            if session.get('emotion') != "No label":
                frame = bbox(frame)
        except:
            pass

    imgencode = cv2.imencode('.jpeg', frame, [cv2.IMWRITE_JPEG_QUALITY, 40])[1]

    stringData = base64.b64encode(imgencode).decode('utf-8')
    b64_src = 'data:image/jpeg;base64,'
    stringData = b64_src + stringData

    emit('response_back', stringData)


@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404


@app.errorhandler(500)
def internal_server_error(e):
    return render_template('404.html'), 500


if __name__ == '__main__':
    socketio.run(app)
