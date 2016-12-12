import configparser
import os
from datetime import datetime

import bcrypt
from flask import Flask, jsonify
from flask import redirect
from flask import render_template
from flask import request
from flask import session
from flask import url_for
from flask.ext.pymongo import PyMongo
from flask_bootstrap import Bootstrap
from flask_moment import Moment

app = Flask(__name__)

app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'this_should_be_configured')

bootstrap = Bootstrap(app)
moment = Moment(app)

config = configparser.ConfigParser()
config.read('credential.ini')
app.config['MONGO_DBNAME'] = 'meal_you'
# Database option 1, remote mlab deployment
app.config['MONGO_URI'] = 'mongodb://python:class@ds033086.mlab.com:33086/meal_you'
# app.config['MONGO_URI'] = config['database']['uri']
# Database option 2, localhost:27017
# app.config['MONGO_URI'] = 'mongodb://localhost:27017/meal_you'
mongo = PyMongo(app)


@app.route('/stores', methods=['GET'])
@app.route('/login', methods=['GET'])
@app.route('/home', methods=['GET'])
@app.route('/', methods=['GET'])
def index():
    if 'username' in session:
        user = mongo.db.user
        the_user = user.find_one({'username': session['username']})
        order = []
        if the_user['order']:
            order = the_user['order']
        order.reverse()
        rest_user = mongo.db.restuser
        stores = []
        for q in rest_user.find():
            stores.append(q['username'])
        return render_template('home.html', current_time=datetime.utcnow(), session=session, stores=stores, order=order)
    return render_template('login.html')


@app.route('/login', methods=['POST'])
def login():
    user = mongo.db.user
    username = request.form['username']
    password = request.form['password']
    login_user = user.find_one({'username': username})
    if login_user:
        # if bcrypt.checkpw(password.encode('utf-8'), login_user['password']):
        if bcrypt.hashpw(password.encode('utf-8'), login_user['password']) == login_user['password']:
            session['username'] = username
    return redirect(url_for('index'))


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        user = mongo.db.user
        username = request.form['username']
        password = request.form['password']
        existing_user = user.find_one({'username': username})
        if existing_user is None:
            hashpass = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
            user.insert({'username': username, 'password': hashpass, 'bag': {}, 'order': []})
            session['username'] = username
            return redirect(url_for('index'))
        return 'That username already exists!'
    return render_template('register.html')


@app.route('/stores/<storetitle>', methods=['GET'])
def get_the_store(storetitle):
    username = session['username']
    if username:
        rest_user = mongo.db.restuser
        current_user = rest_user.find_one({'username': storetitle})
        meals = current_user['meals']
        return render_template('store_detail.html', session=session, meals=meals, storetitle=storetitle)
    else:
        return redirect(url_for('index'))


@app.route('/<storetitle>/<mealtitle>', methods=['GET'])
def get_the_meal_to_buy(storetitle, mealtitle):
    username = session['username']
    if username:
        rest_user = mongo.db.restuser
        current_rest_user = rest_user.find_one({'username': storetitle})
        meals = current_rest_user['meals']
        the_meal = meals[mealtitle]
        return render_template('meal_detail_to_buy.html', session=session, meals=meals, mealtitle=mealtitle,
                               meal=the_meal, storetitle=storetitle)


@app.route('/bag', methods=['POST'])
def add_to_bag():
    username = session['username']
    storetitle = request.form['storetitle']
    mealtitle = request.form['mealtitle']
    mealname = request.form['mealname']
    price = request.form['price']
    quantity = request.form['quantity']
    user = mongo.db.user
    current_user = user.find_one({'username': username})
    meals = dict()
    stores = dict()
    bag = dict()
    if 'bag' in current_user:
        bag = current_user['bag']
    if storetitle in bag:
        stores = bag[storetitle]
    if mealtitle in stores:
        meals = stores[mealtitle]
    meals["quantity"] = int(quantity)
    meals["mealname"] = mealname
    meals["price"] = price
    stores[mealtitle] = meals
    bag[storetitle] = stores
    # Can not use this one_step code, have to do it one by one, don't know why
    # bag[storetitle][mealtitle] = int(quantity)
    user.update({'_id': current_user['_id']}, {'$set': {'bag': bag}})
    return redirect(url_for('index'))


@app.route('/bag', methods=['GET'])
def go_to_bag():
    if 'username' in session:
        user = mongo.db.user
        current_user = user.find_one({'username': session['username']})
        bag = current_user['bag']
        return render_template('bag.html', current_time=datetime.utcnow(), session=session, bag=bag)
    return render_template('login.html')


@app.route('/place_order', methods=['POST', 'GET'])
def place_order():
    username = session['username']
    if request.method == 'POST':
        user = mongo.db.user
        rest_user = mongo.db.restuser
        current_user = user.find_one({'username': username})
        data = request.json
        order_id = str(datetime.now())
        order_id = order_id.replace('-', '').replace(' ', '').replace(':', '').replace('.', '')
        for key, value in data.items():
            the_rest_user = rest_user.find_one({'username': key})
            rest_order = dict()
            rest_order['customer'] = username
            rest_order['orderid'] = order_id
            rest_order['meal'] = value
            rest_user.update({'_id': the_rest_user['_id']}, {'$addToSet': {'order': rest_order}})

        customer_order = dict()
        customer_order['orderid'] = order_id
        customer_order['meal'] = data
        user.update({'_id': current_user['_id']}, {'$addToSet': {'order': customer_order}})

        new_bag = {}
        user.update({'_id': current_user['_id']}, {'$set': {'bag': new_bag}})

        success = True
        return jsonify(success=success)
    else:
        return redirect(url_for('index'))


