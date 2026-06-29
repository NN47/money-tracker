from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, KeyboardButton, Message

from handlers.home import send_main_screen
from keyboards.main import BACK_TEXT, back_kb, person_menu_kb, persons_list_kb
from services.persons import create_person, fetch_person, fetch_persons
from services.reports import build_dashboard

router = Router()


class PersonStates(StatesGroup):
    waiting_name = State()


def build_persons_text(persons) -> str:
    lines = [
        "👤 <b>Персоны</b>",
        "",
        "Здесь можно вести отдельный учет финансов для каждого человека.",
        "",
        "Нажмите «➕ Добавить персону», чтобы создать отдельный профиль.",
    ]
    if persons:
        lines.extend(["", "────────────", ""])
        lines.extend(f"👤 {person['name']}" for person in persons)
    return "\n".join(lines)


@router.message(F.text == "👤 Персоны")
async def persons_menu(message: Message, state: FSMContext):
    await state.clear()
    persons = fetch_persons()
    await message.answer(build_persons_text(persons), reply_markup=persons_list_kb(persons), parse_mode="HTML")
    await message.answer("Меню персон:", reply_markup=back_kb([KeyboardButton(text="➕ Добавить персону")]))


@router.message(F.text == "➕ Добавить персону")
async def add_person_start(message: Message, state: FSMContext):
    await state.set_state(PersonStates.waiting_name)
    await message.answer("Введите имя персоны:", reply_markup=back_kb())


@router.message(PersonStates.waiting_name)
async def add_person_finish(message: Message, state: FSMContext):
    if message.text == BACK_TEXT:
        await persons_menu(message, state)
        return
    name = (message.text or "").strip()
    if not name:
        await message.answer("Имя не может быть пустым.")
        return
    person_id = create_person(name)
    await state.clear()
    await state.update_data(person_id=person_id, person_name=name)
    await message.answer(f"Персона «{name}» добавлена ✅", reply_markup=person_menu_kb())
    await message.answer(build_dashboard(person_id=person_id, person_name=name), parse_mode="HTML")


@router.callback_query(F.data.startswith("person:open:"))
async def open_person(callback: CallbackQuery, state: FSMContext):
    try:
        person_id = int(callback.data.rsplit(":", 1)[1])
    except Exception:
        await callback.answer("Не понял персону", show_alert=True)
        return
    person = fetch_person(person_id)
    if not person:
        await callback.answer("Персона не найдена", show_alert=True)
        return
    await state.clear()
    await state.update_data(person_id=person["id"], person_name=person["name"])
    await callback.answer(f"Открыто: {person['name']}")
    if callback.message:
        await callback.message.answer(build_dashboard(person_id=person["id"], person_name=person["name"]), parse_mode="HTML")
        await callback.message.answer(f"👤 {person['name']}", reply_markup=person_menu_kb())


@router.message(F.text == BACK_TEXT)
async def person_back(message: Message, state: FSMContext):
    data = await state.get_data()
    if data.get("person_id"):
        await persons_menu(message, state)
    else:
        await send_main_screen(message, state)
