from sqlalchemy import select, insert, update
from app.db.db_setup import engine, admin_list, user_list

async def add_user(tg_id: int, username: str, name: str, mail: str,
                   education: str = None, faculty: str = None,
                   group: str = None, quest_participation: bool = False) -> None:
    """
    Inserts a new user record into the user_list database table.

    This function initializes a new user profile with their basic Telegram
    information and registration details. The default payment status is strictly
    set to 'pending' upon creation.

    Parameters:
    tg_id (int): The unique Telegram identifier of the user.
    username (str): The Telegram username of the user (can be None if hidden).
    name (str): The full real name of the user (ПІБ).
    mail (str): The primary email address of the user.
    education (str, optional): The user's educational degree or format. Defaults to None.
    faculty (str, optional): The specific faculty or department. Defaults to None.
    group (str, optional): The academic group of the user. Defaults to None.

    Returns:
    None
    """
    async with engine.begin() as conn:
        insert_statement = insert(user_list).values(
            telegram_id=tg_id,
            username=username,
            status="pending",
            name=name,
            mail=mail,
            education=education,
            faculty=faculty,
            group=group,
            quest_participation=quest_participation
        )
        await conn.execute(insert_statement)


async def get_user(tg_id: int):
    """
    Retrieves a complete user record from the database using their Telegram ID.

    Parameters:
    tg_id (int): The unique Telegram identifier of the user to search for.

    Returns:
    sqlalchemy.engine.row.Row: A row object containing all user data if found.
    None: If no user with the specified tg_id exists in the database.
    """
    async with engine.begin() as conn:
        select_statement = select(user_list).where(user_list.c.telegram_id == tg_id)
        result = await conn.execute(select_statement)
        return result.fetchone()

async def get_all_users():
    """
    Fetches all registered users from the user_list database table.

    Returns:
    list: A list of sqlalchemy.engine.row.Row objects representing all users.
    """
    async with engine.begin() as conn:
        select_statement = select(user_list)
        result = await conn.execute(select_statement)
        return result.fetchall()

async def check_user_payment(tg_id: int) -> bool:
    """
    Verifies if a specific user has successfully completed their payment.

    Parameters:
    tg_id (int): The unique Telegram identifier of the user.

    Returns:
    bool: True if the user's status is exactly 'success', False otherwise.
    """
    async with engine.begin() as conn:
        select_statement = select(user_list.c.status).where(user_list.c.telegram_id == tg_id)
        result = await conn.execute(select_statement)
        row = result.fetchone()

        if row and row[0] == "success":
            return True
        return False

async def update_payment_status(tg_id: int, new_status: str) -> None:
    """
    Updates the payment status of a specific user in the database.

    Parameters:
    tg_id (int): The unique Telegram identifier of the user.
    new_status (str): The new status to be assigned. Must be one of
                      the predefined values: 'pending', 'processing', or 'success'.

    Returns:
    None
    """
    if new_status not in ["pending", "processing", "success"]:
        raise ValueError("Invalid status. Must be 'pending', 'processing', or 'success'.")

    async with engine.begin() as conn:
        update_statement = (
            update(user_list)
            .where(user_list.c.telegram_id == tg_id)
            .values(status=new_status)
        )
        await conn.execute(update_statement)

async def update_user_field(tg_id: int, field_name: str, new_value: any) -> None:
    """
    Updates a specific field in the user's database record.

    This function dynamically updates a column based on the provided string.
    It includes basic validation to prevent SQL injection or modifying protected
    columns like telegram_id.

    Parameters:
    tg_id (int): The unique Telegram identifier of the user.
    field_name (str): The exact name of the database column to change
                      (e.g., 'name', 'mail', 'education', 'faculty', 'group').
    new_value (str): The new string value to insert into the specified column.

    Returns: None
    """
    allowed_fields = ["username", "name", "mail", "education", "faculty", "group", "quest_participation"]

    if field_name not in allowed_fields:
        raise ValueError(f"Field '{field_name}' is not allowed to be updated.")

    async with engine.begin() as conn:
        update_data = {field_name: new_value}

        update_statement = (
            update(user_list)
            .where(user_list.c.telegram_id == tg_id)
            .values(**update_data)
        )
        await conn.execute(update_statement)

async def is_admin(user_id: int) -> bool:
    """
    Checks whether a specific user holds an active administrative role.

    This queries the admin_list table to verify if the user exists there
    and if their 'is_active' boolean flag is set to True.

    Parameters:
    user_id (int): The unique Telegram identifier of the user to verify.

    Returns:
    bool: True if the user is an active administrator, False otherwise.
    """
    async with engine.begin() as conn:
        select_statement = select(admin_list).where(
            (admin_list.c.telegram_id == user_id) & (admin_list.c.is_active == True)
        )

        result = await conn.execute(select_statement)
        return result.fetchone() is not None