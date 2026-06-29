from database import dict_cursor, get_connection


def create_person(name: str) -> int:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("INSERT INTO persons(name) VALUES(%s) RETURNING id", (name,))
        person_id = cur.fetchone()[0]
        cur.close()
    return person_id


def fetch_persons():
    with get_connection() as conn:
        cur = dict_cursor(conn)
        cur.execute("SELECT id, name FROM persons ORDER BY LOWER(name), id")
        rows = cur.fetchall()
        cur.close()
    return rows


def fetch_person(person_id: int):
    with get_connection() as conn:
        cur = dict_cursor(conn)
        cur.execute("SELECT id, name FROM persons WHERE id = %s", (person_id,))
        row = cur.fetchone()
        cur.close()
    return row


async def get_person_context(state):
    data = await state.get_data()
    person_id = data.get("person_id")
    person_name = data.get("person_name")
    if person_id and person_name:
        return int(person_id), person_name
    return None, None


async def clear_work_data_keep_person(state):
    data = await state.get_data()
    person_id = data.get("person_id")
    person_name = data.get("person_name")
    await state.clear()
    if person_id and person_name:
        await state.update_data(person_id=person_id, person_name=person_name)
