import grpc
import rent_pb2
import rent_pb2_grpc
import requests

def run():
    channel = grpc.insecure_channel('localhost:8000')
    stub = rent_pb2_grpc.RentalServiceStub(channel)
    user_role = input("Are you a landlord (yes/no)?: ")

    if user_role.lower() == 'yes':
        landlord_menu(stub)
    else:
        tenant_menu(stub)
    
def landlord_menu(stub):
    username = input("Please enter your username: ")
    while True:
        print("\n1. View your listed rentals\n2. Check messages\n3. View all messages\n4. Delete a rental\n5. Add a rental\n6. Exit")
        choice = input("Choose an option: ")
        if choice == '1':
            try:
                response = stub.GetMyRentals(rent_pb2.UserRequest(username=username))
                for rental in response.entries:
                    print(f"{rental.name}, {rental.price}, {rental.location}")
            except Exception as e:
                print(f"Failed to fetch rentals: {e}")
        elif choice == '2':
            response = requests.get(f'http://localhost:5000/leave/receive', params={'recipient': username})
            messages = response.json()
            if messages:
                for message in messages:
                    print(f"From {message['sender']} at {message['timestamp']}: {message['content']}")
            else:
                print("No new messages.")
            pass
        elif choice == '3':
            response = stub.GetAllMessages(rent_pb2.UserRequest(username=username))
            for msg in response.messages:
                print(f"From {msg.sender} at {msg.timestamp}: {msg.content}")
        
        elif choice == '4':
            rental_name = input("Enter the name of the rental to delete: ")
            try:
                response = stub.DeleteRental(rent_pb2.RentalDeleteRequest(name=rental_name, username=username))
                print("Success" if response.success else f"Failed: {response.message}")
            except Exception as e:
                print(f"An error occurred: {e}")
                
        elif choice == '5':
            name = input("Enter rental name: ")
            price = int(input("Enter price: "))  
            location = input("Enter location: ")
            description = input("Enter description: ")
            region = input("Enter region: ")
            owner = username
            try:
                response = stub.AddRental(rent_pb2.RentalEntry(name = name, price = price, location = location, owner = owner, description = description,region = region))
                print("Success" if response.success else f"Failed: {response.message}")
            except Exception as e:
                print(f"An error occurred: {e}")
            
        elif choice == '6':
            break
        else:
            print("Invalid option, please try again.")
    
def tenant_menu(stub):
    username = input("Please enter your username: ")
    region = input("Please enter your region: ")

    while True:
        print("\n1. View information for your region\n2. View information for all regions\n3. Exit")
        choice = input("Choose an option: ")

        if choice == '1':
            response = stub.GetRentalInfo(rent_pb2.RegionRequest(region=region))
            print(f"Rental listings in {region}:")
            for entry in response.entries:
                print(f"{entry.name}, {entry.price}, {entry.location}")
            house_name = input("Enter the name of the house to get more details, or type 'back' to return: ")
            if house_name.lower() != 'back':
                detail_response = stub.GetRentalDetails(rent_pb2.RentalQuery(name=house_name))
                if detail_response.name:
                    print(f"Details: {detail_response.name}, {detail_response.price}, {detail_response.location}, Owner: {detail_response.owner}, {detail_response.description}")
                    recipient = input("Enter the landlord's username: ")
                    message = input("Enter your message: ")
                    response = requests.post('http://localhost:5000/leave/send', json={
                        'sender': username,
                        'recipient': recipient,
                        'content': message
                    })
                    print(response.json()['message'])

                else:
                    print("No details found for the specified house.")
        elif choice == '2':
            response = stub.GetRentalInfo(rent_pb2.RegionRequest(region="all"))
            print("All Rental listings:")
            for entry in response.entries:
                print(f"{entry.name}, {entry.price}, {entry.location}")
        elif choice == '3':
            break
        else:
            print("Invalid option, please try again.")
if __name__ == '__main__':
    run()




