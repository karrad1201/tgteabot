from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Cookie, HTTPException
from fastapi.responses import HTMLResponse
from datetime import datetime, timedelta
import jwt
import asyncio
from typing import Optional
import json

app = FastAPI()

# Секретный ключ для JWT (в продакшене храните в env переменных)
SECRET_KEY = "your-secret-key"
ALGORITHM = "HS256"

# Простая HTML страница для тестирования
html = """
<!DOCTYPE html>
<html>
    <head>
        <title>WebSocket Test with JWT</title>
    </head>
    <body>
        <h1>WebSocket Test with JWT</h1>

        <div>
            <h3>Управление JWT токеном:</h3>
            <input type="text" id="jwtToken" placeholder="Введите JWT токен" value="valid-token" style="width: 300px;"/>
            <button onclick="setJwtToken()">Установить токен</button>
            <button onclick="setInvalidToken()">Установить невалидный токен</button>
            <br>
            <span id="tokenStatus">Токен: valid-token</span>
            <br>
            <span id="cookieStatus">Куки: valid-token</span>
        </div>

        <hr>

        <form action="" onsubmit="sendMessage(event)">
            <input type="text" id="messageText" autocomplete="off"/>
            <button>Send</button>
        </form>

        <ul id='messages'>
        </ul>

        <script>
    let currentToken = "valid-token";

    // Функция для установки куки
    function setCookie(name, value, days = 7) {
        const date = new Date();
        date.setTime(date.getTime() + (days * 24 * 60 * 60 * 1000));
        const expires = "expires=" + date.toUTCString();
        document.cookie = `${name}=${value}; ${expires}; path=/`;
        document.getElementById("cookieStatus").textContent = "Куки: " + value;
        console.log("Куки установлены:", name, value);
    }

    // Функция для получения куки
    function getCookie(name) {
        const value = `; ${document.cookie}`;
        const parts = value.split(`; ${name}=`);
        if (parts.length === 2) return parts.pop().split(';').shift();
        return "";
    }

    function setJwtToken() {
        const input = document.getElementById("jwtToken");
        currentToken = input.value || "valid-token";
        document.getElementById("tokenStatus").textContent = "Токен: " + currentToken;
        
        // Обновляем куки при изменении токена
        setCookie("auth_token", currentToken);
        
        console.log("Токен и куки установлены:", currentToken);
    }

    function setInvalidToken() {
        currentToken = "invalid-token";
        document.getElementById("jwtToken").value = "invalid-token";
        document.getElementById("tokenStatus").textContent = "Токен: invalid-token (невалидный)";
        
        // Обновляем куки
        setCookie("auth_token", "invalid-token");
        
        console.log("Установлен невалидный токен и куки");
    }

    // Устанавливаем начальные куки при загрузке
    setCookie("auth_token", currentToken);

    // Функция для создания WebSocket соединения с текущими куки
    function createWebSocket() {
        // Закрываем предыдущее соединение, если оно есть
        if (window.ws) {
            window.ws.close();
        }

        // Создаем новое соединение - куки будут отправлены автоматически
        window.ws = new WebSocket("ws://localhost:8000/ws");

        window.ws.onopen = function(event) {
            console.log("WebSocket соединение установлено");
            document.getElementById('messages').innerHTML += '<li>Соединение установлено</li>';
        };

        window.ws.onmessage = function(event) {
            const messages = document.getElementById('messages')
            const message = document.createElement('li')

            try {
                const data = JSON.parse(event.data);
                if (data.type === 'healthcheck') {
                    message.innerHTML = `<span style="color: green;">HEALTH: ${data.message} (${new Date().toLocaleTimeString()})</span>`;
                } else if (data.type === 'error') {
                    message.innerHTML = `<span style="color: red;">ERROR: ${data.message}</span>`;
                } else {
                    message.innerHTML = `<strong>${data.sender || 'Клиент'}:</strong> ${data.message}`;
                }
            } catch (e) {
                const content = document.createTextNode(event.data)
                message.appendChild(content)
            }

            messages.appendChild(message)
            messages.scrollTop = messages.scrollHeight;
        };

        window.ws.onclose = function(event) {
            console.log("WebSocket соединение закрыто:", event.code, event.reason);
            const messages = document.getElementById('messages')
            const message = document.createElement('li')
            message.innerHTML = `<span style="color: red;">Соединение закрыто: ${event.reason || 'Код: ' + event.code}</span>`;
            messages.appendChild(message)
        };

        window.ws.onerror = function(error) {
            console.error("WebSocket ошибка:", error);
        };
    }

    // Создаем соединение при загрузке
    createWebSocket();

    // Функция для переподключения с новыми куки
    function reconnectWebSocket() {
        console.log("Переподключение WebSocket с новыми куки...");
        createWebSocket();
    }

    // Обновляем функции для переподключения при изменении токена
    function setJwtToken() {
        const input = document.getElementById("jwtToken");
        currentToken = input.value || "valid-token";
        document.getElementById("tokenStatus").textContent = "Токен: " + currentToken;
        
        setCookie("auth_token", currentToken);
        reconnectWebSocket(); // Переподключаемся
        
        console.log("Токен и куки установлены:", currentToken);
    }

    function setInvalidToken() {
        currentToken = "invalid-token";
        document.getElementById("jwtToken").value = "invalid-token";
        document.getElementById("tokenStatus").textContent = "Токен: invalid-token (невалидный)";
        
        setCookie("auth_token", "invalid-token");
        reconnectWebSocket(); // Переподключаемся
        
        console.log("Установлен невалидный токен и куки");
    }

    function sendMessage(event) {
        event.preventDefault();
        const input = document.getElementById("messageText")

        if (window.ws && window.ws.readyState === WebSocket.OPEN) {
            const messageData = {
                message: input.value,
                timestamp: new Date().toISOString()
            };
            window.ws.send(JSON.stringify(messageData))
            input.value = ''
        } else {
            alert("WebSocket соединение не установлено!");
        }
    }
</script>
    </body>
</html>
"""


