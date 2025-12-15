"""
Interactive chat test - talk directly with Gate.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from engine.response import engine
from memory.state import clear_user_data

def main():
    user_id = "interactive_test"
    clear_user_data(user_id)

    print("=" * 50)
    print("GATE CHAT TEST")
    print("Type 'quit' to exit, 'reset' to start over")
    print("=" * 50)

    while True:
        try:
            user_input = input("\nyou: ").strip()

            if not user_input:
                continue

            if user_input.lower() == 'quit':
                break

            if user_input.lower() == 'reset':
                clear_user_data(user_id)
                print("[reset]")
                continue

            result = engine.process_message(user_id, user_input)
            print(f"gate: {result['response']}")
            print(f"      [{result['phase']}]")

        except KeyboardInterrupt:
            break
        except EOFError:
            break

    print("\n[done]")

if __name__ == "__main__":
    main()
