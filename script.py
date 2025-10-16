import os
import json
import time
from pathlib import Path
from dotenv import load_dotenv, set_key
from core.auth import verify_otp, send_otp, verify_token, logout_user
from core.fetch import get_batches, get_sub, get_ch
from core.dpp_quiz import fetch_dpp_tests, fetch_dpp_test_sol


data_dir = Path("data")
data_dir.mkdir(exist_ok=True)
env_path = data_dir / ".env"
load_dotenv(env_path) 

def get_token():
    load_dotenv(env_path, override=True) 
    token = os.getenv("ACCESS_TOKEN")
    return token if token else None

def save_token(token):
    set_key(env_path, "ACCESS_TOKEN", token)

def login_flow():
    print("\n=== LOGIN REQUIRED ===")
    country_code = input("Enter country code (e.g., +91): ").strip()
    mobile_no = input("Enter mobile number: ").strip()
    if not country_code or not mobile_no:
        print("Invalid input.")
        return None

    success, error = send_otp(country_code, mobile_no)
    if not success:
        print(f"Failed to send OTP: {error}")
        return None

    print("OTP sent successfully.")
    otp = input("Enter received OTP: ").strip()

    result = verify_otp(mobile_no, otp)
    if not result[0]:
        print(f"OTP verification failed: {result[1]}")
        return None

    _, token, exp, user = result
    save_token(token)
    print(f"\nLogin successful. Token saved.\nWelcome, {user.get('f_name', 'User')}!")
    return token

def check_status():
    token = get_token()
    if not token:
        print("\nNo token found. Please log in.")
        return login_flow()

    success, verified = verify_token(token)
    if not success or not verified:
        print("\nToken invalid or expired. Re-login required.")
        return login_flow()

    print("\nToken is valid.")
    return token

def logout():
    token = get_token()
    if not token:
        print("No token found.")
        return
    success = logout_user(token)
    if success:
        print("Logged out successfully.")
        if env_path.exists():
            os.remove(env_path)
        return True
    else:
        print("Logout failed.")
        return False
    
def select_from_list(items, key_name):
    for i, item in enumerate(items, 1):
        print(f"{i}. {item[key_name]}")
    while True:
        try:
            choice = int(input("Select number: "))
            if 1 <= choice <= len(items):
                return items[choice - 1]
        except ValueError:
            pass
        print("Invalid choice. Try again.")

def main():
    token = check_status()
    if not token:
        print("Login failed. Exiting.")
        return


    success, batches = get_batches(token)
    if not success:
        print("Failed to fetch batches:", batches)
        return

    print("\n=== Select Batch ===")
    selected_batch = select_from_list(batches, "batch_name")
    batch_id = selected_batch["batch_id"]

    success, batch_data = get_sub(token, batch_id)
    if not success:
        print("Failed to fetch subjects:", batch_data)
        return

    subjects = batch_data["subjects"]
    if not subjects:
        print("No subjects found.")
        return

    print("\n=== Select Subject ===")
    selected_subject = select_from_list(subjects, "subject_name")
    subject_id = selected_subject["subject_id"]

    success, chapters_by_subject = get_ch(token, batch_id, [subject_id])
    if not success:
        print("Failed to fetch chapters:", chapters_by_subject)
        return

    chapters = chapters_by_subject.get(subject_id, [])
    if not chapters:
        print("No chapters found.")
        return

    print("\n=== Select Chapter ===")
    selected_chapter = select_from_list(chapters, "chapter_name")
    chapter_id = selected_chapter["chapter_id"]

    print("\nFetching DPP tests...")
    tests = fetch_dpp_tests(token, batch_id, subject_id, chapter_id)

    if not tests:
        print("No DPP tests found.")
        return

    print(f"\nFound {len(tests)} DPP tests:")
    for i, t in enumerate(tests, 1):
        print(f"{i}. {t['test_name']} (Attempted: {t['attempted']})")
        
    for test in tests:
        test_name = test.get("test_name")
        attempt_id = test.get("attempt_id")

        if attempt_id:
            sol_data = fetch_dpp_test_sol(token, attempt_id)
            file_name = data_dir / f"{test_name.replace(' ', '_')}_{attempt_id}.json"
            with open(file_name, "w", encoding="utf-8") as f:
                json.dump(sol_data, f, indent=4, ensure_ascii=False)
            print(f"Solution saved: {file_name}")
        else:
            print(f"Test '{test_name}' not attempted. Attempt the test to extract its solution.")


    output_path = data_dir / "dpp_output.json"
    
    
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(tests, f, indent=4, ensure_ascii=False)
    
    

    print(f"\n✅ DPP data saved to {output_path.absolute()}")
    

if __name__ == "__main__":
    main()