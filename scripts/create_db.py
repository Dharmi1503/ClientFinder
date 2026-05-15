#!/usr/bin/env python3
import os
import sqlite3

def ensure_db(path='data/clientfinder.db'):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if not os.path.exists(path):
        conn = sqlite3.connect(path)
        conn.close()
        print('created', path)
    else:
        print(path, 'already exists')

if __name__ == '__main__':
    ensure_db()
