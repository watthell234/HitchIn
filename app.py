from datetime import datetime
import random
import string
import requests

from flask import Flask, request, jsonify, abort, request
from flask_sqlalchemy import SQLAlchemy
from flask_jwt import JWT, jwt_required, current_identity
from flask_socketio import SocketIO, send, emit, join_room, leave_room, close_room, rooms, disconnect
from flask_heroku import Heroku

app = Flask(__name__)
app.config['SECRET_KEY'] = 'super-secret'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
# app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://127.0.0.1/hitchin'
heroku = Heroku(app)
db = SQLAlchemy(app)

from models import *

# Authentication
def authenticate(phoneNumber, password):

    user = db.session.query(User).filter(User.phone_number == phoneNumber).first()
    if user and user.check_password(password):
        return user

def identity(payload):
    user_id = payload['identity']
    return db.session.query(User).filter(User.id == user_id).scalar()

jwt = JWT(app, authenticate, identity)

#Socket
socketio = SocketIO(app)

# HTTP Routes
@app.route("/")
def index():
    return "<h1>Welcome to HitchIn</h1>"

@app.route("/sign-up", methods=['POST'])
def sign_up():

    phone_number = request.json.get('phoneNumber', None)
    first_name = request.json.get('firstName', None)
    last_name = request.json.get('lastName', None)
    email = request.json.get('email', None)
    password = request.json.get('password', None)
    is_driver = request.json.get('checked', None)

    #Check if the phone number exists
    if not phone_number_exists(phone_number):
        #Check if the email exists
        if not email_exists(email):
            new_user = User(phone_number, first_name, last_name, email, is_driver)
            new_user.set_password(password)
            db.session.add(new_user)
            db.session.commit()
            created_user = db.session.query(User).filter(User.phone_number == phone_number).scalar()
            request_token = requests.post('https://hitchin-server.herokuapp.com/auth',
                        json={"username": str(phone_number), "password": password})
            # request_token = requests.post('http://127.0.0.1:5000/auth',
            #             json={"username": str(phone_number), "password": password})

            return jsonify({
                'status': '200',
                'message': 'Successfully Signed Up',
                'id': str(created_user.id),
                'auth_token': request_token.json()['access_token']
            })
        #The email already exists
        else:
            abort(401, description='email_exists')
    #Phone number already exists
    else:
        abort(401, description='phone_number_exists')

def email_exists(email):

    exists = False
    email_exists = db.session.query(User).filter(User.email == email).scalar()

    if email_exists:
        exists = True

    return exists

def phone_number_exists(phone_number):

    exists = False
    phone_number_exists = db.session.query(User).filter(User.phone_number == phone_number).scalar()

    if phone_number_exists:
        exists = True

    return exists

#return pickup spots and dropoff spots in two lists in json
@app.route("/routes", methods=['GET'])
def get_routes():
    pickup_list = []
    dropoff_list = []
    pickup_rows = db.session.query(PickUpLocations).all()
    dropoff_rows = db.session.query(DropOffLocations).all()

    for pickup in pickup_rows:
        pickup_list.append({'location_name': pickup.location_name, 'latitude': pickup.latitude, 'longitude': pickup.longitude})

    for dropoff in dropoff_rows:
        dropoff_list.append({'location_name': dropoff.location_name, 'latitude': dropoff.latitude, 'longitude': dropoff.longitude})

    return jsonify({
        'status': '200',
        'pickup_list': pickup_list,
        'dropoff_list': dropoff_list
    })

@app.route("/car_list", methods=['POST'])
def get_car_list():

    owner_id = request.json.get('userID', None)

    car_list = []
    car_rows = db.session.query(Cars).filter(Cars.owner_id == owner_id).all()

    #only returns license plate for now
    for car in car_rows:
        car_list.append({"car_id": car.id, "license_plate": car.license_plate})

    return jsonify({
        'status': '200',
        'car_list': car_list
    })


@app.route("/login", methods=['POST'])
def login():
    phone_number = request.json.get('phoneNumber', None)
    password = request.json.get('password', None)
    #Check if the phone number exists first.
    if phone_number_exists(phone_number):
        #Now authenticate.
        logged_user = authenticate(phone_number, password)

        request_token = requests.post('https://hitchin-server.herokuapp.com/auth',
            json={"username": str(phone_number), "password": password})

        # request_token = requests.post('http://127.0.0.1:5000/auth',
        #     json={"username": str(phone_number), "password": password})

        if logged_user:
            return jsonify({
                'status': '200',
                'message': 'Successfully Logged in',
                'id': logged_user.id,
                'auth_token': request_token.json()['access_token']
            })
        #if authentication fails, abort with 403.
        else:
            abort(403)
    #if phone_number doesn't exist, abort with 401.
    else:
        abort(401)


