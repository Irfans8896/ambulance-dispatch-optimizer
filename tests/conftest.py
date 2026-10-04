import os

# The older tests call the API directly, without logging in.
# test_complete.py switches login back on for its own checks.
os.environ["AUTH_REQUIRED"] = "0"
