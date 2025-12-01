from flask import Flask, render_template, request, redirect, url_for, flash, session, g
from flask_login import login_required, current_user, login_user, logout_user
from online_restaurant_db import Session, Users, Menu, Orders, Reservations
from flask_login import LoginManager
from datetime import datetime
import os
import uuid
import secrets
from geopy.distance import geodesic

app = Flask(__name__)

FILES_PATH = 'static/menu'

app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
app.config['MAX_FORM_MEMORY_SIZE'] = 1024 * 1024
app.config['MAX_FORM_PARTS'] = 500
app.config['SESSION_COOKIE_SAMESITE'] = 'Strict'
app.config['SECRET_KEY'] = '#cv)4v8w$*s5fk;6c!?y1?:?№4"0)#'

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

RESTAURANT_COORDS = (50.4501, 30.5234)

BOOKING_RADIUS_KM = 20

TABLE_NUM = {
    '1-2': 10,
    '3-4': 8,
    '4+': 4

}

@app.before_request
def generate_nonce():
    """Генерирует nonce перед каждым запросом и сохраняет его в 'g'."""
    g.nonce = secrets.token_urlsafe(16)


@login_manager.user_loader
def load_user(user_id):
    with Session() as session:
        user = session.query(Users).filter_by(id = user_id).first()
        if user:
            return user

@app.after_request
def apply_csp(response):
    if hasattr(g, 'nonce'):
        csp = (
            # базове правило
            f"default-src 'self'; "

            # скрипти (локальні, CDN, nonce)
            f"script-src 'self' 'nonce-{g.nonce}' https://cdn.jsdelivr.net; "

            # стилі (локальні, CDN)
            f"style-src 'self' https://fonts.googleapis.com https://cdn.jsdelivr.net 'unsafe-inline'; "

            # шрифти
            f"font-src 'self' https://fonts.gstatic.com; "

            # картинки
            f"img-src 'self' data:; "

            # ajax / sourcemaps
            f"connect-src 'self' https://cdn.jsdelivr.net; "

            # форма
            f"form-action 'self'; "

            # фрейми
            f"frame-ancestors 'none'; "

            # базовий url
            f"base-uri 'self'; "
        )
        response.headers["Content-Security-Policy"] = csp

    return response




@app.route('/')
@app.route('/home')
def home():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_hex(16)
    return render_template('home.html')

@app.route("/register", methods = ['GET','POST'])
def register():
    if request.method == 'POST':
        if request.form.get("csrf_token") != session["csrf_token"]:
            return "Запит заблоковано!", 403
        nickname = request.form['nickname']
        email = request.form['email']
        password = request.form['password']

        with Session() as cursor:
            if cursor.query(Users).filter_by(email=email).first() or cursor.query(Users).filter_by(nickname = nickname).first():
                flash('Користувач з таким email або нікнеймом вже існує!', 'danger')
                return render_template('register.html',csrf_token=session["csrf_token"])

            new_user = Users(nickname=nickname, email=email)
            new_user.set_password(password)
            cursor.add(new_user)
            cursor.commit()
            cursor.refresh(new_user)
            login_user(new_user)
            return redirect(url_for('home'))
    return render_template('register.html',csrf_token=session["csrf_token"])

@app.route("/login", methods = ["GET","POST"])
def login():
    if request.method == 'POST':
        if request.form.get("csrf_token") != session["csrf_token"]:
            return "Запит заблоковано!", 403

        nickname = request.form['nickname']
        password = request.form['password']

        with Session() as cursor:
            user = cursor.query(Users).filter_by(nickname = nickname).first()
            if user and user.check_password(password):
                login_user(user)
                return redirect(url_for('home'))

            flash('Неправильний nickname або пароль!', 'danger')

    return render_template('login.html', csrf_token=session["csrf_token"])

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


@app.route("/add_position", methods=['GET', 'POST'])
@login_required
def add_position():
    if current_user.nickname != 'Admin':
        return redirect(url_for('home'))

    if request.method == "POST":
        if request.form.get("csrf_token") != session["csrf_token"]:
            return "Запит заблоковано!", 403

        name = request.form['name']
        file = request.files.get('img')
        ingredients = request.form['ingredients']
        description = request.form['description']
        price = request.form['price']
        weight = request.form['weight']

        if not file or not file.filename:
            return 'Файл не вибрано або завантаження не вдалося'

        unique_filename = f"{uuid.uuid4()}_{file.filename}"
        output_path = os.path.join('static/menu', unique_filename)

        with open(output_path, 'wb') as f:
            f.write(file.read())

        with Session() as cursor:
            new_position = Menu(name=name, ingredients=ingredients, description=description,
                                price=price, weight=weight, file_name=unique_filename)
            cursor.add(new_position)
            cursor.commit()

        flash('Позицію додано успішно!')

    return render_template('add_position.html', csrf_token=session["csrf_token"])


