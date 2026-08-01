import time
from datetime import datetime
from main import create_table
import sqlite3

balance = 1000
count = 0

conn = sqlite3.connect("database.db")
c = conn.cursor()


""" Создаем БЕСКОНЕЧНЫЙ ЦИКЛ """
while True:
    try:
        user_input = input("Вы хотите попополнить счет или снять деньги: ")

        """ Условие на пополнение суммы """
        if user_input == "пополнить".lower():
            user_amount = float(input("Введите сумму которую хотите пополнить: "))
            if user_amount < 50:
                print("Нельзя пополнить меньше 50р")
            else:
                balance += user_amount
                time.sleep(2)
                print(f"Пополнение на сумму | {user_amount} | Успешно!")

            """ Условие на снятие денег с баланса """

        elif user_input == "снять".lower():
            user_amount = float(input("Введите сумму для снятие: "))
            if user_amount <= balance:
                balance -= user_amount
                print(f"Снятие счета на сумму: {user_amount}")
            else:
                print("Недостаточно средств на балансе")


            c.execute("INSERT INTO users (amount) VALUES (?)", (user_amount))

            conn.commit()
    except ValueError:
        print("Ошибка")
    except TypeError:
        print("Ошибка")

    
