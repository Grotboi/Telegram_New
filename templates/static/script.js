const socket = io();
const messageForm = document.getElementById('messageForm');
const messageInput = document.getElementById('messageInput');
const messagesDiv = document.getElementById('messages');
const usersList = document.getElementById('users-list');

// Загружаем пользователей
function loadUsers() {
    fetch('/users')
        .then(res => res.json())
        .then(usernames => {
            usernames.forEach(username => {
                if (username !== currentUser) {
                    const li = document.createElement('li');
                    li.textContent = username;
                    li.className = 'user';
                    li.dataset.recipient = username;
                    li.addEventListener('click', () => {
                        document.querySelectorAll('.user').forEach(el => el.classList.remove('active'));
                        li.classList.add('active');
                        currentRecipient = li.dataset.recipient;
                        loadMessages();  // загружаем переписку
                    });
                    usersList.appendChild(li);
                }
            });
        });
}

// Загружаем сообщения
function loadMessages() {
    fetch('/messages')
        .then(res => res.json())
        .then(data => {
            messagesDiv.innerHTML = '';
            data.forEach(msg => {
                // Показываем только те, что относятся к текущему чату
                if (isMessageRelevant(msg)) {
                    addMessageToChat(msg.username, msg.message, msg.time, msg.recipient);
                }
            });
            messagesDiv.scrollTop = messagesDiv.scrollHeight;
        });
}

// Проверяем, нужно ли показать сообщение
function isMessageRelevant(msg) {
    if (currentRecipient === null) {
        return msg.recipient === null;  // общий чат
    } else {
        return (msg.username === currentUser && msg.recipient === currentRecipient) ||
               (msg.recipient === currentUser && msg.username === currentRecipient);
    }
}

// Добавляем сообщение
function addMessageToChat(username, message, time, recipient) {
    const p = document.createElement('p');
    const direction = username === currentUser ? 'sent' : 'received';
    p.className = direction;

    let prefix = '';
    if (recipient) {
        prefix = `💌 `;
    }

    p.innerHTML = `<strong>${prefix}${username}</strong> <small>${time}</small><br>${message}`;
    messagesDiv.appendChild(p);
}
messagesDiv.scrollTop = messagesDiv.scrollHeight;

// Отправка
messageForm.addEventListener('submit', (e) => {
    e.preventDefault();
    const message = messageInput.value.trim();
    if (!message) return;

    socket.emit('send_message', {
        message: message,
        recipient: currentRecipient  // null или имя
    });

    messageInput.value = '';
});

// Пришло новое сообщение
socket.on('receive_message', (data) => {
    if (isMessageRelevant(data)) {
        addMessageToChat(data.username, data.message, data.time, data.recipient);
    }
});

// Загружаем всё при старте
loadUsers();
loadMessages();