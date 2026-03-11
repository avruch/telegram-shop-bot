from aiogram.fsm.state import State, StatesGroup


class ShopStates(StatesGroup):
    browsing = State()           # Default AI-chat state
    collecting_name = State()    # Checkout: enter full name
    collecting_address = State() # Checkout: enter shipping address
    collecting_phone = State()   # Checkout: enter phone number
    waiting_payment = State()    # Awaiting payment screenshot upload
