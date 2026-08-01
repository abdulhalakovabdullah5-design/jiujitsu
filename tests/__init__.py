import sqlite3
from main import create_table

conn = sqlite3.connect("database.db")
c = conn.cursor()

while True:
    user_name = input("Введите имя: ")
    user_age = int(input("Введите ваш возраст: "))
    c.execute('''
INSERT INTO users (name, age) VALUES (?, ?)
''', (user_name, int(user_age)))

    print(f"Пользователь: {user_name} Был добавлен☺")

    conn.commit()

    