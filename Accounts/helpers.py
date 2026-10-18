import string
import random

def generate_unique_name(length=25):
    name = ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))
    return name