@app.route('/orders/<orderid>', methods=['GET'])
def order_detail_for_customer(orderid):
    username = session['username']

    user = mongo.db.user
    the_user = user.find_one({'username': username})
    order = the_user['order']
    the_order = {}

    for item in order:
        if item['orderid'] == orderid:
            the_order = item
            break

    return render_template('order_detail_for_customer.html', username=username, order=the_order)


@app.route('/logout', methods=['GET'])
def logout():
    if 'rest_username' in session:
        session.clear()
        return redirect(url_for('rest_index'))
    elif 'username' in session:
        session.clear()
    return redirect(url_for('index'))


@app.route('/rest/login', methods=['GET'])
@app.route('/rest/home', methods=['GET'])
@app.route('/rest/', methods=['GET'])
@app.route('/rest', methods=['GET'])
def rest_index():
    if 'rest_username' in session:
        rest_user = mongo.db.restuser
        current_user = rest_user.find_one({'username': session['rest_username']})
        meals = current_user['meals']
        order = []
        if current_user['order']:
            order = current_user['order']
        order.reverse()
        return render_template('rest_home.html', current_time=datetime.utcnow(), session=session, meals=meals,
                               order=order)
    return render_template('rest_login.html')


@app.route('/rest/login', methods=['POST'])
def rest_login():
    rest_user = mongo.db.restuser
    username = request.form['username']
    password = request.form['password']
    login_user = rest_user.find_one({'username': username})
    if login_user:
        if bcrypt.hashpw(password.encode('utf-8'), login_user['password']) == login_user['password']:
            session['rest_username'] = username
    return redirect(url_for('rest_index'))


@app.route('/rest/register', methods=['GET', 'POST'])
def rest_register():
    if request.method == 'POST':
        rest_user = mongo.db.restuser
        username = request.form['username']
        password = request.form['password']
        meals = {}
        existing_user = rest_user.find_one({'username': username})
        if existing_user is None:
            hashpass = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
            rest_user.insert({'username': username, 'password': hashpass, 'meals': meals, 'order': []})
            session['rest_username'] = username
            return redirect(url_for('rest_index'))
        return render_template('rest_register.html')
    return render_template('rest_register.html')


@app.route('/rest/add_meal', methods=['GET', 'POST'])
def add_meal():
    username = session['rest_username']
    if username:
        if request.method == 'POST':
            rest_user = mongo.db.restuser
            current_user = rest_user.find_one({'username': username})
            meals = {}
            if 'meals' in current_user:
                meals = current_user['meals']
            mealtitle = request.form['mealtitle']
            mealname = request.form['mealname']
            price = request.form['price']
            detail = {'name': mealname, 'price': price}
            if mealtitle in meals:
                return 'meal exists, please choose a new meal title'
            meals[mealtitle] = detail
            rest_user.update({'_id': current_user['_id']}, {'$set': {'meals': meals}})
            return redirect(url_for('rest_index'))
        else:
            return render_template('add_meal.html', current_time=datetime.utcnow(), session=session)
    else:
        return redirect(url_for('rest_index'))


@app.route('/rest/meals/<mealtitle>', methods=['POST'])
def update_meal(mealtitle):
    username = session['rest_username']
    if username:
        rest_user = mongo.db.restuser
        current_user = rest_user.find_one({'username': username})
        meals = {}
        if 'meals' in current_user:
            meals = current_user['meals']
        mealtitle = mealtitle
        mealname = request.form['mealname']
        price = request.form['price']
        detail = {'name': mealname, 'price': price}
        if mealtitle in meals:
            meals[mealtitle] = detail
            rest_user.update({'_id': current_user['_id']}, {'$set': {'meals': meals}})
    return redirect(url_for('rest_index'))


@app.route('/rest/meals/<mealtitle>', methods=['GET'])
def get_the_meal(mealtitle):
    username = session['rest_username']
    if username:
        rest_user = mongo.db.restuser
        current_user = rest_user.find_one({'username': username})
        meals = current_user['meals']
        the_meal = {}
        if mealtitle in meals:
            the_meal = meals[mealtitle]
        return render_template('meal_detail.html', session=session, meal=the_meal, mealtitle=mealtitle)


@app.route('/rest/meals/<mealtitle>/delete', methods=['POST'])
def delete_the_meal(mealtitle):
    username = session['rest_username']
    if username:
        rest_user = mongo.db.restuser
        current_user = rest_user.find_one({'username': username})
        meals = current_user['meals']
        del meals[mealtitle]
        rest_user.update({'_id': current_user['_id']}, {'$set': {'meals': meals}})
        return redirect(url_for('rest_index'))


@app.route('/rest/orders/<orderid>', methods=['GET'])
def order_detail_for_rest(orderid):
    rest_username = session['rest_username']
    rest_user = mongo.db.restuser
    the_user = rest_user.find_one({'username': rest_username})
    order = the_user['order']
    the_order = {}
    for item in order:
        if item['orderid'] == orderid:
            the_order = item
            break
    return render_template('order_detail_for_rest.html', username=rest_username, order=the_order)


if __name__ == '__main__':
    app.debug = True
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