@app.route("/create_car", methods=['POST'])
@jwt_required()
def create_car():

    letters = string.ascii_letters
    qr_string = ''.join(random.choice(letters) for i in range(18))
    owner_id = request.json.get('userID', None)
    car_maker = request.json.get('car_maker', None)
    car_year = request.json.get('car_year', None)
    license_plate = request.json.get('car_plate', None)
    ezpass_tag = request.json.get('ezpass_tag', None)

    #check if the license plate already exists.
    #If not, proceed.
    if not car_exists(license_plate):
        car = Cars(qr_string, owner_id, car_maker, car_year, license_plate, ezpass_tag)
        db.session.add(car)
        db.session.commit()
        created_car_id = db.session.query(Cars).filter(Cars.license_plate == license_plate).scalar()

        return jsonify({
            'status': '200',
            'message': 'Successfully registered car',
            'car_id': str(created_car_id.id),
            'qr_id': qr_string
        })

    #if it does, abort with 401.
    else:
        abort(401)

def car_exists(car_plate):

    exists = False
    car_plate_exists = db.session.query(Cars).filter(Cars.license_plate == car_plate).scalar()

    if car_plate_exists:
        exists = True

    return exists

@app.route("/checkin", methods=['POST'])
@jwt_required()
def checkin():
    car_qr = request.json.get('carQr', None)
    user_id = request.json.get('userId', None)
    try:
        logged_car = db.session.query(Cars).filter(Cars.qr_string == car_qr).first()
        checkin = Trips(None, 2, logged_car.id)
        db.session.add(checkin)
        db.session.commit()
        return jsonify({
            'status': '200',
            'message': 'Successfully sluggin'
        })
    except:
        abort(404)


@app.route("/pooltrips/<int:car_id>", methods=['GET', 'PUT'])
@jwt_required()
def pool_trips(car_id):

    if request.method == 'GET':

        passng_checked = (db.session.query(Trips).filter(Trips.car == car_id, Trips.time_ended == None).all())
        passenger_count = len(passng_checked)
        return jsonify({
            'status': '200',
            'car_id': car_id,
            'slugs': passenger_count
        })
    if request.method == 'PUT':
        end_trip = db.session.query(Trips).filter(Trips.car == car_id, Trips.time_ended == None).all().update().values({Trips.time_ended: datetime.utcnow})
        db.session.commit()
        return jsonify({
            'status': '200'
        })


# Socket Route
@socketio.on('event')
def test_message(message):
    print("Button was pressed")
    json = {'data': message + " from server"}
    emit('events', json)

#DRIVER RELATED
@socketio.on('register_trip')
def handle_register_trip(data):
    userID = data['userID']
    carID = data['carID']
    pickup = data['pickup']
    destination = data['dropoff']
    session_id = data['session_id']
    car_list = []
    driver_name = ''

    print(datetime.now())
    print(userID)
    print(carID)
    car = db.session.query(Cars).filter(Cars.id == carID).scalar()
    print(car.qr_string)
    trip = Trips(userID, carID, pickup, destination, car.qr_string, session_id)
    db.session.add(trip)
    db.session.commit()

    driver = db.session.query(User).filter(User.id == trip.driver_id).scalar()

    trip_rows = db.session.query(Trips).filter(Trips.pickup == pickup).filter(Trips.active.is_(False)).all()

    #ASSUME EVERY TRIP'S CAR IS UNIQUE FOR NOW.
    for trip in trip_rows:
        car = db.session.query(Cars).filter(Cars.id == trip.car_id).scalar()
        car_list.append({'car_id': car.id, 'license_plate': car.license_plate, 'car_maker': car.car_make})

    print(car_list)
    print(pickup)

    emit('trip_id_' + carID, {'trip_id': trip.id, 'driver_name': driver.first_name + ' ' + driver.last_name}, to=request.sid)
    emit('updated_car_list_' + pickup.replace(" ", "_"), {'car_list': car_list}, broadcast=True)

@socketio.on('delete_trip')
def handle_delete_trip(data):
    tripID = data['tripID']
    pickup = data['pickup']
    car_list = []

    #dont think I need this, but I'll still get it anyway.
    dropoff = data['dropoff']

    print(tripID)
    #DOESN'T ALWAYS WORK? PROBABLY BECAUSE the client disconnects first before this line gets executed. Not sure.
    trip = db.session.query(Trips).filter(Trips.id == tripID).scalar()

    db.session.delete(trip)
    db.session.commit()

    #CASCADE DELETES ALL THE PASSENGERS ASSOCIATED WITH THE TRIP

    emit('trip_deleted', to=request.sid)

    trip_rows = db.session.query(Trips).filter(Trips.pickup == pickup).filter(Trips.active.is_(False)).all()

    #ASSUME EVERY TRIP'S CAR IS UNIQUE FOR NOW.
    for trip in trip_rows:
        car = db.session.query(Cars).filter(Cars.id == trip.car_id).scalar()
        car_list.append({'car_id': car.id, 'license_plate': car.license_plate, 'car_maker': car.car_make})

    print(car_list)
    print(pickup.replace(" ", "_"))
    emit('updated_car_list_' + pickup.replace(" ", "_"), {'car_list': car_list}, broadcast=True)