@app.route('/menu')
def menu():
    with Session() as session:
        all_positions = session.query(Menu).filter_by(active = True).all()
    return render_template('menu.html',all_positions = all_positions)


@app.route('/position/<name>', methods = ['GET','POST'])
def position(name):
    if request.method == 'POST':

        if request.form.get("csrf_token") != session["csrf_token"]:
            return "Запит заблоковано!", 403

        position_name = request.form.get('name')
        position_num = request.form.get('num')
        if 'basket' not in session:
            basket = {}
            basket[position_name] = position_num
            session['basket'] = basket
        else:
            basket = session.get('basket')
            basket[position_name] = position_num
            session['basket'] = basket
        flash('Позицію додано у кошик!')
    with Session() as cursor:
        us_position = cursor.query(Menu).filter_by(active = True, name = name).first()
    return render_template('position.html', csrf_token=session["csrf_token"] ,position = us_position)


@app.route('/test_basket')
def test_basket():
    basket = session.get('basket', {})
    return basket


@app.route('/create_order', methods=['GET','POST'])
def create_order():
    basket = session.get('basket', {})

    # Рахуємо суму
    total_price = 0
    with Session() as cursor:
        for name, qty in basket.items():
            pos = cursor.query(Menu).filter_by(name=name).first()
            if pos:
                total_price += int(pos.price) * int(qty)

    if request.method == 'POST':
        if request.form.get("csrf_token") != session["csrf_token"]:
            return "Запит заблоковано!", 403

        if not current_user.is_authenticated:
            flash("Для оформлення замовлення необхідно бути зареєстрованим")
        else:
            if not basket:
                flash("Ваш кошик порожній")
            else:
                with Session() as cursor:
                    new_order = Orders(
                        order_list=basket,
                        order_time=datetime.now(),
                        user_id=current_user.id
                    )
                    cursor.add(new_order)
                    cursor.commit()
                    session.pop('basket')
                    cursor.refresh(new_order)
                    return redirect(f"/my_order/{new_order.id}")

    return render_template(
        'create_order.html',
        csrf_token=session["csrf_token"],
        basket=basket,
        total_price=total_price
    )



@app.route('/my_orders')
@login_required
def my_orders():
    with Session() as cursor:
        us_orders = cursor.query(Orders).filter_by(user_id = current_user.id).all()
    return render_template('my_orders.html', us_orders = us_orders)

@app.route('/my_order/<int:id>')
@login_required
def my_order(id):
    with Session() as cursor:
        us_order = cursor.query(Orders).filter_by(id = id).first()

        if not us_order or (us_order.user_id != current_user.id and current_user.nickname != 'Admin'):
            flash('Замовлення не знайдено або у вас немає доступу.', 'danger')
            return redirect(url_for('my_orders'))

        total_price = sum(int(cursor.query(Menu).filter_by(name=i).first().price) * int(cnt) for i, cnt in us_order.order_list.items())

        return render_template('my_order.html', order=us_order, total_price=total_price)

@app.route('/cancel_order/<int:id>', methods=['POST'])
@login_required
def cancel_order(id):
    if request.form.get('csrf_token') != session['csrf_token']:
        return 'Запит заблоковано!', 403

    with Session() as cursor:
        order = cursor.query(Orders).filter_by(id=id, user_id=current_user.id).first()

        if order:
            cursor.delete(order)
            cursor.commit()
            flash('Замовлення скасовано', 'success')
        else:
            flash('Не вдалося знайти замовлення або у вас немає прав', 'danger')

    return redirect(url_for('my_orders'))


