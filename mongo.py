from pymongo import MongoClient
import os
uri = os.getenv("DB_CRED")

try:
    client = MongoClient(uri)
    db = client['meatstory_db']

    print("--- 🔍 SEARCHING FOR VALID TEST DATA ---")

    # 1. Find a User
    user = db['users'].find_one()
    if user:
        u_id = str(user['_id'])
        print(f"✅ VALID USER ID: {u_id} ({user.get('email', 'No Email')})")
        
        # 2. Find an Address for THIS user
        address = db['addresses'].find_one({"user": user['_id']})
        if not address: # Fallback: just find any address
            address = db['addresses'].find_one()
        
        if address:
            print(f"✅ VALID ADDRESS ID: {str(address['_id'])}")
        else:
            print("❌ No Address found in DB.")

        # 3. Find a Pet for THIS user
        pet = db['pets'].find_one({"user": user['_id']})
        if not pet: # Fallback: just find any pet
            pet = db['pets'].find_one()

        if pet:
            print(f"✅ VALID PET ID: {str(pet['_id'])}")
        else:
            print("❌ No Pet found in DB.")
            
    else:
        print("❌ No Users found in the 'users' collection.")

    print("\n--- 🚀 ACTION STEP ---")
    print("Copy these 3 IDs into your Postman Body and hit Send!")

except Exception as e:
    print(f"❌ Error connecting to DB: {e}")