@socketio.on('start_trip')
def handle_start_trip(data):
    tripID = data['tripID']
    pickup = data['pickup']
    dropoff = data['dropoff']
    car_list = []

    print(tripID)
    trip = db.session.query(Trips).filter(Trips.session_id == request.sid).scalar()

    trip.active = True;
    db.session.commit()

    emit('start_trip', to=trip.session_id)

    trip_rows = db.session.query(Trips).filter(Trips.pickup == pickup).filter(Trips.active.is_(False)).all()

    #ASSUME EVERY TRIP'S CAR IS UNIQUE FOR NOW.
    for trip in trip_rows:
        print(trip.active)
        car = db.session.query(Cars).filter(Cars.id == trip.car_id).scalar()
        car_list.append({'car_id': car.id, 'license_plate': car.license_plate, 'car_maker': car.car_make})

    print(car_list)
    print(pickup.replace(" ", "_"))
    emit('updated_car_list_' + pickup.replace(" ", "_"), {'car_list': car_list}, broadcast=True)

#RIDER RELATED
#Emits a list of cars available at the pickup spot.
@socketio.on('init_ride')
def handle_init_ride(data):
    pickup = data['pickup']
    destination = data['dropoff']

    print(pickup)
    print(destination)

    car_list = []
    trip_rows = db.session.query(Trips).filter(Trips.pickup == pickup).all()

    for trip in trip_rows:
        car = db.session.query(Cars).filter(Cars.id == trip.car_id).scalar()
        car_list.append({'car_id': car.id, 'license_plate': car.license_plate, 'car_maker': car.car_make})

    print(car_list)

    emit('car_list_' + pickup.replace(" ", "_"), {'car_list': car_list})

# This is used to add people into carpool trip
@socketio.on('join_trip')
def handle_join_trip(data):

    qr_string = data['qr_string']
    userID = data['userID']
    passenger_list = []
    print(userID)

    #ASSUME THERE IS ONLY ONE CAR WITH THE QR_STRING AT A TIME IN TRIPS TABLE FOR NOW
    trip = db.session.query(Trips).filter(Trips.qr_string == qr_string).scalar()
    if trip:
        print(trip.id)
        print(trip.qr_string)
        print(trip.session_id)
        passenger = Passengers(userID, trip.id)
        db.session.add(passenger)
        db.session.commit()
        join_room(trip.session_id)
        print(rooms())

        #Update passenger information
        passenger_rows = db.session.query(Passengers).filter(Passengers.trip_id == trip.id).all()

        for passenger_row in passenger_rows:
            passenger = db.session.query(User).filter(User.id == passenger_row.user_id).scalar()
            passenger_list.append({'passenger_name': passenger.first_name + ' ' + passenger.last_name})

        print(passenger_list)

        driver = db.session.query(User).filter(User.id == trip.driver_id).scalar()

        emit('passenger_update', {'action': 'add', 'passenger_list': passenger_list}, to=trip.session_id)
        emit('join_trip_response_' + userID, {'success': 1, 'driver_name': driver.first_name + ' ' + driver.last_name, 'tripID': trip.id}, to=trip.session_id)
    else:
        emit('join_trip_response_' + userID, {'success': 0})

# This is used to have people exit the carpool trip
@socketio.on('leave_trip')
def handle_leave_trip(data):
    userID = data['userID']
    passenger_list = []

    passengers = db.session.query(Passengers).filter(Passengers.user_id == userID).all()
    trip = db.session.query(Trips).filter(Trips.id == passengers[0].trip_id).scalar()

    for passenger in passengers:
        db.session.delete(passenger)

    db.session.commit()

    #Update passenger information
    passenger_rows = db.session.query(Passengers).filter(Passengers.trip_id == trip.id).all()

    for passenger_row in passenger_rows:
        passenger = db.session.query(User).filter(User.id == passenger_row.user_id).scalar()
        passenger_list.append({'passenger_name': passenger.first_name + ' ' + passenger.last_name})

    print(passenger_list)

    emit('passenger_update', {'action': 'subtract', 'passenger_list': passenger_list}, to=trip.session_id)

    leave_room(trip.session_id)
    print(rooms())

#returns a list of passengers before updating.
@socketio.on('init_passenger_list')
def handle_init_passenger_list(data):
    tripID = data['tripID']
    passenger_list = []
    print(tripID)

    trip = db.session.query(Trips).filter(Trips.id == tripID).scalar()

    passenger_rows = db.session.query(Passengers).filter(Passengers.trip_id == trip.id).all()

    for passenger_row in passenger_rows:
        passenger = db.session.query(User).filter(User.id == passenger_row.user_id).scalar()
        passenger_list.append({'passenger_name': passenger.first_name + ' ' + passenger.last_name})

    emit('passenger_list', {'passenger_list': passenger_list}, to=trip.session_id)

# Closes the carpool room created
@socketio.on('close')
def on_leave(data):
    pool_id = data['pool_id']
    data = {'data': 'carpool: ' + str(pool_id) + ' is now over'}
    emit('completetrip', data, to=pool_id)
    close_room(pool_id)
    print(data)

@socketio.on('connect')
def handle_connect():
    json = {
    'sid': request.sid
    }
    emit('room_ID', json)

@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected')

if __name__ == '__main__':
    app.debug = True
    # app.run()
    socketio.run(app)
