from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, KeyboardButton, Message

from handlers.home import send_main_screen
from handlers.settings import settings_menu as global_settings_menu
from keyboards.main import BACK_TEXT, back_kb, person_menu_kb, persons_list_kb, with_back_kb
from services.persons import create_person, fetch_person, fetch_persons, set_person_include_in_budget
from services.reports import build_dashboard

router = Router()


class PersonStates(StatesGroup):
    waiting_name = State()


def build_persons_text(persons) -> str:
    lines = [
        "📁 <b>Проекты</b>",
        "",
        "Здесь можно вести отдельный учет доходов и расходов по любым направлениям: семье, близким, сотрудникам, бизнесу или личным задачам.",
        "",
        "➕ Добавить проект",
    ]
    if persons:
        lines.extend(["", "────────────", ""])
        lines.extend(f"📁 {person['name']}" for person in persons)
    return "\n".join(lines)


def build_project_settings_text(project) -> str:
    status = "Вкл" if project.get("include_in_budget") else "Выкл"
    return "\n".join(
        [
            f"⚙️ <b>Настройки проекта: {project['name']}</b>",
            "",
            f"Учитывать проект в общем бюджете: <b>{status}</b>",
            "",
            "Если выключено, операции проекта считаются только внутри проекта и не попадают в общий бюджет.",
            "Если включено, операции проекта также учитываются в общем главном экране, общем балансе, общем календаре и общем отчете.",
        ]
    )


def project_settings_kb(project) -> object:
    next_text = "Учитывать в общем бюджете: Выкл" if project.get("include_in_budget") else "Учитывать в общем бюджете: Вкл"
    return with_back_kb([KeyboardButton(text=next_text)])


@router.message(F.text == "📁 Проекты")
async def persons_menu(message: Message, state: FSMContext):
    await state.clear()
    persons = fetch_persons()
    await message.answer(build_persons_text(persons), reply_markup=persons_list_kb(persons), parse_mode="HTML")
    await message.answer("Меню проектов:", reply_markup=with_back_kb([KeyboardButton(text="➕ Добавить проект")]))


@router.message(F.text == "➕ Добавить проект")
async def add_person_start(message: Message, state: FSMContext):
    await state.set_state(PersonStates.waiting_name)
    await message.answer("Введите название проекта:", reply_markup=back_kb())


@router.message(PersonStates.waiting_name)
async def add_person_finish(message: Message, state: FSMContext):
    if message.text == BACK_TEXT:
        await persons_menu(message, state)
        return
    name = (message.text or "").strip()
    if not name:
        await message.answer("Название проекта не может быть пустым.")
        return
    person_id = create_person(name)
    await state.clear()
    await state.update_data(person_id=person_id, person_name=name)
    await message.answer(f"Проект «{name}» добавлен ✅", reply_markup=person_menu_kb())
    await message.answer(build_dashboard(person_id=person_id, person_name=name), parse_mode="HTML")


@router.callback_query(F.data.startswith("person:open:"))
async def open_person(callback: CallbackQuery, state: FSMContext):
    try:
        person_id = int(callback.data.rsplit(":", 1)[1])
    except Exception:
        await callback.answer("Не понял проект", show_alert=True)
        return
    person = fetch_person(person_id)
    if not person:
        await callback.answer("Проект не найден", show_alert=True)
        return
    await state.clear()
    await state.update_data(person_id=person["id"], person_name=person["name"])
    await callback.answer(f"Открыто: {person['name']}")
    if callback.message:
        await callback.message.answer(build_dashboard(person_id=person["id"], person_name=person["name"]), parse_mode="HTML")
        await callback.message.answer(f"📁 {person['name']}", reply_markup=person_menu_kb())


@router.message(F.text == "⚙️ Настройки")
async def project_settings(message: Message, state: FSMContext):
    data = await state.get_data()
    person_id = data.get("person_id")
    if not person_id:
        await global_settings_menu(message, state)
        return
    project = fetch_person(int(person_id))
    if not project:
        await persons_menu(message, state)
        return
    await message.answer(build_project_settings_text(project), reply_markup=project_settings_kb(project), parse_mode="HTML")


@router.message(F.text.in_({"Учитывать в общем бюджете: Вкл", "Учитывать в общем бюджете: Выкл"}))
async def toggle_project_budget(message: Message, state: FSMContext):
    data = await state.get_data()
    person_id = data.get("person_id")
    if not person_id:
        await send_main_screen(message, state)
        return
    include = message.text.endswith("Вкл")
    project = set_person_include_in_budget(int(person_id), include)
    if not project:
        await persons_menu(message, state)
        return
    await state.update_data(person_id=project["id"], person_name=project["name"])
    await message.answer(build_project_settings_text(project), reply_markup=project_settings_kb(project), parse_mode="HTML")


@router.message(F.text == BACK_TEXT)
async def person_back(message: Message, state: FSMContext):
    data = await state.get_data()
    if data.get("person_id"):
        await persons_menu(message, state)
    else:
        await send_main_screen(message, state)