@app.get("/")
async def get():
    return HTMLResponse(html)


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "websocket_connections": len(manager.active_connections)
    }


@app.get("/generate-token/{user_id}")
async def generate_token(user_id: str):
    """Генерация тестового JWT токена"""
    payload = {
        "sub": user_id,
        "exp": datetime.utcnow() + timedelta(hours=1)
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    return {"token": token}


def validate_jwt_token(token: str) -> bool:
    """Валидация JWT токена"""
    try:
        print(f"Validating token: {token}")  # Добавьте это для отладки
        if token == "valid-token":
            return True
        else:
            return False

        # Этот код никогда не выполнится из-за return выше
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return True
    except jwt.PyJWTError:
        return False
    except Exception:
        return False


# Хранилище активных подключений
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def send_personal_message(self, message: dict, websocket: WebSocket):
        await websocket.send_json(message)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except:
                self.disconnect(connection)

    async def health_check_all(self):
        """Отправка healthcheck сообщений всем клиентам"""
        health_message = {
            "type": "healthcheck",
            "message": "Connection alive",
            "timestamp": datetime.now().isoformat()
        }
        await self.broadcast(health_message)


manager = ConnectionManager()


@app.websocket("/ws")
async def websocket_endpoint(
        websocket: WebSocket,
        auth_token: Optional[str] = Cookie(None)
):
    # Валидация JWT токена
    if not auth_token or not validate_jwt_token(auth_token):
        await websocket.close(code=1008, reason="Invalid JWT token")
        return

    await manager.connect(websocket)

    # Отправляем приветственное сообщение
    await manager.send_personal_message({
        "type": "connection",
        "message": "Вы подключились к WebSocket",
        "timestamp": datetime.now().isoformat()
    }, websocket)

    try:
        # Запускаем периодическую проверку здоровья
        async def health_check_task():
            while True:
                await asyncio.sleep(15)  # Каждые 15 секунд
                try:
                    # Проверяем валидность токена
                    if not validate_jwt_token(auth_token):
                        await websocket.close(code=1008, reason="JWT token expired")
                        break

                    # Отправляем healthcheck
                    await manager.send_personal_message({
                        "type": "healthcheck",
                        "message": "JWT valid, connection active",
                        "timestamp": datetime.now().isoformat()
                    }, websocket)
                except:
                    break

        # Запускаем задачу в фоне
        health_task = asyncio.create_task(health_check_task())

        # Основной цикл обработки сообщений
        while True:
            data = await websocket.receive_text()

            # Парсим входящее сообщение
            try:
                message_data = json.loads(data)
                text_message = message_data.get('message', '')
                timestamp = message_data.get('timestamp', '')
            except:
                text_message = data
                timestamp = datetime.now().isoformat()

            # Рассылаем сообщение всем клиентам
            await manager.broadcast({
                "type": "message",
                "sender": "Client",
                "message": text_message,
                "timestamp": timestamp
            })

    except WebSocketDisconnect:
        manager.disconnect(websocket)
        await manager.broadcast({
            "type": "connection",
            "message": "Клиент отключился",
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        manager.disconnect(websocket)
        print(f"WebSocket error: {e}")


# Фоновая задача для глобального healthcheck
async def global_health_check():
    while True:
        await asyncio.sleep(30)  # Каждые 30 секунд
        await manager.health_check_all()


@app.on_event("startup")
async def startup_event():
    # Запускаем глобальную проверку здоровья при старте
    asyncio.create_task(global_health_check())


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
