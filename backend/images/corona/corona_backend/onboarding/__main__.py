import os

from .app import main

if __name__ == "__main__":
    main(int(os.environ.get("PORT", "8080")))
