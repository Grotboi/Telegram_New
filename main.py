from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from werkzeug.security import generate_password_hash, check_password_hash
from flask_socketio import SocketIO, emit
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'Gro478dj2jf3hjschwfbas'
socketio = SocketIO(app, cors_allowed_origins="*", manage_session=False)

# Подключение к базе данных
def get_db_connection():
    return psycopg2.connect(
        dbname="chat_db",
        host="localhost",
        user="postgres",
        password="root", 
        port="8887"
    )

# Проверка авторизации
def is_authenticated():
    return 'username' in session

# Получить пользователя по имени
def get_user(username):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM users WHERE username = %s", (username,))
    user = cur.fetchone()
    cur.close()
    conn.close()
    return user


#########################################################################################
# Главная страница — только для авторизованных
#########################################################################################

@app.route("/")
def index():
    if not is_authenticated():
        return redirect(url_for('login'))
    return render_template('messages.html')


#########################################################################################
# Получение старых сообщений
#########################################################################################

@app.route('/messages')
def get_messages():
    current_user = session.get('username')
    if not current_user:
        return jsonify([])

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT username, message, recipient, to_char(created_at, 'HH24:MI:SS') AS time
        FROM messages
        WHERE recipient IS NULL                          -- общий чат
           OR recipient = %s                             -- или мне
           OR (username = %s AND recipient IS NOT NULL)  -- или я отправил приватное
        ORDER BY created_at ASC
        LIMIT 100;
    """, (current_user, current_user))
    messages = cur.fetchall()
    cur.close()
    conn.close()
    return jsonify(messages)


#########################################################################################
# Регистрация
#########################################################################################

@app.route('/register', methods=['GET', 'POST'])
def register():
    error = None

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        if len(password) < 8:
            error = "Пароль должен быть не менее 8 символов"
        elif get_user(username):
            error = "Пользователь уже существует"
        else:
            hashed = generate_password_hash(password)
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("INSERT INTO users (username, password) VALUES (%s, %s)", (username, hashed))
            conn.commit()
            cur.close()
            conn.close()
            return redirect(url_for('login'))

    return render_template('register.html', error=error)


#########################################################################################
# Вход
#########################################################################################

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None  # Сначала ошибки нет

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        user = get_user(username)
        if user and check_password_hash(user['password'], password):
            session['username'] = username
            return redirect(url_for('index'))
        else:
            error = "Неверный логин или пароль"  # Сохраняем ошибку

    return render_template('login.html', error=error)

#########################################################################################
# Выход
#########################################################################################

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))


@app.route('/users')
def get_users():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT username FROM users ORDER BY username")
    users = [row[0] for row in cur.fetchall()]
    cur.close()
    conn.close()
    return jsonify(users)

#########################################################################################
# Сокеты — реальное время
#########################################################################################

@socketio.on('connect')
def handle_connect():
    if not is_authenticated():
        return False  # Запрещаем подключаться без входа
    print(f"Пользователь {session['username']} подключился")

@socketio.on('send_message')
def handle_message(data):
    sender = session.get('username')
    message = data.get('message', '').strip()
    recipient = data.get('recipient')  # может быть None

    if not sender or not message:
        return

    # Сохраняем в БД
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO messages (username, message, recipient) VALUES (%s, %s, %s)",
        (sender, message, recipient)
    )
    conn.commit()
    cur.close()
    conn.close()

    # Формируем событие
    emit_data = {
        'username': sender,
        'message': message,
        'recipient': recipient,
        'time': datetime.now().strftime('%H:%M:%S')
    }

    if recipient:
        # Приватное: отправляем только отправителю и получателю
        emit('receive_message', emit_data, room=recipient)
        emit('receive_message', emit_data, room=sender)
    else:
        # Общий чат: всем
        emit('receive_message', emit_data, broadcast=True)

#########################################################################################
# Запуск сервера
#########################################################################################

if __name__ == '__main__':
    socketio.run(app, debug=True, host='127.0.0.1', port=5000)