from enum import Enum

class ridestatus(Enum):
    requested = 1
    matched = 2
    in_progress = 3
    completed = 4
    cancelled = 5 

class location:
    def __init__(self, x, y):
        self.x = x
        self.y = y

class rider:
    def __init__(self, rider_id, name):
        self.rider_id = rider_id
        self.name  = name 

class driver:
    def __init__(self, driver_id, name, location):
        self.driver_id = driver_id
        self.name = name
        self.location = location
        self.available = True 

class ride:
    def __init__(self, ride_id, rider, pickup, destination):
        self.ride_id = ride_id
        self.rider = rider
        self.pickup = pickup 
        self.destination = destination
        self.status = ridestatus.requested 
        self.fare = 0 
        
class payment:
    def pay(self, amount):
        raise NotImplementedError
        
class cardpayment(payment):
    def pay(self, amount):
        print (f"Card payment of ${amount} sucessful")
        return True 

class cashpayment(payment):
    def pay(self, amount):
        print(f" Cash payment of {amount} sucessful")

class rideservice:
    def __init__(self):
        self.drivers = []
        self.rides = {}
        self.next_ride_id = 1

    def add_driver(self, driver):
        self.drivers.append(driver)

    def find_driver(self, pickup):
        for driver in self.drivers:
            if driver.available:
                return driver 
        
        return None
    
    def request_ride(self, rider, pickup, destination):
        ride = ride( self.next_ride_id, rider, pickup, destination)

        self.next_ride_id += 1
        driver = self.find_driver(pickup)

        if driver is None:
            print("No drivers available")
            return None

        ride.driver = driver
        ride.status = ridestatus.matched 
        driver.available = False
        self.rides[ride.ride_id] = ride

        print( f"Ride {ride.ride_id} matched with " f"{driver.name}" )

        return ride

    def start_ride(self, ride):
        if ride.status != ridestatus.matched:
            print("Ride cannot be started")
            return

        ride.status = ridestatus.in_progress

    def complete_ride(self, ride):
        if ride.status != ridestatus.in_progress:
            print("Ride cannot be completed")
            return

        ride.fare = 20
        ride.status = ridestatus.completed 
        ride.driver.available = True
        ride.driver.location = ride.destination

    def make_payment(self, ride, payment):
        if ride.status != ridestatus.completed:
            print("Ride is not completed")
            return False

        return payment.pay(ride.fare)
    
    