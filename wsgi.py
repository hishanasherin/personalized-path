import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from app import app, init_db

init_db()

if __name__ == "__main__":
    app.run()
