import time

def get_epoch_filename(ext):
    return f"temp/{str(time.time()).split('.')[0]}.{ext}"