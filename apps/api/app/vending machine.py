from enum import Enum


class State(Enum):
    IDLE = 1
    WAITING_FOR_PAYMENT = 2
    READY_TO_DISPENSE = 3


class Product:
    def __init__(self, product_id, name, price):
        self.product_id = product_id
        self.name = name
        self.price = price

class Inventory:
    def __init__(self):
        self.products = {}

    def add_product(self, product, quantity):
        if product.product_id in self.products:
            self.products[product.product_id][1] += quantity
        else:
            self.products[product.product_id] = [product, quantity]

    def is_available(self, product_id):
        return (
            product_id in self.products
            and self.products[product_id][1] > 0
        )

    def get_product(self, product_id):
        if product_id not in self.products:
            return None

        return self.products[product_id][0]

    def remove_product(self, product_id):
        if not self.is_available(product_id):
            return False

        self.products[product_id][1] -= 1
        return True


class Payment:
    def pay(self, amount):
        raise NotImplementedError


class CashPayment(Payment):
    def __init__(self, inserted_amount):
        self.inserted_amount = inserted_amount

    def pay(self, amount):
        if self.inserted_amount < amount:
            return False, 0

        change = self.inserted_amount - amount
        return True, change


class CardPayment(Payment):
    def pay(self, amount):
        return True, 0


class VendingMachine:
    def __init__(self):
        self.inventory = Inventory()
        self.state = State.IDLE
        self.selected_product = None

    def select_product(self, product_id):
        if self.state != State.IDLE:
            print("Finish current transaction first")
            return False

        if not self.inventory.is_available(product_id):
            print("Product unavailable")
            return False

        self.selected_product = self.inventory.get_product(product_id)
        self.state = State.WAITING_FOR_PAYMENT

        print(
            f"Selected {self.selected_product.name}, "
            f"price: ${self.selected_product.price}"
        )

        return True

    def make_payment(self, payment):
        if self.state != State.WAITING_FOR_PAYMENT:
            print("Select a product first")
            return False

        success, change = payment.pay(
            self.selected_product.price
        )

        if not success:
            print("Insufficient payment")
            return False

        self.state = State.READY_TO_DISPENSE

        self.dispense_product()

        if change > 0:
            print(f"Returning change: ${change}")

        return True

    def dispense_product(self):
        if self.state != State.READY_TO_DISPENSE:
            print("Payment required")
            return False

        product = self.selected_product

        self.inventory.remove_product(product.product_id)

        print(f"Dispensing {product.name}")

        self.reset()
        return True

    def cancel(self):
        if self.state == State.IDLE:
            print("No active transaction")
            return

        print("Transaction cancelled")
        self.reset()

    def reset(self):
        self.selected_product = None
        self.state = State.IDLE