@app.route('/reserved', methods=['GET', 'POST'])
@login_required
def reserved():
    message = None
    if request.method == "POST":
        if request.form.get("csrf_token") != session["csrf_token"]:
            return "Запит заблоковано!", 403

        table_type = request.form['table_type']
        reserved_time_start = request.form['time']
        user_latitude = request.form['latitude']
        user_longitude = request.form['longitude']

        if not user_longitude or not user_latitude:
            message = 'Ви не надали інформацію про своє місцезнаходження. Дозвольте доступ до геолокації.'
            return render_template('reserved.html', message=message, csrf_token=session["csrf_token"])

        user_cords = (float(user_latitude), float(user_longitude))
        distance = geodesic(RESTAURANT_COORDS, user_cords).km

        if distance > BOOKING_RADIUS_KM:
            message = f"Ви знаходитеся в {distance:.2f} км від нас. На жаль, ви за межами зони бронювання ({BOOKING_RADIUS_KM} км)."
            return render_template('reserved.html', message=message, csrf_token=session["csrf_token"])

        with Session() as cursor:
            reserved_check = cursor.query(Reservations).filter_by(type_table=table_type).count()
            user_reserved_check = cursor.query(Reservations).filter_by(user_id=current_user.id).first()

            if user_reserved_check:
                message = 'Можна мати лише одну активну бронь. Скасуйте стару, щоб створити нову.'
            elif reserved_check >= TABLE_NUM.get(table_type):
                message = 'На жаль, всі столики цього типу наразі заброньовані.'
            else:
                new_reserved = Reservations(
                    type_table=table_type,
                    time_start=reserved_time_start,
                    user_id=current_user.id
                )
                cursor.add(new_reserved)
                cursor.commit()
                message = f'Бронь на {reserved_time_start} столика на {table_type} людини успішно створено!'

        return render_template('reserved.html', message=message, csrf_token=session["csrf_token"])

    return render_template('reserved.html', csrf_token=session["csrf_token"], message=message, nonce=g.nonce)


@app.route('/reservations_check', methods=['GET', 'POST'])
@login_required
def reservations_check():
    if current_user.nickname != 'Admin':
        return redirect(url_for('home'))

    if request.method == 'POST':
        if request.form.get('csrf_token') != session['csrf_token']:
            return 'Запит заблоковано!', 403

        reserv_id = request.form['reserv_id']
        with Session() as cursor:
            reservation = cursor.query(Reservations).filter_by(id = reserv_id).first()
            if reservation:
                cursor.delete(reservation)
                cursor.commit()


    with Session() as cursor:
        all_reservations = cursor.query(Reservations).all()
        return render_template('reservations_check.html', all_reservations=all_reservations, csrf_token=session['csrf_token'])

@app.route('/menu_check', methods=['GET', 'POST'])
@login_required
def menu_check():
    if current_user.nickname != 'Admin':
        return redirect(url_for('home'))

    if request.method == "POST":
        if request.form.get("csrf_token") != session["csrf_token"]:
            return "Запит заблоковано!", 403

        position_id = request.form['pos_id']
        with Session() as cursor:
            position_obj = cursor.query(Menu).filter_by(id=position_id).first()

            if 'change_status' in request.form:
                position_obj.active = not position_obj.active
            elif 'delete_position' in request.form:
                cursor.delete(position_obj)
            cursor.commit()

    with Session() as cursor:
        all_positions = cursor.query(Menu).all()
    return render_template('check_menu.html', all_positions=all_positions, csrf_token=session["csrf_token"])


@app.route('/all_users')
@login_required
def all_users():
    if current_user.nickname != 'Admin':
        return redirect(url_for('home'))

    with Session() as cursor:
        all_users = cursor.query(Users).with_entities(Users.id, Users.nickname, Users.email).all()
        return render_template('all_users.html', all_users=all_users)


@app.route('/basket/update/<item_name>', methods=['POST'])
def update_basket(item_name):
    if request.form.get("csrf_token") != session["csrf_token"]:
        return "Запит заблоковано!", 403

    if not current_user.is_authenticated:
        flash("Для оформлення замовлення необхідно бути зареєстрованим")

    basket = session.get('basket', {})

    if item_name not in basket:
        flash("Товар не знайдено у кошику", "danger")
        return redirect(url_for('create_order'))

    qty = int(basket[item_name])
    action = request.form.get('action')

    if action == "plus":
        if qty < 10:
            basket[item_name] = qty + 1
        else:
            flash("Максимальна кількість — 10", "warning")

    elif action == "minus":
        if qty > 1:
            basket[item_name] = qty - 1
        else:
            flash("Мінімальна кількість — 1", "warning")

    elif action == "delete":
        basket.pop(item_name)

    session['basket'] = basket
    return redirect(url_for('create_order'))

@app.route('/basket/clear', methods=['POST'])
def clear_basket():
    if request.form.get("csrf_token") != session['csrf_token']:
        return "Запит заблоковано!", 403

    session.pop('basket', None)
    flash("Кошик очищено")

    return redirect(url_for('create_order'))




if __name__ == '__main__':
    app.run(debug=True)