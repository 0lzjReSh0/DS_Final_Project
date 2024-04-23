import grpc
from concurrent import futures
import rent_pb2
import rent_pb2_grpc
import psycopg2
import threading
from flask import Flask, request, jsonify
app = Flask(__name__)

@app.route('/leave/send', methods=['POST'])
def send_message():
    try:
        data = request.get_json()
        with psycopg2.connect(host="localhost", database="DS", user="postgres", password="020603") as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO messagesB (sender, recipient, content, read) VALUES (%s, %s, %s, %s)",
                    (data['sender'], data['recipient'], data['content'], False)
                )
                conn.commit()
        return jsonify({'message': 'Message sent successfully!'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/leave/receive', methods=['GET'])
def get_messages():
    recipient = request.args.get('recipient')
    messages = []
    with psycopg2.connect(host="localhost", database="DS", user="postgres", password="020603") as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT sender, content, timestamp FROM messages_all WHERE recipient = %s AND read = FALSE",
                (recipient,)
            )
            rows = cursor.fetchall()
            for row in rows:
                messages.append({'sender': row[0], 'content': row[1], 'timestamp': row[2]})
                cursor.execute(
                    "UPDATE messagesB SET read = TRUE WHERE recipient = %s AND sender = %s",
                    (recipient, row[0])
                )
                conn.commit()
    return jsonify(messages), 200


class RentalServiceServicer(rent_pb2_grpc.RentalServiceServicer):
    def __init__(self):
        self.conn = psycopg2.connect(
            host="localhost",
            database="DS",
            user="postgres",
            password="020603"
        )
        self.cursor = self.conn.cursor()
    def push_data_to_peer(self, method, data, peer_address):

        try:
            with grpc.insecure_channel(peer_address) as channel:
                stub = rent_pb2_grpc.RentalServiceStub(channel)
                
                getattr(stub, method)(data)
        except grpc.RpcError as e:
            print(f"Error pushing data to peer at {peer_address}: {e}")
                
    def DeleteRental(self, request, context):
        try:
            if request.region == "A district":
                table = "rent"  
                self.cursor.execute(f"DELETE FROM {table} WHERE name = %s AND owner = %s", (request.name, request.username))
                self.conn.commit()
                
                self.push_data_to_peer("DeleteRental", request, peer_address='localhost:8000')
            else:
                table = "rentB"  
                self.cursor.execute(f"DELETE FROM {table} WHERE name = %s AND owner = %s", (request.name, request.username))
                self.conn.commit()
            return rent_pb2.ActionResponse(success=True)
        except Exception as e:
            self.conn.rollback()
            return rent_pb2.ActionResponse(success=False, message=str(e))

    def AddRental(self, request, context):
        try:
            if request.region == "A district":
                table = "rent"  
                self.cursor.execute(
                    f"INSERT INTO {table} (name, price, location, owner, description, region) VALUES (%s, %s, %s, %s, %s, %s)",
                    (request.name, request.price, request.location, request.owner, request.description, request.region)
                )
                self.conn.commit()

                self.push_data_to_peer("AddRental", request, peer_address='localhost:8000')
            else:
                table = "rentB"  
                self.cursor.execute(
                    f"INSERT INTO {table} (name, price, location, owner, description, region) VALUES (%s, %s, %s, %s, %s, %s)",
                    (request.name, request.price, request.location, request.owner, request.description, request.region)
                )
                self.conn.commit()
            return rent_pb2.ActionResponse(success=True, message="Rental added successfully.")
        except Exception as e:
            self.conn.rollback()
            return rent_pb2.ActionResponse(success=False, message=str(e))

    def GetAllMessages(self, request, context):
        messages = []
        try:
            self.cursor.execute(
                "SELECT sender, content, timestamp FROM messagesB WHERE recipient = %s",
                (request.username,)
            )
            rows = self.cursor.fetchall()
            for row in rows:
                timestamp_str = str(row[2]) if not isinstance(row[2], str) else row[2]
                messages.append(rent_pb2.Message(sender=row[0], content=row[1], timestamp=timestamp_str))
            return rent_pb2.MessageList(messages=messages)
        except Exception as e:
            context.set_details(str(e))
            context.set_code(grpc.StatusCode.INTERNAL)
            return rent_pb2.MessageList()
    
    def GetMyRentals(self, request, context):
        try:
            self.cursor.execute("BEGIN;")  
            self.cursor.execute("SELECT name, price, location, description FROM rentB WHERE owner = %s", (request.username,))
            rows = self.cursor.fetchall()
            rentals = [rent_pb2.RentalEntry(name=row[0], price=row[1], location=row[2], description=row[3]) for row in rows]
            self.cursor.execute("COMMIT;") 
            return rent_pb2.RentalList(entries=rentals)
        except Exception as e:
            self.cursor.execute("ROLLBACK;")  
            context.set_details(str(e))
            context.set_code(grpc.StatusCode.INTERNAL)
            return rent_pb2.RentalList()

        
    def SyncData(self, request, context):
        try:
            for entry in request.entries:
                self.cursor.execute(
                    "INSERT INTO rentB (name, price, location, owner, description) VALUES (%s, %s, %s, %s, %s) ON CONFLICT (name) DO UPDATE SET price = EXCLUDED.price, location = EXCLUDED.location, owner = EXCLUDED.owner, description = EXCLUDED.description",
                    (entry.name, entry.price, entry.location, entry.owner, entry.description)
                )
            self.conn.commit()
            return rent_pb2.SyncResponse(success=True)
        except Exception as e:
            return rent_pb2.SyncResponse(success=False)


        
    def GetRentalInfo(self, request, context):
        try:
            query = "SELECT name, price, location, region FROM rentB WHERE region = 'B district'"
            if request.region == "all":
                query = "SELECT name, price, location FROM rent_all"
            self.cursor.execute(query, (request.region,))
            rows = self.cursor.fetchall()
            entries = [rent_pb2.RentalEntry(name=row[0], price=row[1], location=row[2]) for row in rows]
            return rent_pb2.RentalList(entries=entries)
        
        except Exception as e:
            context.set_details(str(e))
            context.set_code(grpc.StatusCode.INTERNAL)
            return rent_pb2.RentalList()
        
    def CommunicateWithOwner(self, request, context):
        
        return rent_pb2.ChatResponse(message="Greetings from " + request.ownerName)
    
    def IsLandlordOnline(self, request, context):

        return rent_pb2.OwnerOnlineStatus(isOnline=True)

    def StartChat(self, request, context):

        try:

            yield rent_pb2.ChatMessage(Source="Server", message="Chat started.")
            
            while True:
                received_message = yield
                print(f"Received message from {received_message.Source}: {received_message.message}")
                
                
                if "quit" in received_message.message.lower():
                    print("Chat ended by user request.")
                    break
                yield rent_pb2.ChatMessage(Source="Server", message=f"Echo: {received_message.message}")

        except grpc.RpcError as e:
            print(f"RPC error: {e}")
    
    def GetRentalDetails(self, request, context):
        try:
            
            query = "SELECT name, price, location, owner, description FROM rentB WHERE name = %s"
            self.cursor.execute(query, (request.name,))
            row = self.cursor.fetchone()
            if row:
                
                return rent_pb2.RentalInfo(
                    name=row[0], 
                    price=f"{row[1]} EUR", 
                    location=row[2], 
                    owner=row[3], 
                    description=row[4]
                )
            else:
                context.set_details('No rental found with that name.')
                context.set_code(grpc.StatusCode.NOT_FOUND)
                return rent_pb2.RentalInfo()
        except Exception as e:
            context.set_details(str(e))
            context.set_code(grpc.StatusCode.INTERNAL)
            return rent_pb2.RentalInfo()
        
    def __del__(self):
        self.cursor.close()
        self.conn.close()

def run_grpc_server():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    rent_pb2_grpc.add_RentalServiceServicer_to_server(RentalServiceServicer(), server)
    server.add_insecure_port('[::]:8001')
    server.start()
    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        server.stop(0)
        
    
def run_flask_app():
    app.run(debug=True, port=5001, use_reloader=False)
    
if __name__ == '__main__':
    grpc_thread = threading.Thread(target=run_grpc_server)
    flask_thread = threading.Thread(target=run_flask_app)
    grpc_thread.start()
    flask_thread.start()
    grpc_thread.join()
    flask_thread.join()
