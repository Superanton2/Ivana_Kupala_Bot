import gspread
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()


def get_sheet():
    gc = gspread.service_account(filename='app/data/credentials.json')
    return gc.open(os.getenv("LOG_SHEET_NAME"))


def _append_row_sync(sheet_name: str, row_data: list):
    sh = get_sheet()
    ws = sh.worksheet(sheet_name)
    ws.append_row(row_data)


async def add_user_to_sheet(tg_id: int, username: str, name: str, mail: str,
                            status: str = "pending", education: str = None,
                            faculty: str = None, group: str = None, quest_participation: bool = False):
    try:
        quest_str = "Так" if quest_participation else "Ні"
        row = [str(tg_id), username, status, name, mail, education, faculty, group, quest_str]

        row = [item if item is not None else "" for item in row]

        await asyncio.to_thread(_append_row_sync, "Users", row)
        print(f"✅ Користувача {name} успішно додано в Sheets!")
    except Exception as e:
        print(f"❌ ПОМИЛКА додавання користувача в Sheets: {e}")


def _update_user_sync(tg_id: str, field: str, new_value: any):
    sh = get_sheet()
    ws = sh.worksheet("Users")
    try:
        cell = ws.find(str(tg_id), in_column=1)
        if cell:
            col_map = {
                "username": "B",
                "status": "C",
                "name": "D",
                "mail": "E",
                "education": "F",
                "faculty": "G",
                "group": "H",
                "quest_participation": "I"
            }
            if field in col_map:
                cell_label = f"{col_map[field]}{cell.row}"

                # Обробка булевого значення для запису текстом
                if field == "quest_participation":
                    write_value = "Так" if new_value else "Ні"
                else:
                    write_value = new_value if new_value is not None else ""

                ws.update_acell(cell_label, write_value)
                print(f"✅ Sheets: Оновлено ID {tg_id}, поле {field} -> {write_value}")
        else:
            print(f"⚠️ Sheets: Користувача {tg_id} не знайдено для оновлення.")
    except Exception as e:
        print(f"❌ Sheets: Помилка оновлення користувача: {e}")


async def update_user_in_sheet(tg_id: int, field: str, new_value: any):
    await asyncio.to_thread(_update_user_sync, str(tg_id), field, new_value)